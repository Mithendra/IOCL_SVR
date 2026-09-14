"""Section 4.2 computed from the day's own figures, locked to the SEP14 tab.

The client's sheet leaves 4.2 ("Total Today Sale Amount After Expenses (Beta,
Testing and Density)") hand-typed, and it is the only opinion in a chain of
facts: 4.1 carries forward from yesterday, 4.4 is counted cash and bank, 4.3 and
4.5 calculate themselves. So 4.2 is the only line that can be wrong, and when it
is, 4.5 sends someone looking for a cash difference that was never there.

On SEP14 it was keyed as 100,436.251. The day's own figures give 100,432.781,
and 4.5 read -3.481 as a result.

Figures below are read off the client's own files, cited so they can be checked:

  Trail_balance_14SEP2026.xlsx, tab SEP14
      E27  101,913.081     Daily Sales Total (F17 gas + F26 oil)
      D49  2,117,522.08    ='SEP13'!D52, yesterday's Cash/Book value
      D50  100,436.251     as typed by the station
      D52  2,217,954.85    =D47, the counted cash and bank
      D53  -3.481          =D52-D51

  SVR_DSR_12BC4523V-RD_14Sept2026.xlsx, tab 'Daily Sales Report'
      O22  1,480.30        Daily Diesel(5L) & Petrol(5L) + Density Testing + Beta
      R19  101,913.081     Total Gas & Oil Sales Amt

The Office pump filed a zero-activity day (Current = Last on both nozzles), so
its O22 is 0 and contributes nothing.
"""

from __future__ import annotations

from svr_backend.calc.daily_trial_balance import derive_manual

SALES_TOTAL = 101913.081     # SEP14!E27  == Road DSR R19
BETA_TESTING = 1480.30       # Road DSR O22
YESTERDAY = 2117522.08       # SEP14!D49
REPORTED = 2217954.85        # SEP14!D52
TYPED = 100436.251           # SEP14!D50, as the station keyed it


def _s4(manual_s4: dict, day_sales: dict | None) -> dict:
    return derive_manual({"section4": manual_s4}, 0.0, 136, None, day_sales)["section4"]


def test_4_2_is_the_days_sales_less_the_beta_testing_expense():
    d = _s4(
        {"yesterday": YESTERDAY, "reported": REPORTED},
        {"sales_total": SALES_TOTAL, "beta_testing": BETA_TESTING},
    )
    # 101,913.081 - 1,480.30
    assert round(d["todaysale_computed"], 3) == 100432.781
    assert d["todaysale_source"] == "computed"


def test_the_computed_figure_closes_sep14_to_a_hundredth():
    """As filed, 4.5 read -3.481. Off the day's own figures it is -0.011 - inside
    the paisa, and inside the Rs 50 escalation limit either way. The residual is
    the Net Bal rounding, not this formula: the sheet's B31 holds 14,981.77 where
    the DSR's own O53 computes 14,981.781, and the engine's truncate-per-row rule
    (verified against three client files on 2026-09-11) produces 14,981.77 too.
    """
    d = _s4(
        {"yesterday": YESTERDAY, "reported": REPORTED},
        {"sales_total": SALES_TOTAL, "beta_testing": BETA_TESTING},
    )
    assert round(d["total3"], 3) == 2217954.861     # 4.3
    assert round(d["diff"], 3) == -0.011            # 4.5
    assert abs(d["diff"]) < 50                      # inside the escalation limit


def test_what_the_station_typed_is_reproduced_when_there_is_no_entry():
    """A day with no Daily Sales Entry - an imported or historical record - must
    fall back to the typed figure rather than compute the day as zero sales.
    """
    d = _s4(
        {"yesterday": YESTERDAY, "todaysale": TYPED, "reported": REPORTED},
        {"sales_total": None},
    )
    assert d["todaysale"] == TYPED
    assert d["todaysale_source"] == "typed"
    assert round(d["diff"], 3) == -3.481            # SEP14 exactly as filed


def test_both_figures_are_returned_so_a_mismatch_can_be_shown():
    """ADR-5: recompute and flag, never silently overwrite what someone entered.
    The screen needs both to say "you typed X, the day says Y".
    """
    d = _s4(
        {"yesterday": YESTERDAY, "todaysale": TYPED, "reported": REPORTED},
        {"sales_total": SALES_TOTAL, "beta_testing": BETA_TESTING},
    )
    assert d["todaysale_typed"] == TYPED
    assert round(d["todaysale_computed"], 3) == 100432.781
    assert d["todaysale"] == d["todaysale_computed"]      # computed wins
    assert round(d["todaysale_typed"] - d["todaysale_computed"], 3) == 3.470


def test_a_blank_beta_testing_expense_is_not_a_missing_day():
    """Zero expense is a real answer (the Office pump's idle day). It must not be
    confused with "no form submitted", which is what sales_total=None means.
    """
    d = _s4(
        {"yesterday": YESTERDAY, "reported": REPORTED},
        {"sales_total": SALES_TOTAL, "beta_testing": None},
    )
    assert round(d["todaysale_computed"], 3) == round(SALES_TOTAL, 3)
    assert d["todaysale_source"] == "computed"
