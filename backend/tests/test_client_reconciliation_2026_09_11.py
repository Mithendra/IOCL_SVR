"""Reconciliation gate: the app must reproduce the client's own filled forms exactly.

This is the test that would have caught both round-2 defects. Earlier checks only
asserted that individual fields *parsed*; none ever asked whether the final rupee
figure matched the paper. Two separate errors hid behind that:

* Net Bal Hand Off added every non-cash line instead of subtracting it (inherited
  from the mockup's JS, and the paper form's own printed label agrees with the
  mockup - both are wrong).
* Oil rates were taken from placeholder Rate Master seeds instead of the sheet,
  turning the 2026-09-09 Office oil total of 290 into 1310.

Each file below is compared against the figures the station itself printed on the
form - gas total (P9), oil total (R18), Cash (J50) and Net Bal (J57). Exact
equality, no tolerance: a 0.01 drift here means the arithmetic is wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from svr_backend.calc.daily_sales_entry import compute_payload
from svr_backend.excel import parse_workbook

SAMPLES = (
    Path(__file__).resolve().parents[2] / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"
)

# (filename, sheet/pump serial, gas_total, oil_total, cash, net_bal)
# Every figure is read off the client's own filled form, not computed by us.
CASES = [
    ("SVR_DSR_11CC2012V-OFF_09Sep2026_A4.xlsx", "11CC2012V-OFF",
     101417.07, 290.00, 101707.07, 23298.77),
    ("10Sep2026_11CC2012V-OFF.xlsx", "11CC2012V-OFF",
     134758.54, 235.00, 134993.54, 38993.84),
    ("10Sep2026_12BC4523V-RD.xlsx", "12BC4523V-RD",
     2949.54, 0.00, 2949.54, 1601.20),
]


def _rates_from_sheet(payload: dict) -> dict:
    """Apply the gas Sell Rates the way the backend does on save.

    Gas rate stays backend-locked (Rate Master), and Rate Master's gas figures
    already match the forms (105.36 / 117.70). Oil rates come from the sheet and
    are already in the parsed payload, so nothing to overlay for them.
    """
    payload["hs"]["rate"] = 105.36
    payload["ms"]["rate"] = 117.70
    return payload


@pytest.mark.parametrize("fname,pump,gas,oil,cash,net_bal", CASES)
def test_client_form_reconciles_exactly(fname, pump, gas, oil, cash, net_bal):
    path = SAMPLES / fname
    if not path.exists():
        pytest.skip(f"client sample {fname} not present")

    payload, _, _ = parse_workbook(path.read_bytes(), pump_serial=pump)
    result = compute_payload(_rates_from_sheet(payload))

    assert result["gas_total"] == gas, f"{fname}: gas total"
    assert result["oil_total"] == oil, f"{fname}: oil total"
    assert result["sum_cash"] == cash, f"{fname}: Cash (Gas+Oils)"
    assert result["net_bal_hand_off"] == net_bal, f"{fname}: Net Bal Hand Off"


def test_oil_rate_comes_from_the_sheet_not_rate_master():
    """The specific defect: Rate Master's stale oil rates must not override the
    sheet. On 2026-09-09 the sheet prices 2T/2.40 at 17 and Acid Water 5L at 120;
    the old seeds said 118 and 130, which produced 1310 instead of 290."""
    path = SAMPLES / "SVR_DSR_11CC2012V-OFF_09Sep2026_A4.xlsx"
    if not path.exists():
        pytest.skip("client sample not present")

    payload, _, _ = parse_workbook(path.read_bytes(), pump_serial="11CC2012V-OFF")
    rates = [o.get("rate") for o in payload["oils"]]
    assert rates == [30, 17, 0, 120, 130]

    # A blank Rate cell reads as a real 0, never as "unset" - otherwise it would
    # silently fall back to Rate Master downstream.
    assert payload["oils"][2]["rate"] == 0

    result = compute_payload(payload)
    assert result["oil_total"] == 290.00
    assert [o["amount"] for o in result["oils"]] == [None, 170.00, None, 120.00, None]


def test_truncation_not_rounding():
    """The sheets cut each row at two decimals rather than rounding. 2026-09-10
    Office proves it: 629.49 x 105.36 = 66323.0664 is printed 66323.06 (rounding
    would give .07) and 581.44 x 117.7 = 68435.488 is printed 68435.48 (not .49).
    """
    path = SAMPLES / "10Sep2026_11CC2012V-OFF.xlsx"
    if not path.exists():
        pytest.skip("client sample not present")

    payload, _, _ = parse_workbook(path.read_bytes(), pump_serial="11CC2012V-OFF")
    result = compute_payload(_rates_from_sheet(payload))

    assert result["hs"]["amount"] == 66323.06  # not 66323.07
    assert result["ms"]["amount"] == 68435.48  # not 68435.49
