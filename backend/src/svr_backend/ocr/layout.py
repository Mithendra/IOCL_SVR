"""Where each Daily Sales Entry field sits on the SVR Daily Sales Report, so
`ocr.pipeline` can pull values out of a scan or a typed PDF's text layer.

Two ways to locate a value in its row:
  * `x_lo` / `x_hi` - a fixed horizontal band (page-fraction), calibrated from the
    template. Reliable for the machine-generated / typed form (the common case now).
  * `col_anchors` - a printed header word. Fallback for a scan where the grid
    shifts. Only the row is ever anchored on a label.

Only the high-value numeric fields are mapped; the operator types the rest and
verifies every value before Save (SDD ADR-5).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    key: str                          # dotted path into the Daily Sales Entry payload
    row_anchors: tuple[str, ...]      # printed label(s) identifying the row band
    x_lo: float | None = None         # fixed column band, page-fraction
    x_hi: float | None = None
    col_anchors: tuple[str, ...] = ()  # header word for the column (scan fallback)
    numeric: bool = True
    max_words: int = 3
    row_tol: float = 0.013            # half-height of the row band, page-fraction
    min_digits: int = 0
    lo: float | None = None
    hi: float | None = None


# Column bands from the SVR template (see docs/.../ocr-samples/*typed-bw.pdf):
#   gas: current .13-.30 | last .31-.47 | cons .48-.62 | rate .63-.77 | amount .77-.92
#   right-hand amount column (expenses / summary): .80-.98
_HS = ("diesel", "hs-nz1", "hs-nz")
_MS = ("petrol", "ms-nz-2", "ms-nz")

DAILY_SALES_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("hs.current", _HS, 0.13, 0.30, ("current",), min_digits=5),
    FieldSpec("hs.last", _HS, 0.31, 0.47, ("last", "shift"), min_digits=5),
    FieldSpec("hs.rate", _HS, 0.63, 0.77, ("rate",), lo=40, hi=200),
    FieldSpec("ms.current", _MS, 0.13, 0.30, ("current",), min_digits=5),
    FieldSpec("ms.last", _MS, 0.31, 0.47, ("last", "shift"), min_digits=5),
    FieldSpec("ms.rate", _MS, 0.63, 0.77, ("rate",), lo=40, hi=200),
    FieldSpec("phone_pay_settled", ("phone pay settled total",), 0.80, 0.98, min_digits=2),
    FieldSpec("phone_pay_unsettled", ("phone pay not settled total",), 0.80, 0.98, min_digits=2),
    FieldSpec("night_cash", ("night cash hand off total",), 0.80, 0.98, min_digits=2),
)
