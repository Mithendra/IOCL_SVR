"""Two-factor auth (TOTP) helpers.

Enrollment is per-user and self-service: /auth/2fa/setup stores a Fernet-encrypted
secret with ``totp_enabled = 0``; /auth/2fa/activate verifies a code and flips it
on. At login, a user with 2FA active gets a short-lived *challenge* (this module),
not a session; /auth/login/totp exchanges the challenge + a valid code for a
session. An Owner/Manager can clear a locked-out user's 2FA from Manage Users.
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

import pyotp

from svr_backend.core.config import get_settings

_ISO = "%Y-%m-%dT%H:%M:%S.%fZ"


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, login_name: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=login_name, issuer_name=get_settings().totp_issuer
    )


def verify_code(secret: str | None, code: str | None) -> bool:
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    # valid_window=1 tolerates one 30s step of clock skew each way.
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def _now() -> datetime:
    return datetime.now(UTC)


def issue_challenge(conn: sqlite3.Connection, user_id: int) -> str:
    """Replace any pending challenge for the user with a fresh one."""
    conn.execute("DELETE FROM totp_challenge WHERE user_id = ?", (user_id,))
    challenge = secrets.token_urlsafe(32)
    expires = _now() + timedelta(minutes=get_settings().totp_challenge_ttl_minutes)
    conn.execute(
        "INSERT INTO totp_challenge (challenge, user_id, expires_at) VALUES (?, ?, ?)",
        (challenge, user_id, expires.strftime(_ISO)),
    )
    return challenge


def consume_challenge(conn: sqlite3.Connection, challenge: str | None) -> int | None:
    """Return the user_id for a valid, unexpired challenge and delete it. None otherwise."""
    conn.execute("DELETE FROM totp_challenge WHERE expires_at < ?", (_now().strftime(_ISO),))
    if not challenge:
        return None
    row = conn.execute(
        "SELECT user_id, expires_at FROM totp_challenge WHERE challenge = ?", (challenge,)
    ).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM totp_challenge WHERE challenge = ?", (challenge,))
    try:
        expires = datetime.strptime(row["expires_at"], _ISO).replace(tzinfo=UTC)
    except ValueError:
        return None
    return row["user_id"] if expires >= _now() else None
