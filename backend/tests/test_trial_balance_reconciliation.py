"""Daily Trial Balance reconciled end-to-end against the client's real figures.

Client-requested audit (2026-09-11), after Daily Sales Entry was found to have
two formula errors that every previous check missed. Trial Balance was the main
worry: its formulas were also ported from a mockup, it consumes Daily Sales
Summary, and until now its tests only exercised synthetic round numbers
(100/60/200/190) - the shapes of the formulas, never a real day's figures.

**SEP06 is the primary case** - the client's most recent data, and the tab they
explicitly validated ("I will not use AUG excel sheets at all... the same logic
was built in SEP", 2026-09-11). AUG11/AUG12 are kept below only as historical
corroboration; nothing in the client's testing depends on them.

Sources:
  * SEP06 - ``docs/01-BRD-Requirement-Gathering/SVR-Trial-Balance-Audit-2026-09-06.md``,
    transcribed from the client's live ``Trail_balance_SEP062026 1.xlsx``.
    **That workbook is not in the repo** - see the note at the bottom.
  * AUG11/AUG12 - ``docs/01-BRD-Requirement-Gathering/GAS_STATION_AUG11_AUG12.xlsx``.

**Outcome: every Trial Balance formula reproduces the real figures exactly.**
The one mismatch was a seeded Buy Rate, corrected by migration 0016.
"""

from __future__ import annotations

from svr_backend.calc.daily_trial_balance import Section1Input, TrialBalanceInput, compute

# Buy Rates confirmed by SEP06 and AUG11 alike (migration 0016 corrects the
# seeded 101.50 / 112.30, which imply impossible fractional-litre readings).
BUY_HS, BUY_MS = 102.75, 113.56


def test_sep06_section6_and_section7_reconcile_exactly():
    """SEP06 Section 6 Stock Value and the Section 7 grand total.

    The client-validated figures are 936,977.25 (HS) + 1,140,483.08 (MS) =
    2,077,460.33. ``stock_ltrs`` is today's IOCL reading verbatim - the
    2026-09-06 correction away from ``diff - consumption``, which produced
    physically meaningless negative litres and reported HS stock as -1,305.95.
    """
    hs_current, ms_current = 9119, 10043
    view = compute(
        TrialBalanceInput(
            # diff = yesterday - current = 549 on the real tab.
            s1=Section1Input(hs_yesterday=hs_current + 549, hs_current=hs_current,
                             ms_current=ms_current),
            s3_hs_consumption=561.71,
            buy_rate_hs=BUY_HS, buy_rate_ms=BUY_MS,
            cash_book_value=1000000,
        )
    ).to_dict()

    s1, s6, s7 = view["section1"], view["section6"], view["section7"]
    assert s1["hs"]["stock_ltrs"] == 9119          # the reading itself, verbatim
    assert s1["ms"]["stock_ltrs"] == 10043
    assert round(s1["hs"]["stock_amount"], 2) == 936977.25
    assert round(s1["ms"]["stock_amount"], 2) == 1140483.08
    assert round(s6["total"], 2) == 2077460.33

    # Section 7 = cash/book value + stock value.
    assert round(s7["7_3_total"], 2) == round(1000000 + 2077460.33, 2)


def test_sep06_section1_matches():
    """SEP06 Diesel: diff 549, pump consumption 561.71.

    computer_pump_diff = 561.71 - 549 = 12.71, and benefit_loss is
    ``consumption + computer_pump_diff`` (the 2026-09-06 correction away from
    ``cons + diff``).
    """
    view = compute(
        TrialBalanceInput(
            s1=Section1Input(hs_yesterday=9668, hs_current=9119),
            s3_hs_consumption=561.71,
            buy_rate_hs=BUY_HS, buy_rate_ms=BUY_MS,
        )
    ).to_dict()
    hs = view["section1"]["hs"]
    assert hs["diff"] == 549
    assert round(hs["computer_pump_diff"], 2) == 12.71
    assert round(hs["benefit_loss"], 2) == 574.42       # 561.71 + 12.71
    assert round(hs["deduct_testing"], 2) == 551.71     # 561.71 - 10


def test_the_seeded_buy_rates_could_not_have_been_right():
    """Guards the correction in migration 0016 with the reason it was made.

    IOCL stock readings are whole litres. At the seeded 101.50 / 112.30 the
    client-validated SEP06 rupee figures imply 9,231.30 L and 10,155.68 L -
    impossible. At 102.75 / 113.56 they resolve to exactly 9,119 and 10,043.
    """
    for amount, good, bad in ((936977.25, BUY_HS, 101.50), (1140483.08, BUY_MS, 112.30)):
        assert (amount / good).is_integer()
        assert not (amount / bad).is_integer()


# --------------------------------------------------------------- corroboration
# AUG11/AUG12, kept only to show the same formulas held a month earlier. The
# client's testing does not use these; SEP06 above is the case that matters.

AUG = [
    ("AUG11", "HS", 7182, 6678, 519.110000000015, 15.1100000000151, 534.22),
    ("AUG11", "MS", 7747, 7089, 672.360000000044, 14.3600000000442, 686.72),
    ("AUG12", "HS", 6678, 5393, 1317.51999999999, 32.5199999999895, 1350.04),
    ("AUG12", "MS", 7089, 6516, 584.649999999965, 11.6499999999651, 596.30),
]


def test_section1_also_holds_on_the_august_tabs():
    for tab, fuel, last, current, pump_cons, want_diff, want_benefit in AUG:
        diff = pump_cons - (last - current)
        assert round(diff, 4) == round(want_diff, 4), f"{tab} {fuel} computer/pump diff"
        assert round(pump_cons + diff, 2) == want_benefit, f"{tab} {fuel} benefit/loss"


# ---------------------------------------------------------------------------
# FINDINGS - both CLOSED. No Trial Balance formula was wrong.
#
# 1. testing_density_deduction seeded 10; the AUG tabs imply 10.5.
#    CLOSED - client 2026-09-11: "it is just a cost, there is no need to worry
#    about it." Left at 10, Owner-editable via system_parameter (ADR-3).
#
# 2. Buy Rates seeded 101.50 / 112.30 vs the real 102.75 / 113.56.
#    CLOSED - corrected in migration 0016, on September evidence.
#
# STILL WANTED: the client's live ``Trail_balance_SEP062026 1.xlsx`` is not in
# the repo, so the SEP06 figures above are transcribed from the audit doc rather
# than read from the file. Everything here is arithmetically self-checking (the
# whole-litre test above is what caught the buy rate), but per the 2026-09-11
# standard - reconcile against the real form, not a transcription - that
# workbook should be added to docs/01-BRD-Requirement-Gathering/ and these
# assertions re-pointed at it.
# ---------------------------------------------------------------------------
