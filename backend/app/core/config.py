"""
Central application configuration.

Every value here is overridable via environment variable (or a `.env` file
in the backend/ directory) — nothing secret is hardcoded. See
`.env.example` at the repo root for the full list with descriptions.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- General ---
    PROJECT_NAME: str = "ASTRA-OPS"
    API_V1_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"  # development | production | test

    # --- Security ---
    # SECRET_KEY has NO default in production: docker-compose / .env must set
    # it. The fallback below only exists so `pytest` and local scripts work
    # out of the box without a .env file; it is intentionally obviously fake.
    SECRET_KEY: str = "dev-only-insecure-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Database ---
    # Defaults to a local SQLite file so the API is runnable without Postgres
    # (handy for quick scripts / CI). docker-compose overrides this to the
    # Postgres DSN. See app/db/session.py for the engine-selection logic.
    DATABASE_URL: str = "sqlite:///./astra_ops.db"

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # --- File storage ---
    STORAGE_ROOT: Path = Path(__file__).resolve().parents[2] / "storage"
    FITS_STORAGE_DIR: Path = STORAGE_ROOT / "fits"
    REPORTS_STORAGE_DIR: Path = STORAGE_ROOT / "reports"
    MAX_UPLOAD_SIZE_MB: int = 200
    ALLOWED_FITS_EXTENSIONS: tuple[str, ...] = (".fits", ".fit", ".fts")

    # --- Observatory defaults (used for astronomy calcs when a specific
    # Observatory record isn't supplied) ---
    DEFAULT_OBSERVATORY_NAME: str = "Vainu Bappu Observatory (demo)"
    DEFAULT_LATITUDE_DEG: float = 12.5748
    DEFAULT_LONGITUDE_DEG: float = 78.8205
    DEFAULT_ELEVATION_M: float = 725.0
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    # --- AI Assistant (wired up in a later stage; present now so the env
    # contract is documented from day one) ---
    ANTHROPIC_API_KEY: str | None = None
    AI_ASSISTANT_MODEL: str = "claude-sonnet-4-6"

    # --- Simulators (clearly not real hardware/sensors — see README) ---
    TELESCOPE_SLEW_RATE_DEG_PER_SEC: float = 3.0
    WEATHER_UPDATE_INTERVAL_SEC: int = 60


settings = Settings()

# Ensure storage directories exist at import time so upload/report endpoints
# never fail on a missing folder in a fresh checkout.
settings.FITS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
