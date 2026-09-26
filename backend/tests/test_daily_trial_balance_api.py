"""Daily Trial Balance: Section 1 formulas (SDD 9 r1), Section 3 pull from Daily
Sales Summary, Section 6/7 stock value + total, finalize lock, maker-checker RBAC,
and ADR-2 Close & Sign-Off carry-forward (gating, seeding, variance escalation)."""

from __future__ import annotations

import json

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


def test_the_projected_total_is_computed_not_typed(client, auth_headers):
    """The box is gone; the ADR-2 escalation check is not.

    "Today's Projected Trial Balance (optional, from Section 7)" was a typed
    field, and the client asked for it to go (2026-09-25) - it is 7.3, which the
    form already computes from 7.1 + 7.2. The check now reads that figure.

    With 7.1 BLANK there is nothing to compare: 7.3 collapses to today's profit,
    and holding that against Net Worth would refuse to close every day whose 7.1
    had not been entered. So the check is skipped - decided by whether the data
    exists, not by whether someone filled in a second copy of it.
    """
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 60},
               headers=auth_headers("Manager"))
    ok = client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    assert ok.status_code == 200
    assert ok.json()["variance_amount"] is None


def test_a_breach_is_caught_from_the_computed_figure_with_no_box_to_type_in(
    client, auth_headers
):
    """7.1 entered, so 7.3 is real - and a day that is out by more than the
    threshold still demands a reason without anyone typing the projected total."""
    date = "2026-02-03"
    client.put(f"/daily-trial-balance/{date}", json={
        "s54_cash_book_value": 500000,
        "manual": {"section7": {"yesterday": 1000}},   # 7.3 = 1000 + today's profit
    }, headers=auth_headers("Manager"))

    breach = client.post(f"/daily-trial-balance/{date}/finalize",
                         headers=auth_headers("Manager"))
    assert breach.status_code == 422, breach.text
    assert "Actual Reported Minus Projected" in breach.json()["detail"]

    ok = client.post(f"/daily-trial-balance/{date}/finalize",
                     json={"reason": "Stock revalued after the IOCL load"},
                     headers=auth_headers("Manager"))
    assert ok.status_code == 200
    assert ok.json()["variance_amount"] is not None


# --- dropdown lists (migration 0021) -----------------------------------------


def test_option_lists_come_from_the_database(client, auth_headers):
    """The SEP12 sheet's own Data Validation lists, seeded. They are served rather
    than hard-coded in the renderer so the station can extend them itself."""
    lists = client.get("/daily-trial-balance/options", headers=auth_headers("Sales")).json()
    assert "Anil/Nani New Credit" in lists["creditors"]
    # "Anil New Credit" is gone from the OFFER as of migration 0028: the client
    # confirmed on 2026-09-14 that Anil and Nani are one person, and two
    # spellings of one creditor is how a balance ends up split in two. Records
    # already saved under the old label keep it - the screen renders a value that
    # is no longer listed rather than blanking the cell.
    assert "Anil New Credit" not in lists["creditors"]
    # Salary advances moved to the expenses list, named per person.
    assert not any(v.startswith("Salary Advance ") for v in lists["creditors"])
    assert "Salary Advances Ravindra" in lists["expenses"]
    assert "Other - If Any" in lists["expenses"]
    assert lists["expenses"] == [
        "Salaries Middle of the Month - Total",
        "Salaries End of the Month Total",
        "Power Bill",
        "Unload Beta",
        "Salary Advances Vijay",
        "Salary Advances Ravindra",
        "Salary Advances Ashok",
        "Other - If Any",
    ]
    assert "Sajja Old Credit Remitted Amt" in lists["remittance"]
    # 8.7 Old Credit Collections is aligned to the Remittance wording. The sheet
    # spelled the same creditor two ways ("Anil Old Credit Remitted" here,
    # "Anil/Nani Old Credit Remitted Amt" in 4.7), which is how one balance ends
    # up recorded as two. FLAGGED to the client, not assumed settled.
    assert lists["old_credit"] == lists["remittance"]
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
    # The template's own 2.1 labels are blank since 2026-09-25 - it ships no
    # station data at all now, and BOTH exports write the oil names from the live
    # item list. So the pack names are asserted on what comes OUT, below and in
    # test_the_blank_form_names_its_oil_rows, rather than on the template.
    assert tpl["A20"].value in (None, "")

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


