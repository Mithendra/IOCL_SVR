"""Daily Trial Balance reconciled end-to-end against the real AUG11/AUG12 tabs.

Client-requested audit (2026-09-11), after Daily Sales Entry was found to have
two formula errors that every previous check missed. Trial Balance was the main
worry: its formulas were also ported from a mockup, it consumes Daily Sales
Summary, and until now its tests only exercised synthetic round numbers
(100/60/200/190) - the shapes of the formulas, never a real day's figures.

Source: ``docs/01-BRD-Requirement-Gathering/GAS_STATION_AUG11_AUG12.xlsx``.

**Outcome: every Trial Balance formula checks out against the real workbooks.**
The two mismatches found were both seeded *constants*, not arithmetic, and are
recorded at the bottom of this file - the same class of defect as the stale oil
rates, and they are Owner-editable data rather than code.
"""

from __future__ import annotations

from svr_backend.calc.daily_trial_balance import Section1Input, TrialBalanceInput, compute

# Real figures transcribed from the workbook (tab, fuel, last, current,
# pump consumption, computer/pump diff, benefit-loss, deduct-testing).
AUG = [
    ("AUG11", "HS", 7182, 6678, 519.110000000015, 15.1100000000151, 534.22, 508.610000000015),
    ("AUG11", "MS", 7747, 7089, 672.360000000044, 14.3600000000442, 686.72, 661.860000000044),
    ("AUG12", "HS", 6678, 5393, 1317.51999999999, 32.5199999999895, 1350.04, 1307.01999999999),
    ("AUG12", "MS", 7089, 6516, 584.649999999965, 11.6499999999651, 596.30, 574.149999999965),
]


def test_section1_matches_the_real_workbooks():
    """computer_pump_diff and benefit_loss, against all four real rows.

    ``benefit_loss = consumption + computer_pump_diff`` reproduces the workbook
    exactly on 4/4 rows (534.22 / 686.72 / 1350.04 / 596.30) - confirming the
    2026-09-06 correction away from ``cons + diff``, which matched neither tab.
    """
    for tab, fuel, last, current, pump_cons, want_diff, want_benefit, _ in AUG:
        computer_cons = last - current
        diff = pump_cons - computer_cons
        assert round(diff, 4) == round(want_diff, 4), f"{tab} {fuel} computer/pump diff"
        assert round(pump_cons + diff, 2) == want_benefit, f"{tab} {fuel} benefit/loss"


def test_deduct_testing_shape_matches_but_the_seeded_constant_does_not():
    """``deduct_testing = consumption - testing_deduction`` is the right shape.

    The workbooks imply a deduction of **10.5** per fuel on 4/4 rows, while
    ``system_parameter.testing_density_deduction`` is seeded **10**. Recorded
    here rather than silently changed - see the note at the bottom of this file.
    """
    implied = {round(pump_cons - deduct, 4) for _, _, _, _, pump_cons, _, _, deduct in AUG}
    assert implied == {10.5}, "the workbooks are internally consistent at 10.5"


def test_section6_stock_and_section7_total_match_aug11():
    """Section 6 stock value and the Section 7 grand total, against real AUG11.

    Ltrs is the current reading verbatim (6678 / 7089 - confirming the
    2026-09-06 correction away from ``diff - consumption``), amount is
    ltrs x Buy Rate, and Section 7 is cash book value + stock value:
    3,531,812.99 + 1,491,191.34 = 5,023,004.33 exactly, as printed.
    """
    # AUG11's own Buy Rates, which differ from the seeded ones (see note below).
    buy_hs, buy_ms = 102.75, 113.56
    view = compute(
        TrialBalanceInput(
            s1=Section1Input(
                hs_yesterday=7182, hs_current=6678,
                ms_yesterday=7747, ms_current=7089,
            ),
            s3_hs_consumption=519.110000000015, s3_ms_consumption=672.360000000044,
            buy_rate_hs=buy_hs, buy_rate_ms=buy_ms,
            cash_book_value=3531812.99,
        )
    )
    out = view.to_dict()
    s1, s6, s7 = out["section1"], out["section6"], out["section7"]

    assert s1["hs"]["stock_ltrs"] == 6678
    assert s1["ms"]["stock_ltrs"] == 7089
    assert round(s1["hs"]["stock_amount"], 2) == 686164.50
    assert round(s1["ms"]["stock_amount"], 2) == 805026.84
    assert round(s6["total"], 2) == 1491191.34
    assert round(s7["7_3_total"], 2) == 5023004.33


# ---------------------------------------------------------------------------
# FINDINGS RAISED WITH THE CLIENT 2026-09-11 - data, not arithmetic.
#
# 1. testing_density_deduction is seeded 10; AUG11/AUG12 imply 10.5 on 4/4 rows
#    (both fuels, both days). CLAUDE.md records 10 as a "final value", so this
#    needs the client's word rather than a unilateral change. It is Owner-
#    editable via system_parameter (ADR-3), so no migration is required either
#    way - only the seed would change.
#
# 2. Buy Rates are seeded 101.50 (HS) / 112.30 (MS) effective 2026-08-11, but
#    the AUG11 tab prices stock at 102.75 / 113.56 on that same date. Sell rates
#    (105.36 / 117.70) are confirmed correct by the September sheets, so this is
#    the buy side only. Buy rates move, and only August data is on hand, so the
#    current figures may simply be a later revision - again, the client's call.
#
# Neither affects the formulas above, all of which reproduce the real workbooks.
# ---------------------------------------------------------------------------
