from __future__ import annotations

from datetime import datetime

from app.models.alert import AlertSeverity, AlertType
from app.schemas.common import ORMBase


class AlertRead(ORMBase):
    id: int
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    source_entity_type: str | None
    source_entity_id: int | None
    is_acknowledged: bool
    acknowledged_by_id: int | None
    acknowledged_at: datetime | None
    created_at: datetime
