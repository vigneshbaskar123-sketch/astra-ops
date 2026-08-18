from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.observation import ObservationSession
from app.models.target import Target
from app.models.user import User, UserRole
from app.schemas.observation import ObservationSessionRead
from app.schemas.target import TargetCreate, TargetRead, TargetUpdate
from app.services import audit_service

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get("", response_model=list[TargetRead])
def list_targets(
    q: str | None = None, db: Session = Depends(get_db), _u: User = Depends(get_current_user)
) -> list[Target]:
    query = db.query(Target)
    if q:
        query = query.filter(Target.name.ilike(f"%{q}%"))
    return query.order_by(Target.name).all()


@router.post("", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
def create_target(
    payload: TargetCreate, db: Session = Depends(get_db), current: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))
) -> Target:
    target = Target(**payload.model_dump(), created_by_id=current.id)
    db.add(target)
    db.flush()
    audit_service.record(db, user_id=current.id, action="create_target", entity_type="target", entity_id=target.id)
    db.commit()
    db.refresh(target)
    return target


@router.get("/{target_id}", response_model=TargetRead)
def get_target(target_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> Target:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    return target


@router.patch("/{target_id}", response_model=TargetRead)
def update_target(
    target_id: int,
    payload: TargetUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> Target:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field, value)

    audit_service.record(db, user_id=current.id, action="update_target", entity_type="target", entity_id=target.id)
    db.commit()
    db.refresh(target)
    return target


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: int, db: Session = Depends(get_db), current: User = Depends(require_role(UserRole.ADMIN))
) -> None:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    db.delete(target)
    audit_service.record(db, user_id=current.id, action="delete_target", entity_type="target", entity_id=target_id)
    db.commit()


@router.get("/{target_id}/observations", response_model=list[ObservationSessionRead])
def target_observation_history(
    target_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)
) -> list[ObservationSession]:
    if not db.get(Target, target_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    return (
        db.query(ObservationSession)
        .filter(ObservationSession.target_id == target_id)
        .order_by(ObservationSession.start_time.desc())
        .all()
    )
