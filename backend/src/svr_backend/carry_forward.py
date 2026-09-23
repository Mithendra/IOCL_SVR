"""23:59 IST (Asia/Kolkata) carry-forward of each pump's Current Reading into the
next day's Last Shift Reading (SDD 7.7).

Two policies are required and implemented here:

* **Gap-day skip-back** - carry from the most recent day that actually has a
  reading, never literally "yesterday". Falls out naturally from ordering entries
  by ``shift_date`` and taking the first non-null.
* **Catch-up on startup** - if the PC was off at 23:59, :func:`catch_up_on_startup`
  replays every shift date that has entries but no recorded run.

Post-rollover corrections are *not* auto-propagated (confirmed policy, SDD 7.7): a
next-day ``*_last`` that is already set is left alone.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

JOB_NAME = "carry_forward"


@dataclass(frozen=True)
class CarriedReadings:
    hs: float | None
    ms: float | None
    source_date: str | None


def carried_last_readings(
    conn: sqlite3.Connection, pump_serial: str, before_date: str
) -> CarriedReadings:
    """Readings to seed a new entry for ``before_date`` on ``pump_serial``.

    The most recent prior entry (``shift_date < before_date``) that has a Current
    Reading. Gap days - which have no entry, or an entry with null readings - are
    skipped by the ``IS NOT NULL`` filter and the ``ORDER BY ... DESC LIMIT 1``.
    """
    row = conn.execute(
        """
        SELECT shift_date, hs_current, ms_current
        FROM daily_sales_entry
        WHERE pump_serial = ?
          AND shift_date < ?
          AND (hs_current IS NOT NULL OR ms_current IS NOT NULL)
        ORDER BY shift_date DESC, id DESC
        LIMIT 1
        """,
        (pump_serial, before_date),
    ).fetchone()

    # An Owner reset (migration 0036) says "as of this date the meter reads X".
    # It competes with the last saved entry and the LATER one wins; on a tie the
    # baseline wins, because it was entered deliberately to correct that very day.
    #
    # The baseline never edits the saved entry. Rewriting a day the station has
    # already signed off, to fix today, is how an audit trail stops meaning
    # anything - so the correction is recorded beside history, not on top of it.
    base = conn.execute(
        """
        SELECT effective_date, hs_last, ms_last
        FROM reading_baseline
        WHERE pump_serial = ? AND effective_date < ?
        ORDER BY effective_date DESC, id DESC
        LIMIT 1
        """,
        (pump_serial, before_date),
    ).fetchone()

    if base is not None and (row is None or base["effective_date"] >= row["shift_date"]):
        return CarriedReadings(
            hs=base["hs_last"], ms=base["ms_last"], source_date=base["effective_date"]
        )
    if row is None:
        return CarriedReadings(hs=None, ms=None, source_date=None)
    return CarriedReadings(
        hs=row["hs_current"], ms=row["ms_current"], source_date=row["shift_date"]
    )


def run_carry_forward(conn: sqlite3.Connection, for_date: str) -> dict:
    """Roll ``for_date``'s Current Readings into ``for_date + 1``.

    Idempotent. Records the run in ``scheduler_run`` and back-fills any already-
    existing next-day entry whose ``*_last`` is still null.
    """
    next_date = (date.fromisoformat(for_date) + timedelta(days=1)).isoformat()
    pumps = [
        r["pump_serial"]
        for r in conn.execute(
            "SELECT DISTINCT pump_serial FROM daily_sales_entry WHERE shift_date <= ?",
            (for_date,),
        )
    ]
    filled = []
    for pump in pumps:
        carried = carried_last_readings(conn, pump, next_date)
        if carried.source_date is None:
            continue
        cur = conn.execute(
            """
            UPDATE daily_sales_entry
            SET hs_last = COALESCE(hs_last, ?),
                ms_last = COALESCE(ms_last, ?)
            WHERE pump_serial = ? AND shift_date = ?
              AND (hs_last IS NULL OR ms_last IS NULL)
            """,
            (carried.hs, carried.ms, pump, next_date),
        )
        if cur.rowcount:
            filled.append(pump)
    conn.execute(
        "INSERT OR IGNORE INTO scheduler_run (job_name, for_date) VALUES (?, ?)",
        (JOB_NAME, for_date),
    )
    return {"for_date": for_date, "next_date": next_date, "pumps": pumps, "backfilled": filled}


def catch_up_on_startup(conn: sqlite3.Connection) -> list[dict]:
    """Replay carry-forward for every shift date with entries but no recorded run."""
    dates = [
        r["shift_date"]
        for r in conn.execute(
            """
            SELECT DISTINCT shift_date FROM daily_sales_entry
            WHERE shift_date NOT IN (SELECT for_date FROM scheduler_run WHERE job_name = ?)
            ORDER BY shift_date
            """,
            (JOB_NAME,),
        )
    ]
    return [run_carry_forward(conn, d) for d in dates]
