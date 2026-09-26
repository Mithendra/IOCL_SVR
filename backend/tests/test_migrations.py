"""Migration runner: builds a fresh DB, is idempotent, and seeds parameters/rates."""

from __future__ import annotations

from svr_backend.core.db import connect
from svr_backend.migrations.runner import applied_versions, migrate


def test_fresh_db_has_all_tables(conn):
    names = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    for expected in (
        "users",
        "sessions",
        "system_parameter",
        "rate_master",
        "user_preference",
        "audit_log",
        "scheduler_run",
        "daily_sales_entry",
        "daily_sales_summary",
        "schema_migrations",
    ):
        assert expected in names


def test_seeds_present(conn):
    # system_parameter is append-only by effective_date, so read the SEED row
    # rather than "the row" - testing_density_deduction has two versions since
    # migration 0019 (10.0 seeded, 5.5 from 2026-09-12 per the client's SEP12 tab).
    params = {
        r["name"]: r["value"]
        for r in conn.execute(
            "SELECT name, value FROM system_parameter WHERE updated_by = 'seed'"
        )
    }
    assert params["testing_density_deduction"] == 10
    assert params["trial_balance_alert_threshold"] == 100
    keys = {r["item_key"] for r in conn.execute("SELECT item_key FROM rate_master")}
    assert {"HS", "MS", "oil1", "oil2", "oil3", "oil4", "oil5", "oil6", "oil7"} <= keys


def test_migrate_is_idempotent(db_path):
    c = connect(db_path)
    try:
        first = migrate(c)
        assert first  # applied something
        again = migrate(c)
        assert again == []  # nothing left to do
        assert "0001_init.sql" in applied_versions(c)
        assert "0002_daily_sales_entry.sql" in applied_versions(c)
    finally:
        c.close()


def test_no_two_migrations_share_a_number():
    """Two files numbered 0027 shipped on 2026-09-14: a rename during a
    revert/re-apply left both the old and the new name in the tree, and both ran.
    The orphan inserted a `testing_litres_per_pump` parameter nothing reads.

    Ordering between same-numbered files is then decided by the rest of the
    filename, which is not something anyone should have to reason about.
    """
    from svr_backend.migrations.runner import _discover

    seen: dict[str, str] = {}
    clashes = []
    for name, _ in _discover():
        number = name.split("_", 1)[0]
        if number in seen:
            clashes.append(f"{number}: {seen[number]} and {name}")
        seen[number] = name
    assert not clashes, "duplicate migration numbers: " + "; ".join(clashes)


def test_0037_moves_an_already_posted_salary_line_to_monthly_expenses(conn):
    """Lines posted BEFORE the routing fix are stranded in the credit master.

    posting.category_for() sends a salary or staff advance to Monthly Expenses
    from now on, but it only fires while a line is still unposted. "Salary
    Advance Reavindra" had already gone through as a CREDIT - so the Creditor
    Balance Summary showed the station owed 10,000 by its own employee, which is
    backwards: the station paid that out (client, 2026-09-25, with the
    screenshot).

    Migration 0037 repairs those. This drives the shipped SQL against exactly
    that state, because the migration runs once and a fresh database has nothing
    for it to fix - so without this the repair is untested code that already ran.
    """
    from svr_backend.migrations.runner import _discover

    sql = next(text for name, text in _discover() if name.startswith("0037_"))

    # The state the client's machine was in: posted, filed as a credit.
    conn.execute(
        "INSERT INTO credit_transaction (kind, creditor_name, amount, txn_date, "
        "created_by, last_updated_by) VALUES ('credit', 'Salary Advance Reavindra', "
        "10000, '2026-09-14', 'test', 'test')"
    )
    txn_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute(
        "INSERT INTO trial_balance_posting (shift_date, category, source_block, "
        "row_index, label, amount, status, target_table, target_id) VALUES "
        "('2026-09-14', 'credit', 'section3.new_credits', 1, "
        "'Salary Advance Reavindra', 10000, 'posted', 'credit_transaction', ?)",
        (txn_id,),
    )
    # A real fuel credit alongside it, which must NOT be touched.
    conn.execute(
        "INSERT INTO credit_transaction (kind, creditor_name, amount, txn_date, "
        "created_by, last_updated_by) VALUES ('credit', 'AirTel Hari', 11674, "
        "'2026-09-14', 'test', 'test')"
    )
    keep_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute(
        "INSERT INTO trial_balance_posting (shift_date, category, source_block, "
        "row_index, label, amount, status, target_table, target_id) VALUES "
        "('2026-09-14', 'credit', 'section3.new_credits', 0, "
        "'AirTel Hari New Credit', 11674, 'posted', 'credit_transaction', ?)",
        (keep_id,),
    )
    conn.execute(
        "INSERT INTO trial_balance_option (list_key, value, sort_order) "
        "VALUES ('creditors', 'Salary Advance Reavindra', 9)"
    )
    conn.commit()

    conn.executescript(sql)

    # It is an expense now, as payroll, on the day it happened.
    row = conn.execute(
        "SELECT me.amount, me.expense_date, ec.name, ec.kind FROM monthly_expense me "
        "JOIN expense_category ec ON ec.id = me.category_id WHERE ec.name = ?",
        ("Salary Advance Reavindra",),
    ).fetchone()
    assert row is not None, "the salary advance never reached Monthly Expenses"
    assert row["amount"] == 10000
    assert row["expense_date"] == "2026-09-14"
    assert row["kind"] == "payroll"

    # ...and gone from the credit master, so nobody owes the station for it.
    assert conn.execute(
        "SELECT COUNT(*) c FROM credit_transaction WHERE creditor_name = ?",
        ("Salary Advance Reavindra",),
    ).fetchone()["c"] == 0

    # The posting row points at its new home.
    moved = conn.execute(
        "SELECT category, target_table FROM trial_balance_posting WHERE label = ?",
        ("Salary Advance Reavindra",),
    ).fetchone()
    assert moved["category"] == "expense"
    assert moved["target_table"] == "monthly_expense"

    # The genuine creditor is untouched.
    kept = conn.execute(
        "SELECT kind, amount FROM credit_transaction WHERE creditor_name = 'AirTel Hari'"
    ).fetchone()
    assert kept["kind"] == "credit"
    assert kept["amount"] == 11674

    # And it cannot be picked in 3.14 again.
    creditors = [
        r["value"] for r in conn.execute(
            "SELECT value FROM trial_balance_option WHERE list_key = 'creditors'"
        )
    ]
    assert not any("advance" in c.lower() or "salar" in c.lower() for c in creditors), creditors
