"""Daily Sales Entry API: calc endpoint, create with locked context, RBAC on delete,
and audit on every write (SDD 4.2 / 7.3 / 13.4).
"""

from __future__ import annotations

PUMP = "12BC4523V-RD"


def _entry_body(**over):
    body = {
        "pump_serial": PUMP,
        "shift_date": "2026-08-12",
        "hs": {"current": "1317.52"},
        "ms": {"current": "1000"},
        "oils": [{"qty": "4"}],
        "expenses": ["500+100=600"],
        "credit_card_amounts": ["1000"],
        "new_credits": [{"ltrs": "10", "rate": "105.36"}],
        "night_cash": "5000",
    }
    body.update(over)
    return body


def test_calc_endpoint_uses_engine(client, auth_headers):
    resp = client.post(
        "/daily-sales-entry/calc",
        json={"hs": {"current": "1317.52", "last": "0", "rate": "105.36"}},
        headers=auth_headers("Sales"),
    )
    assert resp.status_code == 200
    # 1317.52 x 105.36 = 138813.9072 exactly; row amounts are truncated to paise
    # the way the station's own forms do (trunc2, 2026-09-11).
    assert resp.json()["hs"]["amount"] == 138813.90


def test_create_locks_sell_rates_and_carried_last_reading(client, auth_headers, conn):
    # Prior day establishes the carry-forward source.
    client.post(
        "/daily-sales-entry",
        json=_entry_body(shift_date="2026-08-11", hs={"current": "1300"}, ms={"current": "900"}),
        headers=auth_headers("Sales"),
    )
    resp = client.post(
        "/daily-sales-entry", json=_entry_body(), headers=auth_headers("Sales")
    )
    assert resp.status_code == 201, resp.text
    row = resp.json()
    # Seeded Sell Rates from migration 0001 (HS 105.36 / MS 117.70), not client input.
    assert row["sell_rate_hs"] == 105.36
    assert row["sell_rate_ms"] == 117.7
    # Last Shift Reading carried from the 2026-08-11 entry's Current Reading.
    assert row["hs_last"] == 1300.0
    assert row["ms_last"] == 900.0
    # Consumption uses the carried last reading: 1317.52 - 1300 = 17.52
    assert row["result"]["hs"]["cons"] == 17.52
    assert row["entry_mode"] == "manual"
    assert row["last_updated_by"] == "sales"

    audit = conn.execute(
        "SELECT * FROM audit_log WHERE table_name = 'daily_sales_entry' AND action = 'create'"
    ).fetchall()
    assert len(audit) == 2  # both creates logged


def test_client_cannot_override_locked_rate(client, auth_headers):
    resp = client.post(
        "/daily-sales-entry",
        json=_entry_body(hs={"current": "1317.52", "rate": "999"}),
        headers=auth_headers("Sales"),
    )
    assert resp.json()["sell_rate_hs"] == 105.36  # client's 999 ignored


def test_first_entry_for_a_pump_accepts_a_manual_last_shift_reading(client, auth_headers):
    # No prior entry exists anywhere for this pump - nothing to carry - so the
    # operator's own Last Shift Reading is trusted instead of being wiped blank.
    resp = client.post(
        "/daily-sales-entry",
        json=_entry_body(hs={"current": "1317.52", "last": "1300"}, ms={"current": "1000", "last": "900"}),
        headers=auth_headers("Sales"),
    )
    assert resp.status_code == 201, resp.text
    row = resp.json()
    assert row["hs_last"] == 1300.0
    assert row["ms_last"] == 900.0
    assert row["result"]["hs"]["cons"] == 17.52  # 1317.52 - 1300, not blank


