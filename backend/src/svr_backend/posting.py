"""Posting the Trial Balance's expense, credit and remittance lines to the
master forms, and tracking each line afterwards (client, 2026-09-14).

    "Part of the Close and Sign off, all three categories should be posted...
     Unless posted do not allow Close & Sign Off."

A posted line does NOT disappear. Expenses stay on view for the rest of the
month; a credit stays until a remittance settles it and the month is tidied up.
That is the point of the feature - an unpaid credit taken on Tuesday has to be
in front of the operator on Thursday.

These lines are already counted in the Trial Balance's own arithmetic. Posting
copies them OUT for reporting and never feeds back into a total here, never
touches carry-forward, and - the client was explicit - expenses and remittances
are not part of the next day's accounting.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime

from svr_backend.calc.amounts import is_blank, parse_amt
from svr_backend.core.audit import record_write

TABLE = "trial_balance_posting"

# Which block of the form feeds which master form. Section 8's blocks are the
# management-report duplicates of Section 4's; both are listed because either can
# be the one actually filled in on a given day, and the unique index on
# (shift_date, source_block, row_index) keeps them from colliding.
BLOCKS: dict[str, tuple[str, str]] = {
    # source block                       category        rows key
    "section4.expenses":                 ("expense",     "expenses"),
    "section8.regular_expenses":         ("expense",     "regular_expenses"),
    "section3.new_credits":              ("credit",      "new_credits"),
    "section4.remittance":               ("remittance",  "remittance"),
    "section8.old_credit_collections":   ("remittance",  "old_credit_collections"),
}

_LABEL_FIELDS = ("category", "type", "label")

# A salary, a bi-weekly or month-end salary run, or a staff advance is an
# EXPENSE - wherever on the form it was typed (client, 2026-09-25: "Any Salary or
# Bi-weekly Salary or Month end salary entered in Daily Trial balance as Expense
# ... should appear in Monthly Expenses. Any kind of expense in trail can be
# posted to Monthly expenses").
#
# It has to be decided from the LABEL, not from the block. Section 3.14 is called
# "New Credit / Salary Advance" and feeds the credit master, so "Salary Advance
# Reavindra" picked there posted as a creditor - it showed up under New Credit in
# the Credit/Remittance Master, owing the station 10,000, and never reached
# Monthly Expenses at all (client, 2026-09-25, with the screenshot). Migration
# 0028 had already moved salary advances off the creditors list for exactly this
# reason; someone re-added one through "+ New Name", and a list is not a rule.
#
# None of the station's real creditors - AirTel Hari, Anil/Nani, Sajja Function
# Hall - carry either word, so this cannot capture a genuine fuel credit.
_SALARY_WORDS = re.compile(r"salar|advance", re.I)


def category_for(block_category: str, label: str) -> str:
    """The master form a line really belongs to, by what it says it is."""
    if block_category == "credit" and _SALARY_WORDS.search(label or ""):
        return "expense"
    return block_category


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def _label(row: dict) -> str:
    for f in _LABEL_FIELDS:
        v = row.get(f)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def _amount(row: dict) -> float:
    v = row.get("amount")
    return 0.0 if is_blank(v) else parse_amt(v)


def lines_from_manual(manual: dict | None) -> list[dict]:
    """Every postable line on a day's form, as {block, index, category, label, amount}.

    A row with no label or no amount is not a line - the form always carries
    blank rows waiting to be filled, and posting those would put empty expenses
    into Monthly Expenses every single day.
    """
    out: list[dict] = []
    m = manual or {}
    for block, (category, key) in BLOCKS.items():
        section = block.split(".")[0]
        rows = (m.get(section) or {}).get(key)
        if not isinstance(rows, list):
            continue
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            label, amount = _label(row), _amount(row)
            if not label or amount == 0:
                continue
            out.append({
                "block": block, "index": i,
                "category": category_for(category, label),
                "label": label, "amount": amount,
                "given_on": row.get("given_on"),
            })
    return out


def sync_lines(conn: sqlite3.Connection, shift_date: str, manual: dict | None,
               actor: str) -> None:
    """Keep the posting rows in step with what is on the form.

    Called on every save. A line that changes before it is posted simply updates;
    a line that DISAPPEARS from the form is removed, but only while still
    unposted - once it exists in a master form, deleting it here silently would
    strand that row with nothing pointing at it.
    """
    seen: set[tuple[str, int]] = set()
    for line in lines_from_manual(manual):
        seen.add((line["block"], line["index"]))
        existing = conn.execute(
            f"SELECT id, status FROM {TABLE} WHERE shift_date = ? AND source_block = ? "
            "AND row_index = ?",
            (shift_date, line["block"], line["index"]),
        ).fetchone()
        if existing is None:
            conn.execute(
                f"INSERT INTO {TABLE} (shift_date, category, source_block, row_index, "
                "label, amount, last_updated_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (shift_date, line["category"], line["block"], line["index"],
                 line["label"], line["amount"], actor),
            )
        elif existing["status"] == "not_posted":
            # category travels too: a line typed before this rule existed, or
            # re-picked as a salary advance, must re-route on the next save
            # rather than keep the master form it was first filed under.
            conn.execute(
                f"UPDATE {TABLE} SET label = ?, amount = ?, category = ?, "
                "last_updated_by = ?, last_updated_at = ? WHERE id = ?",
                (line["label"], line["amount"], line["category"], actor, _now(),
                 existing["id"]),
            )
    for row in conn.execute(
        f"SELECT id, source_block, row_index FROM {TABLE} "
        "WHERE shift_date = ? AND status = 'not_posted'", (shift_date,)
    ).fetchall():
        if (row["source_block"], row["row_index"]) not in seen:
            conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (row["id"],))


def unposted(conn: sqlite3.Connection, shift_date: str) -> list[sqlite3.Row]:
    return conn.execute(
        f"SELECT * FROM {TABLE} WHERE shift_date = ? AND status = 'not_posted' "
        "ORDER BY category, source_block, row_index", (shift_date,)
    ).fetchall()


def _expense_category_id(conn: sqlite3.Connection, label: str) -> int:
    """Find the Monthly Expenses category matching this label, or create it.

    Matched on the station's own wording rather than a hand-written mapping, so
    a category they add to the Trial Balance list tomorrow ("Other - If Any", a
    new person's salary advance) posts without anyone editing code. The seeded
    categories stay; this only ever adds.
    """
    row = conn.execute(
        "SELECT id FROM expense_category WHERE name = ? COLLATE NOCASE", (label,)
    ).fetchone()
    if row is not None:
        return int(row["id"])
    kind = "payroll" if ("salar" in label.lower() or "advance" in label.lower()) else "operational"
    cur = conn.execute(
        "INSERT INTO expense_category (name, kind) VALUES (?, ?)", (label, kind)
    )
    return int(cur.lastrowid)


def _creditor_name(label: str) -> str:
    """The creditor behind a dropdown label.

    The list stores a whole phrase - "AirTel Hari New Credit", "Sajja Old Credit
    Remitted Amt" - while credit_transaction groups a balance by creditor_name,
    so the name has to come out of it. Only the known trailing phrases are
    stripped, longest first; anything unrecognised is left whole rather than
    guessed at, because a wrong split here silently creates a second creditor.
    """
    name = label.strip()
    for suffix in (
        " - New Credit", " Old Credit Remitted Amt", " New Credit Remitted Amt",
        " Old Credit Remitted", " New Credit Remitted", " New Credit",
    ):
        if name.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name


def post_line(conn: sqlite3.Connection, row: sqlite3.Row, actor: str) -> tuple[str, int]:
    """Write one line into its master form. Returns (table, id)."""
    if row["category"] == "expense":
        cur = conn.execute(
            "INSERT INTO monthly_expense (expense_date, category_id, amount, description, "
            "created_by, last_updated_by) VALUES (?, ?, ?, ?, ?, ?)",
            (row["shift_date"], _expense_category_id(conn, row["label"]), row["amount"],
             f"Daily Trial Balance {row['shift_date']} — {row['label']}", actor, actor),
        )
        target = ("monthly_expense", int(cur.lastrowid))
        record_write(conn, table="monthly_expense", record_id=target[1], action="create",
                     actor=actor, new={"amount": row["amount"], "from": "daily-trial-balance"})
    else:
        kind = "credit" if row["category"] == "credit" else "remittance"
        cur = conn.execute(
            "INSERT INTO credit_transaction (kind, creditor_name, amount, txn_date, note, "
            "created_by, last_updated_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, _creditor_name(row["label"]), row["amount"], row["shift_date"],
             f"Daily Trial Balance {row['shift_date']} — {row['label']}", actor, actor),
        )
        target = ("credit_transaction", int(cur.lastrowid))
        record_write(conn, table="credit_transaction", record_id=target[1], action="create",
                     actor=actor, new={"kind": kind, "amount": row["amount"],
                                       "from": "daily-trial-balance"})
    return target


def post_day(conn: sqlite3.Connection, shift_date: str, actor: str,
             ids: list[int] | None = None) -> dict:
    """Post unposted lines for a day, then settle what the remittances pay.

    ``ids`` posts only those lines; omitted, it posts the lot. The operator asked
    to be able to pick (client, 2026-09-25) - a day can carry a line that is
    genuinely not ready to leave the Trial Balance yet, and posting was all or
    nothing.

    ``already`` is returned alongside ``posted`` because the count on its own
    read as a fault: three lines posted earlier plus one added afterwards
    reported "Posted 1 line(s)" against four lines on screen, which looks like
    three went missing.

    A remittance marks that creditor's outstanding credits PAID, oldest first,
    which is how a part-payment behaves: it clears what it covers and leaves the
    rest outstanding.
    """
    rows = unposted(conn, shift_date)
    already = conn.execute(
        f"SELECT COUNT(*) c FROM {TABLE} WHERE shift_date = ? AND status != 'not_posted'",
        (shift_date,),
    ).fetchone()["c"]
    if ids is not None:
        wanted = set(ids)
        rows = [r for r in rows if r["id"] in wanted]
    now = _now()
    for row in rows:
        table, target_id = post_line(conn, row, actor)
        conn.execute(
            f"UPDATE {TABLE} SET status = 'posted', target_table = ?, target_id = ?, "
            "posted_by = ?, posted_at = ?, last_updated_by = ?, last_updated_at = ? "
            "WHERE id = ?",
            (table, target_id, actor, now, actor, now, row["id"]),
        )
    settled = _settle_remittances(conn, shift_date, actor, now)
    return {
        "posted": len(rows),
        "already_posted": already,
        "still_unposted": len(unposted(conn, shift_date)),
        "settled": settled,
    }


def _settle_remittances(conn: sqlite3.Connection, shift_date: str, actor: str,
                        now: str) -> int:
    """Flip credits to PAID when a remittance for the same creditor comes in."""
    settled = 0
    remittances = conn.execute(
        f"SELECT * FROM {TABLE} WHERE shift_date = ? AND category = 'remittance' "
        "AND status = 'posted'", (shift_date,)
    ).fetchall()
    for rem in remittances:
        who = _creditor_name(rem["label"])
        owed = conn.execute(
            f"SELECT * FROM {TABLE} WHERE category = 'credit' AND status = 'posted' "
            "ORDER BY shift_date, id", ()
        ).fetchall()
        remaining = rem["amount"]
        for credit in owed:
            if remaining <= 0:
                break
            if _creditor_name(credit["label"]) != who:
                continue
            if credit["amount"] > remaining:
                continue        # a part-payment leaves the rest outstanding
            conn.execute(
                f"UPDATE {TABLE} SET status = 'paid', paid_at = ?, paid_by_posting = ?, "
                "last_updated_by = ?, last_updated_at = ? WHERE id = ?",
                (now, rem["id"], actor, now, credit["id"]),
            )
            remaining -= credit["amount"]
            settled += 1
    return settled


def open_lines(conn: sqlite3.Connection, month_prefix: str | None = None) -> list[dict]:
    """The running view: everything not yet cleared, newest day first.

    Deliberately spans days. An expense posted on the 3rd is still here on the
    20th, and a credit stays until it is paid and the month is tidied up.
    """
    sql = f"SELECT * FROM {TABLE} WHERE status != 'cleared'"
    args: list = []
    if month_prefix:
        sql += " AND shift_date LIKE ?"
        args.append(f"{month_prefix}%")
    sql += " ORDER BY shift_date DESC, category, row_index"
    return [dict(r) for r in conn.execute(sql, args)]


def clear_lines(conn: sqlite3.Connection, ids: list[int], actor: str) -> int:
    """Month-end tidy-up: drop settled lines off the running view.

    Only a posted expense or a PAID credit can be cleared. An unpaid credit is
    exactly what the operator needs to keep seeing, and an unposted line has not
    reached a master form at all - clearing either would hide something that
    still needs doing.
    """
    if not ids:
        return 0
    marks = ",".join("?" * len(ids))
    now = _now()
    cur = conn.execute(
        f"UPDATE {TABLE} SET status = 'cleared', cleared_by = ?, cleared_at = ?, "
        f"last_updated_by = ?, last_updated_at = ? WHERE id IN ({marks}) AND ("
        "status = 'paid' OR (status = 'posted' AND category = 'expense'))",
        [actor, now, actor, now, *ids],
    )
    return cur.rowcount


def unpost_day(conn: sqlite3.Connection, shift_date: str, actor: str) -> dict:
    """Undo a day's postings, so a signed-off day can be corrected.

    Deletes the rows this day put into the master forms and returns its lines to
    'not_posted'. Without this, the first correction to a closed day would leave
    a duplicate expense in Monthly Expenses and a creditor's balance counted
    twice - the reverse-and-reapply rule the client approved for the Inventory
    sync, applied here.

    A credit already marked PAID is NOT touched. Its remittance came in on some
    other day, which is not the day being corrected, and silently un-settling it
    would resurrect a debt the creditor has already cleared.
    """
    rows = conn.execute(
        f"SELECT * FROM {TABLE} WHERE shift_date = ? AND status = 'posted'", (shift_date,)
    ).fetchall()
    removed = 0
    for row in rows:
        if row["target_table"] and row["target_id"]:
            cur = conn.execute(
                f"DELETE FROM {row['target_table']} WHERE id = ?", (row["target_id"],)
            )
            removed += cur.rowcount
            record_write(conn, table=row["target_table"], record_id=row["target_id"],
                         action="delete", actor=actor,
                         old={"amount": row["amount"], "from": "daily-trial-balance"})
        conn.execute(
            f"UPDATE {TABLE} SET status = 'not_posted', target_table = NULL, "
            "target_id = NULL, posted_by = NULL, posted_at = NULL, "
            "last_updated_by = ?, last_updated_at = ? WHERE id = ?",
            (actor, _now(), row["id"]),
        )
    kept = conn.execute(
        f"SELECT COUNT(*) c FROM {TABLE} WHERE shift_date = ? AND status = 'paid'",
        (shift_date,),
    ).fetchone()["c"]
    return {"unposted": len(rows), "removed_from_masters": removed, "left_paid": kept}
