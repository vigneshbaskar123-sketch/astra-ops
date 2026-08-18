from __future__ import annotations

import io

import numpy as np
from astropy.io import fits

from tests.conftest import auth_headers
from tests.fixtures.synthetic_images import make_synthetic_star_field


def _fits_bytes(shape=(120, 120), n_stars=20, **kwargs) -> bytes:
    data, _ = make_synthetic_star_field(shape=shape, n_stars=n_stars, **kwargs)
    hdu = fits.PrimaryHDU(data=data.astype(np.float32))
    hdu.header["OBJECT"] = "M31"
    hdu.header["RA"] = "00:42:44.3"
    hdu.header["DEC"] = "+41:16:09"
    hdu.header["DATE-OBS"] = "2026-08-01T21:15:00"
    hdu.header["EXPTIME"] = 60.0
    hdu.header["FILTER"] = "L"
    hdu.header["TELESCOP"] = "ASTRA-OPS Simulated"
    hdu.header["INSTRUME"] = "SimCam-1"
    buf = io.BytesIO()
    hdu.writeto(buf)
    return buf.getvalue()


def test_fits_upload_full_pipeline(client, operator_user):
    headers = auth_headers(client, "operator_user")
    content = _fits_bytes(n_stars=25, psf_sigma_px=1.8, peak_amplitude=6000.0, noise_std=10.0, seed=100)

    resp = client.post(
        "/api/fits/upload",
        files={"file": ("m31_frame_001.fits", content, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["fits_file"]["header_object"] == "M31"
    assert body["fits_file"]["header_filter"] == "L"
    assert body["fits_file"]["missing_keywords"] is None
    assert body["quality_result"]["star_count"] > 0
    assert body["quality_result"]["rating"] in ("GOOD", "ACCEPTABLE", "POOR")

    fits_file_id = body["fits_file"]["id"]
    get_resp = client.get(f"/api/fits/{fits_file_id}", headers=headers)
    assert get_resp.status_code == 200

    quality_resp = client.get(f"/api/fits/{fits_file_id}/quality", headers=headers)
    assert quality_resp.status_code == 200


def test_fits_upload_rejects_non_fits_file(client, operator_user):
    headers = auth_headers(client, "operator_user")
    resp = client.post(
        "/api/fits/upload",
        files={"file": ("not_real.fits", b"plain garbage bytes, not a FITS file", "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 400


def test_fits_upload_rejects_bad_extension(client, operator_user):
    headers = auth_headers(client, "operator_user")
    resp = client.post(
        "/api/fits/upload",
        files={"file": ("script.exe", b"anything", "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 400


def test_poor_quality_upload_raises_alert(client, operator_user):
    headers = auth_headers(client, "operator_user")
    # Deliberately terrible image: almost no stars, very noisy.
    content = _fits_bytes(shape=(100, 100), n_stars=1, psf_sigma_px=7.0, peak_amplitude=100.0, noise_std=60.0, seed=200)

    resp = client.post(
        "/api/fits/upload", files={"file": ("bad_frame.fits", content, "application/octet-stream")}, headers=headers
    )
    assert resp.status_code == 201
    assert resp.json()["quality_result"]["rating"] == "POOR"

    alerts_resp = client.get("/api/alerts", params={"unacknowledged_only": True}, headers=headers)
    assert alerts_resp.status_code == 200
    alert_types = [a["alert_type"] for a in alerts_resp.json()]
    assert "poor_image_quality" in alert_types


def test_missing_metadata_alert(client, operator_user):
    headers = auth_headers(client, "operator_user")
    data, _ = make_synthetic_star_field(n_stars=10, seed=300)
    hdu = fits.PrimaryHDU(data=data.astype(np.float32))  # no header keywords set at all
    buf = io.BytesIO()
    hdu.writeto(buf)

    resp = client.post(
        "/api/fits/upload", files={"file": ("no_headers.fits", buf.getvalue(), "application/octet-stream")}, headers=headers
    )
    assert resp.status_code == 201
    assert resp.json()["fits_file"]["missing_keywords"] is not None

    alerts_resp = client.get("/api/alerts", headers=headers)
    alert_types = [a["alert_type"] for a in alerts_resp.json()]
    assert "missing_metadata" in alert_types
