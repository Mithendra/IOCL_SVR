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
                json={"list_key": "card_types", "value": "Scratch Card"}, headers=h)
    assert "Scratch Card" in client.get("/daily-trial-balance/options",
                                        headers=h).json()["card_types"]

    r = client.post("/daily-trial-balance/options/remove",
                    json={"list_key": "card_types", "value": "Scratch Card"}, headers=h)
    assert r.status_code == 200, r.text[:200]
    assert "Scratch Card" not in r.json()["card_types"]


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
                    json={"list_key": "card_types", "value": "Never Existed"},
                    headers=auth_headers("Sales"))
    assert r.status_code == 404


def test_an_unknown_list_is_refused_rather_than_silently_doing_nothing(client, auth_headers):
    r = client.post("/daily-trial-balance/options/remove",
                    json={"list_key": "not_a_list", "value": "x"},
                    headers=auth_headers("Manager"))
    assert r.status_code == 400


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