def test_section10_shows_the_last_load_on_the_days_between_deliveries(
    client, auth_headers
):
    """IOCL delivers about every ten days; Section 10 went blank in between.

    Client, 2026-09-25: "This data should be there until the next load comes in
    which is typically 10 days old need to keep."

    Carried for display only. The day the load arrived owns the record - copying
    it into each following day would put the same delivery on the books nine
    more times - so the following day gets `last_load` and an empty section10 of
    its own.
    """
    h = auth_headers("Manager")
    load_day, quiet_day = "2026-03-02", "2026-03-01"   # ADR-2: later date first

    client.put(f"/daily-trial-balance/{load_day}", json={
        "s1_hs_current": 4937,
        "manual": {"section10": {
            "hs_afterunload": "12207", "hs_old": "2207",
            "hs_new": "12079", "hs_load": "10000",
        }},
    }, headers=h)

    # The delivery day shows its own figures and carries nothing.
    own = client.get(f"/daily-trial-balance/{load_day}", headers=h).json()
    assert own["manual"]["section10"]["hs_new"] == "12079"
    assert own["last_load"] is None, "the day of the load must not carry itself"

    # A day with no delivery of its own carries the last one, named by its date.
    quiet = client.get(f"/daily-trial-balance/{quiet_day}", headers=h).json()
    assert (quiet["manual"].get("section10") or {}) == {}, "nothing recorded here"
    # 2026-03-01 is BEFORE the load, so there is nothing yet to carry.
    assert quiet["last_load"] is None

    later = "2026-03-09"
    client.put(f"/daily-trial-balance/{later}", json={"s1_hs_current": 4937}, headers=h)
    after = client.get(f"/daily-trial-balance/{later}", headers=h).json()
    assert after["last_load"] is not None, "the last delivery is unreachable"
    assert after["last_load"]["shift_date"] == load_day
    assert after["last_load"]["values"]["hs_new"] == "12079"
    assert not (after["manual"].get("section10") or {}), "carried, never stored"


def test_the_export_never_carries_the_templates_own_day(client, auth_headers):
    """A field this day has no value for must come out EMPTY, not showing SEP12's.

    The template IS the station's real SEP12 tab - that is the point, it carries
    their bands, formulas and column widths - and the writer deliberately skips a
    cell when there is nothing to put. Together that meant an export of any other
    day came out holding SEP12's figures wherever this day was quiet: its
    Load/Unload readings, its Airtel balances, its whole 30-row Mgr ledger, and an
    "Anil New Credit 1500" nobody had entered.

    Client, 2026-09-25: "Export to Trail balance to Excel Sheet is incomplete and
    it has lot empty rows." Empty is the correct outcome; a fortnight-old number
    presented as today's is not.
    """
    import io

    from openpyxl import load_workbook

    h = auth_headers("Manager")
    # A day with Section 1 only - nothing in 3.14, 4.6, 4.7, 8.6, 9, 10 or 11.
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 4937}, headers=h)
    ws = load_workbook(
        io.BytesIO(client.get(f"/daily-trial-balance/{DATE}/export-excel", headers=h).content)
    )["SEP12"]

    for ref, what in (
        ("A46", "3.14 New Credit - SEP12's 'Anil New Credit'"),
        ("D46", "3.14 New Credit - SEP12's 1500"),
        ("A55", "4.6 Expenses - SEP12's category"),
        ("A61", "4.7 Credit Remittance - SEP12's creditor"),
        ("A88", "8.6 Regular Expenses - SEP12's category"),
        ("A109", "9. Mgr ledger - SEP12's first dated row"),
        ("B109", "9. Mgr ledger - SEP12's MS sale"),
        ("A127", "9. Mgr ledger - SEP12's last dated row"),
        ("B133", "10. Load/Unload - SEP12's HS reading"),
        ("E134", "10. Load/Unload - SEP12's MS IOCL load"),
        ("B138", "11.1 - SEP12's Airtel balance"),
        ("B139", "11.2 - SEP12's old Airtel balance"),
    ):
        assert ws[ref].value in (None, ""), f"{ref} still carries {what}: {ws[ref].value!r}"

    # The sheet's own structure is untouched - only the input cells are cleared.
    assert ws["A107"].value and "Mgr" in str(ws["A107"].value)      # section heading
    assert str(ws["D109"].value or "").startswith("=")              # its formula
    assert ws["B3"].value == 4937 or ws["C3"].value == 4937         # and the day IS written


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


