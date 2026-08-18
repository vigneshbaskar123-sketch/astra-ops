from __future__ import annotations

from app.services.image_quality import analyze_image
from tests.fixtures.synthetic_images import make_synthetic_star_field


def test_background_and_noise_recovered_close_to_ground_truth():
    data, _ = make_synthetic_star_field(n_stars=15, background=500.0, noise_std=20.0, seed=1)
    metrics = analyze_image(data, bit_depth=16)

    assert abs(metrics.background_level - 500.0) < 10.0
    assert abs(metrics.background_noise - 20.0) < 8.0


def test_fwhm_measurement_close_to_known_injected_sigma():
    true_sigma = 2.5
    expected_fwhm = true_sigma * 2.3548200450309493  # ~5.887 px

    data, _ = make_synthetic_star_field(
        n_stars=15, psf_sigma_px=true_sigma, peak_amplitude=4000.0, noise_std=15.0, seed=3
    )
    metrics = analyze_image(data, bit_depth=16)

    assert metrics.fwhm_px is not None
    # Gaussian fit on noisy, discretely-detected stars: allow ~30% tolerance.
    assert abs(metrics.fwhm_px - expected_fwhm) / expected_fwhm < 0.3


def test_star_count_roughly_matches_injected_star_count():
    data, positions = make_synthetic_star_field(n_stars=18, peak_amplitude=4000.0, noise_std=15.0, seed=5)
    metrics = analyze_image(data, bit_depth=16)

    # DAOStarFinder won't recover every star at the edges/overlaps, but
    # should be in the right ballpark.
    assert abs(metrics.star_count - len(positions)) <= 5


def test_saturation_detection_with_injected_saturated_stars():
    data, _ = make_synthetic_star_field(
        n_stars=10, n_saturated_stars=3, saturation_value=65000.0, noise_std=20.0, seed=9
    )
    metrics = analyze_image(data, bit_depth=16, saturation_threshold=65000.0 * 0.99)

    assert metrics.saturated_pixel_count > 0
    assert metrics.saturated_pixel_pct > 0.0


def test_no_saturation_when_no_bright_injected_stars():
    data, _ = make_synthetic_star_field(n_stars=10, n_saturated_stars=0, peak_amplitude=1500.0, noise_std=20.0, seed=11)
    metrics = analyze_image(data, bit_depth=16)

    assert metrics.saturated_pixel_count == 0
    assert metrics.saturation_score == 15.0  # full points


def test_high_quality_image_rates_good():
    data, _ = make_synthetic_star_field(
        shape=(300, 300),
        n_stars=30,
        psf_sigma_px=1.8,  # tight PSF
        peak_amplitude=6000.0,
        background=500.0,
        noise_std=10.0,  # low noise -> high SNR
        seed=21,
    )
    metrics = analyze_image(data, bit_depth=16)

    assert metrics.rating == "GOOD"
    assert metrics.total_score >= 80.0


def test_low_quality_image_rates_poor():
    data, _ = make_synthetic_star_field(
        shape=(150, 150),
        n_stars=2,  # very few stars
        psf_sigma_px=6.0,  # badly out of focus
        peak_amplitude=150.0,  # faint
        background=500.0,
        noise_std=60.0,  # very noisy -> low SNR
        seed=33,
    )
    metrics = analyze_image(data, bit_depth=16)

    assert metrics.rating == "POOR"
    assert metrics.total_score < 50.0


def test_scoring_is_transparent_and_sums_correctly():
    data, _ = make_synthetic_star_field(n_stars=15, seed=45)
    metrics = analyze_image(data, bit_depth=16)

    component_sum = (
        metrics.star_quality_score
        + metrics.fwhm_score
        + metrics.snr_score
        + metrics.background_score
        + metrics.saturation_score
    )
    assert abs(component_sum - metrics.total_score) < 0.01
    assert 0.0 <= metrics.total_score <= 100.0
