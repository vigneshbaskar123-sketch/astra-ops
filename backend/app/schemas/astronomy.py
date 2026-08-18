from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AltAzPoint(BaseModel):
    time: datetime
    altitude_deg: float
    azimuth_deg: float


class ObservationWindow(BaseModel):
    start: datetime
    end: datetime
    duration_minutes: float


class VisibilityReport(BaseModel):
    """Everything the planner UI (and the AI assistant, later) needs to
    reason about a target for a given night — every field here is a real
    astropy/astroplan computation, not an estimate."""

    target_id: int
    target_name: str
    observatory_id: int
    date: str

    current_altitude_deg: float
    current_azimuth_deg: float
    is_currently_visible: bool

    sun_altitude_deg: float
    moon_altitude_deg: float
    moon_illumination_pct: float

    min_altitude_threshold_deg: float
    recommended_window: ObservationWindow | None
    all_visibility_windows: list[ObservationWindow]
    altitude_curve: list[AltAzPoint]
