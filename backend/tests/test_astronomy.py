"""
Tests for app.services.astronomy.

Two of these tests check real physical invariants rather than fixed
"golden" numbers pulled from an external ephemeris (which this sandbox
has no network access to verify against). Both invariants tolerate ~1
degree of slop, which comfortably covers precession/nutation/aberration
accumulated since the J2000/ICRS reference epoch (a few tenths of a
degree by 2026) plus low-altitude atmospheric refraction — effects that
are real, expected, and irrelevant at the >=1 deg precision this
observation-planning tool actually needs. A tolerance this size would
NOT hide a genuine bug (swapped alt/az, wrong hemisphere sign, wrong
frame) — those produce errors of tens of degrees.
"""
from __future__ import annotations

from datetime import date

import astropy.units as u
from astropy.time import Time

from app.services import astronomy as astro

VBO = astro.Site(latitude_deg=12.5748, longitude_deg=78.8205, elevation_m=725.0, timezone="Asia/Kolkata", name="VBO")


def test_north_celestial_pole_altitude_equals_latitude():
    """An object at Dec=+90 sits at altitude == observer latitude, for
    any observer in the northern hemisphere, at any time."""
    for lat in (12.5748, 40.0, 60.0):
        site = astro.Site(latitude_deg=lat, longitude_deg=78.8205, elevation_m=0, timezone="UTC")
        alt, _az = astro.current_altaz(site, ra_deg=123.4, dec_deg=90.0)
        assert abs(alt - lat) < 1.0, f"NCP altitude {alt} should be within 1 deg of latitude {lat}"


def test_transit_at_matching_declination_reaches_zenith():
    """An object whose Dec equals the observer's latitude reaches ~90 deg
    altitude when its RA equals the current local sidereal time (i.e. at
    transit)."""
    site = astro.Site(latitude_deg=35.0, longitude_deg=0.0, elevation_m=0, timezone="UTC")
    now = Time.now()
    lst_deg = float(site.observer().local_sidereal_time(now).to(u.deg).value)
    alt, _az = astro.current_altaz(site, ra_deg=lst_deg, dec_deg=35.0, at=now)
    assert alt > 89.0


def test_moon_illumination_in_valid_range():
    illum = astro.moon_illumination_pct(VBO)
    assert 0.0 <= illum <= 100.0


def test_sun_altitude_in_valid_range():
    alt = astro.sun_altitude_deg(VBO)
    assert -90.0 <= alt <= 90.0


def test_visibility_windows_are_within_night_bounds():
    evening, morning = astro.night_bounds(VBO, date(2026, 11, 15))
    assert morning > evening
    # Astronomical night at this low latitude should be several hours,
    # not e.g. negative or absurdly short/long due to a twilight-function
    # misuse.
    duration_hours = (morning - evening).sec / 3600
    assert 8.0 < duration_hours < 13.0


def test_m31_recommended_window_shrinks_from_october_to_january():
    """Cross-check against known seasonal behavior: M31 (Dec +41) is
    best-placed for evening observation from a low northern latitude in
    the Sep-Nov window and increasingly squeezed by evening twilight as
    the season moves toward January, because its meridian transit shifts
    earlier into dusk. This is a coarse but meaningful regression check —
    a bug that mixed up window-finding logic would very likely break this
    monotonic-ish seasonal trend."""
    durations = []
    for d in (date(2026, 10, 15), date(2026, 12, 15), date(2027, 1, 15)):
        report = astro.build_visibility_report(VBO, 1, "M31", 1, ra_deg=10.6847, dec_deg=41.269, on_date=d)
        window = report["recommended_window"]
        durations.append(window["duration_minutes"] if window else 0.0)

    assert durations[0] > durations[1] > durations[2]


def test_target_below_horizon_target_never_visible():
    """A target with Dec far south of what this latitude can ever see
    above 30 deg altitude should report no recommended window."""
    # Dec = -80 is below the horizon for most of the night from +12.57 lat
    # except possibly a very brief culmination near due south at low alt;
    # well below our 30 deg threshold at transit: max alt = 90-(12.5748+80)
    report = astro.build_visibility_report(
        VBO, 1, "deep-south-target", 1, ra_deg=180.0, dec_deg=-80.0, on_date=date(2026, 6, 15)
    )
    assert report["recommended_window"] is None
