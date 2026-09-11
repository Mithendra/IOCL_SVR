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
    """
    return math.floor(n * 10000 + 0.5) / 10000


def is_blank(raw: Number) -> bool:
    """A lone "-" is the paper form's own universal "nothing to report" marker
    (every real client sample uses it consistently across every optional field),
    so it's treated the same as an empty cell - never as a real value (2026-09-11).
    """
    if raw is None:
        return True
    return str(raw).strip() in ("", "-")
