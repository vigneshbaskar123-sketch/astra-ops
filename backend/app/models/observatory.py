from __future__ import annotations

import enum

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Observatory(TimestampMixin, Base):
    """A physical site. Latitude/longitude/elevation/timezone are the
    ground truth used by the astronomy service for every visibility
    calculation — they are real, user-entered site data, not simulated."""

    __tablename__ = "observatories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    latitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    longitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    telescopes: Mapped[list["Telescope"]] = relationship(back_populates="observatory", cascade="all, delete-orphan")
    weather_records: Mapped[list["WeatherRecord"]] = relationship(back_populates="observatory", cascade="all, delete-orphan")


class MountType(str, enum.Enum):
    EQUATORIAL = "equatorial"
    ALT_AZ = "alt_az"
    DOBSONIAN = "dobsonian"


class Telescope(TimestampMixin, Base):
    """Static equipment record. Live pointing/tracking/dome/camera state is
    NOT stored here as continuously-updated columns — it is served from
    `services.telescope_simulator` (or, later, a real hardware adapter
    implementing the same `TelescopeInterface`) and only persisted to the
    DB when it matters for the record (e.g. at observation start/end, or
    when an alert fires)."""

    __tablename__ = "telescopes"

    id: Mapped[int] = mapped_column(primary_key=True)
    observatory_id: Mapped[int] = mapped_column(ForeignKey("observatories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    aperture_mm: Mapped[float] = mapped_column(Float, nullable=False)
    focal_length_mm: Mapped[float] = mapped_column(Float, nullable=False)
    mount_type: Mapped[MountType] = mapped_column(Enum(MountType, native_enum=False, length=16), default=MountType.EQUATORIAL)
    is_simulated: Mapped[bool] = mapped_column(default=True, nullable=False)

    observatory: Mapped["Observatory"] = relationship(back_populates="telescopes")
    instruments: Mapped[list["Instrument"]] = relationship(back_populates="telescope", cascade="all, delete-orphan")
    observation_sessions: Mapped[list["ObservationSession"]] = relationship(back_populates="telescope")


class InstrumentType(str, enum.Enum):
    CAMERA = "camera"
    SPECTROGRAPH = "spectrograph"
    PHOTOMETER = "photometer"


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    telescope_id: Mapped[int] = mapped_column(ForeignKey("telescopes.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    instrument_type: Mapped[InstrumentType] = mapped_column(
        Enum(InstrumentType, native_enum=False, length=16), default=InstrumentType.CAMERA
    )
    pixel_size_um: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution_x: Mapped[int | None] = mapped_column(nullable=True)
    resolution_y: Mapped[int | None] = mapped_column(nullable=True)
    bit_depth: Mapped[int] = mapped_column(default=16, nullable=False)
    available_filters: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Comma-separated filter names, e.g. 'L,R,G,B,Ha'"
    )

    telescope: Mapped["Telescope"] = relationship(back_populates="instruments")
    observation_sessions: Mapped[list["ObservationSession"]] = relationship(back_populates="instrument")
