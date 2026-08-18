from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # Needed because SQLite by default only allows the connection to be used
    # from the thread that created it; FastAPI can hand requests to a
    # thread pool for sync path operations.
    _connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
