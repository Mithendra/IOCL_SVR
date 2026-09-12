"""Sanity-check the Daily Sales Entry calculation engine against the BRD/SDD worked
example. Exits non-zero on mismatch.

    python skills/daily-sales-entry/scripts/verify_calc.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from svr_backend.calc.daily_sales_entry import (  # noqa: E402
    DailySalesEntryInput,
    GasRow,
    NewCreditRow,
    OilRow,
    compute,
)

CHECKS: list[tuple[str, float, float]] = []


def check(label: str, actual: float, expected: float) -> None:
    CHECKS.append((label, actual, expected))


# SDD §9 worked example. The exact product is 138813.9072; the station's forms
# cut every row amount at paise rather than rounding (trunc2, client-confirmed
# 2026-09-11), so the reported figure is 138813.90.
r = compute(DailySalesEntryInput(hs=GasRow(current="1317.52", last="0", rate="105.36")))
check("HS consumption", r.hs.cons, 1317.52)
check("HS amount (1317.52 x 105.36, truncated to paise)", r.hs.amount, 138813.90)

# Full chain.
full = compute(
    DailySalesEntryInput(
        hs=GasRow(current="1317.52", last="0", rate="105.36"),
        ms=GasRow(current="1000", last="0", rate="117.70"),
        oils=[OilRow(label="2T/1.20 ML Total#", qty="4", rate="62", opening="20")],
        expenses=["500+100=600", "250"],
        credit_card_amounts=["1000", "500"],
        new_credits=[NewCreditRow(ltrs="10", rate="105.36")],
        old_credit_amounts=["300"],
        phone_pay_settled="150",
        phone_pay_unsettled="200",
        night_cash="5000",
    )
)
check("Oil total (4 x 62)", full.oil_total, 248.0)
check("Expenses total", full.expenses_total, 850.0)
check("Credit cards total", full.credit_cards_total, 1500.0)
check("New credits total (10 x 105.36)", full.new_credits_total, 1053.6)
check("Old credit total (excluded from today)", full.sum_old_credit, 300.0)
check(
    # Every non-cash line is SUBTRACTED - Net Bal is the physical cash handed
    # over (client-confirmed 2026-09-11 against three real filled forms).
    "Net Bal Hand Off",
    full.net_bal_hand_off,
    (138813.90 + 117700.0) + 248.0 - 850.0 - 150.0 - 200.0 - 1053.6 - 1500.0 - 5000.0,
)

failures = [(lbl, a, e) for lbl, a, e in CHECKS if abs((a or 0) - e) > 1e-6]
for lbl, a, e in CHECKS:
    mark = "FAIL" if (lbl, a, e) in failures else "ok  "
    print(f"{mark}  {lbl}: got {a}, expected {e}")

if failures:
    print(f"\n{len(failures)} check(s) failed.")
    sys.exit(1)
print(f"\nAll {len(CHECKS)} checks passed.")
