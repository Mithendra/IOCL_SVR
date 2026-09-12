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
