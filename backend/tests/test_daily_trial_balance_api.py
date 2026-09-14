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
    # 50 - 10. Testing is 5 litres PER NOZZLE and follows how many pumps ran
    # (migrations 0026/0027), not a flat per-fuel constant. _seed_summary files
    # BOTH pumps and neither is in repair, so both are tested: 2 x 5 = 10.
    #
    # This is the figure the station's own Section 9 ledger carried while both
    # pumps were running (10 / 10.5 to 6 September). The flat 5 that used to be
    # asserted here was the ONE-pump case - correct only because one pump was in
    # the workshop from the 7th, which nothing in the app recorded until now.
    assert hs["deduct_testing"] == 40.0
    # stock_ltrs = today's current reading, verbatim (2026-09-06: corrected against
    # AUG11/AUG12/SEP05/SEP06 real workbooks, SEP06 client-validated - was
    # `diff - consumption`, which produced negative litres against real data).
    assert hs["stock_ltrs"] == 60           # = s1_hs_current
    # Section 6 stock amount = stock_ltrs x Buy Rate HS. 102.75 since migration
    # 0016 - the seeded 101.50 was wrong, confirmed against SEP06's own figures
    # (9,119 L x 102.75 = 936,977.25, the client-validated number).
    assert hs["stock_amount"] == 6165.0


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
    """Decision step 1: the escalation threshold rule, enforced server-side
    instead of being a comment nobody reliably reads. The threshold itself is
    the 'trial_balance_alert_threshold' parameter - Rs 50 since migration 0025.
    """
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


def test_threshold_is_fifty_not_the_seeded_hundred(client, auth_headers):
    """Migration 0025. The seed was Rs 100 and nothing had moved it, so a variance
    anywhere in the 50-100 band signed off silently. The client's figure has been
    Rs 50 all along (re-confirmed 2026-09-13), and the two tests above pass under
    either value - 250 breaches both, 21.87 clears both - so neither pinned it.
    75 is the case that tells them apart.
    """
    view = client.put(
        f"/daily-trial-balance/{DATE}",
        json={"s54_cash_book_value": 500000},
        headers=auth_headers("Manager"),
    ).json()
    reported = view["computed"]["section7"]["7_3_total"]

    breach = client.post(
        f"/daily-trial-balance/{DATE}/finalize",
        json={"projected_total": reported - 75},
        headers=auth_headers("Manager"),
    )
    assert breach.status_code == 422, "Rs 75 must demand a reason under the Rs 50 rule"
    assert "50" in breach.json()["detail"], breach.json()["detail"]

    ok = client.post(
        f"/daily-trial-balance/{DATE}/finalize",
        json={"projected_total": reported - 75, "reason": "Counted short, recounted next morning"},
        headers=auth_headers("Manager"),
    )
    assert ok.status_code == 200
    assert ok.json()["variance_amount"] == 75


def test_finalize_without_projected_total_skips_the_check(client, auth_headers):
    """The Projected total isn't computed server-side yet (ADR-1's remaining
    sections) - omitting it must not block sign-off."""
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 60},
               headers=auth_headers("Manager"))
    ok = client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    assert ok.status_code == 200
    assert ok.json()["variance_amount"] is None


# --- dropdown lists (migration 0021) -----------------------------------------


def test_option_lists_come_from_the_database(client, auth_headers):
    """The SEP12 sheet's own Data Validation lists, seeded. They are served rather
    than hard-coded in the renderer so the station can extend them itself."""
    lists = client.get("/daily-trial-balance/options", headers=auth_headers("Sales")).json()
    assert "Anil/Nani New Credit" in lists["creditors"]
    assert "Anil New Credit" in lists["creditors"]        # the sheet carries both spellings
    assert lists["expenses"] == [
        "Salaries Mid/End of Month - Total", "Power Bill", "Unload Beta",
        "Salary Advances Total",
    ]
    assert "Sajja Old Credit Remitted Amt" in lists["remittance"]
    assert "Anil Old Credit Remitted" in lists["old_credit"]
    assert "Gopi" in lists["staff"]


