"""
Security primitives: password hashing and JWT issuing/verification.

Design notes
------------
* Passwords are hashed with bcrypt via passlib. bcrypt is pinned to <4.1 in
  requirements.txt to avoid the well-known passlib 1.7.4 / bcrypt>=4.1
  incompatibility (passlib probes `bcrypt.__about__`, which newer bcrypt
  removed).
* Tokens are stateless JWTs (HS256). `/auth/logout` revokes a token by
  storing its `jti` in an in-memory denylist checked on every request.
  This is sufficient for a single-process prototype but does NOT survive a
  restart and does NOT work across multiple uvicorn workers — a real
  deployment should swap this for a Redis-backed or DB-backed denylist
  (see docstring on `TokenDenylist`). That swap point is intentionally
  isolated to this one class.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


class TokenDenylist:
    """Process-local set of revoked JWT IDs (jti).

    Swap point for production: replace `_revoked: set[str]` with a Redis
    SET (SADD/SISMEMBER with TTL = token expiry) so revocation is shared
    across workers/restarts. The public interface (`revoke`, `is_revoked`)
    would not need to change.
    """

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, jti: str) -> None:
        self._revoked.add(jti)

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked


token_denylist = TokenDenylist()


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode + validate a JWT. Raises jose.JWTError on any failure
    (expired, bad signature, malformed). Also raises JWTError if the
    token's jti has been revoked via /auth/logout."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    jti = payload.get("jti")
    if jti and token_denylist.is_revoked(jti):
        raise JWTError("Token has been revoked")
    return payload
