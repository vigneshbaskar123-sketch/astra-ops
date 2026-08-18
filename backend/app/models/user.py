from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False, length=16), default=UserRole.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    observation_sessions: Mapped[list["ObservationSession"]] = relationship(
        back_populates="observer", foreign_keys="ObservationSession.observer_id"
    )
    targets_created: Mapped[list["Target"]] = relationship(back_populates="created_by")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<User id={self.id} username={self.username!r} role={self.role}>"
