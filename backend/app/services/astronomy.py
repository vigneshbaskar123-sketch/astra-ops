"""
Astronomy calculation service.

Every function here does a real astropy/astroplan calculation for a real
site (an `Observatory` row's lat/lon/elevation/timezone) and a real target
(RA/Dec). Nothing in this module is simulated or invented — this is the
one place in the codebase where "simulated" must never leak in, because
the AI assistant (a later stage) and the planner UI both treat these
numbers as ground truth.

Two deliberate engineering choices, documented here because they affect
correctness/behavior:

1. IERS auto-download is disabled (`iers.conf.auto_download = False`).
   Precise Earth-orientation parameters (UT1-UTC, polar motion) are
   normally fetched from an online IERS bulletin; astropy falls back to
   bundled approximate values when download is off. That costs a small
   amount of pointing precision (sub-arcsecond to arcsecond-level) which
   is irrelevant for planning-level altitude/visibility work, and it
   means this service never makes a surprise network call or hangs
   waiting for one in an offline/sandboxed deployment. A production build
   aiming for precise go-to pointing would re-enable this and vendor a
   pinned IERS snapshot instead.

2. ErfaWarning ("dubious year") is expected and suppressed. It fires for
   any date astropy's bundled tables don't yet cover (e.g. far-future
   dates) and does not indicate a calculation error at this precision
   level.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time as time_type
from zoneinfo import ZoneInfo

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy.utils import iers
from astroplan import FixedTarget, Observer

iers.conf.auto_download = False

try:  # pragma: no cover - depends on erfa version exposing this class
    from erfa import ErfaWarning
    warnings.filterwarnings("ignore", category=ErfaWarning)
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Site:
    """Plain-data view of an Observatory row, decoupled from the ORM so
    this module has no DB dependency and is trivially unit-testable."""

    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    timezone: str
    name: str = "site"

    def observer(self) -> Observer:
        return Observer(
            latitude=self.latitude_deg * u.deg,
            longitude=self.longitude_deg * u.deg,
            elevation=self.elevation_m * u.m,
            timezone=ZoneInfo(self.timezone),
            name=self.name,
        )


def target_skycoord(ra_deg: float, dec_deg: float) -> SkyCoord:
    return SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")


def current_altaz(site: Site, ra_deg: float, dec_deg: float, at: Time | None = None) -> tuple[float, float]:
    """Return (altitude_deg, azimuth_deg) for a target right now (or at
    the given astropy Time)."""
    observer = site.observer()
    coord = target_skycoord(ra_deg, dec_deg)
    t = at or Time.now()
    altaz = observer.altaz(t, FixedTarget(coord=coord))
    return float(altaz.alt.degree), float(altaz.az.degree)


def sun_altitude_deg(site: Site, at: Time | None = None) -> float:
    observer = site.observer()
    t = at or Time.now()
    return float(observer.sun_altaz(t).alt.degree)


def moon_altitude_deg(site: Site, at: Time | None = None) -> float:
    observer = site.observer()
    t = at or Time.now()
    return float(observer.moon_altaz(t).alt.degree)


def moon_illumination_pct(site: Site, at: Time | None = None) -> float:
    observer = site.observer()
    t = at or Time.now()
    return float(observer.moon_illumination(t) * 100.0)


def is_target_up(site: Site, ra_deg: float, dec_deg: float, min_altitude_deg: float = 20.0, at: Time | None = None) -> bool:
    alt, _ = current_altaz(site, ra_deg, dec_deg, at=at)
    return alt >= min_altitude_deg


def _local_noon(site: Site, on_date: date_type) -> Time:
    tz = ZoneInfo(site.timezone)
    local_dt = datetime.combine(on_date, time_type(12, 0), tzinfo=tz)
    return Time(local_dt)


def night_bounds(site: Site, on_date: date_type) -> tuple[Time, Time]:
    """Astronomical-twilight bounds (sun below -18 degrees) for the night
    that begins on `on_date` (local calendar date at the site)."""
    observer = site.observer()
    ref = _local_noon(site, on_date)
    evening = observer.twilight_evening_astronomical(ref, which="next")
    morning = observer.twilight_morning_astronomical(evening, which="next")
    return evening, morning


def altitude_curve(
    site: Site, ra_deg: float, dec_deg: float, start: Time, end: Time, step_minutes: float = 10.0
) -> list[tuple[Time, float, float]]:
    """Vectorized altitude/azimuth sample over [start, end]."""
    observer = site.observer()
    coord = target_skycoord(ra_deg, dec_deg)
    duration_min = (end - start).sec / 60.0
    n_steps = max(2, int(duration_min / step_minutes) + 1)
    offsets_min = np.linspace(0, duration_min, n_steps)
    times = start + offsets_min * u.min
    altaz = observer.altaz(times, FixedTarget(coord=coord))
    return list(zip(times, altaz.alt.degree.tolist(), altaz.az.degree.tolist()))


def find_visibility_windows(
    curve: list[tuple[Time, float, float]], min_altitude_deg: float
) -> list[tuple[Time, Time]]:
    """Contiguous runs of the altitude curve at/above the threshold."""
    windows: list[tuple[Time, Time]] = []
    run_start: Time | None = None
    for t, alt, _az in curve:
        above = alt >= min_altitude_deg
        if above and run_start is None:
            run_start = t
        elif not above and run_start is not None:
            windows.append((run_start, t))
            run_start = None
    if run_start is not None:
        windows.append((run_start, curve[-1][0]))
    return windows


def best_window(windows: list[tuple[Time, Time]]) -> tuple[Time, Time] | None:
    if not windows:
        return None
    return max(windows, key=lambda w: (w[1] - w[0]).sec)


def build_visibility_report(
    site: Site,
    target_id: int,
    target_name: str,
    observatory_id: int,
    ra_deg: float,
    dec_deg: float,
    on_date: date_type,
    min_altitude_deg: float = 30.0,
    step_minutes: float = 10.0,
):
    """High-level assembly used directly by the /planner API route."""
    now = Time.now()
    cur_alt, cur_az = current_altaz(site, ra_deg, dec_deg, at=now)
    sun_alt = sun_altitude_deg(site, at=now)
    moon_alt = moon_altitude_deg(site, at=now)
    moon_illum = moon_illumination_pct(site, at=now)

    evening, morning = night_bounds(site, on_date)
    curve = altitude_curve(site, ra_deg, dec_deg, evening, morning, step_minutes=step_minutes)
    windows = find_visibility_windows(curve, min_altitude_deg)
    best = best_window(windows)

    return {
        "target_id": target_id,
        "target_name": target_name,
        "observatory_id": observatory_id,
        "date": on_date.isoformat(),
        "current_altitude_deg": cur_alt,
        "current_azimuth_deg": cur_az,
        "is_currently_visible": cur_alt >= min_altitude_deg,
        "sun_altitude_deg": sun_alt,
        "moon_altitude_deg": moon_alt,
        "moon_illumination_pct": moon_illum,
        "min_altitude_threshold_deg": min_altitude_deg,
        "recommended_window": (
            {
                "start": best[0].to_datetime(),
                "end": best[1].to_datetime(),
                "duration_minutes": (best[1] - best[0]).sec / 60.0,
            }
            if best
            else None
        ),
        "all_visibility_windows": [
            {"start": w[0].to_datetime(), "end": w[1].to_datetime(), "duration_minutes": (w[1] - w[0]).sec / 60.0}
            for w in windows
        ],
        "altitude_curve": [
            {"time": t.to_datetime(), "altitude_deg": alt, "azimuth_deg": az} for t, alt, az in curve
        ],
    }
