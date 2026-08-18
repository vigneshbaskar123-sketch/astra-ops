from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, oauth2_scheme
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, token_denylist, verify_password
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserRead
from app.services import audit_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    token = create_access_token(subject=user.username, role=user.role.value)
    audit_service.record(
        db, user_id=user.id, action="login", entity_type="user", entity_id=user.id, ip_address=request.client.host if request.client else None
    )
    db.commit()
    return Token(access_token=token, expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> dict:
    try:
        payload = decode_access_token(token)
    except JWTError:
        # Already invalid/expired — logout is idempotent either way.
        return {"detail": "Logged out"}

    jti = payload.get("jti")
    if jti:
        token_denylist.revoke(jti)

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first() if username else None
    audit_service.record(db, user_id=user.id if user else None, action="logout", entity_type="user", entity_id=user.id if user else None)
    db.commit()
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