def test_sales_can_add_a_creditor_mid_entry(client, auth_headers, conn):
    """A new customer asking for credit is discovered by the maker, mid-entry. A
    form that can't take the name until a Manager logs in gets bypassed on paper,
    so Sales may add one - and it is audited."""
    r = client.post(
        "/daily-trial-balance/options",
        json={"list_key": "creditors", "value": "  Ramesh   Transport New Credit "},
        headers=auth_headers("Sales"),
    )
    assert r.status_code == 201
    # Stray whitespace collapsed, wording otherwise untouched.
    assert "Ramesh Transport New Credit" in r.json()["creditors"]

    again = client.get("/daily-trial-balance/options", headers=auth_headers("Manager")).json()
    assert "Ramesh Transport New Credit" in again["creditors"]  # persists for everyone

    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name = 'trial_balance_option'"
    ).fetchone()["c"] == 1


def test_a_duplicate_or_unknown_list_is_refused(client, auth_headers):
    assert client.post(
        "/daily-trial-balance/options",
        json={"list_key": "expenses", "value": "Power Bill"},
        headers=auth_headers("Manager"),
    ).status_code == 409
    assert client.post(
        "/daily-trial-balance/options",
        json={"list_key": "not_a_list", "value": "x"},
        headers=auth_headers("Manager"),
    ).status_code == 400
    assert client.post(
        "/daily-trial-balance/options",
        json={"list_key": "expenses", "value": "   "},
        headers=auth_headers("Manager"),
    ).status_code == 400


def test_expenses_is_one_shared_list_for_sections_4_and_8(client, auth_headers):
    """The SEP12 sheet points 4.6 and 8.6 at the same validation range, so a
    category added in either place must appear in both. One list key, not two."""
    added = client.post(
        "/daily-trial-balance/options",
        json={"list_key": "expenses", "value": "Borewell Repair"},
        headers=auth_headers("Owner"),
    ).json()
    assert added["expenses"][-1] == "Borewell Repair"


# --- whole-sheet export and date lookup (client, 2026-09-12) ------------------


def test_whole_trial_balance_exports_as_the_stations_own_sheet(client, auth_headers):
    """The export is not a rebuilt approximation - it is the client's SEP12 tab
    with the day's figures written into its input cells (client, 2026-09-12:
    "exactly the same thing"). So assert the SHEET's own headings came through
    untouched, and that our numbers landed in its cells."""
    import io

    from openpyxl import load_workbook

    h = auth_headers("Manager")
    client.put(f"/daily-trial-balance/{DATE}", json={
        "s1_hs_yesterday": 5514, "s1_hs_current": 4937,
        "s1_ms_yesterday": 7584, "s1_ms_current": 7043,
        "manual": {
            "section3": {"onhand": 76096.51, "night": 40000, "indianbank": 1311580.42},
            "section4": {"yesterday": 1861869.74, "yesbank_return": 8525.95},
            "section8": {"prepared_by": "Gopi", "verified_by": "Girish/Sriharsha"},
            "section10": {"hs_old": 2207, "hs_new": 12079, "hs_load": 10000},
            "section11": {"new_airtel": 64352},
        },
    }, headers=h)

    r = client.get(f"/daily-trial-balance/{DATE}/export-excel", headers=h)
    assert r.status_code == 200
    assert f"SVR-TrialBalance-{DATE}.xlsx" in r.headers["content-disposition"]

    ws = load_workbook(io.BytesIO(r.content))["SEP12"]

    # The station's own wording and layout, verbatim - spacing and typos included,
    # because any difference here means we stopped shipping their sheet.
    assert ws["A1"].value == "1.IOCL Stock Readings "
    assert ws["A5"].value == "2.Day Sales Report "
    assert ws["A18"].value == "2.1 Oil Sales"
    assert ws["A65"].value == "5.Stock Value  "
    assert ws["A131"].value.startswith("10.Load/Unload Details")

    # Its formulas are left alone, so Excel recalculates from the new inputs.
    assert ws["D3"].value == "=B3-C3"
    assert ws["D69"].value == "=D67+D68"
    assert ws["F26"].value == "=F19+F20+F21+F22+F23+F24+F25"

    # Our figures landed in its input cells.
    assert ws["B3"].value == 5514
    assert ws["C4"].value == 7043
    assert ws["B29"].value == 76096.51
    assert ws["D37"].value == 1311580.42
    assert ws["F55"].value == 8525.95
    assert ws["D103"].value == "Gopi"
    assert ws["C133"].value == 2207
    assert ws["B138"].value == 64352
    assert f"Trial Balance {DATE}" in ws["A2"].value

    # The two cross-sheet references become values - a one-tab export cannot
    # resolve ='SEP11'!D51 and would open showing #REF!.
    assert ws["D49"].value == 1861869.74


