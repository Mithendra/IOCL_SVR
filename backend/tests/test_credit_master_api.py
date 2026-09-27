"""Credit / Remittance Master: amount = ltrs x rate, grouped summary with
outstanding balance (pending first), RBAC, audit (SDD 5.17)."""

from __future__ import annotations


def test_sales_has_no_access(client, auth_headers):
    assert client.get("/credit-master/summary", headers=auth_headers("Sales")).status_code == 403
    assert client.post(
        "/credit-master/credit",
        json={"creditor_name": "X", "amount": 100},
        headers=auth_headers("Sales"),
    ).status_code == 403


def test_credit_amount_is_ltrs_times_rate(client, auth_headers):
    r = client.post(
        "/credit-master/credit",
        json={"creditor_name": "Ramesh Traders", "ltrs": 40, "rate": 105.36, "fuel_type": "Diesel"},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 201
    assert r.json()["amount"] == 4214.4


def test_credit_requires_amount_or_ltrs_and_rate(client, auth_headers):
    bad = client.post(
        "/credit-master/credit",
        json={"creditor_name": "NoAmount", "ltrs": 10},  # rate missing, no amount
        headers=auth_headers("Manager"),
    )
    assert bad.status_code == 422


def test_summary_groups_by_name_with_outstanding_pending_first(client, auth_headers, conn):
    h = auth_headers("Owner")
    # Big creditor, partially repaid.
    client.post("/credit-master/credit", json={"creditor_name": "Ramesh Traders", "amount": 5000}, headers=h)
    client.post("/credit-master/credit", json={"creditor_name": "Ramesh Traders", "amount": 2000}, headers=h)
    client.post("/credit-master/remittance", json={"creditor_name": "Ramesh Traders", "amount": 3000}, headers=h)
    # Small creditor, fully settled.
    client.post("/credit-master/credit", json={"creditor_name": "Anil Auto", "amount": 800}, headers=h)
    client.post("/credit-master/remittance", json={"creditor_name": "Anil Auto", "amount": 800}, headers=h)

    summary = client.get("/credit-master/summary", headers=h).json()
    by_name = {s["creditor_name"]: s for s in summary}
    assert by_name["Ramesh Traders"]["total_credit"] == 7000
    assert by_name["Ramesh Traders"]["total_remitted"] == 3000
    assert by_name["Ramesh Traders"]["outstanding"] == 4000
    assert by_name["Anil Auto"]["outstanding"] == 0
    # Pending (largest outstanding) first.
    assert summary[0]["creditor_name"] == "Ramesh Traders"

    audit = conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name = 'credit_transaction'"
    ).fetchone()["c"]
    # 5 creates (3 credits, 2 remittances) + 2 settlement updates - Ramesh's
    # 2000 credit and Anil's 800 credit each flip to 'paid' and are audited
    # as their own write (client, 2026-09-27: settling a credit is a write
    # like any other, so it gets its own audit_log row too).
    assert audit == 7


def test_delete_transaction_updates_summary_and_audits(client, auth_headers, conn):
    h = auth_headers("Manager")
    created = client.post(
        "/credit-master/credit", json={"creditor_name": "Temp Co", "amount": 900}, headers=h
    ).json()
    assert client.delete(f"/credit-master/transactions/{created['id']}", headers=h).status_code == 204
    summary = client.get("/credit-master/summary", headers=h).json()
    assert all(s["creditor_name"] != "Temp Co" for s in summary)
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='credit_transaction' AND action='delete'"
    ).fetchone()["c"] == 1
