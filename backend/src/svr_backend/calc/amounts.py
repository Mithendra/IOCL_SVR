"""Shared numeric helpers, ported verbatim from ``daily_sales_report_branded.html``.

The two behaviours here are load-bearing business rules, not conveniences:

* ``parse_amt`` accepts the inline scratch-work pump sales men actually write on the
  paper form - ``"527+588+100=1215"`` or a bare ``"527+588+100"`` (BRD 8, SDD 11.2).
* ``round4`` pins arithmetic to 4 decimal places so the worked example
  ``1317.52 * 105.36 = 138813.9072`` reproduces exactly with no float drift (SDD 9).
"""

from __future__ import annotations

import math

Number = str | int | float | None


def parse_amt(raw: Number) -> float:
    """Mirror of the mockup's ``parseAmt``.

    ``""`` / ``None`` -> 0. ``"a+b=c"`` -> the part after the last ``=``.
    ``"a+b+c"`` -> the sum of the numeric parts. Anything unparseable -> 0.
    """
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if text == "":
        return 0.0

    if "=" in text:
        text = text.split("=")[-1].strip()

    if "+" in text:
        total = 0.0
        for part in text.split("+"):
            try:
                total += float(part)
            except ValueError:
                continue
        return total

    try:
        return float(text)
    except ValueError:
        return 0.0


def round4(n: float) -> float:
    """4-dp round-half-up, matching JS ``Math.round(n * 10000) / 10000`` exactly.

    Python's built-in ``round`` uses banker's rounding, which the mockup does not;
    ``math.floor(x + 0.5)`` reproduces ``Math.round`` for both signs.

    Retained for callers that genuinely want 4-dp. Daily Sales Entry now uses
    ``trunc2`` instead - see below.
    """
    return math.floor(n * 10000 + 0.5) / 10000


def trunc2(n: float) -> float:
    """2-dp truncation (toward zero) - what the station's own forms actually do.

    Proven against the real filled client sheets (2026-09-11): every row amount
    on the paper form is the product cut off at two decimals, never rounded.
    Truncation reproduced 4/4 sampled gas rows where rounding failed 2/4 -
    e.g. ``629.49 * 105.36 = 66323.0664`` is printed as ``66323.06``, not
    ``.07``, and ``581.44 * 117.7 = 68435.488`` as ``68435.48``, not ``.49``.
    Applying this per row and then summing reproduces all three sheets' Net Bal
    figures exactly (23298.77 / 38993.84 / 1601.20).

    The inner ``round(..., 6)`` absorbs binary-float noise before the cut, so a
    value that is mathematically ``x.29`` but stored as ``x.28999999999999998``
    truncates to ``.29`` rather than ``.28``.
    """
    return math.trunc(round(n * 100, 6)) / 100


def is_blank(raw: Number) -> bool:
    """A lone "-" is the paper form's own universal "nothing to report" marker
    (every real client sample uses it consistently across every optional field),
    so it's treated the same as an empty cell - never as a real value (2026-09-11).
    """
    if raw is None:
        return True
    return str(raw).strip() in ("", "-")
