"""The 2026-09-12 Daily Sales Entry form change: Oil Sale(s) 5 rows -> 7, the
"Total Gas & Oil Sales Amt" row, and the removal of Night Cash Hand Off.

The risk this file exists for is not the arithmetic - it is that the Oil Sale(s)
ROW ORDER changed under records that were already saved. Anything that reads a
stored payload/result by position now reads a different item than the one that was
written there, and it does so silently. Every such reader must resolve by the
row's own stored label instead (`oils_by_key`), and that is what most of these
tests pin down.
"""

from __future__ import annotations

import json

from svr_backend.calc.daily_sales_entry import (
    OIL_ITEMS,
    OIL_KEYS,
    OIL_LABELS,
    compute_payload,
    oils_by_key,
    resolve_oil_key,
)

DATE = "2026-09-20"

# One pre-2026-09-12 record, exactly as it would have been stored: five rows, in
# the old order, each carrying its own label.
LEGACY_OILS = [
    {"label": "2T/1.20 ML Total#", "qty": None, "rate": 30, "opening": 64},
    {"label": "2T/2.40 ML Total#", "qty": "10", "rate": 17, "opening": 44},
    {"label": "Acid Water Total 1 Lts", "qty": None, "rate": 0, "opening": 28},
    {"label": "Acid Water Total 5 Lts", "qty": "1", "rate": 120, "opening": 20},
    {"label": "20/40 Engine Total in Lts", "qty": None, "rate": 130, "opening": 42},
]


def test_the_form_carries_the_clients_seven_rows_in_order():
    assert [label for _, label in OIL_ITEMS] == [
        "2T/1.50 ML Total#",
        "2T/2.40 ML Total#",
        "Acid Water Total 1 Lts",
        "Battery Water Total 1 Lts",
        "Battery Water Total 5 Lts",
        "20/40 Engine Total in 05. Lts",
        "20/40 Engine Total in 1 Lts",
    ]
    # Display order is NOT key order: a key identifies a product, so the three
    # relabelled products kept theirs and only moved position.
    assert OIL_KEYS == ("oil1", "oil2", "oil3", "oil6", "oil4", "oil7", "oil5")


def test_a_record_saved_under_the_old_row_order_still_resolves_by_item():
    """The whole point of resolving by label. Under plain positional reading,
    index 3 of this record ("Acid Water Total 5 Lts") would now be read as
    Battery Water Total 1 Lts, and its 120 quantity credited to the wrong item."""
    by_key = oils_by_key(LEGACY_OILS)

    assert by_key["oil4"]["qty"] == "1"  # the 5 L water row, not the new 1 L one
    assert by_key["oil5"]["rate"] == 130  # 20/40 Engine, not the new 0.5 L row
    assert by_key["oil1"]["opening"] == 64
    # The two rows that did not exist on the old form stay absent rather than
    # picking up a neighbour's figures.
    assert "oil6" not in by_key
    assert "oil7" not in by_key


def test_resolve_falls_back_to_position_only_when_there_is_no_label():
    assert resolve_oil_key({"label": "20/40 Engine Total in Lts"}, 0) == "oil5"
    assert resolve_oil_key({}, 0) == "oil1"
    assert resolve_oil_key({}, 4) == "oil4"
    assert resolve_oil_key({}, 99) is None


def test_total_gas_and_oil_sales_amt():
    result = compute_payload({
        "hs": {"current": "100", "last": "0", "rate": "105.36"},
        "oils": [{"label": OIL_LABELS["oil2"], "qty": "10", "rate": "17", "opening": "44"}],
    })
    assert result["gas_total"] == 10536.00
    assert result["oil_total"] == 170.00
    assert result["gas_oil_total"] == 10706.00
    # Section 7's Cash line is the same figure - both are on the client's form.
    assert result["sum_cash"] == result["gas_oil_total"]


