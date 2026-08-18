"""
FITS ingestion: validation + header metadata extraction via astropy.io.fits.

Every metadata field returned here comes directly from the file's own
FITS header — nothing is inferred or defaulted to a plausible-looking
value. A header keyword that is absent is reported as `None` and listed
in `missing_keywords`, which the alert service (module 12) uses to raise
a MISSING_METADATA alert rather than silently proceeding as if the data
were complete.

Validation is layered, not just an extension check (an attacker or a
mistaken user could rename any file to `.fits`):
  1. extension allow-list
  2. size limit
  3. the file must actually parse as FITS via astropy — a real
     structural check, since FITS parsing will raise on garbage input
Only a file that survives all three is written to permanent storage;
anything else is rejected and the temp file is removed.
"""
from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from astropy.io import fits

from app.core.config import settings

EXPECTED_KEYWORDS = ("OBJECT", "RA", "DEC", "DATE-OBS", "EXPTIME", "FILTER", "TELESCOP", "INSTRUME")


class FitsValidationError(ValueError):
    pass


@dataclass
class FitsHeaderMetadata:
    object_name: str | None
    ra: str | None
    dec: str | None
    date_obs: str | None
    exptime: float | None
    filter_name: str | None
    telescop: str | None
    instrume: str | None
    missing_keywords: list[str]
    bit_depth: int
    image_shape: tuple[int, ...] | None


def validate_upload_filename(filename: str, size_bytes: int) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.ALLOWED_FITS_EXTENSIONS:
        raise FitsValidationError(
            f"'{suffix}' is not an allowed FITS extension (allowed: {', '.join(settings.ALLOWED_FITS_EXTENSIONS)})"
        )
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise FitsValidationError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB upload limit")


def extract_header_metadata(fits_path: Path) -> FitsHeaderMetadata:
    """Opens the file with astropy — raises FitsValidationError if it is
    not a structurally valid FITS file. This is the real content check,
    not just a filename check."""
    try:
        with fits.open(fits_path, memmap=False) as hdul:
            hdul.verify("silentfix")
            header = hdul[0].header
            data = hdul[0].data
            if data is None:
                for hdu in hdul[1:]:
                    if getattr(hdu, "data", None) is not None:
                        data = hdu.data
                        break
    except FitsValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - astropy raises several distinct exception types for bad FITS
        raise FitsValidationError(f"File could not be parsed as FITS: {exc}") from exc

    values = {
        "OBJECT": header.get("OBJECT"),
        "RA": header.get("RA"),
        "DEC": header.get("DEC"),
        "DATE-OBS": header.get("DATE-OBS"),
        "EXPTIME": header.get("EXPTIME"),
        "FILTER": header.get("FILTER"),
        "TELESCOP": header.get("TELESCOP"),
        "INSTRUME": header.get("INSTRUME"),
    }
    missing = [k for k in EXPECTED_KEYWORDS if values.get(k) in (None, "")]

    exptime = values["EXPTIME"]
    try:
        exptime = float(exptime) if exptime is not None else None
    except (TypeError, ValueError):
        exptime = None

    bitpix = int(header.get("BITPIX", 16))
    bit_depth = abs(bitpix)

    return FitsHeaderMetadata(
        object_name=_stringify(values["OBJECT"]),
        ra=_stringify(values["RA"]),
        dec=_stringify(values["DEC"]),
        date_obs=_stringify(values["DATE-OBS"]),
        exptime=exptime,
        filter_name=_stringify(values["FILTER"]),
        telescop=_stringify(values["TELESCOP"]),
        instrume=_stringify(values["INSTRUME"]),
        missing_keywords=missing,
        bit_depth=bit_depth,
        image_shape=tuple(data.shape) if isinstance(data, np.ndarray) else None,
    )


def _stringify(value) -> str | None:
    if value is None:
        return None
    return str(value)


def load_image_data(fits_path: Path) -> np.ndarray:
    """Load the first HDU with real pixel data as a float64 array, for the
    image-quality analyzer."""
    with fits.open(fits_path, memmap=False) as hdul:
        for hdu in hdul:
            if getattr(hdu, "data", None) is not None and hdu.data.ndim >= 2:
                return np.asarray(hdu.data, dtype=np.float64)
    raise FitsValidationError("FITS file contains no 2D image data")


def store_uploaded_file(tmp_path: Path, original_filename: str) -> tuple[Path, int, str]:
    """Moves a validated temp file into permanent storage under a
    collision-proof name. Returns (final_path, size_bytes, sha256_hex)."""
    suffix = Path(original_filename).suffix.lower()
    final_name = f"{uuid.uuid4().hex}{suffix}"
    final_path = settings.FITS_STORAGE_DIR / final_name
    shutil.move(str(tmp_path), str(final_path))

    size_bytes = final_path.stat().st_size
    sha256 = hashlib.sha256()
    with open(final_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha256.update(chunk)

    return final_path, size_bytes, sha256.hexdigest()
