"""The Oil Sale(s) item list, as data.

The seven rows used to be a Python tuple (``OIL_ITEMS`` in
``calc/daily_sales_entry.py``), so adding an eighth meant a code change across six
modules plus a release. The list is the station's, not the build's, so it lives in
the ``oil_item`` table (migration 0023) and the Owner edits it.

Two rules carry over from the constant and are the whole reason this is safe:

* **``item_key`` identifies a product, not a row position.** Relabelling a row or
  moving it keeps its Rate Master history and its tracked Inventory stock.
* **A saved row carries its own label**, and ``oil_item_alias`` maps every label
  the station has ever used back to its product. That is what lets a record
  written before the 2026-09-12 relabel still read back as the right item.

Removing an item **deactivates** it. Days already recorded name it in their own
rows; deleting it would leave those pointing at nothing and silently change
historical totals. An inactive item drops off the entry form but still resolves.

``calc/daily_sales_entry.py`` stays pure and label-driven - it never reads the
database. Its constants remain as the fallback for a payload that arrives with no
labels at all (the renderer's stateless ``/calc`` probe).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class OilItem:
    key: str
    label: str
    unit: str
    sort_order: int
    active: bool


def _rows(conn: sqlite3.Connection, *, active_only: bool) -> tuple[OilItem, ...]:
    sql = "SELECT item_key, label, unit, sort_order, active FROM oil_item"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY sort_order, item_key"
    return tuple(
        OilItem(r["item_key"], r["label"], r["unit"], r["sort_order"], bool(r["active"]))
        for r in conn.execute(sql)
    )


def active_items(conn: sqlite3.Connection) -> tuple[OilItem, ...]:
    """What the entry form shows today, in display order."""
    return _rows(conn, active_only=True)


def all_items(conn: sqlite3.Connection) -> tuple[OilItem, ...]:
    """Including retired ones - for reading historical records and for the admin UI."""
    return _rows(conn, active_only=False)


def keys(conn: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(i.key for i in active_items(conn))


def labels(conn: sqlite3.Connection) -> dict[str, str]:
    """key -> current label, for every item including retired ones.

    Retired items are included because a stored record can name one, and it should
    read back under the label it was sold as rather than as a bare key.
    """
    return {i.key: i.label for i in all_items(conn)}


def label_to_key(conn: sqlite3.Connection) -> dict[str, str]:
    """Every label the station has ever used -> the product it names."""
    rows = conn.execute("SELECT label, item_key FROM oil_item_alias")
    return {r["label"]: r["item_key"] for r in rows}


def resolve_key(conn: sqlite3.Connection, row: dict, index: int) -> str | None:
    """Which item a stored/submitted row actually is.

    By the row's own label when it has one - order-proof, and the only thing that
    survives a row-order change. Position is the fallback, and is only correct for
    a payload written by the current form.
    """
    key = label_to_key(conn).get(str(row.get("label") or "").strip())
    if key is not None:
        return key
    ks = keys(conn)
    return ks[index] if index < len(ks) else None


def oils_by_key(conn: sqlite3.Connection, oils: list[dict] | None) -> dict[str, dict]:
    """``payload["oils"]`` / ``result["oils"]`` keyed by item, not by position."""
    by_label = label_to_key(conn)
    ks = keys(conn)
    out: dict[str, dict] = {}
    for i, row in enumerate(oils or []):
        r = row or {}
        key = by_label.get(str(r.get("label") or "").strip())
        if key is None:
            key = ks[i] if i < len(ks) else None
        if key is not None and key not in out:
            out[key] = r
    return out


def next_key(conn: sqlite3.Connection) -> str:
    """The next free ``oilN``.

    Numbered past the highest ever used, including retired items, so a key is
    never reused for a different product - that would silently graft one
    product's rate history and stock onto another.
    """
    highest = 0
    for r in conn.execute("SELECT item_key FROM oil_item"):
        k = str(r["item_key"])
        if k.startswith("oil") and k[3:].isdigit():
            highest = max(highest, int(k[3:]))
    return f"oil{highest + 1}"


def next_sort_order(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(sort_order), 0) AS m FROM oil_item").fetchone()
    return int(row["m"]) + 10
