from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReportType(str, enum.Enum):
    DAILY = "daily"
    SESSION = "session"
    IMAGE_QUALITY = "image_quality"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    CSV = "csv"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType, native_enum=False, length=16))
    format: Mapped[ReportFormat] = mapped_column(Enum(ReportFormat, native_enum=False, length=8))
    generated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True, doc="e.g. date range, session id, filters used")

    generated_by: Mapped["User | None"] = relationship()
