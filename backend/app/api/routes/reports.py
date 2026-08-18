"""
Report generation (module 11).

CSV export is implemented here with the stdlib `csv` module — genuinely
functional, not a stub. PDF export is intentionally NOT implemented yet:
it's deferred to the stage that also builds the frontend (report
layout/branding decisions belong with that pass, and Claude's `pdf`
skill — with its guidance on which PDF library to use reliably in this
environment — hasn't been consulted yet). Calling format=pdf right now
returns 501 with a clear message rather than a silent stub file.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date as date_type, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.fits_data import ImageQualityResult
from app.models.observation import ObservationSession
from app.models.report import Report, ReportFormat, ReportType
from app.models.user import User
from app.services import audit_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily")
def daily_report(
    report_date: date_type = Query(...),
    format: ReportFormat = Query(ReportFormat.CSV),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if format == ReportFormat.PDF:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="PDF reports arrive in a later stage; use format=csv for now.")

    sessions = db.query(ObservationSession).filter(ObservationSession.observation_date == report_date).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["session_id", "target_id", "telescope_id", "observer_id", "start_time", "end_time", "exposure_time_s", "num_frames", "filter", "status"])
    for s in sessions:
        writer.writerow([s.id, s.target_id, s.telescope_id, s.observer_id, s.start_time, s.end_time, s.exposure_time_s, s.num_frames, s.filter_name, s.status.value])

    _record_report(db, current, ReportType.DAILY, ReportFormat.CSV, {"date": str(report_date)})
    return _csv_response(buffer, f"daily_report_{report_date}.csv")


@router.get("/session/{session_id}")
def session_report(
    session_id: int, format: ReportFormat = Query(ReportFormat.CSV), db: Session = Depends(get_db), current: User = Depends(get_current_user)
):
    if format == ReportFormat.PDF:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="PDF reports arrive in a later stage; use format=csv for now.")

    session = db.get(ObservationSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation session not found")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["field", "value"])
    for field in ("id", "target_id", "telescope_id", "instrument_id", "observer_id", "observation_date", "start_time", "end_time", "exposure_time_s", "num_frames", "filter_name", "priority", "status", "notes"):
        value = getattr(session, field)
        writer.writerow([field, value.value if hasattr(value, "value") else value])
    for fits_file in session.fits_files:
        writer.writerow(["fits_file", fits_file.filename])
        if fits_file.quality_result:
            writer.writerow(["  quality_rating", fits_file.quality_result.rating.value])
            writer.writerow(["  quality_score", fits_file.quality_result.total_score])

    _record_report(db, current, ReportType.SESSION, ReportFormat.CSV, {"session_id": session_id})
    return _csv_response(buffer, f"session_report_{session_id}.csv")


@router.get("/image-quality")
def image_quality_report(
    format: ReportFormat = Query(ReportFormat.CSV), db: Session = Depends(get_db), current: User = Depends(get_current_user)
):
    if format == ReportFormat.PDF:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="PDF reports arrive in a later stage; use format=csv for now.")

    results = db.query(ImageQualityResult).order_by(ImageQualityResult.analyzed_at.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["fits_file_id", "star_count", "fwhm_px", "snr", "saturated_pixel_pct", "total_score", "rating"])
    for r in results:
        writer.writerow([r.fits_file_id, r.star_count, r.fwhm_px, r.snr, r.saturated_pixel_pct, r.total_score, r.rating.value])

    _record_report(db, current, ReportType.IMAGE_QUALITY, ReportFormat.CSV, {})
    return _csv_response(buffer, "image_quality_report.csv")


def _csv_response(buffer: io.StringIO, filename: str) -> StreamingResponse:
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _record_report(db: Session, user: User, report_type: ReportType, fmt: ReportFormat, parameters: dict) -> None:
    report = Report(
        report_type=report_type,
        format=fmt,
        generated_by_id=user.id,
        file_path=f"(streamed, not persisted to disk — {uuid.uuid4().hex})",
        parameters=parameters,
    )
    db.add(report)
    audit_service.record(db, user_id=user.id, action="generate_report", entity_type="report", details=f"{report_type.value}/{fmt.value}")
    db.commit()
