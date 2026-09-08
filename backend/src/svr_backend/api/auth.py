"""Authentication endpoints (SDD 13.1), including the self-service password-reset
flow: request a single-use emailed link, then set a new password with the token.
The password value is never displayed, stored, or transmitted - only its argon2
hash is persisted.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from svr_backend import totp
from svr_backend.core.audit import record_write
from svr_backend.core.config import get_settings
from svr_backend.core.crypto import decrypt, encrypt
from svr_backend.core.db import transaction
from svr_backend.core.email import echo_link_in_response
from svr_backend.core.rbac import _token_from_headers, get_db, get_principal
from svr_backend.core.security import hash_password
from svr_backend.core.session import Principal, check_password, issue_session
from svr_backend.core.session import logout as do_logout
from svr_backend.reset import consume_token, issue_token, reset_link, send_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    login_name: str
    password: str


class LoginResponse(BaseModel):
    token: str = ""
    role: str
    full_name: str
    totp_required: bool = False
    challenge: str | None = None


class TotpLoginRequest(BaseModel):
    challenge: str
    code: str


class TotpCodeRequest(BaseModel):
    code: str


class MeResponse(BaseModel):
    user_id: int
    login_name: str
    full_name: str
    role: str
    totp_enabled: bool = False


_BAD_CREDS = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid login name or password")
_BAD_CODE = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, conn: sqlite3.Connection = Depends(get_db)) -> LoginResponse:
    row = check_password(conn, body.login_name, body.password)
    if row is None:
        raise _BAD_CREDS
    if row["totp_enabled"] and row["totp_secret"]:
        conn.execute("BEGIN")
        try:
            challenge = totp.issue_challenge(conn, row["id"])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return LoginResponse(
            role=row["role"], full_name=row["full_name"], totp_required=True, challenge=challenge
        )
    token = issue_session(conn, row["id"])
    return LoginResponse(token=token, role=row["role"], full_name=row["full_name"])


@router.post("/login/totp", response_model=LoginResponse)
def login_totp(body: TotpLoginRequest, conn: sqlite3.Connection = Depends(get_db)) -> LoginResponse:
    """Second step for a 2FA account: exchange the challenge + a valid code for a session."""
    conn.execute("BEGIN")
    try:
        user_id = totp.consume_challenge(conn, body.challenge)
        if user_id is None:
            conn.execute("ROLLBACK")
            raise _BAD_CODE
        row = conn.execute(
            "SELECT role, full_name, totp_secret FROM users WHERE id = ? AND status = 'Active'",
            (user_id,),
        ).fetchone()
        if row is None or not totp.verify_code(decrypt(row["totp_secret"]), body.code):
            conn.execute("ROLLBACK")
            raise _BAD_CODE
        token = issue_session(conn, user_id)
        conn.execute("COMMIT")
    except HTTPException:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return LoginResponse(token=token, role=row["role"], full_name=row["full_name"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: str | None = Depends(_token_from_headers),
    conn: sqlite3.Connection = Depends(get_db),
    _: Principal = Depends(get_principal),
) -> None:
    if token:
        do_logout(conn, token)


@router.get("/me", response_model=MeResponse)
def me(
    principal: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> MeResponse:
    row = conn.execute(
        "SELECT totp_enabled FROM users WHERE id = ?", (principal.user_id,)
    ).fetchone()
    return MeResponse(
        user_id=principal.user_id,
        login_name=principal.login_name,
        full_name=principal.full_name,
        role=principal.role,
        totp_enabled=bool(row and row["totp_enabled"]),
    )


# ------------------------------------------------------------------ 2FA self-service


@router.get("/2fa/status")
def totp_status(
    principal: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute(
        "SELECT totp_enabled, totp_secret FROM users WHERE id = ?", (principal.user_id,)
    ).fetchone()
    enabled = bool(row and row["totp_enabled"])
    return {"enabled": enabled, "pending": bool(row and row["totp_secret"]) and not enabled}


@router.post("/2fa/setup")
def totp_setup(
    principal: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Generate a new secret (stored, not yet active). Call /2fa/activate with a code."""
    row = conn.execute(
        "SELECT totp_enabled FROM users WHERE id = ?", (principal.user_id,)
    ).fetchone()
    if row and row["totp_enabled"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "2FA is already active; disable it first")
    secret = totp.new_secret()
    with transaction(conn):
        conn.execute(
            "UPDATE users SET totp_secret = ?, totp_enabled = 0, "
            "last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE id = ?",
            (encrypt(secret), principal.login_name, principal.user_id),
        )
    return {"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, principal.login_name)}


@router.post("/2fa/activate", status_code=status.HTTP_204_NO_CONTENT)
def totp_activate(
    body: TotpCodeRequest,
    principal: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute(
        "SELECT totp_secret, totp_enabled FROM users WHERE id = ?", (principal.user_id,)
    ).fetchone()
    if not row or not row["totp_secret"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Run /auth/2fa/setup first")
    if not totp.verify_code(decrypt(row["totp_secret"]), body.code):
        raise _BAD_CODE
    with transaction(conn):
        conn.execute(
            "UPDATE users SET totp_enabled = 1, "
            "last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE id = ?",
            (principal.login_name, principal.user_id),
        )
        record_write(
            conn, table="users", record_id=principal.user_id, action="update",
            actor=principal.login_name, new={"totp_enabled": True},
        )


@router.post("/2fa/disable", status_code=status.HTTP_204_NO_CONTENT)
def totp_disable(
    body: TotpCodeRequest,
    principal: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    """Turn 2FA off from your own account (needs a current code). An Owner/Manager
    can also clear it for a locked-out user from Manage Users."""
    row = conn.execute(
        "SELECT totp_secret, totp_enabled FROM users WHERE id = ?", (principal.user_id,)
    ).fetchone()
    if not row or not row["totp_enabled"]:
        return
    if not totp.verify_code(decrypt(row["totp_secret"]), body.code):
        raise _BAD_CODE
    with transaction(conn):
        conn.execute(
            "UPDATE users SET totp_enabled = 0, totp_secret = NULL, "
            "last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE id = ?",
            (principal.login_name, principal.user_id),
        )
        record_write(
            conn, table="users", record_id=principal.user_id, action="update",
            actor=principal.login_name, new={"totp_enabled": False},
        )


class ResetRequest(BaseModel):
    identifier: str  # login name or email


class ResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=1)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def password_reset_request(
    body: ResetRequest, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Always returns 202 (no account enumeration). Emails a link only if the
    identifier matches an active account. Dev email backends echo the link back."""
    ident = body.identifier.strip()
    row = conn.execute(
        "SELECT id, email, status FROM users WHERE login_name = ? OR email = ?",
        (ident, ident),
    ).fetchone()
    out: dict = {"detail": "If that account exists, a reset link has been emailed."}
    if row is not None and row["status"] == "Active":
        conn.execute("BEGIN")
        try:
            token = issue_token(conn, row["id"])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        send_reset_email(row["email"], token, admin_initiated=False)
        if echo_link_in_response():
            out["dev_reset_link"] = reset_link(token)
    return out


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
def password_reset_confirm(
    body: ResetConfirm, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    if len(body.new_password) < get_settings().min_password_length:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Password must be at least {get_settings().min_password_length} characters",
        )
    conn.execute("BEGIN")
    try:
        user_id = consume_token(conn, body.token)
        if user_id is None:
            conn.execute("ROLLBACK")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset link")
        conn.execute(
            "UPDATE users SET password_hash = ?, last_updated_by = 'password-reset', "
            "last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (hash_password(body.new_password), user_id),
        )
        # Any existing sessions for this user are now stale.
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("COMMIT")
    except HTTPException:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"detail": "Password updated. You can now sign in with the new password."}
