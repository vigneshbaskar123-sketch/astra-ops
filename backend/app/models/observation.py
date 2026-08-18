from __future__ import annotations

import enum

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ObservationPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ObservationStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class ObservationSession(TimestampMixin, Base):
    """A single planned/executed observation. This one table backs both the
    Observation Planner (module 3) and Observation Logging (module 10) —
    a planned row starts as `status=planned`; the same row is updated as
    it executes and completes, which is what "logging" means here rather
    than a separate append-only log table. FITS files and image-quality
    results reference back to the session that produced them."""

    __tablename__ = "observation_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), nullable=False)
    telescope_id: Mapped[int] = mapped_column(ForeignKey("telescopes.id"), nullable=False)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"), nullable=True)
    observer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    weather_record_id: Mapped[int | None] = mapped_column(ForeignKey("weather_records.id"), nullable=True)

    observation_date: Mapped[Date] = mapped_column(Date, nullable=False)
    start_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)

    exposure_time_s: Mapped[float] = mapped_column(Float, nullable=False)
    num_frames: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    filter_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    priority: Mapped[ObservationPriority] = mapped_column(
        Enum(ObservationPriority, native_enum=False, length=16), default=ObservationPriority.NORMAL
    )
    status: Mapped[ObservationStatus] = mapped_column(
        Enum(ObservationStatus, native_enum=False, length=16), default=ObservationStatus.PLANNED, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    target: Mapped["Target"] = relationship(back_populates="observation_sessions")
    telescope: Mapped["Telescope"] = relationship(back_populates="observation_sessions")
    instrument: Mapped["Instrument | None"] = relationship(back_populates="observation_sessions")
    observer: Mapped["User"] = relationship(back_populates="observation_sessions", foreign_keys=[observer_id])
    weather_record: Mapped["WeatherRecord | None"] = relationship()
    fits_files: Mapped[list["FitsFile"]] = relationship(back_populates="observation_session")
