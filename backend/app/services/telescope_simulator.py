"""
Realistic telescope simulator.

What's simulated vs. real (per the project's hardware-honesty rule):
* SIMULATED: whether the mount is slewing/tracking/parked, dome
  open/closed, camera idle/exposing — there is no physical mount.
* REAL: whenever the simulated mount is tracking or slewing, its
  Altitude/Azimuth is computed live from the target RA/Dec via
  `app.services.astronomy` for the telescope's actual Observatory site
  and the actual current time — exactly what a real equatorially-tracking
  mount's Alt/Az readout would show for that same RA/Dec.

State model:
* `slew_to(ra, dec)` records a start position + duration derived from
  angular separation / TELESCOPE_SLEW_RATE_DEG_PER_SEC, then linearly
  interpolates RA/Dec across that duration on each `get_status()` call
  (a wall-clock-driven simulation, not a background thread). On arrival,
  tracking auto-engages, matching typical real go-to behavior.
* While `tracking=True`, RA/Dec is fixed and Alt/Az is recomputed fresh
  every call (the sky moves under a tracking scope only in the sense
  that Alt/Az changes; RA/Dec does not).
* While idle (not tracking, not slewing — e.g. freshly parked or after
  `stop_tracking()`), Alt/Az is frozen at its last computed value rather
  than modeling the RA/Dec drift a truly stationary mount would show.
  This is a deliberate simplification, documented here and in
  ARCHITECTURE.md, so it doesn't read as an oversight; the physically
  correct behavior always applies to the state that matters for
  observation planning (actively tracking).

This class implements `TelescopeInterface` — API routes depend on that
interface, so a future real hardware adapter is a drop-in replacement.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from astropy.time import Time

from app.core.config import settings
from app.services import astronomy as astro
from app.services.telescope_interface import TelescopeInterface, TelescopeState


def _angular_separation_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    c1 = astro.target_skycoord(ra1, dec1)
    c2 = astro.target_skycoord(ra2, dec2)
    return float(c1.separation(c2).degree)


def _lerp(a: float, b: float, frac: float) -> float:
    return a + (b - a) * frac


@dataclass
class _InternalState:
    ra_deg: float
    dec_deg: float
    tracking: bool = False
    slewing: bool = False
    dome_state: str = "closed"
    camera_state: str = "idle"
    current_target_id: int | None = None

    frozen_alt_deg: float = 0.0
    frozen_az_deg: float = 0.0

    slew_started_at: datetime | None = None
    slew_duration_s: float | None = None
    slew_from_ra: float | None = None
    slew_from_dec: float | None = None
    slew_to_ra: float | None = None
    slew_to_dec: float | None = None


class TelescopeSimulator(TelescopeInterface):
    def __init__(
        self,
        get_site_for_telescope: Callable[[int], astro.Site],
        slew_rate_deg_per_sec: float | None = None,
    ) -> None:
        self._get_site = get_site_for_telescope
        self._slew_rate = slew_rate_deg_per_sec or settings.TELESCOPE_SLEW_RATE_DEG_PER_SEC
        self._states: dict[int, _InternalState] = {}

    # -- internal helpers ---------------------------------------------
    def _ensure(self, telescope_id: int) -> _InternalState:
        if telescope_id not in self._states:
            site = self._get_site(telescope_id)
            # Park pointed at the celestial pole visible from this site's
            # hemisphere — a real, common park position — not tracking.
            park_dec = 90.0 if site.latitude_deg >= 0 else -90.0
            state = _InternalState(ra_deg=0.0, dec_deg=park_dec, tracking=False, slewing=False)
            alt, az = astro.current_altaz(site, state.ra_deg, state.dec_deg)
            state.frozen_alt_deg, state.frozen_az_deg = alt, az
            self._states[telescope_id] = state
        return self._states[telescope_id]

    def _advance_slew(self, telescope_id: int, state: _InternalState) -> None:
        if not state.slewing or state.slew_started_at is None or state.slew_duration_s is None:
            return
        elapsed = (datetime.now(timezone.utc) - state.slew_started_at).total_seconds()
        if elapsed >= state.slew_duration_s:
            state.ra_deg = state.slew_to_ra  # type: ignore[assignment]
            state.dec_deg = state.slew_to_dec  # type: ignore[assignment]
            state.slewing = False
            state.tracking = True
            state.slew_started_at = None
            state.slew_duration_s = None
        else:
            frac = elapsed / state.slew_duration_s
            state.ra_deg = _lerp(state.slew_from_ra, state.slew_to_ra, frac)  # type: ignore[arg-type]
            state.dec_deg = _lerp(state.slew_from_dec, state.slew_to_dec, frac)  # type: ignore[arg-type]

    def _snapshot(self, telescope_id: int, state: _InternalState) -> TelescopeState:
        site = self._get_site(telescope_id)
        if state.tracking or state.slewing:
            alt, az = astro.current_altaz(site, state.ra_deg, state.dec_deg, at=Time.now())
            state.frozen_alt_deg, state.frozen_az_deg = alt, az
        else:
            alt, az = state.frozen_alt_deg, state.frozen_az_deg

        return TelescopeState(
            telescope_id=telescope_id,
            ra_deg=state.ra_deg,
            dec_deg=state.dec_deg,
            altitude_deg=alt,
            azimuth_deg=az,
            tracking=state.tracking,
            slewing=state.slewing,
            dome_state=state.dome_state,
            camera_state=state.camera_state,
            current_target_id=state.current_target_id,
            is_simulated=True,
        )

    # -- TelescopeInterface ---------------------------------------------
    def get_status(self, telescope_id: int) -> TelescopeState:
        state = self._ensure(telescope_id)
        self._advance_slew(telescope_id, state)
        return self._snapshot(telescope_id, state)

    def slew_to(self, telescope_id: int, ra_deg: float, dec_deg: float, target_id: int | None = None) -> TelescopeState:
        state = self._ensure(telescope_id)
        self._advance_slew(telescope_id, state)

        separation = _angular_separation_deg(state.ra_deg, state.dec_deg, ra_deg, dec_deg)
        duration = max(separation / self._slew_rate, 0.5)  # floor so tiny slews are still observable as "slewing"

        state.slew_from_ra, state.slew_from_dec = state.ra_deg, state.dec_deg
        state.slew_to_ra, state.slew_to_dec = ra_deg, dec_deg
        state.slew_started_at = datetime.now(timezone.utc)
        state.slew_duration_s = duration
        state.slewing = True
        state.tracking = False
        state.current_target_id = target_id

        return self._snapshot(telescope_id, state)

    def stop_tracking(self, telescope_id: int) -> TelescopeState:
        state = self._ensure(telescope_id)
        self._advance_slew(telescope_id, state)
        state.tracking = False
        return self._snapshot(telescope_id, state)

    def start_tracking(self, telescope_id: int) -> TelescopeState:
        state = self._ensure(telescope_id)
        self._advance_slew(telescope_id, state)
        if not state.slewing:
            state.tracking = True
        return self._snapshot(telescope_id, state)

    def open_dome(self, telescope_id: int) -> TelescopeState:
        state = self._ensure(telescope_id)
        state.dome_state = "open"
        return self._snapshot(telescope_id, state)

    def close_dome(self, telescope_id: int) -> TelescopeState:
        state = self._ensure(telescope_id)
        state.dome_state = "closed"
        state.tracking = False
        return self._snapshot(telescope_id, state)

    def park(self, telescope_id: int) -> TelescopeState:
        state = self._ensure(telescope_id)
        site = self._get_site(telescope_id)
        park_dec = 90.0 if site.latitude_deg >= 0 else -90.0
        state.tracking = False
        state.slewing = False
        state.ra_deg, state.dec_deg = 0.0, park_dec
        state.current_target_id = None
        alt, az = astro.current_altaz(site, state.ra_deg, state.dec_deg)
        state.frozen_alt_deg, state.frozen_az_deg = alt, az
        return self._snapshot(telescope_id, state)


# Process-local singleton registry, one simulator instance shared across
# requests (mirrors how a real hardware-adapter connection would be a
# long-lived singleton, not re-created per request).
_simulator: TelescopeSimulator | None = None


def get_telescope_backend(get_site_for_telescope: Callable[[int], astro.Site]) -> TelescopeInterface:
    global _simulator
    if _simulator is None:
        _simulator = TelescopeSimulator(get_site_for_telescope)
    return _simulator
