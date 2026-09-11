"""Real-world validation: the Road pump's repair gap, 2026-09-11 client delivery.

Client's report: on 2026-09-09 only one salesman worked and the Road pump
(12BC4523V-RD) was under repair, so there is no Daily Sales entry for it that
day; the Office pump (11CC2012V-OFF) ran normally. Client's question: "which
Last [Shift] Reading[s] will apply when [the] meter is not on and in repair
condition" - answered here against the real figures from the six files
delivered alongside the question (docs/.../ocr-samples/SVR_Daily_Sales_*).

Two things are validated with real numbers, not synthetic ones:

1. The Office pump's Last Shift Reading auto-carries correctly across three
   consecutive real days (2026-09-08 -> 09 -> 10), reproducing the exact
   consumption figures printed on the real paper forms.
2. The Road pump's first entry after the repair gap (2026-09-10) has nothing
   in this system to carry from - there is no digital record of the repair
   day, and none from before it either - so the operator must key in the Last
   Shift Reading by hand (the fix from the same date: `_apply_locked_context`
   keeps a manually-supplied reading instead of nulling it when there's
   nothing to carry). That manual entry reproduces the real paper's own
   consumption figures exactly too.

Note: docs/.../ocr-samples/SVR-daily-sales-2026-09-08-road-scan.pdf (from an
earlier session) is mislabeled - its readings (~1,487,xxx) are actually the
Office pump's, not the Road pump's (they match this file's own Office-side
Last Shift Reading below exactly). Flagged to the client separately; not used
here as Road-pump data because of that.
"""

from __future__ import annotations

OFFICE = "11CC2012V-OFF"
ROAD = "12BC4523V-RD"


def test_office_pump_three_day_carry_forward_matches_the_real_paper_figures(
    client, auth_headers
):
    h = auth_headers("Sales")

    # 2026-09-08: seed day (the Sep-9 form's own stated Last Shift Reading is
    # this day's Current Reading - the actual scan for this day is mislabeled
    # as "Road", see module docstring, so it's seeded directly here instead).
    client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": OFFICE, "shift_date": "2026-09-08",
            "hs": {"current": "1487517.430"}, "ms": {"current": "660581.140"},
        },
        headers=h,
    )

    # 2026-09-09 (real file: SVR_Daily_Sales_09Sep2026_11CC2012V-OFF.pdf/.xlsx)
    sep9 = client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": OFFICE, "shift_date": "2026-09-09",
            "hs": {"current": "1487828.110"}, "ms": {"current": "661164.690"},
        },
        headers=h,
    ).json()
    assert sep9["hs_last"] == 1487517.43  # carried from 09-08, matches the paper
    assert sep9["ms_last"] == 660581.14
    assert sep9["result"]["hs"]["cons"] == 310.68
    assert sep9["result"]["ms"]["cons"] == 583.55

    # 2026-09-10 (real file: SVR_Daily_Sales_10Sep2026_11CC2012V-OFF.pdf/.xlsx)
    sep10 = client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": OFFICE, "shift_date": "2026-09-10",
            "hs": {"current": "1488457.600"}, "ms": {"current": "661746.130"},
        },
        headers=h,
    ).json()
    assert sep10["hs_last"] == 1487828.11  # carried from 09-09, matches the paper
    assert sep10["ms_last"] == 661164.69
    assert sep10["result"]["hs"]["cons"] == 629.49
    assert sep10["result"]["ms"]["cons"] == 581.44


def test_road_pump_first_entry_after_repair_needs_a_manual_last_reading(
    client, auth_headers
):
    h = auth_headers("Sales")
    # No 2026-09-09 entry exists for this pump anywhere (the repair day), and
    # none before it either in this fresh system - nothing to carry, so the
    # operator supplies the Last Shift Reading by hand, from their own paper
    # log (real file: SVR_Daily_Sales_10Sep2026_12BC4523V-RD.pdf/.xlsx).
    resp = client.post(
        "/daily-sales-entry",
        json={
            "pump_serial": ROAD, "shift_date": "2026-09-10",
            "hs": {"current": "267859.100", "last": "267841.930"},
            "ms": {"current": "288886.970", "last": "288877.280"},
        },
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    row = resp.json()
    assert row["hs_last"] == 267841.93
    assert row["ms_last"] == 288877.28
    assert row["result"]["hs"]["cons"] == 17.17  # matches the real paper exactly
    assert row["result"]["ms"]["cons"] == 9.69
