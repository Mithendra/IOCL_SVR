"""A brand-new Daily Sales Entry expense line item - not one of the three
printed rows - flows through to Daily Trial Balance and posts to Monthly
Expenses, auto-creating the category if it doesn't already exist there
(client, 2026-09-30: "if the expense type does not exists in expense master
it should accept and define that new line which was define is DS should be
taken by default"). Beta/Testing/Density stays excluded throughout, exactly
as decided the same day.
"""

from __future__ import annotations

DATE = "2026-10-10"
NEW_LABEL = "Vehicle Repair - Brand New Line"


def _seed_entry(client, auth_headers):
    return client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": "11CC2012V-OFF",
            "shift_date": DATE,
            "hs": {"current": "1"},
            "expenses": ["1000", "150", "20000", "500"],
            "expense_labels": [
                "Daily Diesel(5L) & Petrol(5L) + Density Testing + Beta",
                "Any Other Expenses",
                "Last Night Cash Hand-off Person's Name-Signature-Amount",
                NEW_LABEL,
            ],
        },
        headers=auth_headers("Sales"),
    )


def test_new_line_item_is_pulled_but_beta_testing_and_night_cash_are_not(
    client, auth_headers, conn
):
    _seed_entry(client, auth_headers)
    view = client.put(f"/daily-trial-balance/{DATE}", json={}, headers=auth_headers("Manager")).json()
    pulled = view["computed"]["derived"]["section4"]["pulled_dse_expenses"]
    labels = {r["label"] for r in pulled}
    assert labels == {"Any Other Expenses", NEW_LABEL}
    amounts = {r["label"]: r["amount"] for r in pulled}
    assert amounts[NEW_LABEL] == 500.0

    row = conn.execute(
        "SELECT status FROM trial_balance_posting WHERE shift_date = ? AND label = ?",
        (DATE, NEW_LABEL),
    ).fetchone()
    assert row is not None
    assert row["status"] == "not_posted"

    assert conn.execute(
        "SELECT 1 FROM expense_category WHERE name = ?", (NEW_LABEL,)
    ).fetchone() is None


def test_posting_it_auto_creates_the_category_by_the_ds_defined_name(client, auth_headers, conn):
    _seed_entry(client, auth_headers)
    client.put(f"/daily-trial-balance/{DATE}", json={}, headers=auth_headers("Manager"))

    r = client.post(f"/daily-trial-balance/{DATE}/post", headers=auth_headers("Manager"))
    assert r.status_code == 200

    category = conn.execute(
        "SELECT id, kind FROM expense_category WHERE name = ?", (NEW_LABEL,)
    ).fetchone()
    assert category is not None, "posting should auto-create the category from the DS label"
    assert category["kind"] == "operational"

    expense = conn.execute(
        "SELECT amount FROM monthly_expense WHERE category_id = ? AND expense_date = ?",
        (category["id"], DATE),
    ).fetchone()
    assert expense is not None
    assert expense["amount"] == 500.0

    # Beta/Testing/Density never got its own category or expense line.
    assert conn.execute(
        "SELECT 1 FROM expense_category WHERE name LIKE 'Daily Diesel%'"
    ).fetchone() is None
