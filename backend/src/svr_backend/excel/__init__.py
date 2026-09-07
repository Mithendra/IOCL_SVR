"""Excel (.xlsx) import/export for Daily Sales Entry (BRD Section 5.5.1).

This is a **standard data export** - the same fields and values as the form, in a
plain labelled layout. It is deliberately NOT a pixel replica of the printed
report; that (visual-layout replication) is the BRD-flagged open question and is
out of scope until the client decides (BRD 2026-08-15 log).

Round-trip: `build_workbook` writes a hidden-ish "field key" column; `parse_workbook`
reads only that column + the value column, so it tolerates row moves and is
independent of the cosmetic labels. Per SDD ADR-5 the parsed payload is always
recomputed by the calc engine; sheet totals are only compared, never trusted.
"""

from svr_backend.excel.daily_sales_entry import (
    blank_template,
    build_workbook,
    parse_workbook,
)

__all__ = ["build_workbook", "parse_workbook", "blank_template"]
