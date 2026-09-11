"""Daily Sales Summary: combine two pump submissions, per-pump verification, and
the both-verified gate on upload (SDD 5.23-5.25 / 10 / ADR-5)."""

from __future__ import annotations

DATE = "2026-08-12"
OFF = "12BC4523V-OFF"
ROAD = "11CC2012V-RDF"


def _make_entry(client, headers, pump, hs_current):
    body = {
        "pump_serial": pump,
        "shift_date": DATE,
        "hs": {"current": hs_current},
        "ms": {"current": "0"},
    }
    r = client.post("/daily-sales-entry", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _seed_both_pumps(client, auth_headers):
    # Office submitted by Sales, Road submitted by Manager (so the Sales-side
    # restriction has something to bite on).
    off = _make_entry(client, auth_headers("Sales"), OFF, "1317.52")
    road = _make_entry(client, auth_headers("Manager"), ROAD, "1000")
    return off, road


def test_summary_combines_both_submissions(client, auth_headers):
    off, road = _seed_both_pumps(client, auth_headers)
    s = client.get(f"/daily-sales-summary/{DATE}", headers=auth_headers("Manager")).json()

    assert s["both_present"] is True
    assert s["status"] == "draft"
    assert s["can_upload"] is False
    assert s["office"]["entry_id"] == off["id"]
    assert s["road"]["entry_id"] == road["id"]

    exp_hs = off["result"]["hs"]["amount"] + road["result"]["hs"]["amount"]
    assert s["combined"]["hs"]["combined"] == round(exp_hs, 4)
    assert s["combined"]["grand_total"] == round(
        off["gas_total"] + off["oil_total"] + road["gas_total"] + road["oil_total"], 4
    )


def test_missing_pump_does_not_crash(client, auth_headers):
    _make_entry(client, auth_headers("Sales"), OFF, "1200")
    s = client.get(f"/daily-sales-summary/{DATE}", headers=auth_headers("Sales")).json()
    assert s["both_present"] is False
    assert s["road"]["present"] is False
    assert s["can_upload"] is False


def test_upload_blocked_until_both_verified(client, auth_headers):
    _seed_both_pumps(client, auth_headers)

    client.put(
        f"/daily-sales-summary/{DATE}",
        json={"off_verified": True},
        headers=auth_headers("Manager"),
    )
    blocked = client.post(f"/daily-sales-summary/{DATE}/upload", headers=auth_headers("Manager"))
    assert blocked.status_code == 409

    done = client.put(
        f"/daily-sales-summary/{DATE}",
        json={"road_verified": True, "road_verified_note": "matched paper form"},
        headers=auth_headers("Manager"),
    ).json()
    assert done["both_verified"] is True
    assert done["status"] == "verified"
    assert done["can_upload"] is True


def test_upload_requires_manager_and_is_idempotent_once(client, auth_headers, conn):
    _seed_both_pumps(client, auth_headers)
    client.put(
        f"/daily-sales-summary/{DATE}",
        json={"off_verified": True, "road_verified": True},
        headers=auth_headers("Manager"),
    )

    assert client.post(f"/daily-sales-summary/{DATE}/upload", headers=auth_headers("Sales")).status_code == 403

    ok = client.post(f"/daily-sales-summary/{DATE}/upload", headers=auth_headers("Owner"))
    assert ok.status_code == 200
    assert ok.json()["status"] == "uploaded"
    assert ok.json()["uploaded_by"] == "owner"

    again = client.post(f"/daily-sales-summary/{DATE}/upload", headers=auth_headers("Manager"))
    assert again.status_code == 409

    audit = conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name = 'daily_sales_summary'"
    ).fetchone()["c"]
    assert audit >= 2  # verify PUT(s) + the upload


def test_sales_can_only_verify_their_own_pump(client, auth_headers):
    _seed_both_pumps(client, auth_headers)  # OFF by sales, ROAD by manager

    # Sales verifying the Road pump (submitted by manager) -> 403
    denied = client.put(
        f"/daily-sales-summary/{DATE}",
        json={"road_verified": True},
        headers=auth_headers("Sales"),
    )
    assert denied.status_code == 403

    # Sales verifying its own Office pump -> ok
    allowed = client.put(
        f"/daily-sales-summary/{DATE}",
        json={"off_verified": True},
        headers=auth_headers("Sales"),
    )
    assert allowed.status_code == 200
    assert allowed.json()["office"]["verified"] is True


def test_correcting_a_verified_entry_reopens_that_side(client, auth_headers, conn):
    off, _road = _seed_both_pumps(client, auth_headers)
    client.put(
        f"/daily-sales-summary/{DATE}",
        json={"off_verified": True, "road_verified": True},
        headers=auth_headers("Manager"),
    )
    assert client.get(
        f"/daily-sales-summary/{DATE}", headers=auth_headers("Manager")
    ).json()["status"] == "verified"

    # Manager corrects the office entry.
    r = client.put(
        f"/daily-sales-entry/{off['id']}",
        json={"pump_serial": OFF, "shift_date": DATE, "hs": {"current": "1500"}, "ms": {"current": "0"}},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 200
    assert "re-verification" in (r.json().get("summary_note") or "")

    s = client.get(f"/daily-sales-summary/{DATE}", headers=auth_headers("Manager")).json()
    assert s["office"]["verified"] is False   # the edited side must be re-checked
    assert s["road"]["verified"] is True      # the untouched side stands
    assert s["status"] == "draft"
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='daily_sales_summary' AND action='update'"
    ).fetchone()["c"] >= 1


def test_correcting_an_unverified_entry_leaves_the_summary_alone(client, auth_headers):
    off, _road = _seed_both_pumps(client, auth_headers)
    r = client.put(
        f"/daily-sales-entry/{off['id']}",
        json={"pump_serial": OFF, "shift_date": DATE, "hs": {"current": "1500"}, "ms": {"current": "0"}},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 200
    assert r.json().get("summary_note") is None
