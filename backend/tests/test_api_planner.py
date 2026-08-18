from __future__ import annotations

from tests.conftest import auth_headers


def _create_observatory(client, headers):
    resp = client.post(
        "/api/observatories",
        json={
            "name": "Vainu Bappu Observatory (test)",
            "code": "VBO",
            "latitude_deg": 12.5748,
            "longitude_deg": 78.8205,
            "elevation_m": 725.0,
            "timezone": "Asia/Kolkata",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_planner_visibility_uses_real_astronomy(client, admin_user, operator_user):
    admin_headers = auth_headers(client, "admin_user")
    op_headers = auth_headers(client, "operator_user")

    observatory = _create_observatory(client, admin_headers)
    target_resp = client.post(
        "/api/targets", json={"name": "M31", "ra_deg": 10.6847, "dec_deg": 41.269, "target_type": "galaxy"}, headers=op_headers
    )
    assert target_resp.status_code == 201
    target = target_resp.json()

    resp = client.get(
        f"/api/planner/visibility/{target['id']}",
        params={"observatory_id": observatory["id"], "on_date": "2026-10-15", "min_altitude_deg": 30},
        headers=op_headers,
    )
    assert resp.status_code == 200
    report = resp.json()

    assert report["target_name"] == "M31"
    assert -90 <= report["current_altitude_deg"] <= 90
    assert 0 <= report["moon_illumination_pct"] <= 100
    assert report["recommended_window"] is not None
    assert report["recommended_window"]["duration_minutes"] > 0
    assert len(report["altitude_curve"]) > 10


def test_planner_visibility_404_for_unknown_target(client, admin_user, operator_user):
    admin_headers = auth_headers(client, "admin_user")
    observatory = _create_observatory(client, admin_headers)

    resp = client.get(
        f"/api/planner/visibility/99999",
        params={"observatory_id": observatory["id"], "on_date": "2026-10-15"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_currently_visible_targets_only_returns_targets_above_threshold(client, admin_user, operator_user):
    admin_headers = auth_headers(client, "admin_user")
    op_headers = auth_headers(client, "operator_user")
    observatory = _create_observatory(client, admin_headers)

    # A target at the north celestial pole is always above ~12.5 deg
    # altitude from VBO's latitude — guaranteed visible above a low bar.
    client.post("/api/targets", json={"name": "NCP-test", "ra_deg": 0.0, "dec_deg": 89.9}, headers=op_headers)
    # A target far south is never visible above any reasonable threshold
    # from VBO.
    client.post("/api/targets", json={"name": "deep-south-test", "ra_deg": 0.0, "dec_deg": -85.0}, headers=op_headers)

    resp = client.get(
        "/api/planner/currently-visible", params={"observatory_id": observatory["id"], "min_altitude_deg": 10}, headers=op_headers
    )
    assert resp.status_code == 200
    names = [r["target_name"] for r in resp.json()]
    assert "NCP-test" in names
    assert "deep-south-test" not in names
