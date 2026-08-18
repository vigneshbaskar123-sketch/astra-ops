from __future__ import annotations

import time

from app.services import astronomy as astro
from app.services.telescope_simulator import TelescopeSimulator

VBO = astro.Site(latitude_deg=12.5748, longitude_deg=78.8205, elevation_m=725.0, timezone="Asia/Kolkata", name="VBO")


def _site_lookup(_telescope_id: int) -> astro.Site:
    return VBO


def test_fresh_telescope_is_parked_not_tracking():
    sim = TelescopeSimulator(_site_lookup)
    status = sim.get_status(telescope_id=1)
    assert status.tracking is False
    assert status.slewing is False
    assert status.dome_state == "closed"
    assert -90.0 <= status.altitude_deg <= 90.0
    assert 0.0 <= status.azimuth_deg < 360.0


def test_slew_then_arrival_engages_tracking():
    # Very high slew rate so the 0.5s floor duration dominates and we can
    # observe arrival with a short sleep rather than a long one.
    sim = TelescopeSimulator(_site_lookup, slew_rate_deg_per_sec=1000.0)
    mid_status = sim.slew_to(telescope_id=1, ra_deg=10.6847, dec_deg=41.269, target_id=42)
    assert mid_status.slewing is True
    assert mid_status.tracking is False
    assert mid_status.current_target_id == 42

    time.sleep(0.6)
    final_status = sim.get_status(telescope_id=1)
    assert final_status.slewing is False
    assert final_status.tracking is True
    assert final_status.ra_deg == 10.6847
    assert final_status.dec_deg == 41.269


def test_altaz_matches_real_astronomy_service_while_tracking():
    """The whole point of the simulator: while tracking, Alt/Az must equal
    what the real astronomy engine computes for that RA/Dec right now —
    it is not a fabricated number."""
    sim = TelescopeSimulator(_site_lookup, slew_rate_deg_per_sec=1000.0)
    sim.slew_to(telescope_id=1, ra_deg=10.6847, dec_deg=41.269)
    time.sleep(0.6)
    status = sim.get_status(telescope_id=1)

    expected_alt, expected_az = astro.current_altaz(VBO, 10.6847, 41.269)
    assert abs(status.altitude_deg - expected_alt) < 0.01
    assert abs(status.azimuth_deg - expected_az) < 0.01


def test_stop_tracking_freezes_altaz():
    sim = TelescopeSimulator(_site_lookup, slew_rate_deg_per_sec=1000.0)
    sim.slew_to(telescope_id=1, ra_deg=10.6847, dec_deg=41.269)
    time.sleep(0.6)
    sim.get_status(telescope_id=1)
    stopped = sim.stop_tracking(telescope_id=1)
    assert stopped.tracking is False

    frozen_alt = stopped.altitude_deg
    time.sleep(0.2)
    again = sim.get_status(telescope_id=1)
    assert again.altitude_deg == frozen_alt


def test_dome_and_park():
    sim = TelescopeSimulator(_site_lookup)
    opened = sim.open_dome(telescope_id=2)
    assert opened.dome_state == "open"
    closed = sim.close_dome(telescope_id=2)
    assert closed.dome_state == "closed"
    assert closed.tracking is False

    parked = sim.park(telescope_id=2)
    assert parked.tracking is False
    assert parked.slewing is False
    assert parked.current_target_id is None
