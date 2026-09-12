"""Rate Master lookups shared by the Rate Master API and the Daily Sales Entry
snapshot. Buy vs Sell matters: Daily Sales Entry gas rows lock the **Sell** rate
(SDD 9 row 3); Trial Balance Stock Value uses the **Buy** rate (SDD 9 row 6).
"""

from __future__ import annotations

import sqlite3
from datetime import date


def latest_effective_rates(
    conn: sqlite3.Connection, as_of: date | str | None = None
) -> dict[str, sqlite3.Row]:
    """Newest ``rate_master`` row per ``item_key`` with ``effective_date <= as_of``.

    ``as_of`` defaults to today. Returned rows expose ``buy_rate`` and ``sell_rate``.

    Ties on ``effective_date`` are broken by the newest ``id``, so a correction
    entered for a date that already has a rate wins deterministically. The table
    is append-only, so same-date corrections are a normal case (2026-09-11: the
    seeded oil rates were placeholders and were corrected in place this way) -
    without the tie-break the query returns both rows and silently keeps
    whichever SQLite happened to emit last.
    """
    if isinstance(as_of, date):
        as_of_str = as_of.isoformat()
    else:
        as_of_str = as_of or date.today().isoformat()
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT r.*, ROW_NUMBER() OVER (
                PARTITION BY item_key ORDER BY effective_date DESC, id DESC
            ) AS _rn
            FROM rate_master r
            WHERE effective_date <= ?
        ) WHERE _rn = 1
        """,
        (as_of_str,),
    ).fetchall()
    return {row["item_key"]: row for row in rows}
