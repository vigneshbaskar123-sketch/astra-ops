from __future__ import annotations

from datetime import datetime

from app.models.weather import CloudCondition, WeatherSafety, WeatherSource
from app.schemas.common import ORMBase


class WeatherRecordRead(ORMBase):
    id: int
    observatory_id: int
    recorded_at: datetime
    temperature_c: float
    humidity_pct: float
    wind_speed_kph: float
    rain: bool
    cloud_condition: CloudCondition
    safety_state: WeatherSafety
    source: WeatherSource
