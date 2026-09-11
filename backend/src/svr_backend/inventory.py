"""Inventory Tracking derivation (SDD 5.10).

``on_hand`` is the tracked stock level. Per shift date, GET /inventory reports:

    closing = on_hand + received_today - sold_today
    status  = "low" when closing <= reorder_level else "ok"

``received_today`` sums that day's ``restock_entry`` rows; ``sold_today`` sums the
oil quantities across that day's ``daily_sales_entry`` rows (live preview - the
real stock decrement is applied at Daily Trial Balance finalization).
"""

from __future__ import annotations

import json
import sqlite3

from svr_backend.calc.amounts import is_blank
from svr_backend.calc.daily_sales_entry import OIL_KEYS
from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction


def _sold_today(conn: sqlite3.Connection, shift_date: str) -> dict[str, float]:
    sold = {k: 0.0 for k in OIL_KEYS}
    for row in conn.execute(
        "SELECT payload FROM daily_sales_entry WHERE shift_date = ?", (shift_date,)
    ):
        payload = json.loads(row["payload"] or "{}")
        for i, oil in enumerate(payload.get("oils") or []):
            if i >= len(OIL_KEYS):
                break
            qty = oil.get("qty")
            try:
                sold[OIL_KEYS[i]] += float(qty) if qty not in (None, "", " ") else 0.0
            except (TypeError, ValueError):
                pass
    return sold


def _received_today(conn: sqlite3.Connection, on_date: str) -> dict[str, float]:
    rows = conn.execute(
        "SELECT item_key, COALESCE(SUM(quantity), 0) q FROM restock_entry "
        "WHERE restock_date = ? GROUP BY item_key",
        (on_date,),
    ).fetchall()
    return {r["item_key"]: r["q"] for r in rows}


def stock_levels(conn: sqlite3.Connection, as_of: str) -> list[dict]:
    sold = _sold_today(conn, as_of)
    received = _received_today(conn, as_of)
    out = []
    for item in conn.execute("SELECT * FROM inventory_item ORDER BY item_key"):
        key = item["item_key"]
        rcv = round(received.get(key, 0.0), 4)
        sld = round(sold.get(key, 0.0), 4)
        closing = round(item["on_hand"] + rcv - sld, 4)
        out.append(
            {
                "item_key": key,
                "item_label": item["item_label"],
                "unit": item["unit"],
                "opening_stock": item["on_hand"],
                "received_today": rcv,
                "sold_today": sld,
                "closing_stock": closing,
                "reorder_level": item["reorder_level"],
                "status": "low" if closing <= item["reorder_level"] else "ok",
            }
        )
    return out


def on_hand_map(conn: sqlite3.Connection) -> dict[str, float]:
    """Current tracked stock per oil key - used as the Daily Sales Entry opening."""
    return {
        r["item_key"]: r["on_hand"]
        for r in conn.execute("SELECT item_key, on_hand FROM inventory_item")
    }


def sync_from_daily_sales(
    conn: sqlite3.Connection, before_date: str, actor: str
) -> dict[str, dict]:
    """Set each oil item's tracked on_hand to the most recent real Closing Stock
    recorded for it, from any Daily Sales Entry before ``before_date`` (2026-09-11
    "Print & Sync" feature).

    Oil sales are handled by only one submitter on a given day (confirmed
    2026-09-11) - the *other* pump's entry that same day just carries Opening
    Stock through unchanged (qty blank), so it's not a real transaction to sync
    from. Per oil item, independently, this walks backward from the day before
    ``before_date`` (across either pump) until it finds a row where that item's
    Quantity was actually entered, and takes its computed Closing Stock - the
    same gap-skip-back principle already used for gas Last Shift Reading.

    A "set", not an increment: safe to re-run for the same day, and safe if a
    Manager has since corrected on_hand by hand in Inventory Tracking directly
    (this only overwrites it again on the next explicit sync click). Returns
    ``{item_key: {"from": <old on_hand>, "to": <new on_hand>, "source_date":
    <where it came from>}}`` - only for items that had something to sync from.
    """
    rows = conn.execute(
        "SELECT shift_date, payload, result FROM daily_sales_entry "
        "WHERE shift_date < ? ORDER BY shift_date DESC, id DESC",
        (before_date,),
    ).fetchall()

    found: dict[str, dict] = {}
    remaining = set(OIL_KEYS)
    for row in rows:
        if not remaining:
            break
        payload = json.loads(row["payload"] or "{}")
        result = json.loads(row["result"] or "{}")
        oils_in = payload.get("oils") or []
        oils_out = result.get("oils") or []
        for key in list(remaining):
            idx = OIL_KEYS.index(key)
            qty = oils_in[idx].get("qty") if idx < len(oils_in) else None
            if is_blank(qty):
                continue
            closing = oils_out[idx].get("closing") if idx < len(oils_out) else None
            if closing is None:
                continue
            found[key] = {"closing": closing, "source_date": row["shift_date"]}
            remaining.discard(key)

    if not found:
        return {}

    summary: dict[str, dict] = {}
    with transaction(conn):
        for key, info in found.items():
            old = conn.execute(
                "SELECT on_hand FROM inventory_item WHERE item_key = ?", (key,)
            ).fetchone()
            old_on_hand = old["on_hand"] if old else None
            conn.execute(
                "UPDATE inventory_item SET on_hand = ?, last_updated_by = ?, "
                "last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE item_key = ?",
                (info["closing"], actor, key),
            )
            record_write(
                conn, table="inventory_item", record_id=key, action="update", actor=actor,
                old={"on_hand": old_on_hand},
                new={"on_hand": info["closing"], "source_date": info["source_date"]},
            )
            summary[key] = {
                "from": old_on_hand, "to": info["closing"], "source_date": info["source_date"],
            }
    return summary
