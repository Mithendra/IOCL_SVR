"""No account numbers, IFSC codes, UPI handles, MICR or PANs anywhere in the app.

Client, 2026-09-16:

    "no need of actual a/c numbers, just text is fine (no need of account
     numbers, IFSC codes, UPI handles and PANs) in this application - Do not
     want expose those details in the application JUST STATEMENT BALANCE ONLY"

This is a policy test, so it guards the thing the policy is about rather than a
formula. A bank balance is what the station reconciles each night; the account
it sits in adds nothing to that arithmetic and turns a screen share, a support
call or a stolen laptop into a much worse day.

It scans what the application itself ships - migrations, seeds and screens - not
the client's uploaded workbooks, which are evidence and are excluded. The
station's own bank and IOCL statement PDFs are kept out of the repo entirely by
.gitignore, because this repo is public.

If this test fails, the fix is to remove the identifier, not to widen the
pattern. The one legitimate reason to touch the patterns below is a false
positive on a real figure, and then the narrowest possible exclusion wins.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Directories that make up the shipped application.
SCANNED = [
    REPO / "backend" / "src" / "svr_backend",
    REPO / "frontend" / "src",
]

SUFFIXES = {".py", ".sql", ".js", ".html", ".css", ".json"}

# A bare run of 9-18 digits, not part of a longer number and not a decimal.
# Rupee amounts in this codebase are written with a decimal point or are far
# shorter than nine digits, so a match here is an identifier, not money.
ACCOUNT = re.compile(r"(?<![\d.])\d{9,18}(?![\d.])")
# Indian bank branch codes: four letters, a zero, then six alphanumerics.
IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
# UPI virtual payment addresses, e.g. name@okicici, name@ybl.
UPI = re.compile(r"\b[\w.\-]{3,}@(?:ok\w+|ybl|paytm|upi|axl|ibl)\b", re.IGNORECASE)
# Permanent Account Number: five letters, four digits, a letter.
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
# MICR code on a cheque leaf.
MICR = re.compile(r"\bMICR\b[^\n]{0,40}\d{6,9}\b", re.IGNORECASE)

PATTERNS = {
    "account number": ACCOUNT,
    "IFSC code": IFSC,
    "UPI handle": UPI,
    "PAN": PAN,
    "MICR code": MICR,
}

# Narrow, justified exclusions. Each one says why it is not an identifier.
ALLOWED = {
    # Unix epoch milliseconds in date maths.
    re.compile(r"1[6-9]\d{11}"),
    # A run of one repeated digit. 9999999999999999 appears in two comments
    # describing how wide the hand-written Amount column is sized to be; no
    # issued account number, IFSC or PAN looks like that.
    re.compile(r"(\d)\1{8,17}"),
}


def _is_allowed(text: str) -> bool:
    return any(p.fullmatch(text) for p in ALLOWED)


def _files():
    for root in SCANNED:
        for path in root.rglob("*"):
            if path.suffix.lower() not in SUFFIXES:
                continue
            if "__pycache__" in path.parts or "node_modules" in path.parts:
                continue
            yield path


def test_the_application_ships_no_bank_identifiers():
    findings: list[str] = []
    for path in _files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                for match in pattern.findall(line):
                    value = match if isinstance(match, str) else match[0]
                    if _is_allowed(value):
                        continue
                    rel = path.relative_to(REPO).as_posix()
                    findings.append(f"{rel}:{lineno}  {label}: {value!r}")

    assert not findings, (
        "The application must not carry bank identifiers - only a bank NAME and "
        "its statement balance (client, 2026-09-16). Found:\n  "
        + "\n  ".join(findings)
        + "\n\nRemove the identifier. Do not widen the pattern to make this pass."
    )


def test_the_three_banks_are_seeded_as_names_only():
    """The names the client asked for, and nothing beside them."""
    sql = (
        REPO
        / "backend/src/svr_backend/migrations/0035_bank_names_text_only.sql"
    ).read_text(encoding="utf-8")
    for bank in ("Indian Bank", "Yes Bank", "IOCL Spana"):
        assert bank in sql, f"{bank} missing from the seeded bank list"
    # The seed inserts three values and no numeric columns beyond sort_order.
    assert ACCOUNT.search(sql) is None
    assert IFSC.search(sql) is None


def test_every_seeded_dropdown_list_can_also_be_added_to():
    """A list you can see but cannot extend is a dead "+" button.

    The client asked for the tester list and the "+" to add names in one
    sentence. Migration 0034 seeded the names and the dropdown showed them, but
    POST /daily-trial-balance/options rejected 'offload_testers' as an unknown
    list, so the button returned 400. Seeding a list and permitting writes to it
    are two different places in the code; only one had been changed.

    This compares the two directly, so the next list that is seeded without
    being allowed fails here instead of on the station's screen.
    """
    import re as _re

    from svr_backend.api.daily_trial_balance import OPTION_LISTS

    migrations = (REPO / "backend/src/svr_backend/migrations").glob("*.sql")
    seeded: set[str] = set()
    pattern = _re.compile(r"\(\s*'([a-z_]+)'\s*,\s*'[^']*'\s*,\s*\d+\s*,", _re.I)
    for path in migrations:
        text = path.read_text(encoding="utf-8")
        if "trial_balance_option" not in text:
            continue
        seeded.update(pattern.findall(text))

    assert seeded, "no seeded option lists found - has the seed format changed?"
    missing = sorted(seeded - set(OPTION_LISTS))
    assert not missing, (
        "these lists are seeded into trial_balance_option but are not in "
        f"OPTION_LISTS, so their '+' button will return 400: {missing}"
    )
