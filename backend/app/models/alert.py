from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AlertType(str, enum.Enum):
    UNSAFE_WEATHER = "unsafe_weather"
    TELESCOPE_ERROR = "telescope_error"
    CAMERA_ERROR = "camera_error"
    OBSERVATION_FAILED = "observation_failed"
    POOR_IMAGE_QUALITY = "poor_image_quality"
    MISSING_METADATA = "missing_metadata"


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType, native_enum=False, length=32), index=True)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity, native_enum=False, length=16), index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    source_entity_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="e.g. 'observation_session', 'fits_file', 'telescope'"
    )
    source_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    acknowledged_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False
    )

    acknowledged_by: Mapped["User | None"] = relationship()