def test_testing_deducts_five_for_every_nozzle_that_moved(client, auth_headers):
    """Client, 2026-09-14, the rule in full:

        "Section 2 has four readings. When last reading and current reading
         becomes zero for that pump we do not deduct anything - for HS, and for
         MS also... When the difference is not zero, we deduct 5 litres."

    The tested fuel is pumped BACK into the tank, so the pump counted it but the
    site never lost it - which is why Section 1 subtracts it when reconciling
    pump consumption against the IOCL tank reading. The money side is separate
    and lives on the DSR as an expense the salesman takes off his own hand-off.

    Read straight off the four readings: no dropdown, no status, no counting of
    submissions.
    """
    h = auth_headers("Manager")

    def pulled(day, pumps):
        for serial, hs, ms in pumps:
            client.post("/daily-sales-entry", json={
                "pump_serial": serial, "shift_date": day,
                "hs": {"current": hs[0], "last": hs[1]},
                "ms": {"current": ms[0], "last": ms[1]},
            }, headers=h)
        return client.get(f"/daily-trial-balance/{day}", headers=h).json()["pulled"]

    both = pulled("2026-10-20", [
        ("12BC4523V-RD", ("9000500", "9000000"), ("9000600", "9000000")),
        ("11CC2012V-OFF", ("9000700", "9000000"), ("9000800", "9000000")),
    ])
    assert both["testing_nozzles_hs"] == 2 and both["testing_nozzles_ms"] == 2
    assert both["testing_deduction_hs"] == 10.0
    assert both["testing_deduction_ms"] == 10.0

    # One pump idle. Last Shift Reading is backend-owned and carries from that
    # pump's own previous entry, so "idle" means repeating yesterday's Current
    # Reading - 9000700 / 9000800 from the day above - not an arbitrary figure.
    one = pulled("2026-10-21", [
        ("12BC4523V-RD", ("9001000", "9000500"), ("9001100", "9000600")),
        ("11CC2012V-OFF", ("9000700", "9000700"), ("9000800", "9000800")),
    ])
    assert one["testing_nozzles_hs"] == 1 and one["testing_nozzles_ms"] == 1
    assert one["testing_deduction_hs"] == 5.0
    assert one["testing_deduction_ms"] == 5.0


def test_a_nozzle_can_be_tested_while_its_partner_is_not(client, auth_headers):
    """The fuels are counted separately, so a pump with one working nozzle
    deducts for that nozzle only. This is the SEP12 shape: the office pump's
    petrol moved 17.5 litres while its diesel never moved at all."""
    h = auth_headers("Manager")
    day = "2026-10-22"
    # Same carry-forward rule: the office pump's diesel repeats 9000700 (idle),
    # while its petrol moves 17.5 from the 9000800 it carried.
    for serial, hs, ms in (
        ("12BC4523V-RD", ("9001500", "9001000"), ("9001600", "9001100")),
        ("11CC2012V-OFF", ("9000700", "9000700"), ("9000817.5", "9000800")),
    ):
        client.post("/daily-sales-entry", json={
            "pump_serial": serial, "shift_date": day,
            "hs": {"current": hs[0], "last": hs[1]},
            "ms": {"current": ms[0], "last": ms[1]},
        }, headers=h)
    p = client.get(f"/daily-trial-balance/{day}", headers=h).json()["pulled"]
    assert p["testing_nozzles_hs"] == 1, "only the road pump's diesel ran"
    assert p["testing_nozzles_ms"] == 2, "both petrol nozzles ran"
    assert p["testing_deduction_hs"] == 5.0
    assert p["testing_deduction_ms"] == 10.0


def test_a_day_with_no_entry_falls_back_to_the_flat_parameter(client, auth_headers):
    """Nothing to count is not the same as nothing tested. An imported or
    historical record must keep the parameter it was computed under rather than
    silently deducting zero."""
    view = client.get("/daily-trial-balance/2098-03-03", headers=auth_headers("Manager")).json()
    assert view["pulled"]["testing_basis"] == "parameter"
    assert view["pulled"]["testing_nozzles_hs"] is None
    assert view["pulled"]["testing_deduction"] > 0


