"""Inventory Tracking: stock levels, restock, low-stock status, RBAC, and the
Daily Sales Entry opening-stock pull (SDD 5.10 / BRD 33/35)."""

from __future__ import annotations

DATE = "2026-08-20"


def test_sales_has_no_access(client, auth_headers):
    assert client.get("/inventory", headers=auth_headers("Sales")).status_code == 403


def test_stock_levels_seeded(client, auth_headers):
    rows = client.get("/inventory", headers=auth_headers("Manager")).json()
    keys = {r["item_key"] for r in rows}
    assert keys == {"oil1", "oil2", "oil3", "oil4", "oil5"}
    oil1 = next(r for r in rows if r["item_key"] == "oil1")
    assert oil1["opening_stock"] == 40
    assert oil1["closing_stock"] == 40  # no restock, no sales yet
    assert oil1["status"] == "ok"


def test_restock_shows_as_received_today_without_moving_opening(client, auth_headers, conn):
    r = client.post(
        "/inventory/restock",
        json={"item_key": "oil3", "quantity": 15, "supplier_ref": "INV-991", "restock_date": DATE},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 201

    rows = client.get(f"/inventory?as_of={DATE}", headers=auth_headers("Manager")).json()
    oil3 = next(x for x in rows if x["item_key"] == "oil3")
    assert oil3["opening_stock"] == 60  # unchanged
    assert oil3["received_today"] == 15
    assert oil3["closing_stock"] == 75  # 60 + 15 - 0

    audit = conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name = 'restock_entry'"
    ).fetchone()["c"]
    assert audit == 1


def test_sold_today_and_low_stock_status(client, auth_headers):
    # A Daily Sales Entry with a big oil4 quantity should drop oil4 below its
    # reorder level (18 on hand, reorder 6) and flip status to "low".
    client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": "12BC4523V-RD",
            "shift_date": DATE,
            "hs": {"current": "1"},
            "oils": [{}, {}, {}, {"qty": "15"}, {}],
        },
        headers=auth_headers("Sales"),
    )
    rows = client.get(f"/inventory?as_of={DATE}", headers=auth_headers("Owner")).json()
    oil4 = next(x for x in rows if x["item_key"] == "oil4")
    assert oil4["sold_today"] == 15
    assert oil4["closing_stock"] == 3  # 18 + 0 - 15
    assert oil4["status"] == "low"


def test_owner_can_correct_reorder_and_on_hand(client, auth_headers):
    out = client.put(
        "/inventory/oil1",
        json={"reorder_level": 5, "on_hand": 100},
        headers=auth_headers("Owner"),
    ).json()
    assert out == {"item_key": "oil1", "reorder_level": 5, "on_hand": 100}


def test_manager_can_set_stock_outright_including_zero(client, auth_headers):
    """Setting stock is Manager-or-Owner (widened 2026-09-11). Restock adds; this
    replaces, which is the only way to establish an opening count or correct a
    miscount - and 0 has to be settable, not treated as "no value given"."""
    assert client.put(
        "/inventory/oil1", json={"on_hand": 42}, headers=auth_headers("Manager")
    ).status_code == 200

    out = client.put(
        "/inventory/oil1", json={"on_hand": 0}, headers=auth_headers("Manager")
    ).json()
    assert out["on_hand"] == 0

    assert client.put(
        "/inventory/oil1", json={"on_hand": 1}, headers=auth_headers("Sales")
    ).status_code == 403


def test_daily_sales_entry_opening_stock_comes_from_inventory(client, auth_headers):
    created = client.post(
        "/daily-sales-entry",
        json={"pump_serial": "12BC4523V-RD", "shift_date": DATE, "hs": {"current": "1"},
              "oils": [{"qty": "2"}, {}, {}, {}, {}]},
        headers=auth_headers("Sales"),
    ).json()
    # oil1 seed on_hand is 40; opening pulled from inventory, closing = 40 - 2.
    assert created["payload"]["oils"][0]["opening"] == 40
    assert created["result"]["oils"][0]["closing"] == 38


