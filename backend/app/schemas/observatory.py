from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.observatory import InstrumentType, MountType
from app.schemas.common import ORMBase


class ObservatoryCreate(BaseModel):
    name: str
    code: str | None = None
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)
    elevation_m: float = 0.0
    timezone: str = "UTC"
    description: str | None = None


class ObservatoryRead(ORMBase):
    id: int
    name: str
    code: str | None
    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    timezone: str
    description: str | None


class TelescopeCreate(BaseModel):
    observatory_id: int
    name: str
    aperture_mm: float = Field(gt=0)
    focal_length_mm: float = Field(gt=0)
    mount_type: MountType = MountType.EQUATORIAL


class TelescopeRead(ORMBase):
    id: int
    observatory_id: int
    name: str
    aperture_mm: float
    focal_length_mm: float
    mount_type: MountType
    is_simulated: bool


class InstrumentCreate(BaseModel):
    telescope_id: int
    name: str
    instrument_type: InstrumentType = InstrumentType.CAMERA
    pixel_size_um: float | None = None
    resolution_x: int | None = None
    resolution_y: int | None = None
    bit_depth: int = 16
    available_filters: str | None = None


class InstrumentRead(ORMBase):
    id: int
    telescope_id: int
    name: str
    instrument_type: InstrumentType
    pixel_size_um: float | None
    resolution_x: int | None
    resolution_y: int | None
    bit_depth: int
    available_filters: str | None


class TelescopeLiveStatus(BaseModel):
    """Live simulator (or, later, hardware-adapter) state — distinct from
    the static TelescopeRead config above. See services/telescope_simulator.py."""

    telescope_id: int
    ra_deg: float
    dec_deg: float
    altitude_deg: float
    azimuth_deg: float
    tracking: bool
    slewing: bool
    dome_state: str
    camera_state: str
    current_target_id: int | None = None
    is_simulated: bool
    as_of: str
