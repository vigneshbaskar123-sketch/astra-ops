from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.common import ORMBase


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(ORMBase):
    id: int
    username: str
    email: str
    full_name: str | None
    role: UserRole
    is_active: bool
