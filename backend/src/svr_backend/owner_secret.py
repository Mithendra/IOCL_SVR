"""The Owner's secret passphrase, shared by every form that is gated on it.

One passphrase, one place. It began life inside ``api/owner_reset.py`` for
re-basing a pump's meter; the client then asked for the Inventory Tracking
Master to be gated the same way (2026-09-25: "Inventory Tracking Master should
have Secert Password to make an update only owner role"). Copying the check into
a second router would have meant two ways to be wrong about who may write, so it
lives here and both import it.

Argon2-hashed in ``owner_secret``, never defaulted by a migration: a passphrase
seeded in SQL would be a password every install shares and nobody chose.
"""

from __future__ import annotations

import sqlite3

from fastapi import HTTPException, status

from svr_backend.core.security import verify_password

MIN_PASSPHRASE = 4


def stored_hash(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT passphrase_hash FROM owner_secret WHERE id = 1").fetchone()
    return row["passphrase_hash"] if row else None


def check_passphrase(conn: sqlite3.Connection, passphrase: str | None) -> None:
    """Refuse unless the passphrase matches. Never says which part was wrong."""
    stored = stored_hash(conn)
    if stored is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No Owner passphrase has been set yet. Set one on the Daily Sales Entry "
            "form (Owner reset) first.",
        )
    if not passphrase or not verify_password(passphrase, stored):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong passphrase.")
