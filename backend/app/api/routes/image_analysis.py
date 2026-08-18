from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.fits_data import FitsFile, ImageQualityRating, ImageQualityResult
from app.models.user import User, UserRole
from app.schemas.fits_data import ImageQualityResultRead
from app.services.fits_service import load_image_data
from app.services.image_quality import analyze_image

router = APIRouter(prefix="/image-analysis", tags=["image-analysis"])


@router.get("/results", response_model=list[ImageQualityResultRead])
def list_quality_results(
    rating: ImageQualityRating | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
) -> list[ImageQualityResult]:
    query = db.query(ImageQualityResult)
    if rating:
        query = query.filter(ImageQualityResult.rating == rating)
    return query.order_by(ImageQualityResult.analyzed_at.desc()).all()


@router.post("/{fits_file_id}/reanalyze", response_model=ImageQualityResultRead)
def reanalyze(
    fits_file_id: int, db: Session = Depends(get_db), _u: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))
) -> ImageQualityResult:
    """Re-runs the scoring pipeline against the stored file — useful after
    a scoring-rubric tweak, without needing to re-upload."""
    fits_file = db.get(FitsFile, fits_file_id)
    if not fits_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FITS file not found")

    data = load_image_data(Path(fits_file.file_path))
    metrics = analyze_image(data)

    result = fits_file.quality_result
    if result is None:
        result = ImageQualityResult(fits_file_id=fits_file.id)
        db.add(result)

    result.star_count = metrics.star_count
    result.fwhm_px = metrics.fwhm_px
    result.snr = metrics.snr
    result.background_level = metrics.background_level
    result.background_noise = metrics.background_noise
    result.saturated_pixel_count = metrics.saturated_pixel_count
    result.saturated_pixel_pct = metrics.saturated_pixel_pct
    result.star_quality_score = metrics.star_quality_score
    result.fwhm_score = metrics.fwhm_score
    result.snr_score = metrics.snr_score
    result.background_score = metrics.background_score
    result.saturation_score = metrics.saturation_score
    result.total_score = metrics.total_score
    result.rating = metrics.rating

    db.commit()
    db.refresh(result)
    return result