def test_oil_opening_stock_can_be_manually_overridden(client, auth_headers):
    # Oil sales are handled by only one person on a given day (2026-09-11
    # short-term fix) - the submitter can correct Opening Stock by hand instead
    # of always trusting the Inventory Tracking on_hand snapshot.
    resp = client.post(
        "/daily-sales-entry",
        json=_entry_body(oils=[{"qty": "4", "opening": "500"}]),
        headers=auth_headers("Sales"),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["payload"]["oils"][0]["opening"] == 500.0
    assert body["result"]["oils"][0]["closing"] == 496.0  # 500 - 4, not the Inventory default


def test_oil_opening_stock_defaults_to_inventory_when_left_blank(client, auth_headers):
    resp = client.post(
        "/daily-sales-entry", json=_entry_body(oils=[{"qty": "4"}]), headers=auth_headers("Sales")
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["payload"]["oils"][0]["opening"] is not None  # the Inventory default, not blank


def test_delete_requires_manager_or_owner(client, auth_headers, conn):
    created = client.post(
        "/daily-sales-entry", json=_entry_body(), headers=auth_headers("Sales")
    ).json()
    eid = created["id"]

    assert client.delete(f"/daily-sales-entry/{eid}", headers=auth_headers("Sales")).status_code == 403
    assert (
        client.delete(f"/daily-sales-entry/{eid}", headers=auth_headers("Manager")).status_code
        == 204
    )
    assert conn.execute(
        "SELECT COUNT(*) c FROM daily_sales_entry WHERE id = ?", (eid,)
    ).fetchone()["c"] == 0
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE record_id = ? AND action = 'delete'", (str(eid),)
    ).fetchone()["c"] == 1


def test_sales_cannot_edit_another_users_submission(client, auth_headers, conn):
    created = client.post(
        "/daily-sales-entry", json=_entry_body(), headers=auth_headers("Sales")
    ).json()
    # Reassign the submission to someone else, then Sales tries to PUT it.
    conn.execute(
        "UPDATE daily_sales_entry SET submitted_by = 'someone_else' WHERE id = ?", (created["id"],)
    )
    resp = client.put(
        f"/daily-sales-entry/{created['id']}", json=_entry_body(), headers=auth_headers("Sales")
    )
    assert resp.status_code == 403


def test_prefill_returns_carried_readings_and_rates(client, auth_headers):
    client.post(
        "/daily-sales-entry",
        json=_entry_body(shift_date="2026-08-11", hs={"current": "1280"}, ms={"current": "870"}),
        headers=auth_headers("Sales"),
    )
    resp = client.get(
        "/daily-sales-entry/prefill",
        params={"pump_serial": PUMP, "shift_date": "2026-08-12"},
        headers=auth_headers("Sales"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["hs_last"] == 1280.0
    assert body["carried_from"] == "2026-08-11"
    assert body["sell_rate_hs"] == 105.36
    assert set(body["oil_labels"]) == {"oil1", "oil2", "oil3", "oil4", "oil5"}


def test_ocr_endpoint_needs_a_file(client, auth_headers):
    # /ocr and /import-excel are both implemented (draft-assist / full). Without a
    # file part FastAPI rejects the request before any engine work.
    r = client.post("/daily-sales-entry/ocr", headers=auth_headers("Sales"))
    assert r.status_code == 422
    # Full OCR behaviour is in test_ocr_pipeline.py (skipped where Tesseract is absent).


# ----------------------------------------------- one entry per pump/date/submitter


def test_second_create_for_same_pump_date_user_is_409(client, auth_headers):
    h = auth_headers("Sales")
    first = client.post("/daily-sales-entry", json=_entry_body(), headers=h)
    assert first.status_code == 201
    dup = client.post("/daily-sales-entry", json=_entry_body(hs={"current": "1400"}), headers=h)
    assert dup.status_code == 409
    assert str(first.json()["id"]) in dup.json()["detail"]  # points at the row to edit


def test_same_pump_date_different_submitter_is_allowed(client, auth_headers):
    assert (
        client.post("/daily-sales-entry", json=_entry_body(), headers=auth_headers("Sales"))
        .status_code
        == 201
    )
    assert (
        client.post("/daily-sales-entry", json=_entry_body(), headers=auth_headers("Manager"))
        .status_code
        == 201
    )


def test_correction_via_put_updates_the_same_row(client, auth_headers, conn):
    h = auth_headers("Sales")
    eid = client.post("/daily-sales-entry", json=_entry_body(), headers=h).json()["id"]
    upd = client.put(
        f"/daily-sales-entry/{eid}", json=_entry_body(hs={"current": "1400"}), headers=h
    )
    assert upd.status_code == 200 and upd.json()["id"] == eid
    n = conn.execute(
        "SELECT COUNT(*) c FROM daily_sales_entry WHERE pump_serial = ? AND shift_date = ?",
        (PUMP, "2026-08-12"),
    ).fetchone()["c"]
    assert n == 1
