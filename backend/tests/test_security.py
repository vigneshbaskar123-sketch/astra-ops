from __future__ import annotations

import time

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    token_denylist,
    verify_password,
)


def test_password_hash_round_trip():
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_same_password_hashes_differently_each_time():
    # bcrypt salts each hash — this also implicitly checks the
    # passlib/bcrypt version pairing works at all (a known real-world
    # incompatibility exists between passlib 1.7.4 and bcrypt>=4.1).
    h1 = hash_password("same-input")
    h2 = hash_password("same-input")
    assert h1 != h2
    assert verify_password("same-input", h1)
    assert verify_password("same-input", h2)


def test_access_token_round_trip():
    token = create_access_token(subject="vignesh", role="admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "vignesh"
    assert payload["role"] == "admin"
    assert "jti" in payload


def test_expired_token_is_rejected():
    token = create_access_token(subject="vignesh", role="viewer", expires_minutes=-1)
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_revoked_token_is_rejected_after_logout():
    token = create_access_token(subject="vignesh", role="operator")
    payload = decode_access_token(token)  # valid before revocation
    assert payload["sub"] == "vignesh"

    token_denylist.revoke(payload["jti"])
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_tampered_token_is_rejected():
    token = create_access_token(subject="vignesh", role="viewer")
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    with pytest.raises(JWTError):
        decode_access_token(tampered)
