from __future__ import annotations

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class TokenPayload(BaseModel):
    sub: str
    role: str
    jti: str