def test_night_cash_is_gone_and_a_stale_one_cannot_come_back_in():
    """The row was removed because the Expenses section's own night-cash row
    already carried that money. A payload that still has the old key must be
    ignored outright, not quietly subtracted again."""
    base = {
        "hs": {"current": "100", "last": "0", "rate": "105.36"},
        "expenses": ["1000"],
        "phone_pay_settled": "500",
    }
    expected = 10536.00 - (1000.00 + 500.00)

    assert compute_payload(base)["net_bal_hand_off"] == expected
    assert compute_payload({**base, "night_cash": "35500"})["net_bal_hand_off"] == expected


def test_rate_master_and_inventory_agree_with_the_form(conn):
    """Migration 0017. Every form row must exist in both tables under the same
    label, or the prefill silently hands the operator a blank rate or a blank
    opening stock for a row that looks perfectly normal."""
    labels = {
        r["item_key"]: r["item_label"]
        for r in conn.execute(
            "SELECT item_key, item_label FROM rate_master WHERE item_key LIKE 'oil%' "
            "GROUP BY item_key HAVING MAX(id)"
        )
    }
    inv = {
        r["item_key"]: r["item_label"]
        for r in conn.execute("SELECT item_key, item_label FROM inventory_item")
    }
    for key, label in OIL_ITEMS:
        assert labels.get(key) == label, f"rate_master {key}"
        assert inv.get(key) == label, f"inventory_item {key}"


def test_only_evidenced_oil_rates_were_carried_forward(conn):
    """A rate is carried onto a renamed row only where the evidence reaches it.
    The other four read 0.00 - "not set, Owner to fill in" - deliberately: a
    plausible-looking placeholder is what put the 2026-09-09 Oil total out by
    1,020.01 (migration 0015), and 0 is the client's own rule for a blank Rate
    cell. Raise these here only when the client confirms the real figures."""
    from svr_backend.rates import latest_effective_rates

    rates = latest_effective_rates(conn, "2026-09-12")
    assert rates["oil2"]["sell_rate"] == 17.00    # label unchanged, priced on the sheets
    assert rates["oil3"]["sell_rate"] == 20.00    # label unchanged, priced on the sheets
    assert rates["oil5"]["sell_rate"] == 130.00   # the old single 20/40 row is the 1 Lts one
    for key in ("oil1", "oil4", "oil6", "oil7"):
        assert rates[key]["sell_rate"] == 0.00, f"{key}: awaiting the Owner's rate"


def test_inventory_credits_a_legacy_entry_to_the_right_item(client, auth_headers, conn):
    """End to end, through the database: an entry stored in the old row order is
    read back by Inventory Tracking as a sale of the 5 L water row (oil4), which
    is where it was actually recorded - not of the new 1 L row now sitting at
    that position."""
    client.post(
        "/daily-sales-entry",
        json={"pump_serial": "12BC4523V-RD", "shift_date": DATE, "hs": {"current": "1"}},
        headers=auth_headers("Sales"),
    )
    # Rewrite the stored payload/result to the pre-change 5-row shape.
    row = conn.execute(
        "SELECT id FROM daily_sales_entry WHERE shift_date = ?", (DATE,)
    ).fetchone()
    conn.execute(
        "UPDATE daily_sales_entry SET payload = ?, result = ? WHERE id = ?",
        (
            json.dumps({"hs": {"current": 1}, "oils": LEGACY_OILS}),
            json.dumps({"oils": [
                {"label": o["label"], "closing": 19 if o["label"].startswith("Acid Water Total 5")
                 else None, "amount": None}
                for o in LEGACY_OILS
            ]}),
            row["id"],
        ),
    )
    conn.commit()

    rows = client.get(f"/inventory?as_of={DATE}", headers=auth_headers("Manager")).json()
    sold = {r["item_key"]: r["sold_today"] for r in rows}
    assert sold["oil4"] == 1.0   # "Acid Water Total 5 Lts" -> "Battery Water Total 5 Lts"
    assert sold["oil2"] == 10.0
    assert sold["oil6"] == 0.0   # the new 1 L row was never on that form
