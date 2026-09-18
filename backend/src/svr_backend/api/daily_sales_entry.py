"""Daily Sales Entry module API (SDD 5.4 / 9).

Access (SDD 4.2): Sales may create/edit their own submission and print/scan;
Manager and Owner have full access including delete (the only roles permitted to
delete a submitted daily form, SDD 4.2 audit-integrity rule).

Every write: RBAC check -> parse + recompute via the calculation engine (the engine
is authoritative, never the client) -> persist -> audit.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from svr_backend import oil_items
from svr_backend.calc.daily_sales_entry import compute_payload
from svr_backend.carry_forward import carried_last_readings
from svr_backend.core.audit import record_write
from svr_backend.core.config import get_settings
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, get_principal, require
from svr_backend.core.session import Principal
from svr_backend.excel import blank_template, build_workbook, parse_workbook
from svr_backend.inventory import on_hand_map, sync_from_daily_sales
from svr_backend.ocr import pipeline as ocr_pipeline
from svr_backend.ocr.runtime import tesseract_version
from svr_backend.rates import latest_effective_rates
from svr_backend.summary import reverify_summary_for_entry

router = APIRouter(prefix="/daily-sales-entry", tags=["daily-sales-entry"])

TABLE = "daily_sales_entry"


# --------------------------------------------------------------------------- models


class CalcRequest(BaseModel):
    """The section 1-7 form, loosely typed - mirrors the mockup's field graph.

    UNKNOWN FIELDS ARE REFUSED. Pydantic's default is to drop anything it does
    not recognise, and on a form where every field is money that is a silent
    data loss: posting `phone_pay_not_settled` instead of `phone_pay_unsettled`
    returned 201 Created, dropped the 2,525, and Net Bal came back 17,506.77
    against the correct 14,981.77 - with no error anywhere. Found by making that
    exact typo against the running app on 2026-09-14.

    A rejected save is recoverable; a wrong figure saved silently is not.
    """

    model_config = ConfigDict(extra="forbid")

    # Retired 2026-09-12, declared purely so it stays TOLERATED now that unknown
    # fields are refused. An older client or an older exported workbook may still
    # send it; the value is ignored rather than 422-ing a save that is otherwise
    # perfectly good. The money it recorded is carried by the Expenses row "Last
    # Night Cash Hand-off Person's Name-Signature-Amount".
    night_cash: object = None

    hs: dict = Field(default_factory=dict)
    ms: dict = Field(default_factory=dict)
    oils: list[dict] = Field(default_factory=list)
    expenses: list = Field(default_factory=list)
    # Descriptions for the Expenses rows, aligned by index with `expenses`
    # (client, 2026-09-13: the section must take extra rows). The first three are
    # the printed form's own fixed labels; anything beyond them is typed, and
    # without this the amount would be saved as a figure with no name against it.
    # The engine never reads these - it only sums the amounts - but they have to
    # survive the round-trip, and an undeclared field is silently dropped by
    # Pydantic on the way in.
    expense_labels: list = Field(default_factory=list)
    credit_card_amounts: list = Field(default_factory=list)
    new_credits: list[dict] = Field(default_factory=list)
    old_credit_amounts: list = Field(default_factory=list)
    phone_pay_settled: float | str | None = None
    phone_pay_unsettled: float | str | None = None
    # "Night Cash Hand Off Total Amt" was removed from the form 2026-09-12 (the
    # client's own Expenses row already carries that money). Pydantic ignores an
    # unknown field, so an older client still posting `night_cash` is accepted and
    # the value is simply dropped rather than 422-ing the save.


# Client, 2026-09-14. Only 'repair' excuses a submission; a pump whose salesman
# is off still files (Current = Last on both nozzles). The state also decides the
# day's testing deduction - a pump in the workshop is not tested.
PUMP_STATUSES = ("online", "salesman_off", "repair")


ENTRY_MODES = ("manual", "ocr", "excel")


class EntryCreate(CalcRequest):
    shift_date: str | None = None  # defaults to today
    pump_serial: str
    pump_status: str = "online"
    # Where these numbers came from, and it changes how they are treated.
    #
    # "manual": the operator is typing today's shift. Last Shift Reading is the
    # app's to own - it carries yesterday's Current Reading forward so nobody
    # retypes a meter reading (SDD 7.7).
    #
    # "excel" / "ocr": the numbers were READ OFF A SHEET the station already
    # filled in. That sheet is the source document and the app must not rewrite
    # any of it. Client, 2026-09-18: "when scanned everything should read it
    # from Attached Excel sheet and it cannot alter any of the existing values.
    # For Manual Entry of course current reading becomes last shift reading and
    # the same will not apply here."
    entry_mode: str = "manual"

    @field_validator("pump_status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        if v not in PUMP_STATUSES:
            raise ValueError(f"pump_status must be one of {', '.join(PUMP_STATUSES)}")
        return v

    @field_validator("entry_mode")
    @classmethod
    def _known_mode(cls, v: str) -> str:
        if v not in ENTRY_MODES:
            raise ValueError(f"entry_mode must be one of {', '.join(ENTRY_MODES)}")
        return v


class EntryOut(BaseModel):
    id: int
    shift_date: str
    pump_serial: str
    pump_status: str = "online"
    submitted_by: str
    entry_mode: str
    summary_note: str | None = None  # set on a PUT that re-opened the day's Summary
    sell_rate_hs: float | None
    sell_rate_ms: float | None
    hs_last: float | None
    ms_last: float | None
    gas_total: float | None
    oil_total: float | None
    net_bal_hand_off: float | None
    payload: dict
    result: dict
    last_updated_by: str | None
    last_updated_at: str


class PrefillOut(BaseModel):
    shift_date: str
    pump_serial: str
    hs_last: float | None
    ms_last: float | None
    carried_from: str | None
    sell_rate_hs: float | None
    sell_rate_ms: float | None
    oil_rates: dict[str, float | None]
    oil_openings: dict[str, float | None]
    oil_labels: dict[str, str]


# ---------------------------------------------------------------------------- helpers


def _row_to_out(row: sqlite3.Row) -> EntryOut:
    return EntryOut(
        id=row["id"],
        shift_date=row["shift_date"],
        pump_serial=row["pump_serial"],
        pump_status=row["pump_status"],
        submitted_by=row["submitted_by"],
        entry_mode=row["entry_mode"],
        sell_rate_hs=row["sell_rate_hs"],
        sell_rate_ms=row["sell_rate_ms"],
        hs_last=row["hs_last"],
        ms_last=row["ms_last"],
        gas_total=row["gas_total"],
        oil_total=row["oil_total"],
        net_bal_hand_off=row["net_bal_hand_off"],
        payload=json.loads(row["payload"]),
        result=json.loads(row["result"]),
        last_updated_by=row["last_updated_by"],
        last_updated_at=row["last_updated_at"],
    )


def _apply_locked_context(
    conn: sqlite3.Connection,
    payload: dict,
    shift_date: str,
    pump_serial: str,
    entry_mode: str = "manual",
) -> tuple[dict, dict]:
    """Overlay carried Last Shift Readings and locked Sell/oil rates onto the payload.

    For a MANUAL entry, Last Shift Reading is backend-owned: it carries yesterday's
    Current Reading forward so nobody retypes a meter reading (SDD 7.7), and a
    client-supplied value is ignored. The very first entry ever made for a pump has
    no carry source, so the operator's own reading is kept and normalized instead.

    For an IMPORTED entry (``entry_mode`` "excel" or "ocr") the reading is taken
    from the sheet, verbatim. The station filled that sheet in; it is the source
    document, and carrying a different figure over the top of it silently
    replaces evidence with a guess.

    That is not hypothetical. On the remote PC, 2026-09-18, the SEP15 road DSR was
    imported into a database that still held the Sep 9/10/12 rounds. The sheet
    said Last Shift 1,489,759.27 and Cons 284.48; the carry-forward overwrote it
    with 267,841.93 from an unrelated meter baseline, and the form showed a
    consumption of 1,222,201.82 litres and a total of Rs 128,771,183.75. Nothing
    warned, because as far as the code was concerned it was doing its job.

    Returns ``(payload, meta)``.
    """
    rates = latest_effective_rates(conn, shift_date)
    hs_rate = rates["HS"]["sell_rate"] if "HS" in rates else None
    ms_rate = rates["MS"]["sell_rate"] if "MS" in rates else None
    # The item list is data now (oil_item, migration 0023), so read it per call
    # rather than from a constant - the Owner can add or retire a row at any time.
    items = oil_items.active_items(conn)
    oil_rates = {i.key: (rates[i.key]["sell_rate"] if i.key in rates else None) for i in items}
    oil_openings = on_hand_map(conn)  # Opening Stock pulled from Inventory Tracking

    from_sheet = entry_mode != "manual"
    carried = carried_last_readings(conn, pump_serial, shift_date)

    payload = json.loads(json.dumps(payload))  # deep copy
    payload.setdefault("hs", {})
    payload.setdefault("ms", {})
    # Last Shift Reading, in one rule:
    #
    #   manual entry      the app owns it - yesterday's Current Reading carries
    #                     forward so nobody re-keys a meter (SDD 7.7).
    #   imported sheet    the sheet owns it, IF it printed one. The station
    #                     filled that sheet in; it is the source document.
    #   imported blank    a form the app itself printed for this pump has the
    #                     cell EMPTY, so there is nothing to transcribe and the
    #                     carry-forward supplies it - last morning's Current
    #                     Reading (client, 2026-09-18).
    #
    # The last case is why this is a fallback and not a flat "never carry on an
    # import": Print Blank for Entry exists precisely so the station can fill a
    # form by hand, and those forms come back with Current filled and Last empty.
    for fuel in ("hs", "ms"):
        carried_value = getattr(carried, fuel)
        from_cell = _num(payload[fuel].get("last"))
        if from_sheet:
            payload[fuel]["last"] = from_cell if from_cell is not None else carried_value
        elif carried_value is not None:
            payload[fuel]["last"] = carried_value
        else:
            # The first entry ever made for a pump has nothing to carry, so the
            # operator's own reading is kept rather than wiped to blank.
            payload[fuel]["last"] = from_cell
    # Same rule as the reading and as the oil Rate below: an imported sheet keeps
    # the rate it prints, and only a blank cell falls back to Rate Master. A
    # manual entry always takes the locked rate.
    for fuel, locked in (("hs", hs_rate), ("ms", ms_rate)):
        submitted = _num(payload[fuel].get("rate")) if from_sheet else None
        payload[fuel]["rate"] = submitted if submitted is not None else locked

    # Match submitted rows to items by their own LABEL, not by position: the form
    # the operator submitted from may be a row out of date with this one if an item
    # was added or retired between the page loading and the save.
    submitted = oil_items.oils_by_key(conn, payload.get("oils"))
    oils = payload.get("oils") or []
    normalized = []
    for item in items:
        key = item.key
        src = submitted.get(key) or {}
        manual_opening = _num(src.get("opening"))
        manual_rate = _num(src.get("rate"))
        normalized.append(
            {
                "label": item.label,
                "qty": src.get("qty"),
                # Oil Rate comes from the submitted form/sheet when given, else
                # Rate Master (client-confirmed 2026-09-11: the sheet's rate is
                # authoritative for oils). Unlike Gas Rate, which stays fully
                # backend-locked, oil rates vary per delivery and the paper form
                # records the one that actually applied on the day.
                "rate": manual_rate if manual_rate is not None else oil_rates[key],
                # Opening Stock defaults to the tracked Inventory on_hand, but the
                # submitter can override it by hand (short-term fix, 2026-09-11):
                # oil sales are handled by only one person on a given day, so on a
                # day the OTHER submission's Oil Sale(s) is blank there's nothing
                # to correct it from but a manual entry, pending a proper
                # day-close sync between Daily Sales Entry and Inventory Tracking.
                "opening": manual_opening if manual_opening is not None else oil_openings.get(key),
            }
        )
    # Keep any row the operator added ad-hoc that is not a registered item - it
    # carries its own label, rate and opening.
    #
    # Identity, not label: oils_by_key() falls back to POSITION for a row with no
    # label, so an unlabelled row is already consumed as items[n] above. Filtering
    # on "label not known" let every unlabelled row through a second time and
    # doubled the day's Oil Total - it put SEP12's Section 1 Total Sale Amt at
    # 4,601.21 against the sheet's 4,185.2135, out by exactly the 416 oil total.
    consumed = {id(r) for r in submitted.values()}
    normalized.extend(
        r for i, r in enumerate(oils)
        if isinstance(r, dict) and id(r) not in consumed and i >= len(items)
    )
    payload["oils"] = normalized

    meta = {
        "sell_rate_hs": hs_rate,
        "sell_rate_ms": ms_rate,
        "oil_rates": oil_rates,
        "oil_openings": oil_openings,
        "carried_from": carried.source_date,
    }
    return payload, meta


# ----------------------------------------------------------------------------- routes


@router.post("/calc")
def calc(body: CalcRequest, _: Principal = Depends(get_principal)) -> dict:
    """Stateless recompute. The renderer calls this on input so it never owns math."""
    return compute_payload(body.model_dump())


@router.get("/prefill", response_model=PrefillOut)
def prefill(
    pump_serial: str,
    shift_date: str | None = None,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> PrefillOut:
    sd = shift_date or date.today().isoformat()
    _, meta = _apply_locked_context(conn, {}, sd, pump_serial)
    return PrefillOut(
        shift_date=sd,
        pump_serial=pump_serial,
        hs_last=carried_last_readings(conn, pump_serial, sd).hs,
        ms_last=carried_last_readings(conn, pump_serial, sd).ms,
        carried_from=meta["carried_from"],
        sell_rate_hs=meta["sell_rate_hs"],
        sell_rate_ms=meta["sell_rate_ms"],
        oil_rates=meta["oil_rates"],
        oil_openings=meta["oil_openings"],
        oil_labels={i.key: i.label for i in oil_items.active_items(conn)},
    )


@router.post("/sync-inventory")
def sync_inventory(
    shift_date: str | None = None,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Set Inventory Tracking's on_hand for each oil item from the most recent
    real Closing Stock recorded before ``shift_date`` (2026-09-11 "Print & Sync"
    feature). Manager/Owner only - it writes to Inventory Tracking, the same
    access as that module itself; a Sales user still has plain Print Blank.
    """
    sd = shift_date or date.today().isoformat()
    return sync_from_daily_sales(conn, sd, principal.login_name)


