from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.observation import ObservationSession, ObservationStatus
from app.models.target import Target
from app.models.observatory import Telescope
from app.models.user import User, UserRole
from app.schemas.observation import ObservationSessionCreate, ObservationSessionRead, ObservationSessionUpdate
from app.services import alert_service, audit_service

router = APIRouter(prefix="/observations", tags=["observations"])


@router.get("", response_model=list[ObservationSessionRead])
def list_observations(
    status_filter: ObservationStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
) -> list[ObservationSession]:
    query = db.query(ObservationSession)
    if status_filter:
        query = query.filter(ObservationSession.status == status_filter)
    return query.order_by(ObservationSession.start_time.desc()).all()


@router.post("", response_model=ObservationSessionRead, status_code=status.HTTP_201_CREATED)
def create_observation(
    payload: ObservationSessionCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> ObservationSession:
    if not db.get(Target, payload.target_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    if not db.get(Telescope, payload.telescope_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telescope not found")

    session = ObservationSession(**payload.model_dump(), observer_id=current.id, status=ObservationStatus.PLANNED)
    db.add(session)
    db.flush()
    audit_service.record(db, user_id=current.id, action="create_observation", entity_type="observation_session", entity_id=session.id)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=ObservationSessionRead)
def get_observation(session_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> ObservationSession:
    session = db.get(ObservationSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation session not found")
    return session


@router.patch("/{session_id}", response_model=ObservationSessionRead)
def update_observation(
    session_id: int,
    payload: ObservationSessionUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> ObservationSession:
    """This is the "logging" half of module 3/10: a planner entry
    transitions through in_progress -> completed/failed/aborted as the
    (simulated) observation actually runs, updating the same row rather
    than writing a separate append-only log."""
    session = db.get(ObservationSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation session not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(session, field, value)

    db.flush()
    if payload.status == ObservationStatus.FAILED:
        alert_service.check_observation_failure(db, session)

    audit_service.record(
        db, user_id=current.id, action="update_observation", entity_type="observation_session", entity_id=session.id,
        details=f"status={session.status.value}",
    )
    db.commit()
    db.refresh(session)
    return session
