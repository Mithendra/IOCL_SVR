"""Yearly Sales Report: FY (Apr-Mar) window, live aggregation from Daily Sales
Entry / Payroll / Monthly Expenses, manual COGS + commission merge, gross/net
math, RBAC (SDD 5.28)."""

from __future__ import annotations


def _seed_fy_2026(client, auth_headers):
    """Revenue in FY 2026-27, one entry in the NEXT FY (excluded), salaries + opex."""
    sh = auth_headers("Sales")
    mh = auth_headers("Manager")
    # inside FY 2026-27 - dated after the seeded Rate Master effective date so a
    # Sell Rate resolves (first entry for this pump: cons = 100).
    client.post("/daily-sales-entry", json={
        "pump_serial": "12BC4523V-RD", "shift_date": "2026-09-10",
        "hs": {"current": "100"}, "ms": {"current": "50"},
        "oils": [{"qty": "2"}, {}, {}, {}, {}],
    }, headers=sh)
    # next FY (Apr 2027 -> excluded from the 2026-27 report)
    client.post("/daily-sales-entry", json={
        "pump_serial": "12BC4523V-RD", "shift_date": "2027-05-01",
        "hs": {"current": "200"},
    }, headers=sh)
    # a payroll run paid inside the FY
    emp = client.post("/employees", json={"name": "R Report", "daily_wage": 500},
                      headers=mh).json()["id"]
    client.post("/payroll-runs", json={
        "period_start": "2026-04-01", "period_end": "2026-04-14", "pay_date": "2026-04-15",
        "lines": [{"employee_id": emp, "days_worked": 10}],
    }, headers=mh)
    # an operational expense inside the FY
    cats = client.get("/expenses/categories", headers=mh).json()
    ops = next(c["id"] for c in cats if c["kind"] == "operational")
    client.post("/expenses", json={"category_id": ops, "amount": 1200, "expense_date": "2026-06-01"},
                headers=mh)


def test_sales_has_no_access(client, auth_headers):
    assert client.get("/reports/yearly/2026", headers=auth_headers("Sales")).status_code == 403


def test_live_aggregation_respects_the_fy_window(client, auth_headers):
    _seed_fy_2026(client, auth_headers)
    rep = client.get("/reports/yearly/2026", headers=auth_headers("Manager")).json()

    assert rep["fy_label"] == "FY 2026-27"
    assert rep["period"] == {"start": "2026-04-01", "end": "2027-03-31"}
    # Only the 2026-09-10 entry counts (cons 100 x seeded HS sell rate 105.36).
    assert rep["live"]["hs_sales"] == 10536.0
    assert rep["live"]["ms_sales"] == 50 * 117.7
    assert rep["live"]["salaries_total"] == 5000  # 10 days x 500
    assert rep["live"]["operational_expenses_total"] == 1200
    assert len(rep["live"]["by_month"]) == 1
    assert rep["live"]["by_month"][0]["month"] == "2026-09"
    assert rep["disclaimer"].startswith("Summary for reference only")


def test_manual_cogs_and_commission_merge_into_net_profit(client, auth_headers):
    _seed_fy_2026(client, auth_headers)
    oh = auth_headers("Owner")

    assert client.put("/reports/yearly/2026", json={"cogs_opening": 100},
                      headers=auth_headers("Manager")).status_code == 403

    client.put("/reports/yearly/2026", json={
        "cogs_opening": 10000, "cogs_purchases": 500000, "cogs_closing": 12000,
        "hs_commission": 30000, "ms_commission": 20000,
    }, headers=oh)

    rep = client.get("/reports/yearly/2026", headers=oh).json()
    assert rep["cogs"] == 10000 + 500000 - 12000  # 498000
    assert rep["total_commission"] == 50000
    expected_gross = round(rep["live"]["total_revenue"] - 498000, 4)
    assert rep["gross_profit"] == expected_gross
    expected_net = round(
        expected_gross + 50000 - (rep["live"]["salaries_total"] + 1200), 4
    )
    assert rep["net_profit"] == expected_net
