from __future__ import annotations

from tests.conftest import auth_headers


def test_login_success_and_me(client, viewer_user):
    headers = auth_headers(client, "viewer_user")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "viewer_user"
    assert body["role"] == "viewer"


def test_login_wrong_password_rejected(client, viewer_user):
    resp = client.post("/api/auth/login", data={"username": "viewer_user", "password": "wrong"})
    assert resp.status_code == 401


def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/targets")
    assert resp.status_code == 401


def test_viewer_cannot_create_target(client, viewer_user):
    headers = auth_headers(client, "viewer_user")
    resp = client.post("/api/targets", json={"name": "M31", "ra_deg": 10.68, "dec_deg": 41.27}, headers=headers)
    assert resp.status_code == 403


def test_operator_can_create_target(client, operator_user):
    headers = auth_headers(client, "operator_user")
    resp = client.post("/api/targets", json={"name": "M31", "ra_deg": 10.68, "dec_deg": 41.27}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "M31"


def test_viewer_can_read_targets(client, viewer_user, operator_user):
    op_headers = auth_headers(client, "operator_user")
    client.post("/api/targets", json={"name": "M42", "ra_deg": 83.82, "dec_deg": -5.39}, headers=op_headers)

    viewer_headers = auth_headers(client, "viewer_user")
    resp = client.get("/api/targets", headers=viewer_headers)
    assert resp.status_code == 200
    assert any(t["name"] == "M42" for t in resp.json())


def test_only_admin_can_delete_target(client, operator_user, admin_user):
    op_headers = auth_headers(client, "operator_user")
    created = client.post("/api/targets", json={"name": "Saturn", "ra_deg": 300.0, "dec_deg": -20.0}, headers=op_headers)
    target_id = created.json()["id"]

    resp = client.delete(f"/api/targets/{target_id}", headers=op_headers)
    assert resp.status_code == 403

    admin_headers = auth_headers(client, "admin_user")
    resp = client.delete(f"/api/targets/{target_id}", headers=admin_headers)
    assert resp.status_code == 204


def test_logout_revokes_token(client, viewer_user):
    headers = auth_headers(client, "viewer_user")
    resp = client.post("/api/auth/logout", headers=headers)
    assert resp.status_code == 200

    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 401
