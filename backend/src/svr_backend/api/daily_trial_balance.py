"""Daily Trial Balance API (SDD 5.8 / 9). One row per date.

Sections 1/6/7 are computed by the calc engine; Section 3 is pulled read-only from
Daily Sales Summary; Sections 2/4/5/8/9/10/11 are stored as a free-form manual
blob - CONFIRMED with client 2026-09-06 as the final design (SDD ADR-1), not an
interim one. Every write recomputes and audits.

RBAC (maker-checker, ADR-2, confirmed 2026-09-06): Sales (the maker) enters and
validates the day's data via GET/PUT; Manager/Owner (the checker) additionally
perform Close & Sign Off via POST .../finalize. The same Manager/Owner may also
enter data themselves (e.g. when the maker is off) - that is an allowed fallback,
not an error path.

Carry-forward (ADR-2): Close & Sign Off is what triggers next-day carry-forward,
never a scheduled job - see
docs/02-System-Design-Architecture/ADR-2-Daily-Trial-Balance-Close-and-Carry-Forward.md
for why this differs from SDD 7.7's 23:59 IST scheduler. Finalizing a day
system-generates the next day's draft (`prev_trial_balance_id`), seeded from this
day's own finalized closing values - replacing the legacy workbook's hand-typed
cross-sheet formula (the root cause of two real carry-forward bugs found in the
2026-09-06 audit). A new shift_date can only be created once every earlier date is
finalized, which is what would have caught the SEP02 skip directly. Carry-forward
always reads the Reported figures (`result_json.section7`), never a same-day
Projected/draft value (ADR-2's non-negotiable invariant).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from svr_backend import oil_items, posting
from svr_backend.calc.amounts import is_blank
from svr_backend.calc.daily_trial_balance import (
    Section1Input,
    TrialBalanceInput,
    compute,
    derive_manual,
)
from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.excel.trial_balance_full import build_full_workbook
from svr_backend.excel.trial_balance_section8 import (
    build_section8_workbook,
    section8_message,
)
from svr_backend.inventory import sync_from_daily_sales
from svr_backend.params import get_param
from svr_backend.rates import latest_effective_rates
from svr_backend.summary import (
    PUMP_SIDE,
    beta_testing_expense,
    build_summary,
    nozzles_tested,
)

router = APIRouter(prefix="/daily-trial-balance", tags=["daily-trial-balance"])

TABLE = "daily_trial_balance"


class TrialBalanceUpsert(BaseModel):
    s1_hs_yesterday: float | None = None
    s1_hs_current: float | None = None
    s1_ms_yesterday: float | None = None
    s1_ms_current: float | None = None
    s54_cash_book_value: float | None = None
    manual: dict = {}


class FinalizeRequest(BaseModel):
    """Body for POST .../finalize (ADR-2 Decision step 1).

    ``projected_total`` is the legacy sheet's "Today's Projected Trial Balance"
    (Section 7/8-equivalent, still a manual figure pending ADR-1) - when supplied,
    it is compared against this day's computed Reported total and checked against
    the `trial_balance_alert_threshold` parameter (Rs 50 since migration 0025).
    When omitted, the check is skipped
    entirely rather than blocking sign-off: the Projected figure isn't computed
    server-side yet (its inputs - margin, 2T sales, sales-after-expenses - live in
    the still-manual sections), so it isn't always available to compare against.
    """

    projected_total: float | None = None
    reason: str | None = None


def _context(conn: sqlite3.Connection, shift_date: str, row: sqlite3.Row | None) -> dict:
    """Pull Section 3 consumption (Daily Sales Summary), Buy rates, testing deduction."""
    summary = build_summary(conn, shift_date)
    # Whatever was submitted, combined. Two submissions are no longer mandatory
    # (client, 2026-09-14) - a pump in the workshop reports nothing, and the day
    # still has to compute off the pump that ran.
    any_present = summary["any_present"]
    s3_hs = summary["combined"]["hs_liters"]["combined"] if any_present else None
    s3_ms = summary["combined"]["ms_liters"]["combined"] if any_present else None
    # Section 1's "2T Sales" column is the day's Oil Sale(s) total, both pumps
    # (SEP12: J4 = 416 = Section 2.1's own total). Pulled, never retyped.
    oil_total = summary["combined"]["oil_total"]["combined"] if any_present else 0.0
    # Section 4.2 is the day's own sales less the Beta/Density/Testing expense.
    # Both halves come from the Daily Sales Entries, so neither is retyped here.
    # `sales_total` stays None when the day has no entry at all - 4.2 then falls
    # back to whatever was typed, rather than computing the day as zero sales.
    gas_combined = summary["combined"]["gas_total"]["combined"]
    oil_combined = summary["combined"]["oil_total"]["combined"]
    has_entry = any_present
    day_sales_total = round(gas_combined + oil_combined, 4) if has_entry else None
    beta_testing = beta_testing_expense(conn, shift_date)

    rates = latest_effective_rates(conn, shift_date)
    buy_hs = rates["HS"]["buy_rate"] if "HS" in rates else None
    buy_ms = rates["MS"]["buy_rate"] if "MS" in rates else None
    sell_hs = rates["HS"]["sell_rate"] if "HS" in rates else None
    sell_ms = rates["MS"]["sell_rate"] if "MS" in rates else None
    # Testing: each NOZZLE that moved drew 5 litres; a nozzle whose reading did
    # not change was not tested (client, 2026-09-14). Read straight off the day's
    # four readings - no dropdown, no status, no counting of submissions. The
    # tested fuel is pumped back into the tank, which is why Section 1 subtracts
    # it when reconciling pump consumption against the IOCL tank reading.
    per_nozzle = get_param(conn, "testing_litres_per_nozzle", 5.0, as_of=shift_date)
    nozzles = nozzles_tested(conn, shift_date)
    if nozzles is None:
        testing = get_param(conn, "testing_density_deduction", 10.0, as_of=shift_date)
        testing_hs = testing_ms = testing
        testing_basis = "parameter"
    else:
        testing_hs = round(per_nozzle * nozzles["hs"], 4)
        testing_ms = round(per_nozzle * nozzles["ms"], 4)
        testing = testing_hs
        testing_basis = "derived"
    # Per-litre margin (commission) rates and the daily-expenses deduction, from
    # the SEP12 formulas (migration 0022).
    margin_hs = get_param(conn, "margin_rate_hs", 0.0, as_of=shift_date)
    margin_ms = get_param(conn, "margin_rate_ms", 0.0, as_of=shift_date)
    daily_expenses = get_param(conn, "daily_expenses_deduction", 0.0, as_of=shift_date)

    data = TrialBalanceInput(
        s1=Section1Input(
            hs_yesterday=row["s1_hs_yesterday"] if row else None,
            hs_current=row["s1_hs_current"] if row else None,
            ms_yesterday=row["s1_ms_yesterday"] if row else None,
            ms_current=row["s1_ms_current"] if row else None,
        ),
        s3_hs_consumption=s3_hs,
        s3_ms_consumption=s3_ms,
        buy_rate_hs=buy_hs,
        buy_rate_ms=buy_ms,
        testing_deduction=testing,
        testing_deduction_hs=None if nozzles is None else testing_hs,
        testing_deduction_ms=None if nozzles is None else testing_ms,
        cash_book_value=row["s54_cash_book_value"] if row else None,
    )
    return {
        "data": data,
        "s3_source": "daily_sales_summary" if any_present else "unavailable",
        "s3_hs_consumption": s3_hs,
        "s3_ms_consumption": s3_ms,
        "oil_total": oil_total,
        "buy_rate_hs": buy_hs,
        "buy_rate_ms": buy_ms,
        "sell_rate_hs": sell_hs,
        "sell_rate_ms": sell_ms,
        "testing_deduction": testing,
        "testing_basis": testing_basis,
        "testing_deduction_hs": testing_hs,
        "testing_deduction_ms": testing_ms,
        "testing_nozzles_hs": None if nozzles is None else nozzles["hs"],
        "testing_nozzles_ms": None if nozzles is None else nozzles["ms"],
        "testing_litres_per_nozzle": per_nozzle,
        "margin_rate_hs": margin_hs,
        "margin_rate_ms": margin_ms,
        "daily_expenses_deduction": daily_expenses,
        "summary_status": summary["status"],
        "day_sales_total": day_sales_total,
        "beta_testing_expense": beta_testing,
    }


def _day_sales(conn: sqlite3.Connection, shift_date: str) -> dict:
    """The day's per-pump readings and oil rows, for Section 2.

    The screen builds this itself from the same entries; the Excel export needs it
    server-side, because the export writes into the station's own workbook and
    Section 2 there is per-pump, not the combined figure Daily Sales Summary
    reports. Oil rows come back in the item list's display order, resolved by
    each saved row's own label (the order changed on 2026-09-12, and the list
    itself is now editable - migration 0023).

    Oil Sale(s) is handled by ONE submitter a day, so one entry owns the oil
    section; the other pump's rows are blanks the backend filled in from Inventory
    at save time, and are indistinguishable from typed figures once stored. Take
    every oil row from that owner rather than merging the two per row - merging
    made this and the screen prefer opposite entries on the zero-quantity rows,
    so Acid Water's Opening Stock read 60 here and 64 on screen where the SEP12
    sheet's own D21 says 64. Oldest entry of the day is the fallback when nothing
    sold, so the same day always resolves the same way.
    """
    out: dict = {"road": {}, "office": {}, "oils": []}
    payloads: list[dict] = []
    for row in conn.execute(
        "SELECT pump_serial, payload FROM daily_sales_entry WHERE shift_date = ? "
        "ORDER BY id DESC",
        (shift_date,),
    ):
        side = PUMP_SIDE.get(row["pump_serial"])
        if side is None:
            continue
        payload = json.loads(row["payload"] or "{}")
        payloads.append(payload)
        if not out[side]:
            for fuel in ("hs", "ms"):
                f = payload.get(fuel) or {}
                out[side][fuel] = {
                    "current": f.get("current"), "last": f.get("last"), "rate": f.get("rate"),
                }

    def _qty(oil: dict) -> float:
        # Quantities come back as whatever was submitted - "8", 8, "" or None - so
        # coerce rather than testing membership: the string "0" is falsy as a
        # quantity but not equal to 0.
        try:
            return float(oil.get("qty") or 0)
        except (TypeError, ValueError):
            return 0.0

    def _sold(payload: dict) -> bool:
        return any(
            _qty(oil) > 0 for oil in oil_items.oils_by_key(conn, payload.get("oils")).values()
        )

    owner = next((p for p in payloads if _sold(p)), payloads[-1] if payloads else {})
    oil_rows = oil_items.oils_by_key(conn, owner.get("oils"))
    out["oils"] = [
        {
            "label": item.label,
            "qty": (oil_rows.get(item.key) or {}).get("qty"),
            "rate": (oil_rows.get(item.key) or {}).get("rate"),
            "opening": (oil_rows.get(item.key) or {}).get("opening"),
        }
        for item in oil_items.active_items(conn)
    ]
    return out


def _most_recent_finalized(conn: sqlite3.Connection, before_date: str) -> sqlite3.Row | None:
    """Most recent *finalized* row strictly before ``before_date``.

    Gap-tolerant by construction (ADR-2 point 5, mirroring the SDD 7.7 skip-back
    precedent in carry_forward.py): a day with zero activity has no row at all, so
    ordering by ``shift_date`` and taking the first finalized one naturally skips
    over it rather than assuming literally ``before_date - 1``.
    """
    return conn.execute(
        f"SELECT * FROM {TABLE} WHERE status = 'finalized' AND shift_date < ? "
        "ORDER BY shift_date DESC LIMIT 1",
        (before_date,),
    ).fetchone()


def _earliest_open_before(conn: sqlite3.Connection, before_date: str) -> sqlite3.Row | None:
    """Earliest not-yet-finalized row strictly before ``before_date``, if any.

    Used only when creating a brand-new ``shift_date`` (ADR-2 Decision step 4): an
    open predecessor blocks it, which is what would have caught the legacy
    workbook's SEP02 skip directly - Sep 2 could not have been created while Sep 1
    was still open.
    """
    return conn.execute(
        f"SELECT * FROM {TABLE} WHERE status != 'finalized' AND shift_date < ? "
        "ORDER BY shift_date ASC LIMIT 1",
        (before_date,),
    ).fetchone()


def _view(conn: sqlite3.Connection, shift_date: str) -> dict:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE shift_date = ?", (shift_date,)).fetchone()
    ctx = _context(conn, shift_date, row)
    result = compute(ctx["data"]).to_dict()
    manual = json.loads(row["manual_json"]) if row else {}
    # The operator-entered sections store INPUTS only; every total between them is
    # derived here, server-side, exactly as the client's own SEP12 tab computes it
    # ("Rest should be calculated Automatically using Excel Formulas").
    # 6.3 Net Worth is the engine's section7 total under the older SDD numbering -
    # NOT section6, which is Section 5's Stock Value.
    s1 = result["section1"]
    result["derived"] = derive_manual(
        manual,
        result["section7"]["7_3_total"],
        ctx["oil_total"],
        {
            "hs_deduct_testing": s1["hs"]["deduct_testing"],
            "ms_deduct_testing": s1["ms"]["deduct_testing"],
            "hs_computer_pump_diff": s1["hs"]["computer_pump_diff"],
            "ms_computer_pump_diff": s1["ms"]["computer_pump_diff"],
            "margin_rate_hs": ctx["margin_rate_hs"],
            "margin_rate_ms": ctx["margin_rate_ms"],
            "buy_rate_hs": ctx["buy_rate_hs"],
            "buy_rate_ms": ctx["buy_rate_ms"],
            "daily_expenses": ctx["daily_expenses_deduction"],
        },
        {
            "sales_total": ctx["day_sales_total"],
            "beta_testing": ctx["beta_testing_expense"],
        },
    )
    return {
        "shift_date": shift_date,
        "status": row["status"] if row else "draft",
        "inputs": {
            "s1_hs_yesterday": row["s1_hs_yesterday"] if row else None,
            "s1_hs_current": row["s1_hs_current"] if row else None,
            "s1_ms_yesterday": row["s1_ms_yesterday"] if row else None,
            "s1_ms_current": row["s1_ms_current"] if row else None,
            "s54_cash_book_value": row["s54_cash_book_value"] if row else None,
        },
        "manual": manual,
        "pulled": {
            "s3_source": ctx["s3_source"],
            "s3_hs_consumption": ctx["s3_hs_consumption"],
            "s3_ms_consumption": ctx["s3_ms_consumption"],
            "buy_rate_hs": ctx["buy_rate_hs"],
            "buy_rate_ms": ctx["buy_rate_ms"],
            "sell_rate_hs": ctx["sell_rate_hs"],
            "sell_rate_ms": ctx["sell_rate_ms"],
            "testing_deduction": ctx["testing_deduction"],
            # Say WHERE the deduction came from, so 10 vs 5 is never a mystery
            # again: how many pumps were tested, and at how many litres a nozzle.
            "testing_basis": ctx["testing_basis"],
            "testing_deduction_hs": ctx["testing_deduction_hs"],
            "testing_deduction_ms": ctx["testing_deduction_ms"],
            "testing_nozzles_hs": ctx["testing_nozzles_hs"],
            "testing_nozzles_ms": ctx["testing_nozzles_ms"],
            "testing_litres_per_nozzle": ctx["testing_litres_per_nozzle"],
        },
        "computed": result,
        "finalized_by": row["finalized_by"] if row else None,
        "finalized_at": row["finalized_at"] if row else None,
        "carried_from": (
            conn.execute(
                f"SELECT shift_date FROM {TABLE} WHERE id = ?", (row["prev_trial_balance_id"],)
            ).fetchone()["shift_date"]
            if row and row["prev_trial_balance_id"] is not None
            else None
        ),
        "variance_amount": row["variance_amount"] if row else None,
        "variance_reason": row["variance_reason"] if row else None,
        "adr1_note": (
            "Sections 2/4/5/8/9/10/11 are captured in `manual` - CONFIRMED 2026-09-06 "
            "as the final design (SDD ADR-1), not an interim one."
        ),
    }


OPTION_LISTS = ("creditors", "expenses", "remittance", "old_credit", "staff")


class OptionCreate(BaseModel):
    list_key: str
    value: str


@router.get("")
def list_trial_balances(
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 120,
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """Saved Trial Balance days, newest first - for looking one up without
    already knowing its date (client asked 2026-09-12; Daily Sales Entry has had
    this since the round-2 Query work)."""
    clauses, params = [], []
    if date_from:
        clauses.append("shift_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("shift_date <= ?")
        params.append(date_to)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT shift_date, status, finalized_by, finalized_at, last_updated_by, "
        f"last_updated_at FROM {TABLE}{where} ORDER BY shift_date DESC LIMIT ?",
        [*params, max(1, min(limit, 500))],
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/options")
def get_options(
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, list[str]]:
    """The form's dropdown lists (migration 0021).

    Declared BEFORE /{shift_date} so "options" is not swallowed by the date route.
    """
    out: dict[str, list[str]] = {k: [] for k in OPTION_LISTS}
    for row in conn.execute(
        "SELECT list_key, value FROM trial_balance_option ORDER BY list_key, sort_order, id"
    ):
        out.setdefault(row["list_key"], []).append(row["value"])
    return out


@router.post("/options", status_code=status.HTTP_201_CREATED)
def add_option(
    body: OptionCreate,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, list[str]]:
    """Add a value to one of the dropdowns and return the refreshed lists.

    Open to Sales as well as Manager/Owner on purpose: a new customer asking for
    credit is discovered mid-entry by the maker, and a form that cannot accept
    the name until someone else logs in is a form that gets bypassed on paper.
    Every addition is audited.
    """
    key = body.list_key.strip()
    value = " ".join(body.value.split())  # collapse stray whitespace, keep the wording
    if key not in OPTION_LISTS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown list '{key}' - expected one of {', '.join(OPTION_LISTS)}",
        )
    if not value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Value cannot be blank")
    existing = conn.execute(
        "SELECT id FROM trial_balance_option WHERE list_key = ? AND value = ?", (key, value)
    ).fetchone()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f'"{value}" is already in that list')

    with transaction(conn):
        nxt = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM trial_balance_option "
            "WHERE list_key = ?",
            (key,),
        ).fetchone()["n"]
        cur = conn.execute(
            "INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) "
            "VALUES (?, ?, ?, ?)",
            (key, value, nxt, principal.login_name),
        )
        record_write(
            conn, table="trial_balance_option", record_id=cur.lastrowid, action="create",
            actor=principal.login_name, new={"list_key": key, "value": value},
        )
    return get_options(principal, conn)


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/{shift_date}/export-excel")
def export_full(
    shift_date: str,
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> Response:
    """The whole day's Trial Balance - all eleven sections - as one .xlsx."""
    view = _view(conn, shift_date)
    view["day_sales"] = _day_sales(conn, shift_date)
    data = build_full_workbook(view)
    return Response(
        content=data,
        media_type=_XLSX,
        headers={
            "Content-Disposition":
                f'attachment; filename="SVR-TrialBalance-{shift_date}.xlsx"'
        },
    )


