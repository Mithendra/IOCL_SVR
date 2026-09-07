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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from svr_backend.calc.daily_trial_balance import (
    Section1Input,
    TrialBalanceInput,
    compute,
)
from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.params import get_param
from svr_backend.rates import latest_effective_rates
from svr_backend.summary import build_summary

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
    the +-Rs100 `trial_balance_alert_threshold`. When omitted, the check is skipped
    entirely rather than blocking sign-off: the Projected figure isn't computed
    server-side yet (its inputs - margin, 2T sales, sales-after-expenses - live in
    the still-manual sections), so it isn't always available to compare against.
    """

    projected_total: float | None = None
    reason: str | None = None


def _context(conn: sqlite3.Connection, shift_date: str, row: sqlite3.Row | None) -> dict:
    """Pull Section 3 consumption (Daily Sales Summary), Buy rates, testing deduction."""
    summary = build_summary(conn, shift_date)
    s3_hs = summary["combined"]["hs_liters"]["combined"] if summary["both_present"] else None
    s3_ms = summary["combined"]["ms_liters"]["combined"] if summary["both_present"] else None

    rates = latest_effective_rates(conn, shift_date)
    buy_hs = rates["HS"]["buy_rate"] if "HS" in rates else None
    buy_ms = rates["MS"]["buy_rate"] if "MS" in rates else None
    testing = get_param(conn, "testing_density_deduction", 10.0, as_of=shift_date)

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
        cash_book_value=row["s54_cash_book_value"] if row else None,
    )
    return {
        "data": data,
        "s3_source": "daily_sales_summary" if summary["both_present"] else "unavailable",
        "s3_hs_consumption": s3_hs,
        "s3_ms_consumption": s3_ms,
        "buy_rate_hs": buy_hs,
        "buy_rate_ms": buy_ms,
        "testing_deduction": testing,
        "summary_status": summary["status"],
    }


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
        "manual": json.loads(row["manual_json"]) if row else {},
        "pulled": {
            "s3_source": ctx["s3_source"],
            "s3_hs_consumption": ctx["s3_hs_consumption"],
            "s3_ms_consumption": ctx["s3_ms_consumption"],
            "buy_rate_hs": ctx["buy_rate_hs"],
            "buy_rate_ms": ctx["buy_rate_ms"],
            "testing_deduction": ctx["testing_deduction"],
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
        record_write(
            conn, table=TABLE, record_id=rid, action="update", actor=principal.login_name,
            new={"shift_date": shift_date, "s7_3_total": result["section7"]["7_3_total"]},
        )
    return _view(conn, shift_date)


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

    # ADR-2 Decision step 1: re-run the variance/escalation check server-side. Only
    # possible when a Projected total was supplied - it isn't computed server-side
    # yet (still a manual figure pending ADR-1's remaining sections), so this is a
    # best-effort check, not a hard requirement, until that figure is wired up.
    result = json.loads(row["result_json"]) if row["result_json"] else {}
    reported_total = result.get("section7", {}).get("7_3_total")
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

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    next_date = (date.fromisoformat(shift_date) + timedelta(days=1)).isoformat()
    with transaction(conn):
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
    # NOTE: Section 9's historical ledger row and the Inventory stock decrement are
    # still deferred with the remaining ADR-1 sections.
    return _view(conn, shift_date)
