from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import audit_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), _current: User = Depends(get_current_user)) -> list[User]:
    return db.query(User).order_by(User.username).all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), current: User = Depends(require_role(UserRole.ADMIN))) -> User:
    if db.query(User).filter((User.username == payload.username) | (User.email == payload.email)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    audit_service.record(db, user_id=current.id, action="create_user", entity_type="user", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current: User = Depends(require_role(UserRole.ADMIN))
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = hash_password(payload.password)

    audit_service.record(db, user_id=current.id, action="update_user", entity_type="user", entity_id=user.id)
    db.commit()
    db.refresh(user)
    return user
