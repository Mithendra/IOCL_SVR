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
