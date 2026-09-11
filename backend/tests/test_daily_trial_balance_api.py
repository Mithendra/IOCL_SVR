"""Daily Trial Balance: Section 1 formulas (SDD 9 r1), Section 3 pull from Daily
Sales Summary, Section 6/7 stock value + total, finalize lock, maker-checker RBAC,
and ADR-2 Close & Sign-Off carry-forward (gating, seeding, variance escalation)."""

from __future__ import annotations

DATE = "2026-10-05"
NEXT_DATE = "2026-10-06"


def _seed_summary(client, auth_headers, shift_date=DATE):
    """Two pump submissions -> combined HS consumption 50 L, MS consumption 20 L."""
    h = auth_headers("Sales")
    client.post("/daily-sales-entry", json={
        "pump_serial": "12BC4523V-RD", "shift_date": shift_date,
        "hs": {"current": "30"}, "ms": {"current": "15"},
    }, headers=h)
    client.post("/daily-sales-entry", json={
        "pump_serial": "11CC2012V-OFF", "shift_date": shift_date,
        "hs": {"current": "20"}, "ms": {"current": "5"},
    }, headers=auth_headers("Manager"))


def test_maker_checker_rbac(client, auth_headers):
    """ADR-2, confirmed 2026-09-06: Sales is the maker (GET/PUT), Manager/Owner is
    the checker (finalize only). Sales has no finalize access at all."""
    assert client.get(f"/daily-trial-balance/{DATE}", headers=auth_headers("Sales")).status_code == 200
    assert client.put(
        f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 60}, headers=auth_headers("Sales")
    ).status_code == 200
    assert client.post(
        f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Sales")
    ).status_code == 403


def test_section1_formulas_and_section3_pull(client, auth_headers):
    _seed_summary(client, auth_headers)
    r = client.put(
        f"/daily-trial-balance/{DATE}",
        json={"s1_hs_yesterday": 100, "s1_hs_current": 60},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 200
    view = r.json()
    assert view["pulled"]["s3_source"] == "daily_sales_summary"
    assert view["pulled"]["s3_hs_consumption"] == 50

    hs = view["computed"]["section1"]["hs"]
    assert hs["diff"] == 40           # 100 - 60
    assert hs["consumption"] == 50    # pulled from Section 3
    assert hs["computer_pump_diff"] == 10   # 50 - 40
    # benefit_loss = consumption + computer_pump_diff (2026-09-06: corrected against
    # AUG11/AUG12 real workbooks - was `cons + diff`, which matched neither tab).
    assert hs["benefit_loss"] == 60          # 50 + 10
    assert hs["deduct_testing"] == 40       # 50 - 10 (system_parameter)
    # stock_ltrs = today's current reading, verbatim (2026-09-06: corrected against
    # AUG11/AUG12/SEP05/SEP06 real workbooks, SEP06 client-validated - was
    # `diff - consumption`, which produced negative litres against real data).
    assert hs["stock_ltrs"] == 60           # = s1_hs_current
    # Section 6 stock amount = stock_ltrs x Buy Rate HS (seeded 101.50)
    assert hs["stock_amount"] == 6090.0


def test_section7_total_uses_cash_book_value_plus_stock_value(client, auth_headers):
    _seed_summary(client, auth_headers)
    view = client.put(
        f"/daily-trial-balance/{DATE}",
        json={
            "s1_hs_yesterday": 100, "s1_hs_current": 60,
            "s1_ms_yesterday": 200, "s1_ms_current": 190,
            "s54_cash_book_value": 500000,
        },
        headers=auth_headers("Owner"),
    ).json()
    s6 = view["computed"]["section6"]
    s7 = view["computed"]["section7"]
    assert s7["7_1_cash_book_value"] == 500000
    assert s7["7_2_stock_value"] == s6["total"]
    assert s7["7_3_total"] == round(500000 + s6["total"], 4)


def test_section3_unavailable_without_a_summary(client, auth_headers):
    view = client.get("/daily-trial-balance/2099-01-01", headers=auth_headers("Manager")).json()
    assert view["pulled"]["s3_source"] == "unavailable"
    assert view["computed"]["section1"]["hs"]["consumption"] is None


def test_finalize_locks_further_edits(client, auth_headers, conn):
    _seed_summary(client, auth_headers)
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_yesterday": 100, "s1_hs_current": 60},
               headers=auth_headers("Manager"))

    fin = client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"

    assert client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 61},
                      headers=auth_headers("Owner")).status_code == 409
    assert client.post(f"/daily-trial-balance/{DATE}/finalize",
                       headers=auth_headers("Owner")).status_code == 409

    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='daily_trial_balance'"
    ).fetchone()["c"] >= 2


def test_manual_blob_round_trips(client, auth_headers):
    view = client.put(
        f"/daily-trial-balance/{DATE}",
        json={"manual": {"section4": {"4_16_total": 123456}, "section8": {"note": "call owner"}}},
        headers=auth_headers("Manager"),
    ).json()
    assert view["manual"]["section4"]["4_16_total"] == 123456
    assert view["manual"]["section8"]["note"] == "call owner"


# --- ADR-2: Close & Sign-Off carry-forward -----------------------------------


