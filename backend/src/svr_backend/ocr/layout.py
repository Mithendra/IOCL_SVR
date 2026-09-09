"""Where each Daily Sales Entry field sits on the printed SVR report, expressed
as text anchors the OCR can look for (row label + column header). Used by
`ocr.pipeline` to pull handwritten values out of a scan.

Only the high-value numeric fields are mapped - the ones worth pre-filling even
at low confidence. Everything else the operator types from the paper.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    key: str                       # dotted path into the Daily Sales Entry payload
    row_anchors: tuple[str, ...]   # printed label(s) that identify the row band
    col_anchors: tuple[str, ...] = ()   # header word that identifies the column (x)
    numeric: bool = True
    max_words: int = 2
    row_tol: float = 0.013         # half-height of the row band, page-fraction
    min_digits: int = 0            # reject a numeric guess with fewer digits
    lo: float | None = None        # plausibility range for the parsed number
    hi: float | None = None


# Meter readings run to millions with 2-3 decimals; pump rates sit ~90-130.
DAILY_SALES_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("hs.current", ("diesel", "hs-nz1", "hs-nz"), ("current",), min_digits=6),
    FieldSpec("hs.last", ("diesel", "hs-nz1", "hs-nz"), ("last", "shift"), min_digits=6),
    FieldSpec("hs.rate", ("diesel", "hs-nz1", "hs-nz"), ("rate",), lo=40, hi=200),
    FieldSpec("ms.current", ("petrol", "ms-nz-2", "ms-nz"), ("current",), min_digits=6),
    FieldSpec("ms.last", ("petrol", "ms-nz-2", "ms-nz"), ("last", "shift"), min_digits=6),
    FieldSpec("ms.rate", ("petrol", "ms-nz-2", "ms-nz"), ("rate",), lo=40, hi=200),
    FieldSpec("phone_pay_settled", ("phone pay settled", "settled total amt as of"),
              min_digits=3),
    FieldSpec("phone_pay_unsettled", ("phone pay not settled", "not settled total amt"),
              min_digits=3),
    FieldSpec("night_cash", ("night cash hand off total",), min_digits=3),
)
