"""Synthetic FITS-like star field generator for testing the image-quality
analyzer against known ground truth (true PSF sigma, true background,
true noise) — there is no real astronomical test image available in this
sandbox, so validation has to be against data we generated ourselves
with known properties, rather than against an external reference frame."""
from __future__ import annotations

import numpy as np


def make_synthetic_star_field(
    shape: tuple[int, int] = (200, 200),
    n_stars: int = 20,
    seed: int = 42,
    psf_sigma_px: float = 2.5,
    peak_amplitude: float = 3000.0,
    background: float = 500.0,
    noise_std: float = 20.0,
    n_saturated_stars: int = 0,
    saturation_value: float = 65000.0,
) -> tuple[np.ndarray, list[tuple[float, float, float]]]:
    rng = np.random.default_rng(seed)
    data = rng.normal(loc=background, scale=noise_std, size=shape).astype(np.float64)
    yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]]

    positions: list[tuple[float, float, float]] = []
    margin = max(10, int(psf_sigma_px * 4))
    for _ in range(n_stars):
        x0 = rng.uniform(margin, shape[1] - margin)
        y0 = rng.uniform(margin, shape[0] - margin)
        amp = peak_amplitude * rng.uniform(0.3, 1.0)
        data += amp * np.exp(-(((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * psf_sigma_px**2)))
        positions.append((x0, y0, amp))

    for _ in range(n_saturated_stars):
        x0 = rng.uniform(margin, shape[1] - margin)
        y0 = rng.uniform(margin, shape[0] - margin)
        amp = saturation_value * 2.0
        data += amp * np.exp(-(((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * (psf_sigma_px * 0.8) ** 2)))
        positions.append((x0, y0, amp))

    ceiling = saturation_value if (n_saturated_stars or saturation_value) else None
    if ceiling is not None:
        data = np.clip(data, 0, ceiling)

    return data, positions
