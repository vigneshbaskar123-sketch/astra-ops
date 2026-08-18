"""
Importing this package registers every ORM model on `Base.metadata`.

This module must be imported (directly or transitively) before
`Base.metadata.create_all()` / Alembic autogenerate run, and before any
relationship() that references a model by string name (e.g. "Target") is
resolved — SQLAlchemy resolves those lazily against Base's registry, which
is only populated once each model module has executed.
"""
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.audit import AuditLog
from app.models.fits_data import FitsFile, ImageQualityRating, ImageQualityResult
from app.models.observation import ObservationPriority, ObservationSession, ObservationStatus
from app.models.observatory import Instrument, InstrumentType, MountType, Observatory, Telescope
from app.models.report import Report, ReportFormat, ReportType
from app.models.target import Target, TargetType
from app.models.user import User, UserRole
from app.models.weather import CloudCondition, WeatherRecord, WeatherSafety, WeatherSource

__all__ = [
    "Alert",
    "AlertSeverity",
    "AlertType",
    "AuditLog",
    "FitsFile",
    "ImageQualityRating",
    "ImageQualityResult",
    "ObservationPriority",
    "ObservationSession",
    "ObservationStatus",
    "Instrument",
    "InstrumentType",
    "MountType",
    "Observatory",
    "Telescope",
    "Report",
    "ReportFormat",
    "ReportType",
    "Target",
    "TargetType",
    "User",
    "UserRole",
    "CloudCondition",
    "WeatherRecord",
    "WeatherSafety",
    "WeatherSource",
]
