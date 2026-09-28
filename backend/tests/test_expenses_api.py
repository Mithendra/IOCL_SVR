"""Monthly Expenses: date-range + category filtering, category subtotals, RBAC,
Owner-only category creation, audit (SDD 5.15 / 5.19)."""

from __future__ import annotations


def _cat(client, headers, kind):
    cats = client.get("/expenses/categories", headers=headers).json()
    return next(c["id"] for c in cats if c["kind"] == kind)


def test_sales_has_no_access(client, auth_headers):
    assert client.get("/expenses", headers=auth_headers("Sales")).status_code == 403


def test_only_owner_adds_a_category(client, auth_headers):
    body = {"name": "Fuel Testing", "kind": "operational"}
    assert client.post("/expenses/categories", json=body, headers=auth_headers("Manager")).status_code == 403
    r = client.post("/expenses/categories", json=body, headers=auth_headers("Owner"))
    assert r.status_code == 201
    assert r.json()["kind"] == "operational"


def test_add_and_range_filter_is_inclusive(client, auth_headers, conn):
    h = auth_headers("Manager")
    ops = _cat(client, h, "operational")
    pay = _cat(client, h, "payroll")
    client.post("/expenses", json={"category_id": ops, "amount": 1200, "expense_date": "2026-05-01"}, headers=h)
    client.post("/expenses", json={"category_id": ops, "amount": 300, "expense_date": "2026-05-31"}, headers=h)
    client.post("/expenses", json={"category_id": pay, "amount": 9000, "expense_date": "2026-06-02"}, headers=h)

    may = client.get("/expenses?start=2026-05-01&end=2026-05-31", headers=h).json()
    assert may["count"] == 2
    assert may["operational_total"] == 1500
    assert may["payroll_total"] == 0
    assert may["grand_total"] == 1500

    only_payroll = client.get("/expenses?kind=payroll", headers=h).json()
    assert only_payroll["count"] == 1
    assert only_payroll["payroll_total"] == 9000

    audit = conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name = 'monthly_expense' AND action = 'create'"
    ).fetchone()["c"]
    assert audit == 3


def test_summary_groups_with_subtotals(client, auth_headers):
    h = auth_headers("Owner")
    ops = _cat(client, h, "operational")
    pay = _cat(client, h, "payroll")
    client.post("/expenses", json={"category_id": ops, "amount": 500, "expense_date": "2026-07-05"}, headers=h)
    client.post("/expenses", json={"category_id": ops, "amount": 700, "expense_date": "2026-07-10"}, headers=h)
    client.post("/expenses", json={"category_id": pay, "amount": 8000, "expense_date": "2026-07-15"}, headers=h)

    s = client.get("/expenses/summary?start=2026-07-01&end=2026-07-31", headers=h).json()
    assert s["operational_subtotal"] == 1200
    assert s["payroll_subtotal"] == 8000
    assert s["grand_total"] == 9200
    ops_line = next(x for x in s["by_category"] if x["kind"] == "operational")
    assert ops_line["total"] == 1200


def test_delete_expense_audited(client, auth_headers, conn):
    h = auth_headers("Manager")
    ops = _cat(client, h, "operational")
    eid = client.post("/expenses", json={"category_id": ops, "amount": 99}, headers=h).json()["id"]
    assert client.delete(f"/expenses/{eid}", headers=h).status_code == 204
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='monthly_expense' AND action='delete'"
    ).fetchone()["c"] == 1


# The 11 named categories the client gave (migration 0048), "Power Bill"
# retired for real (migration 0051) - it pre-dated and duplicated "Electricity
# - Monthly Power Bill" - and "Fuel Procurement" split into "Fuel Load - HS" /
# "Fuel Load - MS" (migration 0052) so a Diesel load and a Petrol load are two
# different categories, not one bucket that hides which fuel came in.
def test_active_categories_are_the_11_named_ones_only(client, auth_headers):
    names = {c["name"] for c in client.get("/expenses/categories", headers=auth_headers("Manager")).json()}
    assert names == {
        "Fuel Load - HS",
        "Fuel Load - MS",
        "Fuel Transport",
        "Employee payroll - Middle of Month",
        "Employee payroll - End of Month",
        "Electricity - Monthly Power Bill",
        "Monthly Wi-Fi",
        "Equipment maintenance & repairs",
        "Calibration, testing & inspection",
        "Licences, permits & statutory compliance",
        "Employee Insurance",
        "POS - Maintenance",
    }
    assert "Power Bill" not in names
    assert "Fuel Procurement" not in names
    assert "Rent" not in names
