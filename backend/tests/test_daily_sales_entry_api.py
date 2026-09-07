"""Daily Sales Entry API: calc endpoint, create with locked context, RBAC on delete,
and audit on every write (SDD 4.2 / 7.3 / 13.4).
"""

from __future__ import annotations

PUMP = "12BC4523V-OFF"


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
    assert resp.json()["hs"]["amount"] == 138813.9072


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


def test_ocr_endpoint_is_stubbed(client, auth_headers):
    # OCR recognition pipeline not built yet (engine is bundled - see test_ocr_status).
    assert client.post("/daily-sales-entry/ocr", headers=auth_headers("Sales")).status_code == 501
    # Excel import/export are implemented - see test_excel_daily_sales_entry.py.
