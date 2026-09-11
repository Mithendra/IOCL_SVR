"""Daily Sales Summary derivation (SDD 5.23-5.25 / 10).

Combines the two per-pump ``daily_sales_entry`` submissions for a shift date into
one record. The combined per-line totals are computed here from each entry's cached
``result`` JSON and never stored, so they cannot drift from the entries. The
``daily_sales_summary`` row only holds the human verification state + status.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from svr_backend.calc.daily_sales_entry import OIL_KEYS, OIL_LABELS

# Explicit serial -> side map (client-confirmed 2026-09-11), not a substring guess.
# A previous version inferred the side from "OFF"/"RDF" inside the serial itself,
# which broke the moment a serial's own suffix stopped matching its real-world
# side (exactly what prompted this station's actual two serials below).
PUMP_SIDE: dict[str, str] = {
    "12BC4523V-RD": "road",
    "11CC2012V-OFF": "office",
}


def classify_pump(pump_serial: str) -> str | None:
    """'office' | 'road' | None, from the station's fixed two pump serials."""
    return PUMP_SIDE.get((pump_serial or "").strip())


@dataclass
class PumpSide:
    entry_id: int | None = None
    pump_serial: str | None = None
    submitted_by: str | None = None
    entry_mode: str | None = None
    verified: bool = False
    verified_note: str | None = None
    salesman: str | None = None
    hs_amount: float = 0.0
    ms_amount: float = 0.0
    hs_liters: float = 0.0
    ms_liters: float = 0.0
    oil_amounts: list[float] = field(default_factory=lambda: [0.0] * len(OIL_KEYS))
    gas_total: float = 0.0
    oil_total: float = 0.0

    @property
    def present(self) -> bool:
        return self.entry_id is not None


def _latest_entry_for(conn: sqlite3.Connection, shift_date: str, side: str) -> sqlite3.Row | None:
    rows = conn.execute(
        "SELECT * FROM daily_sales_entry WHERE shift_date = ? ORDER BY id DESC",
        (shift_date,),
    ).fetchall()
    for row in rows:
        if classify_pump(row["pump_serial"]) == side:
            return row
    return None


def _side_from_entry(row: sqlite3.Row | None) -> PumpSide:
    side = PumpSide()
    if row is None:
        return side
    result = json.loads(row["result"] or "{}")
    side.entry_id = row["id"]
    side.pump_serial = row["pump_serial"]
    side.submitted_by = row["submitted_by"]
    side.entry_mode = row["entry_mode"]
    side.hs_amount = (result.get("hs") or {}).get("amount") or 0.0
    side.ms_amount = (result.get("ms") or {}).get("amount") or 0.0
    ds = result.get("daily_summary") or {}
    side.hs_liters = ds.get("hs") or 0.0
    side.ms_liters = ds.get("ms") or 0.0
    oils = result.get("oils") or []
    side.oil_amounts = [
        (oils[i].get("amount") if i < len(oils) and oils[i].get("amount") is not None else 0.0)
        for i in range(len(OIL_KEYS))
    ]
    side.gas_total = result.get("gas_total") or 0.0
    side.oil_total = result.get("oil_total") or 0.0
    return side


