from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.models.user import User, UserRole


@pytest.fixture()
def db_session():
    import app.models  # noqa: F401 - register all models before create_all

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    from app.api.deps import get_db as deps_get_db
    from app.db.session import get_db as session_get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[deps_get_db] = override_get_db
    app.dependency_overrides[session_get_db] = override_get_db

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _make_user(db_session, username: str, role: UserRole, password: str = "testpass123") -> User:
    user = User(
        username=username,
        email=f"{username}@example.test",
        full_name=username.title(),
        hashed_password=hash_password(password),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user(db_session):
    return _make_user(db_session, "admin_user", UserRole.ADMIN)


@pytest.fixture()
def operator_user(db_session):
    return _make_user(db_session, "operator_user", UserRole.OPERATOR)


@pytest.fixture()
def viewer_user(db_session):
    return _make_user(db_session, "viewer_user", UserRole.VIEWER)


def auth_headers(client, username: str, password: str = "testpass123") -> dict:
    resp = client.post("/api/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
