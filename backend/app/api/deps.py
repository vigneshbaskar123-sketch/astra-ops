from __future__ import annotations

from collections.abc import Callable, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_role(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Usage: `Depends(require_role(UserRole.ADMIN))` or
    `Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))`. Any
    authenticated user (any role) can hit an endpoint that only depends
    on `get_current_user` — use this dependency specifically to narrow
    write/admin operations."""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not permitted to perform this action.",
            )
        return current_user

    return dependency
