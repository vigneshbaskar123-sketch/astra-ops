from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from app.services.fits_service import (
    FitsValidationError,
    extract_header_metadata,
    load_image_data,
    store_uploaded_file,
    validate_upload_filename,
)


def _write_synthetic_fits(
    path: Path,
    shape=(64, 64),
    include_headers: bool = True,
    bitpix: int = 16,
) -> None:
    rng = np.random.default_rng(1)
    data = rng.integers(100, 2000, size=shape).astype(np.int16 if bitpix == 16 else np.float32)
    hdu = fits.PrimaryHDU(data=data)
    if include_headers:
        hdu.header["OBJECT"] = "M31"
        hdu.header["RA"] = "00:42:44.3"
        hdu.header["DEC"] = "+41:16:09"
        hdu.header["DATE-OBS"] = "2026-08-01T21:15:00"
        hdu.header["EXPTIME"] = 120.0
        hdu.header["FILTER"] = "L"
        hdu.header["TELESCOP"] = "ASTRA-OPS Simulated 0.5m"
        hdu.header["INSTRUME"] = "SimCam-1"
    hdu.writeto(path, overwrite=True)


def test_validate_upload_filename_accepts_fits_extension():
    validate_upload_filename("frame_0001.fits", size_bytes=1024)  # should not raise


def test_validate_upload_filename_rejects_bad_extension():
    with pytest.raises(FitsValidationError):
        validate_upload_filename("not_a_fits_file.exe", size_bytes=1024)


def test_validate_upload_filename_rejects_oversized_file():
    with pytest.raises(FitsValidationError):
        validate_upload_filename("big.fits", size_bytes=10**12)


def test_extract_header_metadata_round_trip(tmp_path: Path):
    fits_path = tmp_path / "test_frame.fits"
    _write_synthetic_fits(fits_path)

    meta = extract_header_metadata(fits_path)

    assert meta.object_name == "M31"
    assert meta.exptime == 120.0
    assert meta.filter_name == "L"
    assert meta.telescop == "ASTRA-OPS Simulated 0.5m"
    assert meta.instrume == "SimCam-1"
    assert meta.missing_keywords == []
    assert meta.image_shape == (64, 64)


def test_extract_header_metadata_flags_missing_keywords(tmp_path: Path):
    fits_path = tmp_path / "no_headers.fits"
    _write_synthetic_fits(fits_path, include_headers=False)

    meta = extract_header_metadata(fits_path)

    assert meta.object_name is None
    assert "OBJECT" in meta.missing_keywords
    assert "TELESCOP" in meta.missing_keywords
    assert len(meta.missing_keywords) == 8


def test_extract_header_metadata_rejects_non_fits_file(tmp_path: Path):
    fake = tmp_path / "fake.fits"
    fake.write_bytes(b"this is definitely not a FITS file, just plain bytes")

    with pytest.raises(FitsValidationError):
        extract_header_metadata(fake)


def test_load_image_data_returns_expected_shape(tmp_path: Path):
    fits_path = tmp_path / "test_frame.fits"
    _write_synthetic_fits(fits_path, shape=(32, 48))

    data = load_image_data(fits_path)

    assert data.shape == (32, 48)
    assert data.dtype == np.float64


def test_store_uploaded_file_moves_and_hashes(tmp_path: Path, monkeypatch):
    from app.core.config import settings

    storage_dir = tmp_path / "fits_storage"
    storage_dir.mkdir()
    monkeypatch.setattr(settings, "FITS_STORAGE_DIR", storage_dir)

    src = tmp_path / "incoming.fits"
    _write_synthetic_fits(src)

    final_path, size_bytes, checksum = store_uploaded_file(src, "incoming.fits")

    assert final_path.exists()
    assert final_path.parent == storage_dir
    assert not src.exists()  # moved, not copied
    assert size_bytes > 0
    assert len(checksum) == 64  # sha256 hex digest length