# --------------------------------------------------- Print & Sync (2026-09-11)


def test_sync_inventory_requires_manager_or_owner(client, auth_headers):
    assert client.post(
        "/daily-sales-entry/sync-inventory", headers=auth_headers("Sales")
    ).status_code == 403
    assert client.post(
        "/daily-sales-entry/sync-inventory", headers=auth_headers("Manager")
    ).status_code == 200


def test_sync_inventory_sets_on_hand_from_the_real_prior_closing(client, auth_headers, conn):
    # oil1 seed on_hand is 40. A real sale of 2 on 2026-08-19 closes it at 38.
    client.post(
        "/daily-sales-entry",
        json={"pump_serial": "12BC4523V-RD", "shift_date": "2026-08-19",
              "hs": {"current": "1"}, "oils": [{"qty": "2"}, {}, {}, {}, {}]},
        headers=auth_headers("Sales"),
    )
    resp = client.post(
        "/daily-sales-entry/sync-inventory?shift_date=2026-08-20",
        headers=auth_headers("Manager"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["oil1"] == {"from": 40, "to": 38, "source_date": "2026-08-19"}

    rows = client.get("/inventory", headers=auth_headers("Manager")).json()
    oil1 = next(r for r in rows if r["item_key"] == "oil1")
    assert oil1["opening_stock"] == 38

    audit = conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name = 'inventory_item' AND action = 'update'"
    ).fetchone()["c"]
    assert audit == 1


def test_sync_inventory_skips_a_blank_day_for_that_item(client, auth_headers):
    # 2026-08-18: a real sale of 3 units of oil2 -> closes at (seed 30) - 3 = 27.
    client.post(
        "/daily-sales-entry",
        json={"pump_serial": "12BC4523V-RD", "shift_date": "2026-08-18",
              "hs": {"current": "1"}, "oils": [{}, {"qty": "3"}, {}, {}, {}]},
        headers=auth_headers("Sales"),
    )
    # 2026-08-19: the other pump submits but doesn't touch oil2 (blank qty) -
    # not a real transaction, must not be mistaken for one even though it's
    # more recent than the real sale above.
    client.post(
        "/daily-sales-entry",
        json={"pump_serial": "11CC2012V-OFF", "shift_date": "2026-08-19", "hs": {"current": "1"}},
        headers=auth_headers("Sales"),
    )
    body = client.post(
        "/daily-sales-entry/sync-inventory?shift_date=2026-08-20",
        headers=auth_headers("Manager"),
    ).json()
    assert body["oil2"] == {"from": 30, "to": 27, "source_date": "2026-08-18"}


def test_sync_inventory_is_idempotent(client, auth_headers):
    client.post(
        "/daily-sales-entry",
        json={"pump_serial": "12BC4523V-RD", "shift_date": "2026-08-19",
              "hs": {"current": "1"}, "oils": [{"qty": "2"}, {}, {}, {}, {}]},
        headers=auth_headers("Sales"),
    )
    first = client.post(
        "/daily-sales-entry/sync-inventory?shift_date=2026-08-20",
        headers=auth_headers("Manager"),
    ).json()
    second = client.post(
        "/daily-sales-entry/sync-inventory?shift_date=2026-08-20",
        headers=auth_headers("Manager"),
    ).json()
    assert first["oil1"]["to"] == second["oil1"]["to"] == 38
    assert second["oil1"]["from"] == 38  # already synced last time - no further change


def test_sync_inventory_nothing_to_sync_returns_empty(client, auth_headers):
    resp = client.post(
        "/daily-sales-entry/sync-inventory?shift_date=2026-08-20",
        headers=auth_headers("Manager"),
    )
    assert resp.status_code == 200
    assert resp.json() == {}
