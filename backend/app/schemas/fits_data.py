from __future__ import annotations

from datetime import datetime

from app.models.fits_data import ImageQualityRating
from app.schemas.common import ORMBase


class FitsFileRead(ORMBase):
    id: int
    observation_session_id: int | None
    filename: str
    uploaded_at: datetime
    file_size_bytes: int
    checksum_sha256: str
    header_object: str | None
    header_ra: str | None
    header_dec: str | None
    header_date_obs: str | None
    header_exptime: float | None
    header_filter: str | None
    header_telescop: str | None
    header_instrume: str | None
    missing_keywords: str | None


class ImageQualityResultRead(ORMBase):
    id: int
    fits_file_id: int
    analyzed_at: datetime
    star_count: int
    fwhm_px: float | None
    snr: float | None
    background_level: float
    background_noise: float
    saturated_pixel_count: int
    saturated_pixel_pct: float
    star_quality_score: float
    fwhm_score: float
    snr_score: float
    background_score: float
    saturation_score: float
    total_score: float
    rating: ImageQualityRating


class FitsUploadResponse(ORMBase):
    fits_file: FitsFileRead
    quality_result: ImageQualityResultRead
