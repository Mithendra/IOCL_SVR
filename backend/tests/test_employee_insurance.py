"""Employee Master insurance (mockup sections 3-5): accidental + health yearly
premium registers and the computed Annual Premium Summary. Manager/Owner only."""

from __future__ import annotations


def _emp(client, auth_headers, name, wage=500):
    return client.post(
        "/employees",
        json={"name": name, "daily_wage": wage},
        headers=auth_headers("Manager"),
    ).json()["id"]


def _add(client, auth_headers, **over):
    body = {
        "kind": "accidental", "employee_name": "R Kumar",
        "provider": "NIC", "policy_number": "ACC-1", "yearly_premium": 1200,
        "renewal_date": "2027-03-31",
    }
    body.update(over)
    return client.post("/employee-insurance", json=body, headers=auth_headers("Manager"))


def test_create_resolves_employee_and_audits(client, auth_headers, conn):
    emp_id = _emp(client, auth_headers, "R Kumar")
    r = _add(client, auth_headers)
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["kind"] == "accidental"
    assert row["employee_id"] == emp_id          # matched by name
    assert row["yearly_premium"] == 1200
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='employee_insurance' AND action='create'"
    ).fetchone()["c"] == 1


def test_create_keeps_name_when_no_employee_match(client, auth_headers):
    r = _add(client, auth_headers, employee_name="Ghost Worker")
    assert r.status_code == 201
    assert r.json()["employee_id"] is None
    assert r.json()["employee_name"] == "Ghost Worker"


def test_bad_kind_rejected(client, auth_headers):
    assert _add(client, auth_headers, kind="life").status_code == 422


def test_list_filters_by_kind(client, auth_headers):
    _add(client, auth_headers, kind="accidental", employee_name="A")
    _add(client, auth_headers, kind="health", employee_name="B", policy_number="H-1")
    acc = client.get("/employee-insurance?kind=accidental", headers=auth_headers("Manager")).json()
    hea = client.get("/employee-insurance?kind=health", headers=auth_headers("Manager")).json()
    assert {r["kind"] for r in acc} == {"accidental"}
    assert {r["kind"] for r in hea} == {"health"}
    assert len(client.get("/employee-insurance", headers=auth_headers("Owner")).json()) == 2


def test_summary_sums_each_kind_and_grand_total(client, auth_headers):
    _add(client, auth_headers, kind="accidental", yearly_premium=1000, employee_name="A")
    _add(client, auth_headers, kind="accidental", yearly_premium=500, employee_name="B")
    _add(client, auth_headers, kind="health", yearly_premium=2200, employee_name="A", policy_number="H")
    s = client.get("/employee-insurance/summary", headers=auth_headers("Manager")).json()
    assert s == {"accidental_total": 1500.0, "health_total": 2200.0, "grand_total": 3700.0}


def test_summary_zero_when_empty(client, auth_headers):
    s = client.get("/employee-insurance/summary", headers=auth_headers("Owner")).json()
    assert s == {"accidental_total": 0.0, "health_total": 0.0, "grand_total": 0.0}


def test_update_and_delete(client, auth_headers):
    iid = _add(client, auth_headers).json()["id"]
    upd = client.put(
        f"/employee-insurance/{iid}",
        json={"yearly_premium": 1500, "provider": "United India"},
        headers=auth_headers("Manager"),
    )
    assert upd.status_code == 200
    assert upd.json()["yearly_premium"] == 1500 and upd.json()["provider"] == "United India"

    d = client.delete(f"/employee-insurance/{iid}", headers=auth_headers("Owner"))
    assert d.status_code == 204
    assert client.get("/employee-insurance", headers=auth_headers("Owner")).json() == []


def test_sales_has_no_access(client, auth_headers):
    assert client.get("/employee-insurance", headers=auth_headers("Sales")).status_code == 403
    assert client.get("/employee-insurance/summary", headers=auth_headers("Sales")).status_code == 403
    assert client.post(
        "/employee-insurance",
        json={"kind": "health", "employee_name": "X", "yearly_premium": 1},
        headers=auth_headers("Sales"),
    ).status_code == 403


def test_employee_delete_softens_the_link(client, auth_headers, conn):
    emp_id = _emp(client, auth_headers, "Temp Worker")
    iid = _add(client, auth_headers, employee_name="Temp Worker").json()["id"]
    assert client.delete(f"/employees/{emp_id}", headers=auth_headers("Owner")).status_code == 204
    row = conn.execute(
        "SELECT employee_id, employee_name FROM employee_insurance WHERE id = ?", (iid,)
    ).fetchone()
    assert row["employee_id"] is None and row["employee_name"] == "Temp Worker"