def test_the_cash_book_difference_is_checked_at_sign_off(client, auth_headers):
    """Section 4's own escalation, which was never checked here at all - only
    Section 7's projected total was, so a cash/book difference of any size signed
    off in silence. The sheet carries the rule on its face at E53."""
    day = "2026-10-28"
    h = auth_headers("Manager")
    client.put(f"/daily-trial-balance/{day}", json={
        "s1_hs_current": 60,
        "manual": {"section4": {"yesterday": 100000, "todaysale": 5000, "reported": 104250}},
    }, headers=h)
    # 104,250 reported against 105,000 projected = -750, well beyond Rs 50.
    blocked = client.post(f"/daily-trial-balance/{day}/finalize", headers=h)
    assert blocked.status_code == 422, blocked.text
    assert "4.5 Diff Reported - Projected" in blocked.json()["detail"]

    ok = client.post(f"/daily-trial-balance/{day}/finalize",
                     json={"reason": "Counted short, recount in the morning"}, headers=h)
    assert ok.status_code == 200, ok.text


def test_on_a_bank_return_day_it_reads_4_10_not_4_5(client, auth_headers):
    """SEP12 is the case this exists for: 4.5 read 8,516.15 where the real figure
    was -9.80, because Yes Bank had returned 8,525.95. Checking 4.5 there would
    demand a reason for money that was never missing."""
    day = "2026-10-29"
    h = auth_headers("Manager")
    view = client.put(f"/daily-trial-balance/{day}", json={
        "s1_hs_current": 60,
        "manual": {"section4": {
            "yesterday": 100000, "todaysale": 5000, "reported": 113516.15,
            "yesbank_return": 8525.95,
        }},
    }, headers=h).json()
    s4 = view["computed"]["derived"]["section4"]
    assert round(s4["diff"], 2) == 8516.15          # 4.5 - looks alarming
    assert round(s4["total_difference"], 2) == -9.80  # 4.10 - the truth

    # 4.10 is inside the limit, so sign-off goes through with no reason asked.
    ok = client.post(f"/daily-trial-balance/{day}/finalize", headers=h)
    assert ok.status_code == 200, ok.text


def test_closing_without_a_verified_summary_warns_but_is_allowed(client, auth_headers):
    """Hard-gating sign-off on the Summary was raised with the client twice and
    never decided, so it is NOT imposed - and their own fallback is that a
    Manager may close a day when the maker is off. What was wrong was that
    `summary_status` had been returned since this endpoint was built and nothing
    ever looked at it, so a day could close on unverified figures in silence."""
    day = "2026-10-30"
    h = auth_headers("Manager")
    client.put(f"/daily-trial-balance/{day}", json={"s1_hs_current": 60}, headers=h)
    out = client.post(f"/daily-trial-balance/{day}/finalize", headers=h)
    assert out.status_code == 200, "a warning, never a refusal"
    note = out.json().get("summary_note", "")
    assert "No Daily Sales Entry" in note
    assert "Closed anyway, which is allowed" in note


def test_the_blank_form_names_its_oil_rows(client, auth_headers):
    """A form to write on has to say what each row is.

    _clear_inputs() blanks column A of 2.1 with the figures - right for a filled
    export, which rewrites those labels from the live item list, and wrong for
    the blank one, which would otherwise print seven unnamed rows.
    """
    import io

    from openpyxl import load_workbook

    r = client.get("/daily-trial-balance/export-excel-blank", headers=auth_headers("Sales"))
    assert r.status_code == 200
    assert "SVR-TrialBalance-BLANK.xlsx" in r.headers["content-disposition"]
    ws = load_workbook(io.BytesIO(r.content))["SEP12"]

    labels = [ws.cell(row=row, column=1).value for row in range(19, 26)]
    assert any(label and "2T/1.50" in str(label) for label in labels), labels
    assert any(label and "2T/2.40" in str(label) for label in labels), labels

    # ...and it is genuinely blank: no figures, on any section.
    for ref in ("B19", "B29", "D36", "D49", "D50", "B133", "B138"):
        assert ws[ref].value in (None, ""), f"{ref} is not blank: {ws[ref].value!r}"
    # ...but it keeps the sheet's own numbering and formulas.
    assert str(ws["A29"].value).startswith("3.1")
    assert str(ws["A103"].value).startswith("8.16")
    assert str(ws["D51"].value or "").startswith("=")


