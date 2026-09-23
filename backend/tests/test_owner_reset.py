"""Owner-only reading reset, behind its own passphrase (client, 2026-09-23)."""

SECRET = "reset-me-2026"


def test_the_form_cannot_be_opened_before_a_passphrase_exists(client, auth_headers):
    r = client.get("/owner-reset/status", headers=auth_headers("Owner"))
    assert r.status_code == 200
    assert r.json()["configured"] is False
    # Unlocking with anything at all is refused while none is set.
    r = client.post("/owner-reset/unlock", json={"passphrase": "guess"},
                    headers=auth_headers("Owner"))
    assert r.status_code == 409


def test_only_an_owner_sees_or_sets_it(client, auth_headers):
    for role in ("Manager", "Sales"):
        assert client.get("/owner-reset/status",
                          headers=auth_headers(role)).status_code == 403
        assert client.post("/owner-reset/secret",
                           json={"new_passphrase": SECRET},
                           headers=auth_headers(role)).status_code == 403


def _set_secret(client, auth_headers):
    r = client.post("/owner-reset/secret", json={"new_passphrase": SECRET},
                    headers=auth_headers("Owner"))
    assert r.status_code == 200, r.text[:200]


def test_set_then_unlock(client, auth_headers):
    _set_secret(client, auth_headers)
    assert client.get("/owner-reset/status",
                      headers=auth_headers("Owner")).json()["configured"] is True
    assert client.post("/owner-reset/unlock", json={"passphrase": SECRET},
                       headers=auth_headers("Owner")).status_code == 200
    assert client.post("/owner-reset/unlock", json={"passphrase": "wrong"},
                       headers=auth_headers("Owner")).status_code == 403


def test_changing_it_needs_the_current_one(client, auth_headers):
    _set_secret(client, auth_headers)
    r = client.post("/owner-reset/secret", json={"new_passphrase": "another-one"},
                    headers=auth_headers("Owner"))
    assert r.status_code == 400, "a set passphrase was replaced without the current one"
    r = client.post("/owner-reset/secret",
                    json={"new_passphrase": "another-one", "current_passphrase": "nope"},
                    headers=auth_headers("Owner"))
    assert r.status_code == 403


def test_a_reset_changes_what_the_next_day_carries(client, auth_headers):
    """The point of the whole feature. A wrong reading is on file; the Owner
    corrects it; the next day's prefill uses the correction, and the saved day it
    replaces is left exactly as it was."""
    serial = "12BC4523V-RD"
    _set_secret(client, auth_headers)
    client.post("/daily-sales-entry", json={
        "pump_serial": serial, "shift_date": "2026-09-13",
        "hs": {"current": "267841.93", "last": "267800"},
        "ms": {"current": "288877.28", "last": "288800"},
    }, headers=auth_headers("Manager"))

    before = client.get(
        f"/daily-sales-entry/prefill?pump_serial={serial}&shift_date=2026-09-15",
        headers=auth_headers("Manager")).json()
    assert float(before["hs_last"]) == 267841.93

    r = client.post("/owner-reset", json={
        "passphrase": SECRET, "pump_serial": serial,
        "effective_date": "2026-09-14",
        "hs_last": 1489759.27, "ms_last": 663546.17,
        "reason": "meter re-based after the Sep 9-12 test rounds",
    }, headers=auth_headers("Owner"))
    assert r.status_code == 201, r.text[:300]

    after = client.get(
        f"/daily-sales-entry/prefill?pump_serial={serial}&shift_date=2026-09-15",
        headers=auth_headers("Manager")).json()
    assert float(after["hs_last"]) == 1489759.27
    assert float(after["ms_last"]) == 663546.17

    # History is untouched: the 13th still reads what it read.
    day13 = client.get(
        f"/daily-sales-entry?pump_serial={serial}&shift_date=2026-09-13",
        headers=auth_headers("Manager")).json()
    assert float(day13[0]["payload"]["hs"]["current"]) == 267841.93


def test_a_reset_needs_the_passphrase_and_a_reason(client, auth_headers):
    _set_secret(client, auth_headers)
    base = {"pump_serial": "12BC4523V-RD", "effective_date": "2026-09-14",
            "hs_last": 1000, "reason": "correcting the meter"}
    assert client.post("/owner-reset", json={**base, "passphrase": "wrong"},
                       headers=auth_headers("Owner")).status_code == 403
    assert client.post("/owner-reset", json={**base, "passphrase": SECRET, "reason": "x"},
                       headers=auth_headers("Owner")).status_code == 422
    assert client.post("/owner-reset",
                       json={**base, "passphrase": SECRET, "hs_last": None, "ms_last": None},
                       headers=auth_headers("Owner")).status_code == 400


def test_every_reset_is_audited_and_listable(client, auth_headers, conn):
    _set_secret(client, auth_headers)
    client.post("/owner-reset", json={
        "passphrase": SECRET, "pump_serial": "11CC2012V-OFF",
        "effective_date": "2026-09-14", "hs_last": 267859.1,
        "reason": "office meter corrected",
    }, headers=auth_headers("Owner"))
    rows = client.get("/owner-reset/baselines",
                      headers=auth_headers("Owner")).json()
    assert len(rows) == 1 and rows[0]["reason"] == "office meter corrected"
    n = conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='reading_baseline'"
    ).fetchone()["c"]
    assert n >= 1, "a reading reset was not audited"
