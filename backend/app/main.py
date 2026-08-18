"""
Application entrypoint.

Schema creation on startup: `Base.metadata.create_all()` is idempotent
(only creates tables that don't already exist) and is what keeps this
prototype "clone it and `docker compose up`"-runnable without a manual
migration step. It is NOT how a production deployment should manage
schema changes over time — that's what `alembic/` (backend/alembic.ini)
is for. Both are present; create_all is a convenience floor, Alembic is
the real migration path once this app has live data to preserve across
schema changes.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

import app.models  # noqa: F401 - registers all models on Base.metadata before create_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("astra_ops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("ASTRA-OPS backend starting up (environment=%s, db=%s)", settings.ENVIRONMENT, _redact_db_url())
    yield
    logger.info("ASTRA-OPS backend shutting down")


def _redact_db_url() -> str:
    url = settings.DATABASE_URL
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        _, host_part = rest.split("@", 1)
        return f"{scheme}://***:***@{host_part}"
    return url


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-Assisted Observatory Operations & Astronomical Data Quality Monitoring System",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "service": settings.PROJECT_NAME, "environment": settings.ENVIRONMENT}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
