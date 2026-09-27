"""Pull Daily Sales Entry's Section 5 (Today New Credit(s)) and Section 6
(Old/Pending Credit Received) rows into Daily Trial Balance, the same way
Section 2 already pulls that day's gas and oil sales - not through Daily
Sales Summary.

Route confirmed with the client, 2026-09-27: Daily Sales Entry -> Daily Trial
Balance -> Credit/Remittance Master, skipping Summary. Summary's whole job is
combining two pumps' numbers into one (litres, gas total, oil total) for a
verify-then-upload gate; it has no concept of an individual row, and its gate
(both pumps present AND verified) would wrongly block a credit recorded on a
day when only one pump had anything to report. Section 2 already sets the
precedent for pulling straight from `daily_sales_entry` without waiting on
that gate - this does the same for Sections 5 and 6.

These are short-lived, day-to-day rows (client: "short term credits like Max
of 7 days"), which is exactly why they belong close to their source rather
than behind an extra hop.
"""

from __future__ import annotations

import json
import sqlite3

from svr_backend.calc.amounts import is_blank, parse_amt, round4


def _rows_for(conn: sqlite3.Connection, shift_date: str) -> list[dict]:
    return list(
        conn.execute(
            "SELECT pump_serial, submitted_by, payload FROM daily_sales_entry "
            "WHERE shift_date = ? ORDER BY id",
            (shift_date,),
        ).fetchall()
    )


def pulled_new_credits(conn: sqlite3.Connection, shift_date: str) -> list[dict]:
    """Section 5's rows, from every pump that filed a Daily Sales Entry that
    day. A row with no name and no amount is a blank spare row on the form,
    not a credit - skipped the same way posting.py skips a blank line.
    """
    out: list[dict] = []
    for row in _rows_for(conn, shift_date):
        payload = json.loads(row["payload"] or "{}")
        for r in payload.get("new_credits") or []:
            if not isinstance(r, dict):
                continue
            name = (r.get("name") or "").strip()
            ltrs, rate = r.get("ltrs"), r.get("rate")
            typed_amount = r.get("amount")
            if not is_blank(typed_amount):
                amount = round4(parse_amt(typed_amount))
            elif not is_blank(ltrs) and not is_blank(rate):
                amount = round4(parse_amt(ltrs) * parse_amt(rate))
            else:
                amount = 0.0
            if not name or amount == 0:
                continue
            out.append({
                "type": name,
                "amount": amount,
                "fuel_type": r.get("fuel_type"),
                "ltrs": r.get("ltrs"),
                "rate": r.get("rate"),
                "payment_mode": r.get("payment_mode"),
                "given_on": shift_date,
                "submitted_by": row["submitted_by"],
                "pump_serial": row["pump_serial"],
            })
    return out


def pulled_old_credits(conn: sqlite3.Connection, shift_date: str) -> list[dict]:
    """Section 6's rows, from every pump that filed a Daily Sales Entry that
    day. `old_credit_amounts[i]` is index-aligned with `old_credit_rows[i]` -
    the same pairing Daily Sales Entry itself uses.
    """
    out: list[dict] = []
    for row in _rows_for(conn, shift_date):
        payload = json.loads(row["payload"] or "{}")
        details = payload.get("old_credit_rows") or []
        amounts = payload.get("old_credit_amounts") or []
        for i, r in enumerate(details):
            if not isinstance(r, dict):
                continue
            name = (r.get("customer") or "").strip()
            amount = round4(parse_amt(amounts[i])) if i < len(amounts) else 0.0
            if not name or amount == 0:
                continue
            out.append({
                "type": name,
                "amount": amount,
                "given_on_date": r.get("given_date"),
                "paid_on": shift_date,
                "payment": r.get("payment"),
                "remittance_entered": r.get("remittance_entered"),
                "collected_by": r.get("collected_by"),
                "payment_mode": r.get("payment_mode"),
                "submitted_by": row["submitted_by"],
                "pump_serial": row["pump_serial"],
            })
    return out


def manual_remittances_for_day(conn: sqlite3.Connection, shift_date: str) -> list[dict]:
    """Section 2 remittances typed straight onto Credit Master - never
    through Daily Sales Entry at all - so Trial Balance's own 4.7 mirror
    shows them too (client, 2026-09-27: "who to clear the entry in DT" -
    the answer is this reads both sources the same way Section 2 itself
    can be filled in from either place).

    Only `status = 'manual'` - a `'posted_dt'` row already ORIGINATED from a
    Daily Sales Entry pull (posting.post_line() stamped it that way), and
    pulled_old_credits() above already accounts for it from its own source;
    reading it again here would double it.
    """
    rows = conn.execute(
        "SELECT * FROM credit_transaction WHERE kind = 'remittance' "
        "AND status = 'manual' AND txn_date = ?", (shift_date,),
    ).fetchall()
    return [
        {
            "type": r["creditor_name"],
            "amount": r["amount"],
            "given_on_date": r["given_on_date"],
            "paid_on": r["txn_date"],
            "payment": r["payment"],
            "remittance_entered": r["remittance_entered"],
            "collected_by": r["collected_by"],
            "payment_mode": r["payment_mode"],
            "submitted_by": r["created_by"],
            "pump_serial": None,
        }
        for r in rows
    ]


def pulled_credit_context(conn: sqlite3.Connection, shift_date: str) -> dict:
    """Both pulls together, for `_context()` to fold into what it already
    builds for Section 2. `PUMP_SIDE` isn't needed here - unlike Section 2,
    a credit or remittance isn't combined across pumps, each row stands on
    its own regardless of which pump it was filed under.
    """
    return {
        "new_credits": pulled_new_credits(conn, shift_date),
        "old_credits": (
            pulled_old_credits(conn, shift_date) + manual_remittances_for_day(conn, shift_date)
        ),
    }
