"""Oil Sale(s) items are data the station edits, not a list in the build.

Client, 2026-09-13: "adding oil sales in new category... people should be able to
add it, or people should be able to remove it."

The thing worth protecting here is not that a row appears on a form - it is that
adding or retiring a row never changes what a day already recorded is worth.
"""

from __future__ import annotations

import json

# The whole Inventory Master form is Owner-only behind the Owner passphrase
# (client, 2026-09-25: "This form Can only be edited by Owner with his Secert
# password and none allowed"). Every write below therefore signs in as Owner and
# carries SECRET; the reads do not.
SECRET = "oil-catalogue-2026"


def _owner(client, auth_headers, role: str = "Manager"):
    """Set the Owner passphrase on THIS test's database, then sign in.

    Manager by default: the client settled on Manager-or-Owner may edit, but
    only with the Owner's passphrase (2026-09-25). The passphrase is the
    authority; the role is who is at the keyboard.

    Set every call, not cached in a module global: the `db_path` fixture is
    function-scoped, so every test gets a fresh database and a cached "already
    set" flag leaves the next one with no passphrase at all.
    """
    r = client.post("/owner-reset/secret", json={"new_passphrase": SECRET},
                    headers=auth_headers("Owner"))
    assert r.status_code in (200, 400), r.text[:200]
    return auth_headers(role)


DATE = "2026-11-02"
PUMP = "12BC4523V-RD"


