from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FitsFile(Base):
    """Metadata extracted from an uploaded FITS file's primary header via
    astropy.io.fits — never hand-entered or invented. Any header keyword
    that was missing on upload is stored as NULL and (per module 12) can
    trigger a MISSING_METADATA alert rather than being silently guessed."""

    __tablename__ = "fits_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    observation_session_id: Mapped[int | None] = mapped_column(ForeignKey("observation_sessions.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # --- Header-derived fields (module 7) — nullable because real headers
    # legitimately omit keywords ---
    header_object: Mapped[str | None] = mapped_column(String(128), nullable=True)
    header_ra: Mapped[str | None] = mapped_column(String(64), nullable=True)
    header_dec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    header_date_obs: Mapped[str | None] = mapped_column(String(64), nullable=True)
    header_exptime: Mapped[float | None] = mapped_column(Float, nullable=True)
    header_filter: Mapped[str | None] = mapped_column(String(32), nullable=True)
    header_telescop: Mapped[str | None] = mapped_column(String(128), nullable=True)
    header_instrume: Mapped[str | None] = mapped_column(String(128), nullable=True)
    missing_keywords: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Comma-separated list of expected FITS keywords absent from the header"
    )

    observation_session: Mapped["ObservationSession | None"] = relationship(back_populates="fits_files")
    uploaded_by: Mapped["User | None"] = relationship()
    quality_result: Mapped["ImageQualityResult | None"] = relationship(
        back_populates="fits_file", uselist=False, cascade="all, delete-orphan"
    )


class ImageQualityRating(str, enum.Enum):
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"


class ImageQualityResult(Base):
    """Output of services/image_quality.py — every numeric field here is a
    real measurement made on the pixel data (star detection, Gaussian PSF
    fit, sigma-clipped background stats), never a placeholder."""

    __tablename__ = "image_quality_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    fits_file_id: Mapped[int] = mapped_column(ForeignKey("fits_files.id"), unique=True, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    star_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fwhm_px: Mapped[float | None] = mapped_column(Float, nullable=True)
    snr: Mapped[float | None] = mapped_column(Float, nullable=True)
    background_level: Mapped[float] = mapped_column(Float, nullable=False)
    background_noise: Mapped[float] = mapped_column(Float, nullable=False)
    saturated_pixel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    saturated_pixel_pct: Mapped[float] = mapped_column(Float, nullable=False)

    star_quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    fwhm_score: Mapped[float] = mapped_column(Float, nullable=False)
    snr_score: Mapped[float] = mapped_column(Float, nullable=False)
    background_score: Mapped[float] = mapped_column(Float, nullable=False)
    saturation_score: Mapped[float] = mapped_column(Float, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    rating: Mapped[ImageQualityRating] = mapped_column(Enum(ImageQualityRating, native_enum=False, length=16), index=True)

    fits_file: Mapped["FitsFile"] = relationship(back_populates="quality_result")
