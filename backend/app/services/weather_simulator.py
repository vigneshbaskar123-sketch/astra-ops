"""
Simulated weather generator + safety classification.

Everything this module produces is synthetic. `WeatherRecord.source` is
always `SIMULATED` here; a real deployment would add a `SensorWeatherProvider`
(e.g. wrapping a Davis/Vantage Pro API, or a government met-office feed)
implementing the same `WeatherProvider` interface, and the API/DB layer
would not need to change — only which provider is instantiated at startup.

Safety-state thresholds (documented here because "transparent" applies to
this scoring just as much as to image quality):

| Factor          | SAFE        | WARNING       | UNSAFE     |
|------------------|-------------|---------------|------------|
| rain             | none        | —             | any rain   |
| wind speed       | < 25 kph    | 25-40 kph     | > 40 kph   |
| humidity         | < 80%       | 80-90%        | > 90%      |
| cloud condition  | clear       | partly_cloudy | cloudy/overcast |

The overall state is the WORST individual factor (i.e. any single UNSAFE
factor makes the whole reading UNSAFE), which is the conservative,
correct approach for an automated dome/observation safety gate.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.models.weather import CloudCondition, WeatherSafety, WeatherSource

WIND_WARNING_KPH = 25.0
WIND_UNSAFE_KPH = 40.0
HUMIDITY_WARNING_PCT = 80.0
HUMIDITY_UNSAFE_PCT = 90.0


@dataclass
class WeatherReading:
    temperature_c: float
    humidity_pct: float
    wind_speed_kph: float
    rain: bool
    cloud_condition: CloudCondition
    safety_state: WeatherSafety
    source: WeatherSource
    recorded_at: datetime


def classify_safety(
    *, rain: bool, wind_speed_kph: float, humidity_pct: float, cloud_condition: CloudCondition
) -> WeatherSafety:
    factors = [WeatherSafety.SAFE]

    if rain:
        factors.append(WeatherSafety.UNSAFE)

    if wind_speed_kph > WIND_UNSAFE_KPH:
        factors.append(WeatherSafety.UNSAFE)
    elif wind_speed_kph >= WIND_WARNING_KPH:
        factors.append(WeatherSafety.WARNING)

    if humidity_pct > HUMIDITY_UNSAFE_PCT:
        factors.append(WeatherSafety.UNSAFE)
    elif humidity_pct >= HUMIDITY_WARNING_PCT:
        factors.append(WeatherSafety.WARNING)

    if cloud_condition in (CloudCondition.CLOUDY, CloudCondition.OVERCAST):
        factors.append(WeatherSafety.UNSAFE)
    elif cloud_condition == CloudCondition.PARTLY_CLOUDY:
        factors.append(WeatherSafety.WARNING)

    if WeatherSafety.UNSAFE in factors:
        return WeatherSafety.UNSAFE
    if WeatherSafety.WARNING in factors:
        return WeatherSafety.WARNING
    return WeatherSafety.SAFE


class WeatherProvider(Protocol):
    def read(self) -> WeatherReading: ...


class SimulatedWeatherProvider:
    """Diurnal-ish synthetic weather: temperature follows a sine wave
    keyed to time-of-day, humidity anti-correlates loosely with
    temperature, wind is a bounded random walk, cloud cover and rain are
    weighted-random events. Seeded per-instance for reproducible demo
    runs; omit the seed for genuinely random behavior."""

    def __init__(self, seed: int | None = None, base_temp_c: float = 24.0, base_humidity_pct: float = 55.0) -> None:
        self._rng = random.Random(seed)
        self._base_temp_c = base_temp_c
        self._base_humidity_pct = base_humidity_pct
        self._wind_kph = 10.0  # random-walk state

    def read(self) -> WeatherReading:
        now = datetime.now(timezone.utc)
        hour_frac = now.hour + now.minute / 60.0

        # Diurnal temperature curve peaking mid-afternoon (~14:00 local
        # proxy via UTC hour here; good enough for demo purposes).
        diurnal = math.sin((hour_frac - 8) / 24 * 2 * math.pi)
        temperature_c = self._base_temp_c + 6.0 * diurnal + self._rng.uniform(-0.8, 0.8)

        humidity_pct = self._base_humidity_pct - 15.0 * diurnal + self._rng.uniform(-4, 4)
        humidity_pct = min(max(humidity_pct, 5.0), 100.0)

        self._wind_kph += self._rng.uniform(-3, 3)
        self._wind_kph = min(max(self._wind_kph, 0.0), 70.0)

        cloud_condition = self._rng.choices(
            list(CloudCondition), weights=[0.55, 0.25, 0.13, 0.07], k=1
        )[0]
        rain = cloud_condition == CloudCondition.OVERCAST and self._rng.random() < 0.15

        safety = classify_safety(
            rain=rain, wind_speed_kph=self._wind_kph, humidity_pct=humidity_pct, cloud_condition=cloud_condition
        )

        return WeatherReading(
            temperature_c=round(temperature_c, 1),
            humidity_pct=round(humidity_pct, 1),
            wind_speed_kph=round(self._wind_kph, 1),
            rain=rain,
            cloud_condition=cloud_condition,
            safety_state=safety,
            source=WeatherSource.SIMULATED,
            recorded_at=now,
        )


class SensorWeatherProvider:
    """Not implemented — placeholder for a real station/API integration.
    Wiring this in only requires implementing `.read()` and pointing the
    app factory at this class instead of SimulatedWeatherProvider."""

    def read(self) -> WeatherReading:  # pragma: no cover - intentionally unimplemented
        raise NotImplementedError(
            "No real weather sensor/API is configured. Configure a WEATHER_API_* "
            "setting and implement SensorWeatherProvider.read() to enable this."
        )


_provider: WeatherProvider = SimulatedWeatherProvider()


def get_weather_provider() -> WeatherProvider:
    return _provider