@router.get("/{shift_date}/export-section8")
def export_section8(
    shift_date: str,
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> Response:
    """Section 8 alone as .xlsx - the part that goes to management daily.

    Separate from any whole-form export on purpose: a manager wants the five
    reporting lines and the net-worth summary, not eleven sections (BRD; the
    client's own mockup carries this button, reconfirmed 2026-09-12).
    """
    data = build_section8_workbook(_view(conn, shift_date))
    return Response(
        content=data,
        media_type=_XLSX,
        headers={
            "Content-Disposition":
                f'attachment; filename="SVR-Section8-{shift_date}.xlsx"'
        },
    )


@router.get("/{shift_date}/section8-message")
def section8_whatsapp_message(
    shift_date: str,
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """The same figures as plain text, for the WhatsApp send.

    The station has always sent these to management as a message, and a phone on
    the road is not going to open a spreadsheet. The renderer opens wa.me with
    this as the prefilled body; the .xlsx is attached by hand if wanted. No
    WhatsApp Business API is wired up - that needs an account and credentials the
    project does not have, and a button that silently did nothing would be worse
    than one that opens the real chat.
    """
    return {"shift_date": shift_date, "text": section8_message(_view(conn, shift_date))}


@router.get("/{shift_date}")
def get_trial_balance(
    shift_date: str,
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return _view(conn, shift_date)


@router.put("/{shift_date}")
def upsert_trial_balance(
    shift_date: str,
    body: TrialBalanceUpsert,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    existing = conn.execute(
        f"SELECT * FROM {TABLE} WHERE shift_date = ?", (shift_date,)
    ).fetchone()
    if existing and existing["status"] == "finalized":
        raise HTTPException(status.HTTP_409_CONFLICT, "This date's Trial Balance is finalized")

    # ADR-2 Decision step 4: a brand-new date can't be created while an earlier one
    # is still open - this alone would have caught the legacy workbook's SEP02 skip.
    carry: sqlite3.Row | None = None
    if existing is None:
        blocking = _earliest_open_before(conn, shift_date)
        if blocking is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Cannot start {shift_date}'s Trial Balance - {blocking['shift_date']} is "
                "still open (not yet Closed & Signed Off). Close & Sign Off every earlier "
                "date first, in order.",
            )
        # ADR-2 point 5: seed from the most recently *finalized* row, not strictly
        # shift_date - 1, so a genuine gap (no rows at all) is skipped over rather
        # than assumed to be "yesterday". A maker-supplied value in `body` still wins.
        carry = _most_recent_finalized(conn, shift_date)

    def pick(field_name: str, col: str, carry_col: str | None = None):
        v = getattr(body, field_name)
        if v is not None:
            return v
        if existing is not None:
            return existing[col]
        if carry is not None and carry_col is not None:
            return carry[carry_col]
        return None

    values = {
        # Today's IOCL current reading becomes tomorrow's opening "yesterday" -
        # ADR-2 Consequences: "write the next day's opening s1_*_yesterday ...
        # fields from this day's finalized closing values".
        "s1_hs_yesterday": pick("s1_hs_yesterday", "s1_hs_yesterday", "s1_hs_current"),
        "s1_hs_current": pick("s1_hs_current", "s1_hs_current"),
        "s1_ms_yesterday": pick("s1_ms_yesterday", "s1_ms_yesterday", "s1_ms_current"),
        "s1_ms_current": pick("s1_ms_current", "s1_ms_current"),
        "s54_cash_book_value": pick(
            "s54_cash_book_value", "s54_cash_book_value", "s54_cash_book_value"
        ),
    }
    manual = json.loads(existing["manual_json"]) if existing else {}
    manual.update(body.manual or {})

    # recompute with the merged inputs so result_json is always current.
    # _context indexes the row by column name; a plain dict with all five keys works.
    ctx = _context(conn, shift_date, dict(values))
    result = compute(ctx["data"]).to_dict()

    with transaction(conn):
        conn.execute(
            f"""
            INSERT INTO {TABLE} (
                shift_date, s1_hs_yesterday, s1_hs_current, s1_ms_yesterday, s1_ms_current,
                s54_cash_book_value, manual_json, result_json, last_updated_by,
                prev_trial_balance_id
            ) VALUES (:d, :s1hy, :s1hc, :s1my, :s1mc, :cash, :manual, :result, :by, :prev_id)
            ON CONFLICT(shift_date) DO UPDATE SET
                s1_hs_yesterday = :s1hy, s1_hs_current = :s1hc,
                s1_ms_yesterday = :s1my, s1_ms_current = :s1mc,
                s54_cash_book_value = :cash, manual_json = :manual, result_json = :result,
                last_updated_by = :by,
                last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                -- prev_trial_balance_id intentionally NOT updated here: fixed once
                -- at creation, per ADR-2 (a system-generated link, not re-typeable).
            """,
            {
                "d": shift_date,
                "s1hy": values["s1_hs_yesterday"], "s1hc": values["s1_hs_current"],
                "s1my": values["s1_ms_yesterday"], "s1mc": values["s1_ms_current"],
                "cash": values["s54_cash_book_value"],
                "manual": json.dumps(manual), "result": json.dumps(result),
                "by": principal.login_name,
                "prev_id": carry["id"] if carry is not None else None,
            },
        )
        rid = conn.execute(
            f"SELECT id FROM {TABLE} WHERE shift_date = ?", (shift_date,)
        ).fetchone()["id"]
        # Keep the posting rows in step with the form. A line still unposted
        # simply follows what was typed; once posted it is left alone, because a
        # master form already holds it.
        posting.sync_lines(conn, shift_date, manual, principal.login_name)
        record_write(
            conn, table=TABLE, record_id=rid, action="update", actor=principal.login_name,
            new={"shift_date": shift_date, "s7_3_total": result["section7"]["7_3_total"]},
        )
    return _view(conn, shift_date)


@router.post("/{shift_date}/post")
def post_to_masters(
    shift_date: str,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Post the day's expense, credit and remittance lines to the master forms.

    Client, 2026-09-14: expenses go to Monthly Expenses, credits and remittances
    to Credit / Remittance Master, and Close & Sign Off is refused until this has
    run. Posting copies the lines OUT for reporting - they are already counted in
    this day's own arithmetic and never feed back into a total or into
    carry-forward.
    """
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE shift_date = ?", (shift_date,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No Trial Balance for this date yet")
    with transaction(conn):
        out = posting.post_day(conn, shift_date, principal.login_name)
    return {"shift_date": shift_date, **out, "lines": posting.open_lines(conn)}


@router.post("/{shift_date}/reopen")
def reopen_trial_balance(
    shift_date: str,
    principal: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Reopen a signed-off day so it can be corrected.

    Until now a finalized day was locked forever with no way back, which is fine
    until someone signs off a wrong figure - and during live testing that will
    happen. Owner only, and audited.

    Reopening UN-POSTS the day: the rows it put into Monthly Expenses and Credit
    / Remittance Master are removed and its lines return to Not Posted, so the
    correction re-posts cleanly instead of duplicating. A credit already marked
    Paid is left alone - its remittance came in on another day.

    Refused while a LATER day is already closed. ADR-2's whole point is that a
    day is built on the one before it; reopening underneath a closed day would
    leave that day's carried figures pointing at something that no longer exists.
    """
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE shift_date = ?", (shift_date,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No Trial Balance for this date")
    if row["status"] != "finalized":
        raise HTTPException(status.HTTP_409_CONFLICT, "That day is not closed - nothing to reopen")
    later = conn.execute(
        f"SELECT shift_date FROM {TABLE} WHERE shift_date > ? AND status = 'finalized' "
        "ORDER BY shift_date LIMIT 1", (shift_date,)
    ).fetchone()
    if later is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{later['shift_date']} is already closed and is built on this day. "
            f"Reopen {later['shift_date']} first, in reverse order.",
        )
    with transaction(conn):
        out = posting.unpost_day(conn, shift_date, principal.login_name)
        conn.execute(
            f"UPDATE {TABLE} SET status = 'draft', finalized_by = NULL, finalized_at = NULL, "
            "last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE shift_date = ?",
            (principal.login_name, shift_date),
        )
        record_write(conn, table=TABLE, record_id=row["id"], action="update",
                     actor=principal.login_name,
                     old={"status": "finalized"}, new={"status": "draft", **out})
    return {"shift_date": shift_date, "status": "draft", **out}


@router.get("/postings/open")
def open_postings(
    month: str | None = None,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """The running view - every line not yet cleared, newest day first.

    Deliberately spans days: an expense posted on the 3rd is still here on the
    20th, and an unpaid credit stays in front of the operator until a remittance
    settles it. `month` narrows to a YYYY-MM prefix.
    """
    return {"lines": posting.open_lines(conn, month)}


class ClearRequest(BaseModel):
    ids: list[int] = []


@router.post("/postings/clear")
def clear_postings(
    body: ClearRequest,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Month-end tidy-up. Only a posted expense or a PAID credit can go: an
    unpaid credit is exactly what the operator needs to keep seeing."""
    with transaction(conn):
        cleared = posting.clear_lines(conn, body.ids, principal.login_name)
    return {"cleared": cleared, "lines": posting.open_lines(conn)}



def _cash_book_difference(computed: dict, manual: dict) -> tuple[float | None, str]:
    """Section 4's difference, and which line it came from.

    4.10 Total Difference when the bank returned money that day, 4.5 otherwise.
    Returns (None, "") when Section 4 has not been filled in - a day with no cash
    reconciliation yet is not a day with a zero difference.

    `manual` is passed separately because the two live in different columns:
    the computed figures in result_json, the operator's own entries in
    manual_json. Reading `yesbank_return` off the wrong one silently made every
    day look like a non-return day.
    """
    s4 = ((computed or {}).get("derived") or {}).get("section4") or {}
    manual_s4 = (manual or {}).get("section4") or {}
    # 4.4 "Today SVR Cash/Book Value Reported" is what the difference is measured
    # against, so without it there is no reconciliation to check. Section 4's
    # derived block always exists - 4.2 is computed from the day's own entries
    # now - so its mere presence proves nothing about whether anyone counted the
    # cash. Testing that instead made a day with no Section 4 at all fail
    # sign-off, which is not what the escalation rule is for.
    if not s4 or is_blank(manual_s4.get("reported")):
        return None, ""
    # 4.10 whenever ANY line of the side panel is filled in, not just a bank
    # return. The client extended that panel on SEP16 with staff salaries and
    # RTGS charges, and the raw difference read -37,578.64 against a true
    # -20.64. Reading 4.5 there would demand a reason for money that was never
    # missing - the same trap as SEP12's bank return, one month wider.
    adjusted = any(
        manual_s4.get(k) not in (None, "", 0)
        for k in ("yesbank_return", "staff_salaries", "rtgs_charges", "other_adjustment")
    )
    if adjusted:
        return s4.get("total_difference"), "4.10 Total Difference (after adjustments)"
    return s4.get("diff"), "4.5 Diff Reported - Projected"


@router.post("/{shift_date}/finalize")
def finalize_trial_balance(
    shift_date: str,
    body: FinalizeRequest | None = None,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    body = body or FinalizeRequest()
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE shift_date = ?", (shift_date,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No Trial Balance for this date yet")
    if row["status"] == "finalized":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already finalized")

    # Client, 2026-09-14: "unless posted, do not allow Close & Sign Off." The
    # expense, credit and remittance lines have to reach their master forms
    # before the day can be closed - otherwise they exist only inside a signed
    # day nobody reads again.
    pending = posting.unposted(conn, shift_date)
    if pending:
        names = ", ".join(f"{p['label']} ({p['amount']:,.2f})" for p in pending[:6])
        more = f" and {len(pending) - 6} more" if len(pending) > 6 else ""
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{len(pending)} line(s) are not posted yet: {names}{more}. "
            "Post them to Monthly Expenses and Credit / Remittance Master before "
            "Close & Sign Off.",
        )

    # ADR-2 Decision step 1: re-run the variance/escalation check server-side. Only
    # possible when a Projected total was supplied - it isn't computed server-side
    # yet (still a manual figure pending ADR-1's remaining sections), so this is a
    # best-effort check, not a hard requirement, until that figure is wired up.
    result = json.loads(row["result_json"]) if row["result_json"] else {}
    reported_total = result.get("section7", {}).get("7_3_total")
    ctx_for_finalize = _context(conn, shift_date, row)
    threshold = get_param(conn, "trial_balance_alert_threshold", 100.0, as_of=shift_date)
    variance = None
    if body.projected_total is not None and reported_total is not None:
        variance = round(reported_total - body.projected_total, 4)
        if abs(variance) > threshold and not (body.reason and body.reason.strip()):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Difference - Actual Reported Minus Projected is "
                f"{variance:+.2f}, beyond the +/-{threshold:.0f} threshold. "
                "Enter a reason to sign off anyway.",
            )

    # The day's own source data has to be signed off before the day built on it
    # is. `summary_status` has been returned by this endpoint since it was built
    # and nothing ever looked at it, so a Trial Balance could be closed on
    # figures nobody had checked.
    #
    # A WARNING, NEVER A REFUSAL. Hard-gating sign-off on the Summary was raised
    # with the client twice and never decided, so it is not imposed here - and
    # their own stated fallback is that a Manager may enter and close a day when
    # the maker is off. Refusing would strand exactly that case.
    #
    # What was wrong was saying nothing at all. The state is reported on the way
    # out so it is on the record and on the screen.
    summary_status = ctx_for_finalize["summary_status"]
    s3_source = ctx_for_finalize["s3_source"]

    # Section 4's own escalation, which was never checked here at all. The sheet
    # carries the rule on its face at E53 - "Anything Above Rs 100 Call/inform
    # mgmt immediately" - and until now only Section 7's projected total was
    # tested, so a cash/book difference of any size signed off in silence.
    #
    # ON A BANK-RETURN DAY, 4.5 IS THE WRONG LINE TO READ. When the bank sends
    # money back, 4.5 carries the whole return and 4.10 (4.5 less the return) is
    # the real difference. SEP12 is the case: 4.5 read 8,516.15 where the true
    # figure was -9.80. Checking 4.5 there would demand a reason for money that
    # was never missing.
    # Recomputed, not read back from result_json - the derived block is built for
    # the response and has never been stored, so reading it from the row returned
    # an empty dict and this check silently never fired. Recomputing is the right
    # behaviour regardless: sign-off must test what the figures ARE now, not what
    # they were when someone last pressed Save (ADR-5).
    fresh = _view(conn, shift_date)
    cash_diff, cash_line = _cash_book_difference(
        fresh.get("computed") or {}, fresh.get("manual") or {}
    )
    if (
        cash_diff is not None
        and abs(cash_diff) > threshold
        and not (body.reason and body.reason.strip())
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{cash_line} is {cash_diff:+.2f}, beyond the +/-{threshold:.0f} "
            "threshold. Enter a reason to sign off anyway.",
        )

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    next_date = (date.fromisoformat(shift_date) + timedelta(days=1)).isoformat()
    with transaction(conn):
        # Carry the day's oil stock into Inventory Master. Agreed in principle a
        # while back and never built, which is why every figure there was still
        # migration 0004's placeholder until the client's own count arrived on
        # 2026-09-15 - six of seven wrong, and nobody could see it.
        #
        # Sign-off is the right moment: the day's figures are final, and it is a
        # SET from the day's real Closing Stock rather than an increment, so
        # running it twice, or an Owner correcting a count by hand afterwards, is
        # always safe. Shares the mechanism Print & Sync already uses.
        next_day = (date.fromisoformat(shift_date) + timedelta(days=1)).isoformat()
        stock_moved = sync_from_daily_sales(
            conn, next_day, principal.login_name, own_transaction=False
        )
        conn.execute(
            f"UPDATE {TABLE} SET status = 'finalized', finalized_by = ?, finalized_at = ?, "
            f"last_updated_by = ?, variance_amount = ?, variance_reason = ? WHERE shift_date = ?",
            (principal.login_name, now, principal.login_name, variance, body.reason, shift_date),
        )
        record_write(
            conn, table=TABLE, record_id=row["id"], action="update", actor=principal.login_name,
            old={"status": "draft"},
            new={"status": "finalized", "variance_amount": variance, "reason": body.reason},
        )

        # ADR-2 Decision step 3: create tomorrow's draft now, seeded from today's own
        # finalized closing values via a system-generated link - never a human-typed
        # date/cell reference (the root cause of both carry-forward bugs the
        # 2026-09-06 audit found in the legacy workbook). Guarded by
        # `existing_next is None` so it never clobbers a draft that (unusually)
        # already exists.
        existing_next = conn.execute(
            f"SELECT id FROM {TABLE} WHERE shift_date = ?", (next_date,)
        ).fetchone()
        if existing_next is None:
            conn.execute(
                f"""
                INSERT INTO {TABLE} (
                    shift_date, s1_hs_yesterday, s1_ms_yesterday, s54_cash_book_value,
                    prev_trial_balance_id, last_updated_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    next_date, row["s1_hs_current"], row["s1_ms_current"],
                    row["s54_cash_book_value"], row["id"], principal.login_name,
                ),
            )
            new_id = conn.execute(
                f"SELECT id FROM {TABLE} WHERE shift_date = ?", (next_date,)
            ).fetchone()["id"]
            record_write(
                conn, table=TABLE, record_id=new_id, action="create", actor=principal.login_name,
                new={"shift_date": next_date, "prev_trial_balance_id": row["id"],
                     "carried_from": shift_date},
            )
    # NOTE: Section 9's historical ledger row is still a manual cross-check, by
    # the client's own description. Inventory is no longer deferred - it is
    # carried above, at sign-off.
    out = _view(conn, shift_date)
    out["stock_synced"] = stock_moved
    notes = []
    if s3_source == "unavailable":
        notes.append(
            "No Daily Sales Entry for this date, so Section 1's consumption and "
            "Section 3 computed from nothing."
        )
    if summary_status != "uploaded":
        notes.append(
            f"The Daily Sales Summary is still '{summary_status}' - the figures "
            "behind this day have not been verified by the pump side."
        )
    if notes:
        out["summary_note"] = " ".join(notes) + " Closed anyway, which is allowed."
    return out