def test_the_blank_form_carries_working_dropdowns(client, auth_headers):
    """Every dropdown offers the station's CURRENT values, from a named range.

    The client reported "NO DROP DOWN VALUES" (2026-09-25). Driving real Excel
    over their exported copy afterwards showed the dropdowns were in fact live;
    what was wrong was what they offered - the template's frozen SEP12 lists,
    including a "Salary Advance Viaj" typo and a salary advance that migration
    0037 had already taken off the creditors list.

    So the assertion that matters is the VALUES, and that they are rebuilt from
    trial_balance_option rather than shipped in the template. The named range is
    asserted too, because it is what puts those values on a tab the station can
    read and correct.
    """
    import io

    from openpyxl import load_workbook

    h = auth_headers("Manager")
    wb = load_workbook(
        io.BytesIO(client.get("/daily-trial-balance/export-excel-blank", headers=h).content)
    )
    assert "Lists" in wb.sheetnames, "no Lists tab to back the dropdowns"
    ws, lists = wb["SEP12"], wb["Lists"]

    by_range = {str(dv.sqref): dv.formula1 for dv in ws.data_validations.dataValidation}
    # 4.6 Expenses, 8.6 Regular Expenses, 4.7 Credit Remittance, 3.14 New Credit.
    for ref in ("A55:A58", "A88:A90", "A60:A62", "A43:A46", "D103:D105"):
        assert ref in by_range, f"{ref} has no dropdown"
        assert by_range[ref].startswith("=SVR_"), (
            f"{ref} is not backed by a named range: {by_range[ref]!r}"
        )

    # And the range it points at actually holds the station's own values.
    from openpyxl.utils import range_boundaries

    def values_behind(ref: str) -> list[str]:
        name = by_range[ref].lstrip("=")
        cells = str(wb.defined_names[name].attr_text).split("!", 1)[1]
        mn_c, mn_r, mx_c, mx_r = range_boundaries(cells.replace("$", ""))
        return [
            lists.cell(row=r, column=mn_c).value
            for r in range(mn_r, mx_r + 1)
            if lists.cell(row=r, column=mn_c).value
        ]

    expenses = values_behind("A55:A58")
    assert "Power Bill" in expenses, expenses
    assert by_range["A88:A90"] == by_range["A55:A58"], "8.6 must use the same list as 4.6"
    remittances = values_behind("A60:A62")
    assert any("Remitted" in v for v in remittances), remittances
    # The stale SEP12 lists the template shipped are gone for good.
    assert not any("Viaj" in v for v in expenses + remittances)
    assert not any("advance" in v.lower() for v in values_behind("A43:A46"))


def test_closing_a_day_seeds_tomorrows_4_1_from_the_computed_figure(
    client, auth_headers, conn
):
    """ADR-2's whole point: tomorrow's 4.1 comes from today, not from a keyboard.

    This broke silently. 4.4 stopped being typed on 2026-09-24 (it comes from
    3.15), so `manual["section4"]["reported"]` is empty on every day entered
    since - and the seed read exactly there. SEP15's draft was created with a
    blank 4.1 while SEP14 had closed on 2,305,795.10, which is the hand-typed
    cross-day reference ADR-2 was written to abolish.
    """
    day, tomorrow = "2026-04-07", "2026-04-08"
    client.put(f"/daily-trial-balance/{day}", json={
        "s1_hs_current": 4937,
        "s54_cash_book_value": 500000,
        # 4.4 is DERIVED from 3.15 - nothing is typed into it.
        "manual": {"section3": {"onhand": 250000, "night": 100000}},
    }, headers=auth_headers("Manager"))
    closed = client.post(f"/daily-trial-balance/{day}/finalize",
                         json={"reason": "seed test"},
                         headers=auth_headers("Manager"))
    assert closed.status_code == 200, closed.text[:300]

    todays = closed.json()["computed"]["derived"]
    reported = todays["section4"]["reported"]
    assert reported, "4.4 did not compute, so this test proves nothing"

    seeded = json.loads(
        conn.execute("SELECT manual_json FROM daily_trial_balance WHERE shift_date = ?",
                     (tomorrow,)).fetchone()["manual_json"] or "{}"
    )
    assert seeded.get("section4", {}).get("yesterday") == reported, (
        f"tomorrow's 4.1 is {seeded.get('section4')}, today's 4.4 was {reported}"
    )
    # 7.1 is NOT seeded, on purpose. Carrying it switches the ADR-2 escalation
    # check on for every day, and on the client's real SEP15 -> SEP16 figures
    # that refuses sign-off with 7.4 = -170,354.42. Their sheet reads 7.4 as
    # "report to mgmt", not as a gate, so this is their decision to make.
    assert "section7" not in seeded, seeded
