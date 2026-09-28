"""Correcting Section 1's IOCL Last/Current on an already-closed day, behind the
same Owner passphrase every gated form shares (client, 2026-09-28: a new fuel
load changes the reading, unlike Daily Sales' own meter which only runs
forward; Trial Balance is a daily snapshot, "like a bank trial balance", so
this touches ONLY Section 1 and what's derived from it - never Credit/
Remittance or Expense status, already posted or not)."""

from __future__ import annotations

DATE = "2026-10-12"
SECRET = "load-arrived-2026"


def _set_secret(client, auth_headers):
    r = client.post("/owner-reset/secret", json={"new_passphrase": SECRET},
                    headers=auth_headers("Owner"))
    assert r.status_code == 200, r.text[:200]


def _finalized_day(client, auth_headers):
    client.post("/daily-sales-entry", json={
        "pump_serial": "12BC4523V-RD", "shift_date": DATE,
        "hs": {"current": "30"}, "ms": {"current": "15"},
    }, headers=auth_headers("Sales"))
    client.put(f"/daily-trial-balance/{DATE}",
               json={"s1_hs_yesterday": 100, "s1_hs_current": 60,
                     "s1_ms_yesterday": 200, "s1_ms_current": 190},
               headers=auth_headers("Manager"))
    fin = client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"


def test_refused_without_a_passphrase_configured(client, auth_headers):
    _finalized_day(client, auth_headers)
    r = client.post(f"/daily-trial-balance/{DATE}/correct-iocl-readings",
                     json={"passphrase": "anything", "hs_current": 65, "reason": "new load"},
                     headers=auth_headers("Manager"))
    assert r.status_code == 409


def test_wrong_passphrase_refused(client, auth_headers):
    _finalized_day(client, auth_headers)
    _set_secret(client, auth_headers)
    r = client.post(f"/daily-trial-balance/{DATE}/correct-iocl-readings",
                     json={"passphrase": "wrong", "hs_current": 65, "reason": "new load"},
                     headers=auth_headers("Manager"))
    assert r.status_code == 403


def test_sales_cannot_even_attempt_it(client, auth_headers):
    _finalized_day(client, auth_headers)
    _set_secret(client, auth_headers)
    r = client.post(f"/daily-trial-balance/{DATE}/correct-iocl-readings",
                     json={"passphrase": SECRET, "hs_current": 65, "reason": "new load"},
                     headers=auth_headers("Sales"))
    assert r.status_code == 403


def test_reason_is_required(client, auth_headers):
    _finalized_day(client, auth_headers)
    _set_secret(client, auth_headers)
    r = client.post(f"/daily-trial-balance/{DATE}/correct-iocl-readings",
                     json={"passphrase": SECRET, "hs_current": 65},
                     headers=auth_headers("Manager"))
    assert r.status_code == 422


def test_corrects_section1_and_recomputes_without_touching_postings_or_status(
    client, auth_headers, conn
):
    _finalized_day(client, auth_headers)
    _set_secret(client, auth_headers)

    # A credit and an expense, already posted for this same date - these must
    # come out the other side completely untouched.
    credit = client.post("/credit-master/credit", json={
        "creditor_name": "QA Correction Creditor", "ltrs": 10, "rate": 100, "amount": 1000,
    }, headers=auth_headers("Manager")).json()
    expense_cat = next(
        c["id"] for c in client.get("/expenses/categories", headers=auth_headers("Manager")).json()
        if c["kind"] == "operational"
    )
    expense = client.post("/expenses", json={
        "category_id": expense_cat, "amount": 500, "expense_date": DATE,
    }, headers=auth_headers("Manager")).json()

    r = client.post(f"/daily-trial-balance/{DATE}/correct-iocl-readings", json={
        "passphrase": SECRET, "hs_current": 65, "reason": "new HS load arrived after close",
    }, headers=auth_headers("Manager"))
    assert r.status_code == 200, r.text[:300]
    view = r.json()

    # Still finalized - never un-locked, never reopened.
    assert view["status"] == "finalized"
    # Section 1 shows the corrected reading and Section 6's stock value (60 -> 65 L
    # x Buy Rate 102.75) has genuinely recomputed off it.
    hs = view["computed"]["section1"]["hs"]
    assert hs["stock_ltrs"] == 65
    assert view["computed"]["section6"]["hs_amount"] == round(65 * 102.75, 2)

    # The credit and the expense are untouched - same amount, same id, still there.
    credit_after = conn.execute(
        "SELECT status, amount FROM credit_transaction WHERE id = ?", (credit["id"],)
    ).fetchone()
    assert credit_after["amount"] == 1000
    assert credit_after["status"] == "manual"  # unchanged - never re-posted or un-posted

    expense_after = conn.execute(
        "SELECT amount FROM monthly_expense WHERE id = ?", (expense["id"],)
    ).fetchone()
    assert expense_after["amount"] == 500

    # The correction itself is audited, with the reason on file.
    row = conn.execute(
        "SELECT new_value FROM audit_log WHERE table_name='daily_trial_balance' "
        "AND new_value LIKE '%iocl_reading%' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert "new HS load arrived after close" in row["new_value"]


def test_next_day_carry_forward_is_left_as_already_seeded(client, auth_headers):
    """The client's own call: keep this simple, don't cascade or re-check later
    days - Trial Balance is a daily snapshot. Confirms the correction does not
    touch a later day at all, even though that day's own opening figure was
    seeded from the now-corrected value."""
    _finalized_day(client, auth_headers)
    _set_secret(client, auth_headers)
    next_date = "2026-10-13"
    before = client.get(f"/daily-trial-balance/{next_date}", headers=auth_headers("Manager")).json()

    client.post(f"/daily-trial-balance/{DATE}/correct-iocl-readings", json={
        "passphrase": SECRET, "hs_current": 999, "reason": "new load",
    }, headers=auth_headers("Manager"))

    after = client.get(f"/daily-trial-balance/{next_date}", headers=auth_headers("Manager")).json()
    assert before == after