def test_there_is_no_2t_1_40_ml_anywhere(client, auth_headers):
    """Client-confirmed 2026-09-13: the station sells 2T/1.50 and 2T/2.40. There is
    no 1.40 pack and never was - it was a typo in the SEP12 tab, which row 20 of
    the shipped template inherited.

    Checked in the template itself and in an export, because the export writes the
    oil labels over rows 19-25 and would otherwise hide a stale one.
    """
    import io

    from openpyxl import load_workbook

    from svr_backend.excel.trial_balance_full import TEMPLATE

    def cells_mentioning(ws, needle):
        return [
            c.coordinate
            for row in ws.iter_rows(min_row=1, max_row=200, max_col=16)
            for c in row
            if isinstance(c.value, str) and needle in c.value
        ]

    tpl = load_workbook(TEMPLATE, data_only=False)["SEP12"]
    assert cells_mentioning(tpl, "1.40") == []
    assert tpl["A20"].value == "2T/2.40 ML Total#"

    h = auth_headers("Manager")
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 4937}, headers=h)
    out = client.get(f"/daily-trial-balance/{DATE}/export-excel", headers=h)
    ws = load_workbook(io.BytesIO(out.content))["SEP12"]
    assert cells_mentioning(ws, "1.40") == []
    # And the two packs that DO exist are both there.
    assert cells_mentioning(ws, "2T/1.50")
    assert cells_mentioning(ws, "2T/2.40")


def test_oil_opening_stock_comes_from_the_entry_that_sold_it(client, auth_headers):
    """Opening Stock is one tin's level, not something to merge across pumps.

    Oil Sale(s) is handled by one submitter a day. The other pump's entry carries
    the same rows filled in from Inventory, and once stored the two are
    indistinguishable - so merging them per row let this and the screen prefer
    opposite entries, and Acid Water's opening read 60 in the export against 64
    on screen. The sheet's D21 says 64.
    """
    import io

    from openpyxl import load_workbook

    h = auth_headers("Manager")
    # The Road pump records the oils; the Office pump leaves them blank.
    client.post("/daily-sales-entry", json={
        "pump_serial": "12BC4523V-RD", "shift_date": DATE,
        "hs": {"current": "1030"},
        "oils": [
            {"qty": "8", "rate": "17", "opening": "29"},   # sold
            {"qty": "0", "rate": "17", "opening": "0"},
            {"qty": "0", "rate": "30", "opening": "64"},   # NOT sold, still its stock
        ],
    }, headers=h)
    client.post("/daily-sales-entry", json={
        "pump_serial": "11CC2012V-OFF", "shift_date": DATE, "hs": {"current": "2020"},
    }, headers=h)
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 4937}, headers=h)

    r = client.get(f"/daily-trial-balance/{DATE}/export-excel", headers=h)
    ws = load_workbook(io.BytesIO(r.content))["SEP12"]

    assert ws["B19"].value == 8      # sold, from the owning entry
    assert ws["D19"].value == 29     # its opening - not 29 + the other pump's
    assert ws["D21"].value == 64     # a zero-quantity row still takes the owner's


def test_section8_heading_carries_the_records_date_not_todays(client, auth_headers):
    """The Section 8 heading names the report, so it must read the record's own
    day - not the day the export happened to run.

    This shipped wrong and twenty green tests said nothing: the stamp came off
    the clock, so exporting the SEP 12 Trial Balance at 7 a.m. on the 13th
    produced a sheet headed "SEP 13". Invisible while every day was worked on the
    day it happened; wrong the moment a past day is queried and exported, which is
    the whole point of the Query button.
    """
    import io
    from datetime import date

    from openpyxl import load_workbook

    h = auth_headers("Manager")
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 4937}, headers=h)
    r = client.get(f"/daily-trial-balance/{DATE}/export-excel", headers=h)
    heading = load_workbook(io.BytesIO(r.content))["SEP12"]["A81"].value

    on = date.fromisoformat(DATE).strftime("%b %d").upper()
    assert heading.startswith("8. Daily Management Reporting - ")
    assert on in heading, f"expected the record's day {on} in {heading!r}"
    assert heading.rstrip().endswith("IST")
    # DATE is in October, so a stamp taken off the clock would read SEP here and
    # the assertion above would catch it. The template's own frozen Sep 12
    # heading must be gone too.
    assert "SEPT 12" not in heading


