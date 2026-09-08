"""Manage Users: RBAC, login-name derivation + collision, last-Owner guards,
reset stub, and the invariant that no secret is ever returned (SDD 5.3 / 13.1)."""

from __future__ import annotations

import json


def _create(client, headers, **over):
    body = {
        "full_name": "Ravi Kumar",
        "email": "ravi@example.test",
        "role": "Sales",
    }
    body.update(over)
    return client.post("/users", json=body, headers=headers)


def test_sales_has_no_access(client, auth_headers):
    assert client.get("/users", headers=auth_headers("Sales")).status_code == 403
    assert _create(client, auth_headers("Sales")).status_code == 403


def test_create_derives_login_name_and_has_no_password(client, auth_headers, conn):
    r = _create(client, auth_headers("Manager"))
    assert r.status_code == 201
    u = r.json()
    assert u["login_name"] == "rkumar"
    assert u["has_password"] is False
    assert "password_hash" not in u and "totp_secret" not in u

    audit = conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name = 'users' AND action = 'create'"
    ).fetchone()["c"]
    assert audit == 1


def test_login_name_collision_gets_a_suffix(client, auth_headers):
    _create(client, auth_headers("Manager"), full_name="Ravi Kumar")
    second = _create(client, auth_headers("Manager"), full_name="Rahul Kumar").json()
    assert second["login_name"] == "rkumar2"


def test_no_secret_fields_in_list(client, auth_headers):
    rows = client.get("/users", headers=auth_headers("Owner")).json()
    blob = json.dumps(rows)
    assert "password_hash" not in blob
    assert "totp_secret" not in blob


def test_cannot_disable_or_delete_the_last_owner(client, auth_headers, users):
    owner_id = users["Owner"]
    disable = client.put(
        f"/users/{owner_id}", json={"status": "Disabled"}, headers=auth_headers("Manager")
    )
    assert disable.status_code == 409

    demote = client.put(
        f"/users/{owner_id}", json={"role": "Manager"}, headers=auth_headers("Owner")
    )
    assert demote.status_code == 409

    delete = client.delete(f"/users/{owner_id}", headers=auth_headers("Manager"))
    assert delete.status_code == 409


def test_update_and_delete_a_user_with_audit(client, auth_headers, conn):
    uid = _create(client, auth_headers("Manager")).json()["id"]

    upd = client.put(
        f"/users/{uid}",
        json={"role": "Manager", "cell_phone": "+91 90000 11111"},
        headers=auth_headers("Owner"),
    ).json()
    assert upd["role"] == "Manager"
    # An admin may only CLEAR 2FA here (turning it on is 422); see test_totp.py.
    assert (
        client.put(
            f"/users/{uid}", json={"totp_enabled": True}, headers=auth_headers("Owner")
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"/users/{uid}", json={"totp_enabled": False}, headers=auth_headers("Owner")
        ).status_code
        == 200
    )

    assert client.delete(f"/users/{uid}", headers=auth_headers("Manager")).status_code == 204
    assert conn.execute("SELECT COUNT(*) c FROM users WHERE id = ?", (uid,)).fetchone()["c"] == 0
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='users' AND action='delete'"
    ).fetchone()["c"] == 1


def test_cannot_delete_your_own_account(client, auth_headers, users):
    assert client.delete(
        f"/users/{users['Manager']}", headers=auth_headers("Manager")
    ).status_code == 409


def test_admin_reset_password_emails_a_link(client, auth_headers, users):
    r = client.post(f"/users/{users['Sales']}/reset-password", headers=auth_headers("Manager"))
    assert r.status_code == 202
    assert "dev_reset_link" in r.json()  # full flow covered in test_password_reset.py
