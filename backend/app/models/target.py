from __future__ import annotations

import enum

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class TargetType(str, enum.Enum):
    STAR = "star"
    GALAXY = "galaxy"
    NEBULA = "nebula"
    STAR_CLUSTER = "star_cluster"
    PLANET = "planet"
    OTHER = "other"


class Target(TimestampMixin, Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    ra_deg: Mapped[float] = mapped_column(Float, nullable=False, doc="Right ascension, degrees, 0-360")
    dec_deg: Mapped[float] = mapped_column(Float, nullable=False, doc="Declination, degrees, -90..90")
    target_type: Mapped[TargetType] = mapped_column(Enum(TargetType, native_enum=False, length=16), default=TargetType.OTHER)
    magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_by: Mapped["User | None"] = relationship(back_populates="targets_created")
    observation_sessions: Mapped[list["ObservationSession"]] = relationship(back_populates="target")
