"""Payment Receipt: total = liters x rate, rate defaults from Rate Master,
receipt number assignment, POS access for Sales, delete Manager/Owner only (SDD 5.20)."""

from __future__ import annotations


def _body(**over):
    b = {
        "pump_serial": "12BC4523V-RD",
        "attendant": "Gopi",
        "fuel_type": "Diesel",
        "liters": 10,
        "payment_mode": "Cash",
    }
    b.update(over)
    return b


def test_sales_can_issue_a_receipt_with_rate_from_rate_master(client, auth_headers):
    r = client.post("/receipts", json=_body(liters=10), headers=auth_headers("Sales"))
    assert r.status_code == 201
    body = r.json()
    assert body["rate"] == 105.36  # seeded HS sell rate
    assert body["total"] == 1053.6
    assert body["receipt_no"].startswith("SVR-")
    assert body["created_by"] == "sales"


def test_explicit_rate_overrides_and_petrol_uses_ms(client, auth_headers):
    r1 = client.post("/receipts", json=_body(rate=99.99, liters=5), headers=auth_headers("Manager"))
    assert r1.json()["total"] == 499.95

    r2 = client.post("/receipts", json=_body(fuel_type="Petrol", liters=4), headers=auth_headers("Manager"))
    assert r2.json()["rate"] == 117.7  # seeded MS sell rate


def test_delete_requires_manager_or_owner(client, auth_headers, conn):
    rid = client.post("/receipts", json=_body(), headers=auth_headers("Sales")).json()["id"]
    assert client.delete(f"/receipts/{rid}", headers=auth_headers("Sales")).status_code == 403
    assert client.delete(f"/receipts/{rid}", headers=auth_headers("Manager")).status_code == 204
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='payment_receipt' AND action='delete'"
    ).fetchone()["c"] == 1


def test_list_and_get(client, auth_headers):
    rid = client.post("/receipts", json=_body(), headers=auth_headers("Owner")).json()["id"]
    assert any(x["id"] == rid for x in client.get("/receipts", headers=auth_headers("Sales")).json())
    assert client.get(f"/receipts/{rid}", headers=auth_headers("Sales")).json()["id"] == rid
