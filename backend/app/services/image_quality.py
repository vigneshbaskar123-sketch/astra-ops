"""
Astronomical image-quality analysis.

Pipeline (all real measurements on the actual pixel data — nothing here
is a placeholder or a guess):

1. Background: sigma-clipped mean/median/std of the whole frame
   (astropy.stats.sigma_clipped_stats). Sigma-clipping excludes star
   pixels from the statistics automatically.
2. Star detection: photutils.detection.DAOStarFinder on the
   background-subtracted frame, thresholded at N-sigma above the noise.
3. FWHM: for the brightest few detected stars, fit a 2D Gaussian
   (astropy.modeling) to a small cutout around each and convert the
   fitted sigma to FWHM = sigma * 2*sqrt(2*ln2). This is a real per-image
   PSF measurement, not the DAOStarFinder input guess echoed back.
4. SNR: per star, (peak_flux - background) / background_noise, then take
   the median across measured stars.
5. Saturation: fraction of pixels at/above a saturation threshold derived
   from the header bit depth (falls back to 16-bit if unknown).
6. Scoring: five independent sub-scores on the point budget from the
   spec (Star quality 20 / FWHM 25 / SNR 25 / Background 15 /
   Saturation 15 = 100), each a documented piecewise-linear function so
   the score is auditable, not a black box. Final rating: GOOD (>=80),
   ACCEPTABLE (50-79), POOR (<50).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
from astropy.modeling import fitting, models
from astropy.stats import sigma_clipped_stats
from astropy.utils.exceptions import AstropyWarning
from photutils.detection import DAOStarFinder

FWHM_SIGMA_TO_FWHM = 2.3548200450309493  # 2 * sqrt(2 * ln 2)

# --- Scoring rubric breakpoints (documented, tunable in one place) ---
STAR_QUALITY_MAX_POINTS = 20.0
STAR_COUNT_EXCELLENT = 25   # >= this many stars -> full star-quality points
STAR_COUNT_MINIMUM = 3      # < this many -> 0 star-quality points

FWHM_MAX_POINTS = 25.0
FWHM_EXCELLENT_PX = 2.5     # <= this FWHM -> full points (tight, well-focused stars)
FWHM_UNACCEPTABLE_PX = 8.0  # >= this FWHM -> 0 points (badly out of focus / poor seeing)

SNR_MAX_POINTS = 25.0
SNR_EXCELLENT = 50.0        # >= this SNR -> full points
SNR_UNACCEPTABLE = 3.0      # <= this SNR -> 0 points (per common astro convention, SNR 3 ~ detection limit)

BACKGROUND_MAX_POINTS = 15.0
BACKGROUND_NOISE_EXCELLENT = 15.0   # <= this noise (ADU) -> full points
BACKGROUND_NOISE_UNACCEPTABLE = 150.0

SATURATION_MAX_POINTS = 15.0
SATURATION_EXCELLENT_PCT = 0.0     # 0% saturated -> full points
SATURATION_UNACCEPTABLE_PCT = 2.0  # >= 2% of pixels saturated -> 0 points

RATING_GOOD_THRESHOLD = 80.0
RATING_ACCEPTABLE_THRESHOLD = 50.0


def _linear_score(value: float, excellent: float, unacceptable: float, max_points: float) -> float:
    """Piecewise-linear score: `max_points` at/beyond `excellent`, 0 at/
    beyond `unacceptable`, linearly interpolated between. Handles both
    "lower is better" (excellent < unacceptable) and "higher is better"
    (excellent > unacceptable) automatically from the argument order."""
    if excellent == unacceptable:
        return max_points if value == excellent else 0.0
    frac = (value - unacceptable) / (excellent - unacceptable)
    frac = min(max(frac, 0.0), 1.0)
    return frac * max_points


@dataclass
class StarMeasurement:
    x: float
    y: float
    peak: float
    fwhm_px: float | None
    snr: float | None


@dataclass
class ImageQualityMetrics:
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
    rating: str

    star_measurements: list[StarMeasurement] = field(default_factory=list)


def _measure_star_fwhm_and_peak(data: np.ndarray, x: float, y: float, box_size: int = 15) -> tuple[float | None, float]:
    half = box_size // 2
    yi, xi = int(round(y)), int(round(x))
    y0, y1 = max(0, yi - half), min(data.shape[0], yi + half + 1)
    x0, x1 = max(0, xi - half), min(data.shape[1], xi + half + 1)
    cutout = data[y0:y1, x0:x1]

    if cutout.size < 9:
        return None, float(data[yi, xi]) if 0 <= yi < data.shape[0] and 0 <= xi < data.shape[1] else 0.0

    local_bg = float(np.median(cutout))
    peak = float(cutout.max())
    amplitude = peak - local_bg
    if amplitude <= 0:
        return None, peak

    yy, xx = np.mgrid[0 : cutout.shape[0], 0 : cutout.shape[1]]
    g_init = models.Gaussian2D(
        amplitude=amplitude,
        x_mean=cutout.shape[1] / 2,
        y_mean=cutout.shape[0] / 2,
        x_stddev=2.0,
        y_stddev=2.0,
    )
    fitter = fitting.LevMarLSQFitter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=AstropyWarning)
        try:
            g_fit = fitter(g_init, xx, yy, cutout - local_bg)
        except Exception:
            return None, peak

    sigma = (abs(float(g_fit.x_stddev.value)) + abs(float(g_fit.y_stddev.value))) / 2.0
    if sigma <= 0 or sigma > box_size:
        return None, peak
    return sigma * FWHM_SIGMA_TO_FWHM, peak


def analyze_image(
    data: np.ndarray,
    bit_depth: int = 16,
    saturation_threshold: float | None = None,
    detection_sigma: float = 5.0,
    max_stars_to_measure: int = 20,
) -> ImageQualityMetrics:
    data = np.nan_to_num(np.asarray(data, dtype=np.float64))

    mean, median, std = sigma_clipped_stats(data, sigma=3.0, maxiters=5)
    background_level = float(median)
    background_noise = float(std) if std > 0 else 1e-6

    sat_threshold = saturation_threshold or (2**bit_depth - 1) * 0.99
    saturated_mask = data >= sat_threshold
    saturated_count = int(np.count_nonzero(saturated_mask))
    saturated_pct = float(saturated_count / data.size * 100.0)

    finder = DAOStarFinder(fwhm=3.0, threshold=detection_sigma * background_noise)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=AstropyWarning)
        sources = finder(data - background_level)

    star_count = 0 if sources is None else len(sources)

    measurements: list[StarMeasurement] = []
    if sources is not None and star_count > 0:
        # photutils renamed these columns across versions
        # (xcentroid/ycentroid -> x_centroid/y_centroid); support both so
        # this doesn't silently break on a photutils upgrade or downgrade.
        x_col = "x_centroid" if "x_centroid" in sources.colnames else "xcentroid"
        y_col = "y_centroid" if "y_centroid" in sources.colnames else "ycentroid"

        sources.sort("flux")
        sources.reverse()
        for row in list(sources)[:max_stars_to_measure]:
            x, y = float(row[x_col]), float(row[y_col])
            fwhm_px, peak = _measure_star_fwhm_and_peak(data, x, y)
            snr = (peak - background_level) / background_noise if background_noise > 0 else None
            measurements.append(StarMeasurement(x=x, y=y, peak=peak, fwhm_px=fwhm_px, snr=snr))

    valid_fwhms = [m.fwhm_px for m in measurements if m.fwhm_px is not None]
    valid_snrs = [m.snr for m in measurements if m.snr is not None]
    fwhm_px = float(np.median(valid_fwhms)) if valid_fwhms else None
    snr = float(np.median(valid_snrs)) if valid_snrs else None

    star_quality_score = _linear_score(star_count, STAR_COUNT_EXCELLENT, STAR_COUNT_MINIMUM, STAR_QUALITY_MAX_POINTS)
    fwhm_score = (
        _linear_score(fwhm_px, FWHM_EXCELLENT_PX, FWHM_UNACCEPTABLE_PX, FWHM_MAX_POINTS)
        if fwhm_px is not None
        else 0.0
    )
    snr_score = _linear_score(snr, SNR_EXCELLENT, SNR_UNACCEPTABLE, SNR_MAX_POINTS) if snr is not None else 0.0
    background_score = _linear_score(
        background_noise, BACKGROUND_NOISE_EXCELLENT, BACKGROUND_NOISE_UNACCEPTABLE, BACKGROUND_MAX_POINTS
    )
    saturation_score = _linear_score(
        saturated_pct, SATURATION_EXCELLENT_PCT, SATURATION_UNACCEPTABLE_PCT, SATURATION_MAX_POINTS
    )

    # Round each sub-score BEFORE summing, so the displayed total always
    # exactly equals the sum of the displayed components — important for
    # a scoring system that's meant to be manually auditable, not just
    # internally consistent.
    star_quality_score = round(star_quality_score, 2)
    fwhm_score = round(fwhm_score, 2)
    snr_score = round(snr_score, 2)
    background_score = round(background_score, 2)
    saturation_score = round(saturation_score, 2)
    total_score = round(
        star_quality_score + fwhm_score + snr_score + background_score + saturation_score, 2
    )

    if total_score >= RATING_GOOD_THRESHOLD:
        rating = "GOOD"
    elif total_score >= RATING_ACCEPTABLE_THRESHOLD:
        rating = "ACCEPTABLE"
    else:
        rating = "POOR"

    return ImageQualityMetrics(
        star_count=star_count,
        fwhm_px=fwhm_px,
        snr=snr,
        background_level=background_level,
        background_noise=background_noise,
        saturated_pixel_count=saturated_count,
        saturated_pixel_pct=saturated_pct,
        star_quality_score=star_quality_score,
        fwhm_score=fwhm_score,
        snr_score=snr_score,
        background_score=background_score,
        saturation_score=saturation_score,
        total_score=total_score,
        rating=rating,
        star_measurements=measurements,
    )
