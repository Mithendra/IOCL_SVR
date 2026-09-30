"""Posting the Trial Balance's lines to the master forms (client, 2026-09-14).

    "Part of the Close and Sign off, all three categories should be posted...
     Unless posted do not allow Close & Sign Off."

    "Expenses will be posted on that given day... you still show them till end of
     the month, then you clear those expenses. Credit: first not paid, then
     posted, then once it comes back to paid we'll clear them on a monthly basis.
     Once you do the remittance it goes to paid status."

The lines are already counted in the Trial Balance's own arithmetic. Posting
copies them OUT for reporting; it must never feed back into a total here, and
expenses and remittances are not part of the next day's accounting.
"""

from __future__ import annotations

DATE = "2026-11-10"
NEXT = "2026-11-11"


def _day(client, auth_headers, date, *, expenses=(), credits_=(), remittances=()):
    manual = {
        "section4": {
            "expenses": [{"category": c, "amount": a} for c, a in expenses],
            "remittance": [{"type": t, "amount": a} for t, a in remittances],
        },
        "section3": {
            "new_credits": [{"type": t, "amount": a} for t, a in credits_],
        },
    }
    return client.put(
        f"/daily-trial-balance/{date}",
        json={"s1_hs_current": 60, "manual": manual},
        headers=auth_headers("Manager"),
    )


def test_close_and_sign_off_is_refused_until_the_lines_are_posted(client, auth_headers):
    _day(client, auth_headers, DATE,
         expenses=[("Power Bill", 8525.95)],
         credits_=[("AirTel Hari New Credit", 11674)])

    blocked = client.post(f"/daily-trial-balance/{DATE}/finalize",
                          headers=auth_headers("Manager"))
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert "not posted" in detail
    assert "Power Bill" in detail and "AirTel Hari New Credit" in detail

    posted = client.post(f"/daily-trial-balance/{DATE}/post",
                         headers=auth_headers("Manager"))
    assert posted.status_code == 200
    assert posted.json()["posted"] == 2

    ok = client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    assert ok.status_code == 200, ok.text


def test_an_expense_reaches_monthly_expenses(client, auth_headers, conn):
    date = "2026-11-12"
    _day(client, auth_headers, date, expenses=[("Power Bill", 8525.95)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))

    row = conn.execute(
        "SELECT me.amount, me.expense_date, ec.name FROM monthly_expense me "
        "JOIN expense_category ec ON ec.id = me.category_id WHERE me.expense_date = ?",
        (date,),
    ).fetchone()
    assert row is not None, "the expense never reached Monthly Expenses"
    assert row["amount"] == 8525.95
    assert row["name"] == "Power Bill"


