from __future__ import annotations

from datetime import date as date_, datetime

from pydantic import BaseModel, Field

from app.models.observation import ObservationPriority, ObservationStatus
from app.schemas.common import ORMBase


class ObservationSessionCreate(BaseModel):
    target_id: int
    telescope_id: int
    instrument_id: int | None = None
    observation_date: date_
    start_time: datetime
    end_time: datetime
    exposure_time_s: float = Field(gt=0)
    num_frames: int = Field(default=1, ge=1)
    filter_name: str | None = None
    priority: ObservationPriority = ObservationPriority.NORMAL
    notes: str | None = None


class ObservationSessionUpdate(BaseModel):
    status: ObservationStatus | None = None
    notes: str | None = None
    end_time: datetime | None = None


class ObservationSessionRead(ORMBase):
    id: int
    target_id: int
    telescope_id: int
    instrument_id: int | None
    observer_id: int
    weather_record_id: int | None
    observation_date: date_
    start_time: datetime
    end_time: datetime
    exposure_time_s: float
    num_frames: int
    filter_name: str | None
    priority: ObservationPriority
    status: ObservationStatus
    notes: str | None
