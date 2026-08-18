from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.alert import Alert, AlertSeverity
from app.models.user import User
from app.schemas.alert import AlertRead
from app.services import audit_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRead])
def list_alerts(
    unacknowledged_only: bool = False,
    severity: AlertSeverity | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
) -> list[Alert]:
    query = db.query(Alert)
    if unacknowledged_only:
        query = query.filter(Alert.is_acknowledged.is_(False))
    if severity:
        query = query.filter(Alert.severity == severity)
    return query.order_by(Alert.created_at.desc()).all()


@router.post("/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)) -> Alert:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_by_id = current.id
    alert.acknowledged_at = datetime.now(timezone.utc)

    audit_service.record(db, user_id=current.id, action="acknowledge_alert", entity_type="alert", entity_id=alert.id)
    db.commit()
    db.refresh(alert)
    return alert