def test_finalize_creates_and_seeds_the_next_day(client, auth_headers):
    """Decision step 3: finalizing today system-generates tomorrow's draft, seeded
    from today's own finalized closing values - no cell to mistype, no template to
    copy forward with a stale reference baked in."""
    client.put(
        f"/daily-trial-balance/{DATE}",
        json={"s1_hs_yesterday": 100, "s1_hs_current": 60, "s54_cash_book_value": 500000},
        headers=auth_headers("Manager"),
    )
    fin = client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    assert fin.status_code == 200

    nxt = client.get(f"/daily-trial-balance/{NEXT_DATE}", headers=auth_headers("Manager")).json()
    assert nxt["status"] == "draft"
    assert nxt["carried_from"] == DATE
    assert nxt["inputs"]["s1_hs_yesterday"] == 60          # yesterday's s1_hs_current
    assert nxt["inputs"]["s54_cash_book_value"] == 500000  # yesterday's closing cash/book value

    # The maker's own entry for tomorrow still wins over the carried seed.
    edited = client.put(
        f"/daily-trial-balance/{NEXT_DATE}", json={"s1_hs_yesterday": 999},
        headers=auth_headers("Sales"),
    ).json()
    assert edited["inputs"]["s1_hs_yesterday"] == 999


def test_cannot_skip_ahead_while_an_earlier_date_is_open(client, auth_headers):
    """Decision step 4: this alone would have caught the legacy workbook's SEP02
    skip - Sep 2 could not have been created without Sep 1 first being signed off."""
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 60},
               headers=auth_headers("Sales"))  # DATE stays a draft, never finalized

    skip_ahead = "2026-10-09"
    r = client.put(f"/daily-trial-balance/{skip_ahead}", json={"s1_hs_current": 10},
                   headers=auth_headers("Sales"))
    assert r.status_code == 409
    assert DATE in r.json()["detail"]


def test_cold_start_on_an_arbitrary_date_has_no_gate_and_no_seed(client, auth_headers):
    """Point 5, the one case it actually covers today: the very first row in the
    system can start on any date (nothing earlier exists to gate on or seed from) -
    e.g. going live mid-month rather than from day one."""
    r = client.put("/daily-trial-balance/2026-11-15", json={"s1_hs_current": 10},
                   headers=auth_headers("Sales"))
    assert r.status_code == 200
    assert r.json()["carried_from"] is None


def test_reopening_after_a_gap_still_needs_each_auto_created_day_closed(client, auth_headers):
    """Documents a real, currently-open limitation (ADR-2 point 5: "gap-day handling
    not yet designed"): because finalize eagerly creates *tomorrow's* draft every
    time, a multi-day closure (e.g. a festival holiday) leaves a chain of empty
    auto-created drafts that each still need Close & Sign Off before a far-out date
    can be started - true skip-back over a real multi-day gap is not implemented
    yet and needs its own client decision, not one made silently here."""
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 60},
               headers=auth_headers("Manager"))
    client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    # NEXT_DATE now exists as an auto-created, untouched draft - it still blocks:
    far_out = "2026-10-20"
    r = client.put(f"/daily-trial-balance/{far_out}", json={"s1_hs_current": 10},
                   headers=auth_headers("Sales"))
    assert r.status_code == 409
    assert NEXT_DATE in r.json()["detail"]


def test_variance_escalation_requires_a_reason_over_threshold(client, auth_headers):
    """Decision step 1: the +/-Rs100 threshold rule, now enforced server-side
    instead of being a comment nobody reliably reads."""
    view = client.put(
        f"/daily-trial-balance/{DATE}",
        json={"s54_cash_book_value": 500000},
        headers=auth_headers("Manager"),
    ).json()
    reported = view["computed"]["section7"]["7_3_total"]

    breach = client.post(
        f"/daily-trial-balance/{DATE}/finalize",
        json={"projected_total": reported - 250},
        headers=auth_headers("Manager"),
    )
    assert breach.status_code == 422

    ok = client.post(
        f"/daily-trial-balance/{DATE}/finalize",
        json={"projected_total": reported - 250, "reason": "Power bill paid from till today"},
        headers=auth_headers("Manager"),
    )
    assert ok.status_code == 200
    assert ok.json()["variance_amount"] == 250
    assert ok.json()["variance_reason"] == "Power bill paid from till today"


def test_variance_within_threshold_needs_no_reason(client, auth_headers):
    view = client.put(
        f"/daily-trial-balance/{DATE}", json={"s54_cash_book_value": 500000},
        headers=auth_headers("Manager"),
    ).json()
    reported = view["computed"]["section7"]["7_3_total"]

    ok = client.post(
        f"/daily-trial-balance/{DATE}/finalize",
        json={"projected_total": reported - 21.87},
        headers=auth_headers("Manager"),
    )
    assert ok.status_code == 200
    assert ok.json()["variance_amount"] == 21.87


def test_finalize_without_projected_total_skips_the_check(client, auth_headers):
    """The Projected total isn't computed server-side yet (ADR-1's remaining
    sections) - omitting it must not block sign-off."""
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 60},
               headers=auth_headers("Manager"))
    ok = client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    assert ok.status_code == 200
    assert ok.json()["variance_amount"] is None
