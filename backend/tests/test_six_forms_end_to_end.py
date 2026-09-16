"""The three dependent forms, seen from the Trial Balance that feeds them.

Client, 2026-09-15: "Credit/Remittance form, Expenses Master, Inventory Tracking
Master - above all three forms are tied up with Trial balance."

Each of them has its own tests already. What none of them covered is the join:
a line posted at Close & Sign Off has to actually appear on the master form,
under the right name, in the right category, with the balance coming out right.
That is what a remote-PC tester will look at first.
"""

from __future__ import annotations

DAY = "2026-12-20"
NEXT = "2026-12-21"


def _trial_balance_day(client, auth_headers, date, manual):
    return client.put(
        f"/daily-trial-balance/{date}",
        json={"s1_hs_current": 60, "manual": manual},
        headers=auth_headers("Manager"),
    )


def test_a_posted_expense_appears_on_monthly_expenses(client, auth_headers):
    _trial_balance_day(client, auth_headers, DAY, {"section4": {"expenses": [
        {"category": "Power Bill", "amount": 8525.95},
        {"category": "Salary Advances Ravindra", "amount": 10000},
    ]}})
    client.post(f"/daily-trial-balance/{DAY}/post", headers=auth_headers("Manager"))

    body = client.get(f"/expenses?date_from={DAY}&date_to={DAY}",
                      headers=auth_headers("Manager")).json()
    by_name = {r["category"]: r for r in body["items"]}
    assert "Power Bill" in by_name, f"posted expense missing from the form: {body}"
    assert by_name["Power Bill"]["amount"] == 8525.95
    # The station's own wording is kept, and an advance files as payroll.
    assert "Salary Advances Ravindra" in by_name
    assert by_name["Salary Advances Ravindra"]["kind"] == "payroll"
    # It says where it came from, so nobody has to guess.
    assert DAY in by_name["Power Bill"]["description"]


def test_a_posted_credit_and_its_remittance_settle_on_the_creditor_summary(client, auth_headers):
    _trial_balance_day(client, auth_headers, DAY, {"section3": {"new_credits": [
        {"type": "AirTel Hari New Credit", "amount": 11674},
    ]}})
    client.post(f"/daily-trial-balance/{DAY}/post", headers=auth_headers("Manager"))
    client.post(f"/daily-trial-balance/{DAY}/finalize", headers=auth_headers("Manager"))

    summary = client.get("/credit-master/summary", headers=auth_headers("Manager")).json()
    hari = next(r for r in summary if r["creditor_name"] == "AirTel Hari")
    assert hari["total_credit"] == 11674
    assert hari["outstanding"] == 11674, "nothing remitted yet"

    # A part payment the next day leaves the rest outstanding.
    _trial_balance_day(client, auth_headers, NEXT, {"section4": {"remittance": [
        {"type": "AirTel Hari Old Credit Remitted Amt", "amount": 4000},
    ]}})
    client.post(f"/daily-trial-balance/{NEXT}/post", headers=auth_headers("Manager"))

    summary = client.get("/credit-master/summary", headers=auth_headers("Manager")).json()
    hari = next(r for r in summary if r["creditor_name"] == "AirTel Hari")
    assert hari["total_remitted"] == 4000
    assert hari["outstanding"] == 7674, "11,674 less a 4,000 part payment"


def test_the_creditor_name_is_the_person_not_the_dropdown_label(client, auth_headers):
    """The Trial Balance list stores a whole phrase; the balance groups by NAME.
    Getting this wrong silently creates a second creditor - the same failure as
    two spellings of Anil."""
    _trial_balance_day(client, auth_headers, DAY, {"section3": {"new_credits": [
        {"type": "Anil/Nani New Credit", "amount": 1500},
        {"type": "Sajja Function Hall - New Credit", "amount": 5000},
    ]}})
    client.post(f"/daily-trial-balance/{DAY}/post", headers=auth_headers("Manager"))
    names = {r["creditor_name"] for r in
             client.get("/credit-master/summary", headers=auth_headers("Manager")).json()}
    assert "Anil/Nani" in names and "Sajja Function Hall" in names
    assert not any("New Credit" in n for n in names), f"labels leaked into names: {names}"


def test_inventory_tracking_shows_the_stock_sign_off_carried(client, auth_headers):
    """Sign-off sets on_hand from the day's real Closing Stock. The Inventory
    screen has to show that, or nobody can see what the app thinks is on the
    floor - which is how six of seven items sat wrong for weeks."""
    client.post("/daily-sales-entry", json={
        "pump_serial": "12BC4523V-RD", "shift_date": DAY,
        "hs": {"current": "9900000"}, "ms": {"current": "9900000"},
        "oils": [{"label": "2T/2.40 ML Total#", "qty": "4", "rate": "17", "opening": "30"}],
    }, headers=auth_headers("Manager"))
    _trial_balance_day(client, auth_headers, DAY, {})
    client.post(f"/daily-trial-balance/{DAY}/finalize", headers=auth_headers("Manager"))

    rows = client.get("/inventory", headers=auth_headers("Manager")).json()
    oil2 = next(r for r in rows if r["item_label"] == "2T/2.40 ML Total#")
    assert oil2["opening_stock"] == 26, "30 opening less 4 sold, carried at sign-off"


def test_reopening_takes_the_rows_back_off_both_master_forms(client, auth_headers):
    """The join that matters most for a tester: correcting a closed day must not
    leave a duplicate expense or a phantom debt behind."""
    _trial_balance_day(client, auth_headers, DAY, {
        "section4": {"expenses": [{"category": "Power Bill", "amount": 500}]},
        "section3": {"new_credits": [{"type": "Anil/Nani New Credit", "amount": 900}]},
    })
    client.post(f"/daily-trial-balance/{DAY}/post", headers=auth_headers("Manager"))
    client.post(f"/daily-trial-balance/{DAY}/finalize", headers=auth_headers("Manager"))

    def expense_count():
        return client.get(f"/expenses?date_from={DAY}&date_to={DAY}",
                          headers=auth_headers("Manager")).json()["count"]

    assert expense_count() == 1
    client.post(f"/daily-trial-balance/{DAY}/reopen", headers=auth_headers("Owner"))
    assert expense_count() == 0
    summary = client.get("/credit-master/summary", headers=auth_headers("Manager")).json()
    assert not any(r["creditor_name"] == "Anil/Nani" and r["outstanding"]
                   for r in summary), "a reopened day must not leave a phantom debt"