def test_saved_dates_can_be_listed_without_knowing_them(client, auth_headers):
    """Query capability: the Date + Load pair retrieves one day, this finds a day
    when nobody remembers its date."""
    h = auth_headers("Manager")
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 60}, headers=h)

    rows = client.get("/daily-trial-balance", headers=h).json()
    assert [r["shift_date"] for r in rows] == [DATE]
    assert rows[0]["status"] == "draft"
    assert rows[0]["last_updated_by"] == "manager"

    # Range filters, newest first.
    assert client.get(
        f"/daily-trial-balance?date_from={DATE}&date_to={DATE}", headers=h
    ).json()[0]["shift_date"] == DATE
    assert client.get(
        "/daily-trial-balance?date_from=2099-01-01", headers=h
    ).json() == []


def test_sales_can_export_and_list(client, auth_headers):
    """The maker prepares the day, so neither is gated behind Manager."""
    h = auth_headers("Sales")
    assert client.get("/daily-trial-balance", headers=h).status_code == 200
    assert client.get(f"/daily-trial-balance/{DATE}/export-excel", headers=h).status_code == 200


def test_testing_deduction_counts_the_forms_submitted(client, auth_headers, conn):
    """Migrations 0026/0027, client 2026-09-14.

    Each pump draws 5 litres of diesel and 5 of petrol for testing. That fuel is
    pumped BACK into the tank afterwards, so the pump counted it but the site
    never lost it - which is why Section 1 takes it off when reconciling pump
    consumption against the IOCL tank reading. The money side is separate and
    lives on the DSR as an expense; Section 2 stays raw, deducting nothing.

    The count is SUBMISSIONS, not statuses: "whatever we submit you just take it,
    that's all. Don't make it based on the status. If the pump is in repair you
    don't have any reading; in all other cases you will have a reading."
    """
    day = "2026-10-20"
    h = auth_headers("Manager")

    def pulled(serials):
        conn.execute("DELETE FROM daily_sales_entry WHERE shift_date = ?", (day,))
        conn.commit()
        for serial in serials:
            client.post("/daily-sales-entry", json={
                "pump_serial": serial, "shift_date": day,
                "hs": {"current": "8000000"}, "ms": {"current": "8000000"},
            }, headers=h)
        return client.get(f"/daily-trial-balance/{day}", headers=h).json()["pulled"]

    both = pulled(["12BC4523V-RD", "11CC2012V-OFF"])
    assert both["testing_deduction"] == 10.0      # 5 + 5 off each fuel = 20 litres
    assert both["testing_pumps_tested"] == 2
    assert both["testing_basis"] == "derived"

    one = pulled(["12BC4523V-RD"])
    assert one["testing_deduction"] == 5.0        # 10 litres
    assert one["testing_pumps_tested"] == 1


def test_the_status_flag_does_not_change_the_deduction(client, auth_headers, conn):
    """The dropdown says WHY a pump is absent; it is not an input to arithmetic.
    A submitted form counts however it is labelled - client was explicit about
    this on 2026-09-14 after I had wired the status in."""
    day = "2026-10-21"
    h = auth_headers("Manager")
    for serial, status in (("12BC4523V-RD", "online"), ("11CC2012V-OFF", "repair")):
        client.post("/daily-sales-entry", json={
            "pump_serial": serial, "shift_date": day, "pump_status": status,
            "hs": {"current": "8000000"}, "ms": {"current": "8000000"},
        }, headers=h)
    pulled = client.get(f"/daily-trial-balance/{day}", headers=h).json()["pulled"]
    assert pulled["testing_pumps_tested"] == 2, "two forms came in, so two pumps count"
    assert pulled["testing_deduction"] == 10.0


def test_a_day_with_no_entry_falls_back_to_the_flat_parameter(client, auth_headers):
    """Nothing to count is not the same as nothing tested. An imported or
    historical record must keep the parameter it was computed under rather than
    silently deducting zero."""
    view = client.get("/daily-trial-balance/2098-03-03", headers=auth_headers("Manager")).json()
    assert view["pulled"]["testing_basis"] == "parameter"
    assert view["pulled"]["testing_pumps_tested"] is None
    assert view["pulled"]["testing_deduction"] > 0
