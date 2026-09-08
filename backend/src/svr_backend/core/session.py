"""Session issue / lookup. A session is authenticated once at login (SDD 13.1);
every subsequent request carries its token and the backend re-resolves the role.
"""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from svr_backend.core.config import get_settings
from svr_backend.core.security import verify_password

_ISO = "%Y-%m-%dT%H:%M:%S.%fZ"


@dataclass(frozen=True)
class Principal:
    user_id: int
    login_name: str
    full_name: str
    role: str  # 'Sales' | 'Manager' | 'Owner'


def _now() -> datetime:
    return datetime.now(UTC)


def check_password(
    conn: sqlite3.Connection, login_name: str, password: str
) -> sqlite3.Row | None:
    """The password step alone. Returns the user row (incl. totp_* columns) or None.

    No session is created - callers decide whether to issue one directly
    (``issue_session``) or to demand a second factor first.
    """
    row = conn.execute(
        "SELECT id, password_hash, status, role, full_name, totp_enabled, totp_secret "
        "FROM users WHERE login_name = ?",
        (login_name,),
    ).fetchone()
    if row is None or row["status"] != "Active":
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return row


def issue_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(minutes=get_settings().session_ttl_minutes)
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires.strftime(_ISO)),
    )
    return token


def login(conn: sqlite3.Connection, login_name: str, password: str) -> str | None:
    """Password-only login: a fresh session token, or ``None`` if rejected.

    Does NOT consider 2FA - the /auth/login endpoint layers that on. Kept for
    callers/tests that just need "valid password -> session".
    """
    row = check_password(conn, login_name, password)
    return issue_session(conn, row["id"]) if row is not None else None


def resolve(conn: sqlite3.Connection, token: str | None) -> Principal | None:
    if not token:
        return None
    row = conn.execute(
        """
        SELECT s.expires_at, u.id, u.login_name, u.full_name, u.role, u.status
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()
    if row is None or row["status"] != "Active":
        return None
    try:
        expires = datetime.strptime(row["expires_at"], _ISO).replace(tzinfo=UTC)
    except ValueError:
        return None
    if expires < _now():
        return None
    return Principal(
        user_id=row["id"],
        login_name=row["login_name"],
        full_name=row["full_name"],
        role=row["role"],
    )


def logout(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