def _add(client, h, **kw) -> dict:
    body = {"label": "Coolant Total 1 Lts", "unit": "ltr", "rate": 250,
            "opening_stock": 12, "passphrase": SECRET}
    body.update(kw)
    r = client.post("/oil-items", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_new_oil_item_reaches_the_entry_form_with_its_rate_and_stock(client, auth_headers):
    h = _owner(client, auth_headers)
    before = client.get("/oil-items", headers=h).json()
    assert len(before) == 7

    item = _add(client, h)
    assert item["item_key"] == "oil8"  # past the highest ever used, never reused
    assert item["active"] is True

    after = client.get("/oil-items", headers=h).json()
    assert len(after) == 8
    assert after[-1]["label"] == "Coolant Total 1 Lts"

    # An oil row is useless without a rate and a stock figure, so adding the item
    # creates all three together - exactly what migration 0017 did by hand.
    pre = client.get(
        f"/daily-sales-entry/prefill?pump_serial={PUMP}&shift_date={DATE}", headers=h
    ).json()
    assert pre["oil_labels"]["oil8"] == "Coolant Total 1 Lts"
    assert pre["oil_rates"]["oil8"] == 250
    assert pre["oil_openings"]["oil8"] == 12


def test_selling_a_new_item_counts_in_every_total_downstream(client, auth_headers):
    h = _owner(client, auth_headers)
    _add(client, h, label="Coolant Total 1 Lts", rate=250, opening_stock=12)

    r = client.post("/daily-sales-entry", json={
        "pump_serial": PUMP, "shift_date": DATE,
        "hs": {"current": "1000"},
        "oils": [{}, {}, {}, {}, {}, {}, {}, {"qty": "3"}],  # the 8th row
    }, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["oil_total"] == 750.0  # 3 x 250, at the rate the item was created with

    # Daily Sales Summary lists it as its own line, by key and label.
    oils = client.get(f"/daily-sales-summary/{DATE}", headers=h).json()["combined"]["oils"]
    assert len(oils) == 8
    assert oils[-1]["key"] == "oil8"
    assert oils[-1]["label"] == "Coolant Total 1 Lts"
    assert oils[-1]["combined"] == 750.0


def test_retiring_an_item_does_not_change_what_past_days_are_worth(client, auth_headers):
    """The point of retire-not-delete. A day already recorded names the item in its
    own saved rows; a hard delete would leave those pointing at nothing."""
    h = _owner(client, auth_headers)
    _add(client, h, label="Coolant Total 1 Lts", rate=250, opening_stock=12)
    client.post("/daily-sales-entry", json={
        "pump_serial": PUMP, "shift_date": DATE,
        "hs": {"current": "1000"},
        "oils": [{}, {}, {}, {}, {}, {}, {}, {"qty": "3"}],
    }, headers=h)
    before = client.get(f"/daily-sales-summary/{DATE}", headers=h).json()

    assert client.post("/oil-items/oil8/retire", json={"passphrase": SECRET}, headers=h).status_code == 200

    # Off the form...
    assert [i["item_key"] for i in client.get("/oil-items", headers=h).json()].count("oil8") == 0
    assert len(client.get("/oil-items?include_retired=true", headers=h).json()) == 8

    # ...but the day it was sold on is worth exactly what it was worth.
    after = client.get(f"/daily-sales-summary/{DATE}", headers=h).json()
    assert after["combined"]["grand_total"] == before["combined"]["grand_total"]
    entry = client.get(f"/daily-sales-entry?shift_date={DATE}", headers=h).json()[0]
    assert entry["oil_total"] == 750.0
    assert any(o["label"] == "Coolant Total 1 Lts" for o in entry["result"]["oils"])


def test_renaming_keeps_the_product_its_history_and_its_stock(client, auth_headers):
    """item_key identifies a PRODUCT, not a row position or a name. This is the rule
    that carried oil1/oil4/oil5 through the 2026-09-12 relabel."""
    h = _owner(client, auth_headers)
    _add(client, h, label="Coolant Total 1 Lts", rate=250, opening_stock=12)
    client.post("/daily-sales-entry", json={
        "pump_serial": PUMP, "shift_date": DATE,
        "hs": {"current": "1000"},
        "oils": [{}, {}, {}, {}, {}, {}, {}, {"qty": "3"}],
    }, headers=h)

    r = client.patch("/oil-items/oil8", json={"passphrase": SECRET, "label": "Coolant 1 L Pack"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["label"] == "Coolant 1 L Pack"

    # Same key, so the rate and the tracked stock follow the product.
    pre = client.get(
        f"/daily-sales-entry/prefill?pump_serial={PUMP}&shift_date={DATE}", headers=h
    ).json()
    assert pre["oil_rates"]["oil8"] == 250
    assert pre["oil_labels"]["oil8"] == "Coolant 1 L Pack"

    # And the record saved under the OLD name still resolves to it, so the day's
    # figure is unchanged rather than silently dropping to zero.
    oils = client.get(f"/daily-sales-summary/{DATE}", headers=h).json()["combined"]["oils"]
    assert [o for o in oils if o["key"] == "oil8"][0]["combined"] == 750.0


def test_a_retired_label_reactivates_the_same_product_rather_than_forking_it(client, auth_headers):
    h = _owner(client, auth_headers)
    _add(client, h, label="Coolant Total 1 Lts", rate=250, opening_stock=12)
    client.post("/oil-items/oil8/retire", json={"passphrase": SECRET}, headers=h)

    again = _add(client, h, label="Coolant Total 1 Lts", rate=999)
    assert again["item_key"] == "oil8", "a second key would split its rate history and stock"
    assert len(client.get("/oil-items?include_retired=true", headers=h).json()) == 8


def test_adding_the_same_label_twice_is_refused(client, auth_headers):
    h = _owner(client, auth_headers)
    _add(client, h)
    r = client.post("/oil-items", json={"passphrase": SECRET, "label": "Coolant Total 1 Lts"}, headers=h)
    assert r.status_code == 409
    assert "already on the Oil Sale(s) list" in r.json()["detail"]


def test_sales_can_read_the_list_but_not_change_it(client, auth_headers):
    """Sales enters the day's figures; it does not decide what the station sells."""
    s = auth_headers("Sales")
    assert client.get("/oil-items", headers=s).status_code == 200
    assert client.post("/oil-items", json={"passphrase": SECRET, "label": "X"}, headers=s).status_code == 403
    assert client.post("/oil-items/oil1/retire", json={"passphrase": SECRET}, headers=s).status_code == 403
    assert client.patch("/oil-items/oil1", json={"passphrase": SECRET, "label": "X"}, headers=s).status_code == 403


def test_the_last_row_cannot_be_retired(client, auth_headers):
    """Oil Sale(s) with no rows is a broken form, not an empty one - and there would
    be no way back through the UI."""
    h = _owner(client, auth_headers)
    keys = [i["item_key"] for i in client.get("/oil-items", headers=h).json()]
    for k in keys[:-1]:
        assert client.post(f"/oil-items/{k}/retire", json={"passphrase": SECRET}, headers=h).status_code == 200
    r = client.post(f"/oil-items/{keys[-1]}/retire", json={"passphrase": SECRET}, headers=h)
    assert r.status_code == 409
    assert "last Oil Sale(s) row" in r.json()["detail"]


def test_every_change_is_audited(client, auth_headers, conn):
    """Non-negotiable per the client: every write leaves a trail (SDD 13.4). What
    the station sells is exactly the kind of change someone will later want to
    date."""
    h = _owner(client, auth_headers)
    _add(client, h)
    client.patch("/oil-items/oil8", json={"passphrase": SECRET, "label": "Coolant 1 L Pack"}, headers=h)
    client.post("/oil-items/oil8/retire", json={"passphrase": SECRET}, headers=h)

    rows = conn.execute(
        "SELECT action, actor, new_value FROM audit_log "
        "WHERE table_name = 'oil_item' ORDER BY id"
    ).fetchall()
    assert [r["action"] for r in rows] == ["create", "update", "update"]
    assert all(r["actor"] == "manager" for r in rows)
    assert "retired" in rows[-1]["new_value"]  # the retire, recorded as what it is


def test_the_trial_balance_shows_the_new_row_too(client, auth_headers):
    """Section 2.1 is pulled from the day's entries, so it has to follow the list."""
    h = _owner(client, auth_headers)
    _add(client, h, label="Coolant Total 1 Lts", rate=250, opening_stock=12)
    client.post("/daily-sales-entry", json={
        "pump_serial": PUMP, "shift_date": DATE,
        "hs": {"current": "1000"},
        "oils": [{}, {}, {}, {}, {}, {}, {}, {"qty": "3"}],
    }, headers=h)

    r = client.get(f"/daily-sales-entry?shift_date={DATE}", headers=h)
    payload = r.json()[0]["payload"] if isinstance(r.json()[0]["payload"], dict) \
        else json.loads(r.json()[0]["payload"])
    assert len(payload["oils"]) == 8
    assert payload["oils"][7]["label"] == "Coolant Total 1 Lts"