@router.get("/{entry_id}", response_model=EntryOut)
def get_entry(
    entry_id: int,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> EntryOut:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return _row_to_out(row)


@router.get("", response_model=list[EntryOut])
def list_entries(
    shift_date: str | None = None,
    pump_serial: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[EntryOut]:
    """Saved entries, newest first.

    ``shift_date`` pins one day (what the screen uses to reopen a day for
    editing); ``date_from``/``date_to`` select a range, for looking up history
    without re-keying it (client-required 2026-09-11 - previously a saved day
    could only be reached by landing on its exact date).
    """
    clauses, params = [], []
    if shift_date:
        clauses.append("shift_date = ?")
        params.append(shift_date)
    if date_from:
        clauses.append("shift_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("shift_date <= ?")
        params.append(date_to)
    if pump_serial:
        clauses.append("pump_serial = ?")
        params.append(pump_serial)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM {TABLE}{where} ORDER BY shift_date DESC, id DESC LIMIT ?",
        [*params, max(1, min(limit, 1000))],
    ).fetchall()
    return [_row_to_out(r) for r in rows]


def _reject_backwards_readings(result: dict, payload: dict) -> None:
    """A pump meter only ever counts up, so a Current Reading below the Last Shift
    Reading is always a data error - never a real day.

    Client, 2026-09-13: "Pump Reading always monitored by IOCL Remotely and always
    moving forward never goes back no matter what... if you need to reset it should
    be taken care by strictly IOCL, lot of govt regulations."

    Worth refusing rather than warning: nothing downstream questions a negative. A
    transposed pair of readings in testing produced a gas total of
    -234,448,737.88 and every total, the Summary and Trial Balance Section 3
    carried it through without a murmur.
    """
    bad = []
    for fuel, name in (("hs", "Diesel (HS)"), ("ms", "Petrol (MS)")):
        cons = (result.get(fuel) or {}).get("cons")
        if cons is not None and cons < 0:
            f = payload.get(fuel) or {}
            bad.append(
                f"{name}: Current Reading {f.get('current')} is below the Last Shift "
                f"Reading {f.get('last')} ({cons:g} litres)"
            )
    if bad:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A pump meter cannot run backwards - "
            + "; ".join(bad)
            + ". Check the reading; a genuine meter reset has to come from IOCL.",
        )


@router.post("", response_model=EntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: EntryCreate,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> EntryOut:
    shift_date = body.shift_date or date.today().isoformat()

    # One entry per pump per shift per submitter (SDD 5.4). A correction edits
    # that row (PUT), it does not stack a second one.
    dup = conn.execute(
        f"SELECT id FROM {TABLE} WHERE shift_date = ? AND pump_serial = ? AND submitted_by = ?",
        (shift_date, body.pump_serial, principal.login_name),
    ).fetchone()
    if dup is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You already have an entry for {body.pump_serial} on {shift_date} "
            f"(#{dup['id']}) - edit that one instead of creating another.",
        )

    raw = body.model_dump(exclude={"shift_date", "pump_serial", "entry_mode"})
    payload, meta = _apply_locked_context(
        conn, raw, shift_date, body.pump_serial, body.entry_mode
    )
    result = compute_payload(payload)
    if body.pump_status != "repair":
        _reject_backwards_readings(result, payload)

    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {TABLE} (
                shift_date, pump_serial, submitted_by, entry_mode,
                hs_current, ms_current, hs_last, ms_last,
                sell_rate_hs, sell_rate_ms, oil_rates_json,
                gas_total, oil_total, expenses_total, net_bal_hand_off,
                payload, result, last_updated_by, pump_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shift_date,
                body.pump_serial,
                principal.login_name,
                body.entry_mode,
                _num(payload["hs"].get("current")),
                _num(payload["ms"].get("current")),
                meta_last(payload, "hs"),
                meta_last(payload, "ms"),
                meta["sell_rate_hs"],
                meta["sell_rate_ms"],
                json.dumps(meta["oil_rates"]),
                result["gas_total"],
                result["oil_total"],
                result["expenses_total"],
                result["net_bal_hand_off"],
                json.dumps(payload),
                json.dumps(result),
                principal.login_name,
                body.pump_status,
            ),
        )
        entry_id = cur.lastrowid
        record_write(
            conn,
            table=TABLE,
            record_id=entry_id,
            action="create",
            actor=principal.login_name,
            new={
                "shift_date": shift_date,
                "pump_serial": body.pump_serial,
                "net_bal_hand_off": result["net_bal_hand_off"],
            },
        )
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    return _row_to_out(row)


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(
    entry_id: int,
    body: EntryCreate,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> EntryOut:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    # Sales may only edit their own submission (SDD 4.2).
    if principal.role == "Sales" and row["submitted_by"] != principal.login_name:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Sales users can only edit their own submission"
        )

    shift_date = body.shift_date or row["shift_date"]
    # An edit keeps the row's own provenance: re-saving an imported sheet must not
    # quietly turn it into a manual entry and pull the carry-forward back over the
    # readings that came off the sheet.
    entry_mode = body.entry_mode if body.entry_mode != "manual" else row["entry_mode"]
    raw = body.model_dump(exclude={"shift_date", "pump_serial", "entry_mode"})
    payload, meta = _apply_locked_context(
        conn, raw, shift_date, body.pump_serial, entry_mode
    )
    result = compute_payload(payload)
    if body.pump_status != "repair":
        _reject_backwards_readings(result, payload)
    old_snapshot = {
        "net_bal_hand_off": row["net_bal_hand_off"],
        "payload": json.loads(row["payload"]),
    }

    with transaction(conn):
        conn.execute(
            f"""
            UPDATE {TABLE} SET
                shift_date = ?, pump_serial = ?,
                hs_current = ?, ms_current = ?, hs_last = ?, ms_last = ?,
                sell_rate_hs = ?, sell_rate_ms = ?, oil_rates_json = ?,
                gas_total = ?, oil_total = ?, expenses_total = ?, net_bal_hand_off = ?,
                payload = ?, result = ?, pump_status = ?,
                last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (
                shift_date,
                body.pump_serial,
                _num(payload["hs"].get("current")),
                _num(payload["ms"].get("current")),
                meta_last(payload, "hs"),
                meta_last(payload, "ms"),
                meta["sell_rate_hs"],
                meta["sell_rate_ms"],
                json.dumps(meta["oil_rates"]),
                result["gas_total"],
                result["oil_total"],
                result["expenses_total"],
                result["net_bal_hand_off"],
                json.dumps(payload),
                json.dumps(result),
                body.pump_status,
                principal.login_name,
                entry_id,
            ),
        )
        record_write(
            conn,
            table=TABLE,
            record_id=entry_id,
            action="update",
            actor=principal.login_name,
            old=old_snapshot,
            new={"net_bal_hand_off": result["net_bal_hand_off"]},
        )
        note = reverify_summary_for_entry(
            conn, shift_date, body.pump_serial, principal.login_name
        )
    out = _row_to_out(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone())
    out.summary_note = note
    return out


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    with transaction(conn):
        conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (entry_id,))
        record_write(
            conn,
            table=TABLE,
            record_id=entry_id,
            action="delete",
            actor=principal.login_name,
            old={
                "shift_date": row["shift_date"],
                "pump_serial": row["pump_serial"],
                "net_bal_hand_off": row["net_bal_hand_off"],
            },
        )


@router.get("/ocr/status")
def ocr_status(_: Principal = Depends(get_principal)) -> dict:
    """Whether the bundled Tesseract (SDD ADR-6) is present and runnable.

    Lets the post-install / clean-VM check confirm OCR shipped without a real
    scan. `bundled` is False in dev (no SVR_TESSERACT_CMD, no tesseract on PATH).
    """
    version = tesseract_version()
    cmd = get_settings().resolved_tesseract_cmd()
    return {
        "bundled": version is not None,
        "cmd": cmd,
        "version": version,
        # Draft-assist only: stock Tesseract does not read the handwritten forms
        # reliably (see docs/.../OCR-findings-2026-09-09.md). Every field is
        # flagged and nothing is saved without human review (SDD ADR-5).
        "pipeline": "draft-assist",
    }


@router.post("/ocr")
async def ocr_upload(
    file: UploadFile = File(...), _: Principal = Depends(get_principal)
) -> dict:
    """Draft from an uploaded Daily Sales Report.

    A typed / machine-generated PDF is read from its **text layer** (reliable). A
    scan/photo goes through Tesseract (handwriting is unreliable - draft only).
    Either way: never saves, recomputes every total, one review before Save
    (SDD ADR-5).
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    try:
        res = ocr_pipeline.extract(raw, file.filename or "")
    except ocr_pipeline.EngineUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {
        "payload": res.payload,
        "meta": {},  # operator picks pump + date; the scan's own values are unreliable
        "result": compute_payload(res.payload),
        "fields": [
            {"key": f.key, "value": f.value, "confidence": f.confidence, "raw": f.raw}
            for f in res.fields
        ],
        "warnings": res.warnings,
        "engine": res.engine,
        "page_text": res.page_text,
    }


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/import-excel/template")
def import_excel_template(
    pump_serial: str | None = None, _: Principal = Depends(get_principal)
) -> Response:
    """A blank .xlsx to fill offline and feed back through POST /import-excel."""
    return _xlsx_response(blank_template(pump_serial), "SVR-DailySalesEntry-template.xlsx")


@router.post("/import-excel")
async def import_excel(
    file: UploadFile = File(...),
    pump_serial: str | None = None,
    _: Principal = Depends(get_principal),
) -> dict:
    """Parse an uploaded .xlsx into a form payload for human review (SDD ADR-5).

    Does NOT save. The engine recomputes every total; `warnings` flags any cell
    whose value disagreed with the recomputed one. The reviewer edits + Saves
    through the normal POST/PUT path, which re-locks rates/readings.

    ``pump_serial`` is the Pump Serial Number currently selected on the form -
    used only to pick the right sheet out of a multi-pump workbook (one file
    with both a Road and an Office sheet); the parsed payload never trusts an
    in-file pump serial for identity (SDD, "everything is keyed by Pump Serial
    Number" - confirmed 2026-09-11).
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    try:
        payload, meta, warnings = parse_workbook(raw, pump_serial=pump_serial)
    except HTTPException:
        raise
    except Exception as exc:  # surface any openpyxl parse failure as a 400
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Could not read the spreadsheet: {exc}"
        ) from exc
    return {
        "payload": payload,
        "meta": meta,
        "result": compute_payload(payload),
        "warnings": warnings,
    }


@router.get("/{entry_id}/export-excel")
def export_excel(
    entry_id: int,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> Response:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    data = build_workbook(
        {
            "shift_date": row["shift_date"],
            "pump_serial": row["pump_serial"],
            "submitted_by": row["submitted_by"],
            "entry_mode": row["entry_mode"],
            "payload": json.loads(row["payload"]),
            "result": json.loads(row["result"]),
        }
    )
    name = f"SVR-DSE-{row['shift_date']}-{row['pump_serial']}.xlsx"
    return _xlsx_response(data, name)


# ------------------------------------------------------------------------- tiny utils


def _num(value) -> float | None:
    from svr_backend.calc.amounts import is_blank, parse_amt

    return None if is_blank(value) else parse_amt(value)


def meta_last(payload: dict, fuel: str) -> float | None:
    return payload.get(fuel, {}).get("last")