def test_a_category_the_station_invents_posts_without_a_code_change(client, auth_headers, conn):
    """The Trial Balance list is editable, so a new value has to post on its own.
    Matched on the station's own wording, created if it is not there yet."""
    date = "2026-11-13"
    _day(client, auth_headers, date, expenses=[("Salary Advances Ravindra", 10000)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    row = conn.execute(
        "SELECT ec.name, ec.kind FROM monthly_expense me JOIN expense_category ec "
        "ON ec.id = me.category_id WHERE me.expense_date = ?", (date,)
    ).fetchone()
    assert row["name"] == "Salary Advances Ravindra"
    assert row["kind"] == "payroll", "an advance is payroll, not an operational cost"


def test_a_salary_advance_picked_in_3_14_reaches_monthly_expenses(
    client, auth_headers, conn
):
    """A salary or a staff advance is an EXPENSE, wherever it was typed.

    Client, 2026-09-25: "Any Salary or Bi-weekly Salary or Month end salary
    entered in Daily Trial balance as Expense and when those transaction are
    posted from Trail those should appear in Monthly Expenses."

    Section 3.14 is called "New Credit / Salary Advance" and feeds the credit
    master, so "Salary Advance Reavindra" picked there posted as a CREDITOR - it
    showed under New Credit in the Credit/Remittance Master owing the station
    10,000, and never reached Monthly Expenses (client's screenshot, same day).
    """
    date = "2026-11-08"
    _day(client, auth_headers, date, credits_=[("Salary Advance Reavindra", 10000)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))

    row = conn.execute(
        "SELECT me.amount, ec.name, ec.kind FROM monthly_expense me "
        "JOIN expense_category ec ON ec.id = me.category_id WHERE me.expense_date = ?",
        (date,),
    ).fetchone()
    assert row is not None, "the salary advance never reached Monthly Expenses"
    assert row["amount"] == 10000
    assert row["kind"] == "payroll"
    # And it is NOT a creditor - nobody owes the station this money.
    assert conn.execute(
        "SELECT COUNT(*) c FROM credit_transaction WHERE txn_date = ?", (date,)
    ).fetchone()["c"] == 0


def test_a_real_fuel_credit_is_untouched_by_the_salary_rule(client, auth_headers, conn):
    """The rule reads the label, so it must not swallow a genuine creditor.
    None of the station's real creditors carry 'salary' or 'advance'."""
    date = "2026-11-07"
    _day(client, auth_headers, date, credits_=[("Anil/Nani New Credit", 2000)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    row = conn.execute(
        "SELECT kind, creditor_name FROM credit_transaction WHERE txn_date = ?", (date,)
    ).fetchone()
    assert row["kind"] == "credit"
    assert row["creditor_name"] == "Anil/Nani"


def test_a_credit_reaches_credit_master_under_the_creditor_name(client, auth_headers, conn):
    date = "2026-11-14"
    _day(client, auth_headers, date, credits_=[("AirTel Hari New Credit", 11674)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    row = conn.execute(
        "SELECT kind, creditor_name, amount FROM credit_transaction WHERE txn_date = ?",
        (date,),
    ).fetchone()
    assert row["kind"] == "credit"
    # The dropdown says "AirTel Hari New Credit"; the balance groups by the NAME.
    assert row["creditor_name"] == "AirTel Hari"
    assert row["amount"] == 11674


def test_a_remittance_turns_that_creditors_credit_to_paid(client, auth_headers, conn):
    """"Once you do the remittance there, this goes to paid status." These are
    short-term credits - taken today, paid the next day or the one after."""
    _day(client, auth_headers, "2026-11-15",
         credits_=[("Anil/Nani New Credit", 1500)])
    client.post("/daily-trial-balance/2026-11-15/post", headers=auth_headers("Manager"))
    client.post("/daily-trial-balance/2026-11-15/finalize", headers=auth_headers("Manager"))

    before = conn.execute(
        "SELECT status FROM trial_balance_posting WHERE category = 'credit' "
        "AND shift_date = '2026-11-15'").fetchone()
    assert before["status"] == "posted", "not paid until a remittance says so"

    _day(client, auth_headers, "2026-11-16",
         remittances=[("Anil/Nani Old Credit Remitted Amt", 1500)])
    out = client.post("/daily-trial-balance/2026-11-16/post",
                      headers=auth_headers("Manager")).json()
    assert out["settled"] == 1

    after = conn.execute(
        "SELECT status, paid_at FROM trial_balance_posting WHERE category = 'credit' "
        "AND shift_date = '2026-11-15'").fetchone()
    assert after["status"] == "paid"
    assert after["paid_at"]


def test_the_running_view_spans_days(client, auth_headers):
    """A line does not vanish once posted. An unpaid credit from Tuesday has to
    still be in front of the operator on Thursday."""
    _day(client, auth_headers, "2026-11-21", credits_=[("AirTel Hari New Credit", 900)])
    client.post("/daily-trial-balance/2026-11-21/post", headers=auth_headers("Manager"))
    client.post("/daily-trial-balance/2026-11-21/finalize", headers=auth_headers("Manager"))

    _day(client, auth_headers, "2026-11-22", expenses=[("Power Bill", 250)])
    client.post("/daily-trial-balance/2026-11-22/post", headers=auth_headers("Manager"))

    lines = client.get("/daily-trial-balance/postings/open",
                       headers=auth_headers("Sales")).json()["lines"]
    dates = {ln["shift_date"] for ln in lines}
    assert dates == {"2026-11-21", "2026-11-22"}, "both days stay on view"
    assert all(ln["status"] != "cleared" for ln in lines)
    # Tuesday's credit is still unpaid and still showing on Wednesday.
    credit = next(ln for ln in lines if ln["category"] == "credit")
    assert credit["shift_date"] == "2026-11-21" and credit["status"] == "posted"

    # And the month filter narrows it without losing either.
    nov = client.get("/daily-trial-balance/postings/open?month=2026-11",
                     headers=auth_headers("Sales")).json()["lines"]
    assert len(nov) == len(lines)
    assert client.get("/daily-trial-balance/postings/open?month=2026-10",
                      headers=auth_headers("Sales")).json()["lines"] == []


def test_only_settled_lines_can_be_cleared(client, auth_headers, conn):
    """Month-end tidy-up. An UNPAID credit is exactly what must keep showing, and
    an unposted line has not reached a master form at all."""
    date = "2026-11-17"
    _day(client, auth_headers, date,
         expenses=[("Unload Beta", 365)], credits_=[("Sajja Function Hall - New Credit", 5000)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))

    rows = {r["category"]: r["id"] for r in conn.execute(
        "SELECT id, category FROM trial_balance_posting WHERE shift_date = ?", (date,))}
    out = client.post("/daily-trial-balance/postings/clear",
                      json={"ids": [rows["expense"], rows["credit"]]},
                      headers=auth_headers("Manager")).json()
    assert out["cleared"] == 1, "the posted expense clears; the unpaid credit must not"

    still = conn.execute(
        "SELECT status FROM trial_balance_posting WHERE id = ?", (rows["credit"],)
    ).fetchone()
    assert still["status"] == "posted"


def test_posting_twice_does_not_duplicate(client, auth_headers, conn):
    date = "2026-11-18"
    _day(client, auth_headers, date, expenses=[("Power Bill", 100)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    again = client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    assert again.json()["posted"] == 0, "nothing left unposted to post"
    n = conn.execute(
        "SELECT COUNT(*) c FROM monthly_expense WHERE expense_date = ?", (date,)
    ).fetchone()["c"]
    assert n == 1


def test_a_blank_row_is_not_a_line(client, auth_headers, conn):
    """The form always carries empty rows waiting to be filled. Posting those
    would put a zero expense into Monthly Expenses every single day."""
    date = "2026-11-19"
    client.put(f"/daily-trial-balance/{date}", json={
        "s1_hs_current": 60,
        "manual": {"section4": {"expenses": [
            {"category": "", "amount": ""},
            {"category": "Power Bill", "amount": ""},
            {"category": "", "amount": 500},
        ]}},
    }, headers=auth_headers("Manager"))
    n = conn.execute(
        "SELECT COUNT(*) c FROM trial_balance_posting WHERE shift_date = ?", (date,)
    ).fetchone()["c"]
    assert n == 0, "a row needs BOTH a label and an amount to be a line"
    assert client.post(f"/daily-trial-balance/{date}/finalize",
                       headers=auth_headers("Manager")).status_code == 200


def test_posting_never_changes_the_days_own_figures(client, auth_headers):
    """The lines are already counted in the Trial Balance. Posting copies them
    out; it must not move a total here or feed carry-forward."""
    date = "2026-11-20"
    before = _day(client, auth_headers, date, expenses=[("Power Bill", 8525.95)]).json()
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    after = client.get(f"/daily-trial-balance/{date}", headers=auth_headers("Manager")).json()
    assert after["computed"] == before["computed"]
    assert after["derived"] == before["derived"] if "derived" in after else True


# --- reopening a signed-off day ----------------------------------------------


def test_reopening_a_day_takes_its_postings_back_out(client, auth_headers, conn):
    """Until now a closed day was locked forever with no way back - fine until
    someone signs off a wrong figure, which during live testing will happen.

    Reopening must UN-POST, or the correction leaves a duplicate expense in
    Monthly Expenses and a creditor's balance counted twice.
    """
    date = "2026-11-25"
    _day(client, auth_headers, date,
         expenses=[("Power Bill", 8525.95)], credits_=[("AirTel Hari New Credit", 11674)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    client.post(f"/daily-trial-balance/{date}/finalize", headers=auth_headers("Manager"))

    assert conn.execute("SELECT COUNT(*) c FROM monthly_expense").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM credit_transaction").fetchone()["c"] == 1

    out = client.post(f"/daily-trial-balance/{date}/reopen", headers=auth_headers("Owner"))
    assert out.status_code == 200, out.text
    assert out.json()["status"] == "draft"
    assert out.json()["unposted"] == 2

    # The master forms are clean again - nothing stranded.
    assert conn.execute("SELECT COUNT(*) c FROM monthly_expense").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM credit_transaction").fetchone()["c"] == 0
    assert conn.execute(
        "SELECT COUNT(*) c FROM trial_balance_posting WHERE status = 'not_posted'"
    ).fetchone()["c"] == 2

    # And it re-posts cleanly rather than duplicating.
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    assert conn.execute("SELECT COUNT(*) c FROM monthly_expense").fetchone()["c"] == 1


def test_only_an_owner_can_reopen(client, auth_headers):
    date = "2026-11-26"
    _day(client, auth_headers, date, expenses=[("Power Bill", 100)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    client.post(f"/daily-trial-balance/{date}/finalize", headers=auth_headers("Manager"))
    for role in ("Sales", "Manager"):
        assert client.post(f"/daily-trial-balance/{date}/reopen",
                           headers=auth_headers(role)).status_code == 403


def test_a_day_underneath_a_closed_one_cannot_be_reopened(client, auth_headers):
    """ADR-2's whole point is that a day is built on the one before it. Reopening
    underneath a closed day would leave that day's carried figures pointing at
    something that no longer exists."""
    for d in ("2026-11-27", "2026-11-28"):
        _day(client, auth_headers, d, expenses=[("Power Bill", 50)])
        client.post(f"/daily-trial-balance/{d}/post", headers=auth_headers("Manager"))
        client.post(f"/daily-trial-balance/{d}/finalize", headers=auth_headers("Manager"))

    blocked = client.post("/daily-trial-balance/2026-11-27/reopen", headers=auth_headers("Owner"))
    assert blocked.status_code == 409
    assert "2026-11-28" in blocked.json()["detail"]
    assert "reverse order" in blocked.json()["detail"]

    # In the right order it works.
    assert client.post("/daily-trial-balance/2026-11-28/reopen",
                       headers=auth_headers("Owner")).status_code == 200
    assert client.post("/daily-trial-balance/2026-11-27/reopen",
                       headers=auth_headers("Owner")).status_code == 200


def test_a_paid_credit_is_not_un_settled_by_reopening(client, auth_headers, conn):
    """Its remittance came in on some OTHER day. Un-settling it here would
    resurrect a debt the creditor has already cleared."""
    _day(client, auth_headers, "2026-11-29", credits_=[("Anil/Nani New Credit", 1500)])
    client.post("/daily-trial-balance/2026-11-29/post", headers=auth_headers("Manager"))
    client.post("/daily-trial-balance/2026-11-29/finalize", headers=auth_headers("Manager"))
    _day(client, auth_headers, "2026-11-30",
         remittances=[("Anil/Nani Old Credit Remitted Amt", 1500)])
    client.post("/daily-trial-balance/2026-11-30/post", headers=auth_headers("Manager"))
    client.post("/daily-trial-balance/2026-11-30/finalize", headers=auth_headers("Manager"))

    assert conn.execute(
        "SELECT status FROM trial_balance_posting WHERE shift_date = '2026-11-29'"
    ).fetchone()["status"] == "paid"

    client.post("/daily-trial-balance/2026-11-30/reopen", headers=auth_headers("Owner"))
    out = client.post("/daily-trial-balance/2026-11-29/reopen", headers=auth_headers("Owner")).json()
    assert out["left_paid"] == 1
    assert conn.execute(
        "SELECT status FROM trial_balance_posting WHERE shift_date = '2026-11-29'"
    ).fetchone()["status"] == "paid", "a settled debt must not come back"


def test_sign_off_carries_the_days_oil_stock_into_inventory(client, auth_headers, conn):
    """Agreed a while back and never built - which is why every figure in
    Inventory Master was still migration 0004's placeholder until the client's
    own count arrived on 2026-09-15, six of seven wrong and nobody able to see it.

    Sign-off is the right moment: the day's figures are final. It is a SET from
    the real Closing Stock, not an increment, so running it twice is safe.
    """
    date = "2026-12-10"
    h = auth_headers("Manager")
    key = conn.execute(
        "SELECT item_key FROM oil_item WHERE label = '2T/2.40 ML Total#'").fetchone()["item_key"]
    before = conn.execute(
        "SELECT on_hand FROM inventory_item WHERE item_key = ?", (key,)).fetchone()["on_hand"]

    client.post("/daily-sales-entry", json={
        "pump_serial": "12BC4523V-RD", "shift_date": date,
        "hs": {"current": "9700000"}, "ms": {"current": "9700000"},
        "oils": [{"label": "2T/2.40 ML Total#", "qty": "3", "rate": "17", "opening": "20"}],
    }, headers=h)
    client.put(f"/daily-trial-balance/{date}", json={"s1_hs_current": 60}, headers=h)

    out = client.post(f"/daily-trial-balance/{date}/finalize", headers=h)
    assert out.status_code == 200, out.text
    assert "stock_synced" in out.json()

    after = conn.execute(
        "SELECT on_hand FROM inventory_item WHERE item_key = ?", (key,)).fetchone()["on_hand"]
    assert after == 17, f"20 opening less 3 sold; was {before}, now {after}"


def test_there_are_exactly_two_destinations(client, auth_headers, conn):
    """Everything posts to the Credit/Remittance Master or to Monthly Expenses.

    Client, 2026-09-25: "we post everything to either Credit/Remittance Master OR
    Expenses only two kinds of data that's all."

    Written as an invariant rather than a spot-check, because the way this breaks
    is somebody adding a fourth category to BLOCKS and a new table under it, and
    every existing test still passing. Post one line of every kind the form can
    produce and assert that nothing lands anywhere else.
    """
    from svr_backend.posting import BLOCKS

    date = "2026-11-06"
    _day(
        client, auth_headers, date,
        expenses=[("Power Bill", 900)],
        credits_=[("AirTel Hari New Credit", 1200)],
        remittances=[("AirTel Hari Old Credit Remitted Amt", 700)],
    )
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))

    landed = {
        r["target_table"]
        for r in conn.execute(
            "SELECT DISTINCT target_table FROM trial_balance_posting "
            "WHERE target_table IS NOT NULL"
        )
    }
    assert landed == {"credit_transaction", "monthly_expense"}, landed

    # And every block the form can post declares one of the two kinds that reach
    # those tables - an 'expense' goes to Monthly Expenses, anything else to the
    # Credit/Remittance Master (posting.post_line).
    assert {cat for cat, _key in BLOCKS.values()} <= {"expense", "credit", "remittance"}

    # This day's three lines went to the two tables, none missing.
    rows = conn.execute(
        "SELECT category, target_table FROM trial_balance_posting WHERE shift_date = ?",
        (date,),
    ).fetchall()
    assert len(rows) == 3, [dict(r) for r in rows]
    for row in rows:
        expected = "monthly_expense" if row["category"] == "expense" else "credit_transaction"
        assert row["target_table"] == expected, dict(row)


# --------------------------------------------------------------- option delete
#
# Client, 2026-09-26: "In addition to +New also -Delete option is needed to
# delete a selected drop down list across Section 4,5 and 6".

def test_a_dropdown_value_can_be_removed_and_the_lists_come_back_without_it(
    client, auth_headers
):
    h = auth_headers("Sales")
    client.post("/daily-trial-balance/options",
                json={"list_key": "banks", "value": "Scratch Card"}, headers=h)
    assert "Scratch Card" in client.get("/daily-trial-balance/options",
                                        headers=h).json()["banks"]

    r = client.post("/daily-trial-balance/options/remove",
                    json={"list_key": "banks", "value": "Scratch Card"}, headers=h)
    assert r.status_code == 200, r.text[:200]
    assert "Scratch Card" not in r.json()["banks"]


def test_removing_an_option_leaves_saved_entries_alone(client, auth_headers, conn):
    """The whole reason this is safe to expose: an entry stores the text that was
    chosen, not a pointer into the option table. Yesterday's credit must still
    name the person who took it after they leave the station."""
    h = auth_headers("Sales")
    client.post("/daily-trial-balance/options",
                json={"list_key": "customers", "value": "Departing Customer"}, headers=h)
    saved = client.post(
        "/daily-sales-entry",
        json={"pump_serial": "12BC4523V-RD", "shift_date": "2026-09-26",
              "hs": {"current": "9700000"}, "ms": {"current": "9700000"},
              "new_credits": [{"name": "Departing Customer", "ltrs": "10", "rate": "105.36"}]},
        headers=h,
    )
    assert saved.status_code in (200, 201), saved.text[:300]
    client.post("/daily-trial-balance/options/remove",
                json={"list_key": "customers", "value": "Departing Customer"}, headers=h)

    row = conn.execute(
        "SELECT payload FROM daily_sales_entry WHERE shift_date = '2026-09-26'"
    ).fetchone()
    assert row is not None
    assert "Departing Customer" in row["payload"]


def test_removing_something_that_is_not_there_says_so(client, auth_headers):
    r = client.post("/daily-trial-balance/options/remove",
                    json={"list_key": "banks", "value": "Never Existed"},
                    headers=auth_headers("Sales"))
    assert r.status_code == 404


def test_an_unknown_list_is_refused_rather_than_silently_doing_nothing(client, auth_headers):
    r = client.post("/daily-trial-balance/options/remove",
                    json={"list_key": "not_a_list", "value": "x"},
                    headers=auth_headers("Manager"))
    assert r.status_code == 400


def test_fixed_control_values_cannot_be_deleted_only_added(client, auth_headers, conn):
    """2026-09-29: Full, No and Cash all vanished from three separate lists by
    mistake on the same real day - each one a value the calc engine matches on
    literally (Payment Mode's cash-basis fix, for one), not a name. Adding a
    new control value is still fine; only removing one of the existing set is
    refused. A genuine name list (creditors) is completely unaffected."""
    h = auth_headers("Manager")
    for key, value in (
        ("yes_no", "Yes"), ("payment_type", "Full"), ("payment_modes", "Cash"),
        ("credit_payment_modes", "Credit (CR)"), ("expense_payment_mode", "Cash"),
    ):
        r = client.post("/daily-trial-balance/options/remove",
                        json={"list_key": key, "value": value}, headers=h)
        assert r.status_code == 403, f"{key}: {r.text[:200]}"
        assert conn.execute(
            "SELECT 1 FROM trial_balance_option WHERE list_key = ? AND value = ?",
            (key, value),
        ).fetchone() is not None, f"{key}/{value} was deleted despite the 403"

    # Adding a new control value is still allowed - only deleting an existing
    # one is refused.
    r = client.post("/daily-trial-balance/options",
                    json={"list_key": "payment_modes", "value": "UPI"}, headers=h)
    assert r.status_code == 201

    # Real name/free-text lists, in other Daily Sales Entry sections too, still
    # delete exactly as before - Section 5/6's Creditor/Customer Name and
    # Section 4's Card Holder Name are people, and Card Type (reverted here,
    # 2026-09-30 - nothing matches on it literally, unlike the five above) is a
    # free-text category, not a fixed set a formula depends on.
    for key, value in (
        ("creditors", "Temp Test Creditor"), ("card_holders", "Temp Test Holder"),
        ("card_types", "Temp Test Card Type"),
    ):
        client.post("/daily-trial-balance/options",
                    json={"list_key": key, "value": value}, headers=h)
        r = client.post("/daily-trial-balance/options/remove",
                        json={"list_key": key, "value": value}, headers=h)
        assert r.status_code == 200, f"{key}: {r.text[:200]}"


def test_collected_by_has_no_two_name_pairings(client, auth_headers):
    """The pairings belong to 'staff' - 8.16 signs a shift off with two people -
    and must not follow the individuals into Section 6 (client, 2026-09-26)."""
    lists = client.get("/daily-trial-balance/options",
                       headers=auth_headers("Sales")).json()
    assert set(lists["collectors"]) == {
        "Sriharsha", "Girish", "Ravindra", "Ashok", "Vijay"}
    assert not [v for v in lists["collectors"] if "&" in v or "/" in v]
    # ...and 'staff' still has them, for the sign-off that needs them.
    assert [v for v in lists["staff"] if "&" in v or "/" in v]


# ----------------------------------------------------- pulled from Daily Sales
#
# Client, 2026-09-27: "Both of these transaction should come from Daily Trial
# balance report when posted." Route confirmed direct - Daily Sales Entry ->
# Daily Trial Balance -> Credit Master, skipping Daily Sales Summary.

def test_a_section_5_credit_is_posted_with_no_typing_on_the_trial_balance(
    client, auth_headers, conn
):
    """A fuel credit entered on Daily Sales Entry's Section 5 reaches Credit
    Master once the day's Trial Balance is saved and posted - with nothing
    typed into 3.13 at all."""
    date = "2026-11-20"
    h = auth_headers("Sales")
    saved = client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": "12BC4523V-RD", "shift_date": date,
            "hs": {"current": "9700000"}, "ms": {"current": "9700000"},
            "new_credits": [{
                "name": "Sajja Function Hall", "fuel_type": "HS",
                "ltrs": "10", "rate": "105.36", "payment_mode": "Credit (CR)",
            }],
        },
        headers=h,
    )
    assert saved.status_code in (200, 201), saved.text[:300]

    tb = client.put(f"/daily-trial-balance/{date}",
                    json={"s1_hs_current": 60}, headers=auth_headers("Manager"))
    assert tb.status_code == 200, tb.text[:300]

    posted = client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    assert posted.status_code == 200, posted.text[:300]
    assert posted.json()["posted"] == 1

    row = conn.execute(
        "SELECT * FROM credit_transaction WHERE creditor_name = 'Sajja Function Hall'"
    ).fetchone()
    assert row is not None, "the pulled credit never reached Credit Master"
    assert row["kind"] == "credit"
    assert row["amount"] == 1053.6
    assert row["status"] == "posted_dt"
    assert row["fuel_type"] == "HS"
    assert row["ltrs"] == 10
    assert row["rate"] == 105.36
    assert row["payment_mode"] == "Credit (CR)"
    assert row["pump_sales_man"] is not None  # submitted_by, carried through


def test_a_section_6_remittance_is_posted_the_same_way(client, auth_headers, conn):
    date = "2026-11-21"
    h = auth_headers("Sales")
    saved = client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": "12BC4523V-RD", "shift_date": date,
            "hs": {"current": "9700010"}, "ms": {"current": "9700010"},
            "old_credit_rows": [{
                "customer": "Anil/Nani", "given_date": "2026-11-01",
                "payment": "Full", "remittance_entered": "Yes",
                "collected_by": "Sriharsha", "payment_mode": "Cash",
            }],
            "old_credit_amounts": ["2000"],
        },
        headers=h,
    )
    assert saved.status_code in (200, 201), saved.text[:300]

    client.put(f"/daily-trial-balance/{date}",
              json={"s1_hs_current": 61}, headers=auth_headers("Manager"))
    posted = client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    assert posted.status_code == 200, posted.text[:300]

    row = conn.execute(
        "SELECT * FROM credit_transaction WHERE creditor_name = 'Anil/Nani' "
        "AND kind = 'remittance'"
    ).fetchone()
    assert row is not None
    assert row["amount"] == 2000
    assert row["status"] == "posted_dt"
    assert row["payment"] == "Full"
    assert row["remittance_entered"] == "Yes"
    assert row["collected_by"] == "Sriharsha"
    assert row["payment_mode"] == "Cash"
    assert row["given_on_date"] == "2026-11-01"


def test_a_typed_3_13_row_still_wins_over_the_pull_no_double_posting(
    client, auth_headers, conn
):
    """A day with BOTH a typed 3.13 credit and a pulled Section 5 credit must
    post exactly once - the same "typed wins" rule the day's own arithmetic
    already uses, not two postings for one real event."""
    date = "2026-11-22"
    client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": "12BC4523V-RD", "shift_date": date,
            "hs": {"current": "9700020"}, "ms": {"current": "9700020"},
            "new_credits": [{"name": "AirTel Hari", "ltrs": "5", "rate": "105.36"}],
        },
        headers=auth_headers("Sales"),
    )
    client.put(
        f"/daily-trial-balance/{date}",
        json={"s1_hs_current": 62,
              "manual": {"section3": {"new_credits": [
                  {"type": "Salary Advance Ravindra", "amount": 5000}
              ]}}},
        headers=auth_headers("Manager"),
    )
    posted = client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    assert posted.status_code == 200, posted.text[:300]
    # Only the typed row posts (as an expense, matching the salary-word rule);
    # the pulled fuel credit is NOT also posted underneath it.
    assert posted.json()["posted"] == 1
    assert conn.execute(
        "SELECT COUNT(*) c FROM credit_transaction WHERE creditor_name = 'AirTel Hari'"
    ).fetchone()["c"] == 0


def test_daily_expenses_posts_to_monthly_expenses_not_the_cash_total(
    client, auth_headers, conn
):
    """3.13's split (client, 2026-09-27): a payroll item typed under Daily
    Expenses is money paid OUT, so unlike a real credit it must not inflate
    3.15's cash total, and it must reach Monthly Expenses, not Credit Master."""
    date = "2026-11-23"
    r = client.put(
        f"/daily-trial-balance/{date}",
        json={"s1_hs_current": 63,
              "manual": {"section3": {"daily_expenses": [
                  {"type": "Fuel Transport", "amount": 4000}
              ]}}},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 200, r.text[:300]
    derived = r.json()["computed"]["derived"]["section3"]
    assert derived["daily_expenses_total"] == 4000
    # Not counted toward the cash total - only Daily Credits and the pull are.
    assert derived["new_credits_total"] == 0

    posted = client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    assert posted.status_code == 200, posted.text[:300]
    row = conn.execute(
        "SELECT me.amount, ec.name FROM monthly_expense me "
        "JOIN expense_category ec ON ec.id = me.category_id "
        "WHERE me.expense_date = ?", (date,)
    ).fetchone()
    assert row is not None, "Daily Expenses row never reached Monthly Expenses"
    assert row["amount"] == 4000
    assert row["name"] == "Fuel Transport"
    assert conn.execute(
        "SELECT COUNT(*) c FROM credit_transaction WHERE txn_date = ?", (date,)
    ).fetchone()["c"] == 0


def test_the_pulled_rows_view_shows_regardless_of_which_one_is_winning(
    client, auth_headers
):
    """Section 3's mirror of Daily Sales Entry's Section 5 is always
    populated, even on a day where a typed Daily Credits row is the one
    actually counted - so an operator can see both."""
    date = "2026-11-24"
    client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": "12BC4523V-RD", "shift_date": date,
            "hs": {"current": "9700030"}, "ms": {"current": "9700030"},
            "new_credits": [{"name": "AirTel Hari", "ltrs": "3", "rate": "105.36"}],
        },
        headers=auth_headers("Sales"),
    )
    r = client.put(
        f"/daily-trial-balance/{date}",
        json={"s1_hs_current": 64,
              "manual": {"section3": {"new_credits": [
                  {"type": "Sajja Function Hall", "amount": 500}
              ]}}},
        headers=auth_headers("Manager"),
    )
    d = r.json()["computed"]["derived"]["section3"]
    assert d["new_credit_source"] == "typed"
    assert d["new_credits_total"] == 500          # the typed row wins the total
    assert d["pulled_new_credits"][0]["type"] == "AirTel Hari"  # but still visible


def test_a_remittance_typed_on_credit_master_also_shows_on_trial_balance(
    client, auth_headers
):
    """Client, 2026-09-27: "who to clear the entry in DT" for a remittance
    collected straight on Credit Master, never through Daily Sales Entry at
    all. It has to show up on THAT day's Trial Balance the same way a
    pump-filed one does - not just settle silently with nothing on screen."""
    date = "2026-11-25"
    client.post(
        "/credit-master/remittance",
        json={"creditor_name": "Anil/Nani", "amount": 1200, "txn_date": date},
        headers=auth_headers("Manager"),
    )
    r = client.put(
        f"/daily-trial-balance/{date}",
        json={"s1_hs_current": 60},
        headers=auth_headers("Manager"),
    )
    d = r.json()["computed"]["derived"]["section4"]
    assert d["remittance_source"] == "pulled"
    assert d["remittance_total"] == 1200
    assert d["pulled_old_credits"][0]["type"] == "Anil/Nani"


def test_a_posted_remittance_is_not_pulled_a_second_time(client, auth_headers, conn):
    """A remittance that ALREADY reached credit_transaction through the DSE ->
    Trial Balance -> Post pipeline (status='posted_dt') must not be read again
    by the Credit-Master-direct pull, or the same money would double count."""
    date = "2026-11-26"
    _day(client, auth_headers, date, remittances=[("Anil/Nani Old Credit Remitted Amt", 900)])
    client.post(f"/daily-trial-balance/{date}/post", headers=auth_headers("Manager"))
    assert conn.execute(
        "SELECT status FROM credit_transaction WHERE txn_date = ? AND kind = 'remittance'",
        (date,),
    ).fetchone()["status"] == "posted_dt"

    r = client.put(f"/daily-trial-balance/{date}", json={"s1_hs_current": 60},
                   headers=auth_headers("Manager"))
    d = r.json()["computed"]["derived"]["section4"]
    assert d["remittance_total"] == 900, "not 1800 - the posted row must not be pulled again"
