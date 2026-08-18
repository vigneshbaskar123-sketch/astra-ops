from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.target import TargetType
from app.schemas.common import ORMBase


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    ra_deg: float = Field(ge=0, lt=360)
    dec_deg: float = Field(ge=-90, le=90)
    target_type: TargetType = TargetType.OTHER
    magnitude: float | None = None
    notes: str | None = None


class TargetUpdate(BaseModel):
    name: str | None = None
    ra_deg: float | None = Field(default=None, ge=0, lt=360)
    dec_deg: float | None = Field(default=None, ge=-90, le=90)
    target_type: TargetType | None = None
    magnitude: float | None = None
    notes: str | None = None


class TargetRead(ORMBase):
    id: int
    name: str
    ra_deg: float
    dec_deg: float
    target_type: TargetType
    magnitude: float | None
    notes: str | None
    created_by_id: int | None