def build_summary(conn: sqlite3.Connection, shift_date: str) -> dict:
    row = conn.execute(
        "SELECT * FROM daily_sales_summary WHERE shift_date = ?", (shift_date,)
    ).fetchone()

    def bound_or_latest(bound_id_col: str, side: str) -> sqlite3.Row | None:
        if row is not None and row[bound_id_col]:
            return conn.execute(
                "SELECT * FROM daily_sales_entry WHERE id = ?", (row[bound_id_col],)
            ).fetchone()
        return _latest_entry_for(conn, shift_date, side)

    off_row = bound_or_latest("off_entry_id", "office")
    road_row = bound_or_latest("road_entry_id", "road")

    office = _side_from_entry(off_row)
    road = _side_from_entry(road_row)

    if row is not None:
        office.verified = bool(row["off_verified"])
        road.verified = bool(row["road_verified"])
        office.verified_note = row["off_verified_note"]
        road.verified_note = row["road_verified_note"]
        office.salesman = row["off_salesman"]
        road.salesman = row["road_salesman"]

    def line(a: float, b: float) -> dict:
        return {"office": round(a, 4), "road": round(b, 4), "combined": round(a + b, 4)}

    combined = {
        "hs": line(office.hs_amount, road.hs_amount),
        "ms": line(office.ms_amount, road.ms_amount),
        "hs_liters": line(office.hs_liters, road.hs_liters),
        "ms_liters": line(office.ms_liters, road.ms_liters),
        "oils": [
            {"key": OIL_KEYS[i], "label": OIL_LABELS[OIL_KEYS[i]],
             **line(office.oil_amounts[i], road.oil_amounts[i])}
            for i in range(len(OIL_KEYS))
        ],
        "oil_total": line(office.oil_total, road.oil_total),
        "grand_total": round(
            office.gas_total + office.oil_total + road.gas_total + road.oil_total, 4
        ),
    }

    both_present = office.present and road.present
    both_verified = office.verified and road.verified
    status = row["status"] if row is not None else "draft"

    return {
        "shift_date": shift_date,
        "status": status,
        "office": _side_dict(office),
        "road": _side_dict(road),
        "combined": combined,
        "both_present": both_present,
        "both_verified": both_verified,
        "can_upload": both_present and both_verified and status != "uploaded",
        "prepared_by": row["prepared_by"] if row is not None else None,
        "verified_by": row["verified_by"] if row is not None else None,
        "uploaded_by": row["uploaded_by"] if row is not None else None,
        "uploaded_at": row["uploaded_at"] if row is not None else None,
    }


def reverify_summary_for_entry(
    conn: sqlite3.Connection, shift_date: str, pump_serial: str, actor: str
) -> str | None:
    """A Daily Sales Entry for this day was corrected. If its Daily Sales Summary
    was already verified or uploaded, drop the edited side's verification (and the
    uploaded status) so a human re-checks the changed figures (SDD ADR-5).
    Returns a short note if it changed something, else None.
    """
    from svr_backend.core.audit import record_write

    side = classify_pump(pump_serial)
    if side is None:
        return None
    row = conn.execute(
        "SELECT * FROM daily_sales_summary WHERE shift_date = ?", (shift_date,)
    ).fetchone()
    if row is None:
        return None
    col = "off_verified" if side == "office" else "road_verified"
    was_verified = bool(row[col])
    if not was_verified and row["status"] != "uploaded":
        return None
    conn.execute(
        f"UPDATE daily_sales_summary SET {col} = 0, status = 'draft', "
        "verified_by = NULL, uploaded_by = NULL, uploaded_at = NULL, "
        "last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
        "WHERE shift_date = ?",
        (actor, shift_date),
    )
    record_write(
        conn, table="daily_sales_summary", record_id=row["id"], action="update", actor=actor,
        old={"status": row["status"], col: was_verified},
        new={"status": "draft", col: False},
    )
    return (
        f"Daily Sales Summary for {shift_date} re-opened: the {side} side needs "
        "re-verification after this correction."
    )


def _side_dict(side: PumpSide) -> dict:
    return {
        "entry_id": side.entry_id,
        "pump_serial": side.pump_serial,
        "submitted_by": side.submitted_by,
        "entry_mode": side.entry_mode,
        "salesman": side.salesman,
        "verified": side.verified,
        "verified_note": side.verified_note,
        "present": side.present,
        "hs_amount": round(side.hs_amount, 4),
        "ms_amount": round(side.ms_amount, 4),
        "oil_amounts": [round(x, 4) for x in side.oil_amounts],
        "gas_total": round(side.gas_total, 4),
        "oil_total": round(side.oil_total, 4),
    }
