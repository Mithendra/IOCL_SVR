"""Carry-forward: gap-day skip-back and catch-up-on-startup (SDD 7.7)."""

from __future__ import annotations

from svr_backend.carry_forward import (
    carried_last_readings,
    catch_up_on_startup,
    run_carry_forward,
)

PUMP = "11CC2012V-OFF"


def _insert_entry(conn, shift_date, hs_current, ms_current):
    conn.execute(
        """
        INSERT INTO daily_sales_entry
            (shift_date, pump_serial, submitted_by, entry_mode,
             hs_current, ms_current, payload, result, last_updated_by)
        VALUES (?, ?, 'sales', 'manual', ?, ?, '{}', '{}', 'sales')
        """,
        (shift_date, PUMP, hs_current, ms_current),
    )


def test_gap_day_skip_back(conn):
    # Day 1 has readings; day 2 is a gap (no entry); on day 3 we carry from day 1.
    _insert_entry(conn, "2026-08-10", 1000.0, 500.0)
    carried = carried_last_readings(conn, PUMP, "2026-08-12")
    assert carried.hs == 1000.0
    assert carried.ms == 500.0
    assert carried.source_date == "2026-08-10"


def test_run_carry_forward_backfills_next_day_entry(conn):
    _insert_entry(conn, "2026-08-10", 1000.0, 500.0)
    _insert_entry(conn, "2026-08-11", None, None)  # entry exists but readings not in yet
    summary = run_carry_forward(conn, "2026-08-10")
    assert PUMP in summary["backfilled"]
    row = conn.execute(
        "SELECT hs_last, ms_last FROM daily_sales_entry WHERE shift_date = '2026-08-11'"
    ).fetchone()
    assert row["hs_last"] == 1000.0
    assert row["ms_last"] == 500.0


def test_run_carry_forward_does_not_overwrite_existing_last(conn):
    _insert_entry(conn, "2026-08-10", 1000.0, 500.0)
    conn.execute(
        """
        INSERT INTO daily_sales_entry
            (shift_date, pump_serial, submitted_by, entry_mode, hs_last, ms_last,
             payload, result, last_updated_by)
        VALUES ('2026-08-11', ?, 'sales', 'manual', 1234.0, 567.0, '{}', '{}', 'sales')
        """,
        (PUMP,),
    )
    run_carry_forward(conn, "2026-08-10")
    row = conn.execute(
        "SELECT hs_last, ms_last FROM daily_sales_entry WHERE shift_date = '2026-08-11'"
    ).fetchone()
    # Post-rollover correction policy: an already-set value is left alone.
    assert row["hs_last"] == 1234.0
    assert row["ms_last"] == 567.0


def test_catch_up_on_startup_replays_missed_dates_once(conn):
    _insert_entry(conn, "2026-08-10", 1000.0, 500.0)
    _insert_entry(conn, "2026-08-11", 1100.0, 550.0)
    first = catch_up_on_startup(conn)
    assert {r["for_date"] for r in first} == {"2026-08-10", "2026-08-11"}
    # Second call is a no-op - every date already has a recorded run.
    assert catch_up_on_startup(conn) == []
    runs = conn.execute("SELECT COUNT(*) c FROM scheduler_run").fetchone()["c"]
    assert runs == 2
