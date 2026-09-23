"""Owner-only reset of a pump's carried Last Shift Reading, behind a passphrase.

Client, 2026-09-23: "Define a small owner form where you can reset the last
reading for both pumps. To open that form you need to have a secret password."

Two gates, on purpose. Being an Owner opens the form; the passphrase is a second,
deliberate step in front of the one number the whole station is measured from. A
wrong reset does not spoil a single form - it re-bases every later day's
consumption, quietly. The passphrase is friction against an Owner's session left
open on the counter, not a claim of cryptographic defence.

A reset never edits a saved day. It records "as of this date, this pump's meter
reads X", and the carry-forward prefers whichever is later - that baseline or the
last saved entry. Rewriting a signed-off day to fix today is how an audit trail
stops meaning anything.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.security import hash_password, verify_password
from svr_backend.core.session import Principal

router = APIRouter(prefix="/owner-reset", tags=["owner-reset"])

# Four, not eight. The client chose a short PIN (2026-09-23) and for what this
# gate actually defends that is a defensible trade: it stands between an Owner's
# unattended session and one number, on a machine behind the station counter -
# not between the internet and an account. A long passphrase nobody can recall
# gets written on the monitor, which is worse than a PIN.
#
# It is still hashed with Argon2 and never stored or logged in the clear, and it
# is asked for again on Apply, not just to open the form.
MIN_PASSPHRASE = 4


def _stored_hash(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT passphrase_hash FROM owner_secret WHERE id = 1").fetchone()
    return row["passphrase_hash"] if row else None


def _check_passphrase(conn: sqlite3.Connection, passphrase: str) -> None:
    """Refuse unless the passphrase matches. Never says which part was wrong."""
    stored = _stored_hash(conn)
    if stored is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No reset passphrase has been set yet. Set one first.",
        )
    if not verify_password(passphrase, stored):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong passphrase.")


class SecretSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_passphrase: str = Field(min_length=MIN_PASSPHRASE)
    # Required once one exists - so a session left open cannot silently replace
    # the passphrase and hand the next person a working key.
    current_passphrase: str | None = None


class Unlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passphrase: str


class ResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passphrase: str
    pump_serial: str
    effective_date: str
    hs_last: float | None = None
    ms_last: float | None = None
    # Required, and deliberately not defaulted. A reset with no reason is a
    # mystery to whoever finds it in six months.
    reason: str = Field(min_length=3)


@router.get("/status")
def status_(
    _: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Whether a passphrase exists yet. Never returns the hash itself."""
    return {"configured": _stored_hash(conn) is not None, "min_length": MIN_PASSPHRASE}


@router.post("/secret")
def set_secret(
    body: SecretSet,
    principal: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Set the passphrase, or change it by supplying the current one.

    Nothing ships a default: a default passphrase committed to a public
    repository is not a passphrase. The first Owner to open the form sets it.
    """
    existing = _stored_hash(conn)
    if existing is not None:
        if not body.current_passphrase:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A passphrase is already set - supply the current one to change it.",
            )
        if not verify_password(body.current_passphrase, existing):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong passphrase.")

    with transaction(conn):
        conn.execute(
            """
            INSERT INTO owner_secret (id, passphrase_hash, last_updated_by)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                passphrase_hash = excluded.passphrase_hash,
                last_updated_by = excluded.last_updated_by,
                last_updated_at = datetime('now')
            """,
            (hash_password(body.new_passphrase), principal.login_name),
        )
        # The hash is never audited - only the fact that it changed.
        record_write(
            conn, table="owner_secret", record_id=1,
            action="update" if existing else "create",
            actor=principal.login_name, new={"passphrase": "changed"},
        )
    return {"configured": True}


@router.post("/unlock")
def unlock(
    body: Unlock,
    _: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Open the form. The passphrase is required again on the reset itself, so a
    stolen 'unlocked' state on a screen is not by itself enough to change a
    reading."""
    _check_passphrase(conn, body.passphrase)
    return {"ok": True}


@router.get("/baselines")
def baselines(
    pump_serial: str | None = None,
    _: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """Every reset on file, newest first - so a surprising figure can be traced
    to the reset that caused it."""
    sql = "SELECT * FROM reading_baseline"
    args: tuple = ()
    if pump_serial:
        sql += " WHERE pump_serial = ?"
        args = (pump_serial,)
    sql += " ORDER BY effective_date DESC, id DESC LIMIT 50"
    return [dict(r) for r in conn.execute(sql, args)]


@router.post("", status_code=status.HTTP_201_CREATED)
def reset_reading(
    body: ResetIn,
    principal: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Record a corrected Last Shift Reading for a pump, as of a date."""
    _check_passphrase(conn, body.passphrase)
    if body.hs_last is None and body.ms_last is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Give at least one reading - Diesel (HS) or Petrol (MS).",
        )
    for label, v in (("Diesel (HS)", body.hs_last), ("Petrol (MS)", body.ms_last)):
        if v is not None and v < 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"{label} reading cannot be negative."
            )

    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO reading_baseline
                (pump_serial, effective_date, hs_last, ms_last, reason, last_updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                body.pump_serial, body.effective_date, body.hs_last, body.ms_last,
                body.reason.strip(), principal.login_name,
            ),
        )
        new_id = cur.lastrowid
        record_write(
            conn, table="reading_baseline", record_id=new_id, action="create",
            actor=principal.login_name,
            new={
                "pump_serial": body.pump_serial,
                "effective_date": body.effective_date,
                "hs_last": body.hs_last,
                "ms_last": body.ms_last,
                "reason": body.reason.strip(),
            },
        )
    return {"id": new_id, "pump_serial": body.pump_serial,
            "effective_date": body.effective_date,
            "hs_last": body.hs_last, "ms_last": body.ms_last}
