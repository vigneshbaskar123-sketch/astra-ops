from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """Base for response schemas that read directly from ORM objects."""
    model_config = ConfigDict(from_attributes=True)
