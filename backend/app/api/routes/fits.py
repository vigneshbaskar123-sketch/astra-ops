from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.core.config import settings
from app.models.fits_data import FitsFile, ImageQualityResult
from app.models.user import User, UserRole
from app.schemas.fits_data import FitsFileRead, FitsUploadResponse, ImageQualityResultRead
from app.services import alert_service, audit_service
from app.services.fits_service import (
    FitsValidationError,
    extract_header_metadata,
    load_image_data,
    store_uploaded_file,
    validate_upload_filename,
)
from app.services.image_quality import analyze_image

router = APIRouter(prefix="/fits", tags=["fits"])


@router.post("/upload", response_model=FitsUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_fits(
    file: UploadFile = File(...),
    observation_session_id: int | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> FitsUploadResponse:
    raw = await file.read()
    try:
        validate_upload_filename(file.filename or "upload.fits", size_bytes=len(raw))
    except FitsValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Write to a quarantined temp file first — only promoted to permanent
    # storage after it survives astropy parsing below.
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "upload.fits").suffix) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)

    try:
        header_meta = extract_header_metadata(tmp_path)
        image_data = load_image_data(tmp_path)
    except FitsValidationError as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    final_path, size_bytes, checksum = store_uploaded_file(tmp_path, file.filename or "upload.fits")

    fits_file = FitsFile(
        observation_session_id=observation_session_id,
        filename=file.filename or final_path.name,
        file_path=str(final_path),
        uploaded_by_id=current.id,
        file_size_bytes=size_bytes,
        checksum_sha256=checksum,
        header_object=header_meta.object_name,
        header_ra=header_meta.ra,
        header_dec=header_meta.dec,
        header_date_obs=header_meta.date_obs,
        header_exptime=header_meta.exptime,
        header_filter=header_meta.filter_name,
        header_telescop=header_meta.telescop,
        header_instrume=header_meta.instrume,
        missing_keywords=",".join(header_meta.missing_keywords) or None,
    )
    db.add(fits_file)
    db.flush()

    metrics = analyze_image(image_data, bit_depth=header_meta.bit_depth)
    quality = ImageQualityResult(
        fits_file_id=fits_file.id,
        star_count=metrics.star_count,
        fwhm_px=metrics.fwhm_px,
        snr=metrics.snr,
        background_level=metrics.background_level,
        background_noise=metrics.background_noise,
        saturated_pixel_count=metrics.saturated_pixel_count,
        saturated_pixel_pct=metrics.saturated_pixel_pct,
        star_quality_score=metrics.star_quality_score,
        fwhm_score=metrics.fwhm_score,
        snr_score=metrics.snr_score,
        background_score=metrics.background_score,
        saturation_score=metrics.saturation_score,
        total_score=metrics.total_score,
        rating=metrics.rating,
    )
    db.add(quality)
    db.flush()

    alert_service.check_image_quality(db, fits_file, quality)
    alert_service.check_missing_metadata(db, fits_file)
    audit_service.record(
        db, user_id=current.id, action="upload_fits", entity_type="fits_file", entity_id=fits_file.id,
        details=f"rating={quality.rating} score={quality.total_score}",
    )
    db.commit()
    db.refresh(fits_file)
    db.refresh(quality)

    return FitsUploadResponse(fits_file=fits_file, quality_result=quality)


@router.get("", response_model=list[FitsFileRead])
def list_fits_files(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> list[FitsFile]:
    return db.query(FitsFile).order_by(FitsFile.uploaded_at.desc()).all()


@router.get("/{fits_file_id}", response_model=FitsFileRead)
def get_fits_file(fits_file_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> FitsFile:
    fits_file = db.get(FitsFile, fits_file_id)
    if not fits_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FITS file not found")
    return fits_file


@router.get("/{fits_file_id}/quality", response_model=ImageQualityResultRead)
def get_quality_result(fits_file_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> ImageQualityResult:
    fits_file = db.get(FitsFile, fits_file_id)
    if not fits_file or not fits_file.quality_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quality result not found")
    return fits_file.quality_result
