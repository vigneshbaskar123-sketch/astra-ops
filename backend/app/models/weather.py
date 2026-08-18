from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CloudCondition(str, enum.Enum):
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    OVERCAST = "overcast"


class WeatherSafety(str, enum.Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    UNSAFE = "UNSAFE"


class WeatherSource(str, enum.Enum):
    SIMULATED = "simulated"
    SENSOR = "sensor"


class WeatherRecord(Base):
    """A single weather sample. `source` is always `simulated` unless a
    real sensor/API integration is configured (see
    services/weather_simulator.py docstring) — the API never claims
    simulated readings are real."""

    __tablename__ = "weather_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    observatory_id: Mapped[int] = mapped_column(ForeignKey("observatories.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False
    )

    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed_kph: Mapped[float] = mapped_column(Float, nullable=False)
    rain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cloud_condition: Mapped[CloudCondition] = mapped_column(Enum(CloudCondition, native_enum=False, length=16))

    safety_state: Mapped[WeatherSafety] = mapped_column(Enum(WeatherSafety, native_enum=False, length=8), index=True)
    source: Mapped[WeatherSource] = mapped_column(
        Enum(WeatherSource, native_enum=False, length=16), default=WeatherSource.SIMULATED, nullable=False
    )
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    observatory: Mapped["Observatory"] = relationship(back_populates="weather_records")
