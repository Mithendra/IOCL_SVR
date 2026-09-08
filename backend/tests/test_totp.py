"""Two-factor auth (TOTP): self-service enrollment, the two-step login, and the
admin lockout-recovery path. Codes are computed with pyotp, same as a real
authenticator app would."""

from __future__ import annotations

import pyotp

from svr_backend.core.crypto import decrypt

PW = "test-pass-1234"  # conftest DEMO_PASSWORD


def _login(client, role):
    return client.post(
        "/auth/login", json={"login_name": role.lower(), "password": PW}
    )


def _enable_2fa(client, headers):
    secret = client.post("/auth/2fa/setup", headers=headers).json()["secret"]
    code = pyotp.TOTP(secret).now()
    r = client.post("/auth/2fa/activate", json={"code": code}, headers=headers)
    assert r.status_code == 204, r.text
    return secret


# ------------------------------------------------------------------- enrollment


def test_setup_returns_secret_and_uri(client, auth_headers):
    r = client.post("/auth/2fa/setup", headers=auth_headers("Sales"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["secret"]) >= 16
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert "SVR%20IOCL%20Station" in body["otpauth_uri"]


def test_status_pending_then_enabled(client, auth_headers):
    h = auth_headers("Sales")
    client.post("/auth/2fa/setup", headers=h)
    s = client.get("/auth/2fa/status", headers=h).json()
    assert s == {"enabled": False, "pending": True}
    _enable_2fa_from_status(client, h)
    s = client.get("/auth/2fa/status", headers=h).json()
    assert s == {"enabled": True, "pending": False}


def _enable_2fa_from_status(client, headers):
    # setup already called; recover the secret from the DB is not possible via API,
    # so run setup again (still pending) and activate.
    secret = client.post("/auth/2fa/setup", headers=headers).json()["secret"]
    client.post("/auth/2fa/activate", json={"code": pyotp.TOTP(secret).now()}, headers=headers)


def test_activate_rejects_bad_code(client, auth_headers):
    h = auth_headers("Sales")
    client.post("/auth/2fa/setup", headers=h)
    assert client.post("/auth/2fa/activate", json={"code": "000000"}, headers=h).status_code == 401


def test_setup_conflicts_once_active(client, auth_headers):
    h = auth_headers("Sales")
    _enable_2fa(client, h)
    assert client.post("/auth/2fa/setup", headers=h).status_code == 409


# ------------------------------------------------------------------- two-step login


def test_login_with_2fa_needs_second_step(client, auth_headers):
    secret = _enable_2fa(client, auth_headers("Sales"))

    r = _login(client, "Sales")
    assert r.status_code == 200
    body = r.json()
    assert body["totp_required"] is True
    assert body["token"] == ""
    assert body["challenge"]

    ok = client.post(
        "/auth/login/totp",
        json={"challenge": body["challenge"], "code": pyotp.TOTP(secret).now()},
    )
    assert ok.status_code == 200
    token = ok.json()["token"]
    assert token
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["totp_enabled"] is True


def test_login_totp_bad_code_401_and_consumes_challenge(client, auth_headers):
    _enable_2fa(client, auth_headers("Sales"))
    challenge = _login(client, "Sales").json()["challenge"]
    assert client.post(
        "/auth/login/totp", json={"challenge": challenge, "code": "000000"}
    ).status_code == 401
    # challenge is single-use even on failure
    assert client.post(
        "/auth/login/totp", json={"challenge": challenge, "code": "123456"}
    ).status_code == 401


def test_challenge_expiry(client, auth_headers, conn):
    secret = _enable_2fa(client, auth_headers("Sales"))
    challenge = _login(client, "Sales").json()["challenge"]
    conn.execute(
        "UPDATE totp_challenge SET expires_at = '2000-01-01T00:00:00.000Z' WHERE challenge = ?",
        (challenge,),
    )
    r = client.post(
        "/auth/login/totp", json={"challenge": challenge, "code": pyotp.TOTP(secret).now()}
    )
    assert r.status_code == 401


def test_non_2fa_login_unchanged(client):
    r = _login(client, "Manager")
    assert r.status_code == 200
    assert r.json()["token"] and r.json()["totp_required"] is False


# ------------------------------------------------------------------- disable / recovery


def test_disable_from_own_account(client, auth_headers):
    secret = _enable_2fa(client, auth_headers("Sales"))
    h = {"Authorization": f"Bearer {_two_step_token(client, 'Sales', secret)}"}
    assert client.post(
        "/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=h
    ).status_code == 204
    assert client.get("/auth/2fa/status", headers=h).json()["enabled"] is False
    assert _login(client, "Sales").json()["totp_required"] is False


def _two_step_token(client, role, secret):
    ch = _login(client, role).json()["challenge"]
    return client.post(
        "/auth/login/totp", json={"challenge": ch, "code": pyotp.TOTP(secret).now()}
    ).json()["token"]


def test_admin_clears_locked_out_user(client, auth_headers, users, conn):
    _enable_2fa(client, auth_headers("Sales"))
    sales_id = users["Sales"]

    r = client.put(
        f"/users/{sales_id}", json={"totp_enabled": False}, headers=auth_headers("Owner")
    )
    assert r.status_code == 200
    assert conn.execute(
        "SELECT totp_secret FROM users WHERE id = ?", (sales_id,)
    ).fetchone()["totp_secret"] is None
    assert _login(client, "Sales").json()["totp_required"] is False


def test_admin_cannot_enable_2fa_via_users(client, auth_headers, users):
    r = client.put(
        f"/users/{users['Sales']}", json={"totp_enabled": True}, headers=auth_headers("Owner")
    )
    assert r.status_code == 422


def test_secret_is_encrypted_at_rest(client, auth_headers, users, conn):
    secret = _enable_2fa(client, auth_headers("Sales"))
    stored = conn.execute(
        "SELECT totp_secret FROM users WHERE id = ?", (users["Sales"],)
    ).fetchone()["totp_secret"]
    assert stored and stored != secret          # not plaintext
    assert decrypt(stored) == secret            # round-trips via Fernet
