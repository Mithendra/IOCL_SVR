"""Manage Users (SDD 5.3 / 13.1). Manager + Owner only (SDD 4.2).

A created user has no password - they set one through the emailed reset link
(email integration deferred, so POST /users/{id}/reset-password returns 501). No
endpoint here ever returns or accepts a plaintext password.

Guards: the last active Owner cannot be deleted, demoted, or disabled; a user
cannot delete their own account.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.email import echo_link_in_response
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.reset import issue_token, reset_link, send_reset_email
from svr_backend.users import (
    count_active_owners,
    derive_login_name,
    public_user,
    unique_login_name,
)

router = APIRouter(prefix="/users", tags=["users"])

ROLES = ("Sales", "Manager", "Owner")
STATUSES = ("Active", "Disabled")


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1)
    email: str
    cell_phone: str | None = None
    role: str
    status: str = "Active"
    login_name: str | None = None  # optional manual override


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    cell_phone: str | None = None
    role: str | None = None
    status: str | None = None
    # An admin may only CLEAR 2FA here (lockout recovery). Users turn it ON from
    # their own Security page - passing True is a 422.
    totp_enabled: bool | None = None


def _get_or_404(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return row


def _validate_enum(role: str | None, status_val: str | None) -> None:
    if role is not None and role not in ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"role must be one of {ROLES}")
    if status_val is not None and status_val not in STATUSES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"status must be one of {STATUSES}"
        )


@router.get("")
def list_users(
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    rows = conn.execute("SELECT * FROM users ORDER BY role, login_name").fetchall()
    return [public_user(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    _validate_enum(body.role, body.status)
    base = body.login_name or derive_login_name(body.full_name)
    login_name = unique_login_name(conn, base)

    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO users
                (login_name, full_name, email, cell_phone, role, status, totp_enabled,
                 password_hash, last_updated_by)
            VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)
            """,
            (
                login_name, body.full_name, body.email, body.cell_phone,
                body.role, body.status, principal.login_name,
            ),
        )
        record_write(
            conn, table="users", record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"login_name": login_name, "role": body.role, "status": body.status},
        )
    return public_user(_get_or_404(conn, cur.lastrowid))


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = _get_or_404(conn, user_id)
    _validate_enum(body.role, body.status)

    new_role = body.role if body.role is not None else row["role"]
    new_status = body.status if body.status is not None else row["status"]
    demotes_or_disables_owner = row["role"] == "Owner" and (
        new_role != "Owner" or new_status != "Active"
    )
    if demotes_or_disables_owner and count_active_owners(conn, exclude_id=user_id) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot demote or disable the last active Owner",
        )

    if body.totp_enabled is True:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A user enables 2FA from their own Security page; an admin can only clear it here.",
        )

    fields = {
        "full_name": body.full_name,
        "email": body.email if body.email is not None else None,
        "cell_phone": body.cell_phone,
        "role": body.role,
        "status": body.status,
    }
    updates = {k: v for k, v in fields.items() if v is not None}
    if body.totp_enabled is False:  # admin clears a locked-out user's 2FA
        updates["totp_enabled"] = 0
        updates["totp_secret"] = None
    if not updates:
        return public_user(row)

    set_sql = ", ".join(f"{k} = ?" for k in updates)
    with transaction(conn):
        conn.execute(
            f"UPDATE users SET {set_sql}, last_updated_by = ?, "
            f"last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (*updates.values(), principal.login_name, user_id),
        )
        audited = [k for k in updates if k != "totp_secret"]  # never log the secret
        record_write(
            conn, table="users", record_id=user_id, action="update",
            actor=principal.login_name,
            old={k: row[k] for k in audited},
            new={k: updates[k] for k in audited},
        )
    return public_user(_get_or_404(conn, user_id))


@router.post("/{user_id}/reset-password", status_code=status.HTTP_202_ACCEPTED)
def reset_password(
    user_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Admin-initiated reset: emails the same single-use link as self-service
    (SDD 13.1). Covers a brand-new user setting their first password and an
    existing user's reset. Never sets or returns a password value."""
    row = _get_or_404(conn, user_id)
    with transaction(conn):
        token = issue_token(conn, user_id, created_by=principal.login_name)
        record_write(
            conn, table="password_reset_token", record_id=token[:12], action="create",
            actor=principal.login_name,
            new={"user_id": user_id, "login_name": row["login_name"], "admin_initiated": True},
        )
    send_reset_email(row["email"], token, admin_initiated=True)
    out = {"detail": f"Password reset link emailed to {row['login_name']}."}
    if echo_link_in_response():
        out["dev_reset_link"] = reset_link(token)
    return out


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = _get_or_404(conn, user_id)
    if user_id == principal.user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot delete your own account")
    if row["role"] == "Owner" and count_active_owners(conn, exclude_id=user_id) == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot delete the last active Owner")

    with transaction(conn):
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        record_write(
            conn, table="users", record_id=user_id, action="delete",
            actor=principal.login_name,
            old={"login_name": row["login_name"], "role": row["role"]},
        )
