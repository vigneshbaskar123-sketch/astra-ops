"""
Alert generation (module 12). Rule-based and deterministic: given a
concrete input (a weather reading, an image-quality result, a session
outcome), each `check_*` function returns an Alert-worthy payload or
None — no randomness, no LLM involvement. The AI Observation Assistant
(a later stage) reads alerts; it does not create them.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.fits_data import FitsFile, ImageQualityResult
from app.models.observation import ObservationSession, ObservationStatus
from app.models.weather import WeatherRecord, WeatherSafety


def _create(db: Session, alert_type: AlertType, severity: AlertSeverity, message: str, entity_type: str, entity_id: int) -> Alert:
    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        message=message,
        source_entity_type=entity_type,
        source_entity_id=entity_id,
    )
    db.add(alert)
    db.flush()
    return alert


def check_weather(db: Session, record: WeatherRecord) -> Alert | None:
    if record.safety_state == WeatherSafety.UNSAFE:
        return _create(
            db,
            AlertType.UNSAFE_WEATHER,
            AlertSeverity.CRITICAL,
            f"Weather conditions UNSAFE at observatory {record.observatory_id}: "
            f"wind {record.wind_speed_kph} kph, humidity {record.humidity_pct}%, "
            f"rain={record.rain}, clouds={record.cloud_condition.value}.",
            "weather_record",
            record.id,
        )
    return None


def check_observation_failure(db: Session, session: ObservationSession) -> Alert | None:
    if session.status == ObservationStatus.FAILED:
        return _create(
            db,
            AlertType.OBSERVATION_FAILED,
            AlertSeverity.WARNING,
            f"Observation session {session.id} (target {session.target_id}) failed.",
            "observation_session",
            session.id,
        )
    return None


def check_image_quality(db: Session, fits_file: FitsFile, result: ImageQualityResult) -> Alert | None:
    if result.rating == "POOR":
        return _create(
            db,
            AlertType.POOR_IMAGE_QUALITY,
            AlertSeverity.WARNING,
            f"FITS file '{fits_file.filename}' scored POOR image quality "
            f"({result.total_score}/100 — FWHM {result.fwhm_px}, SNR {result.snr}, "
            f"{result.saturated_pixel_pct:.2f}% saturated).",
            "fits_file",
            fits_file.id,
        )
    return None


def check_missing_metadata(db: Session, fits_file: FitsFile) -> Alert | None:
    if fits_file.missing_keywords:
        return _create(
            db,
            AlertType.MISSING_METADATA,
            AlertSeverity.INFO,
            f"FITS file '{fits_file.filename}' is missing header keywords: {fits_file.missing_keywords}.",
            "fits_file",
            fits_file.id,
        )
    return None
