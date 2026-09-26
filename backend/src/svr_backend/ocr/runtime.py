"""Locate and probe the bundled Tesseract binary (SDD ADR-6).

No third-party dependency: the recognition pipeline will add ``pytesseract`` +
``Pillow`` (a ``backend[ocr]`` extra) when it is built, but the packaging
decision only needs to prove the shipped binary runs, which ``subprocess`` does.

Resolution order for the command:
  1. ``SVR_TESSERACT_CMD``  - the absolute path first-run.ps1 writes on the target
  2. a bare ``tesseract`` on ``PATH`` - dev machines / CI

``SVR_TESSDATA_PREFIX`` (when set) is exported to the child as ``TESSDATA_PREFIX``
so Tesseract finds the bundled ``tessdata\\`` rather than a system copy.
"""

from __future__ import annotations

import os
import subprocess
import time

from svr_backend.core.config import get_settings

_VERSION_TIMEOUT_S = 20   # a cold start on a loaded machine is slow, not broken


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    prefix = get_settings().tessdata_prefix
    if prefix:
        env["TESSDATA_PREFIX"] = str(prefix)
    return env


# The last SUCCESSFUL probe, and when the last failed one happened.
#
# This was an @lru_cache(maxsize=1), added to stop a subprocess being spawned on
# every /ocr call - on a loaded machine the 10s probe could time out and the
# engine would appear to vanish, which showed up as OCR tests failing at random.
#
# That cache made it worse, not better. lru_cache stores a FAILURE just as
# happily as a success, so a single slow probe - the first one in a busy test
# run, or on a station PC mid-upload - pinned "Tesseract is unavailable" for the
# life of the process. Nothing short of a service restart brought OCR back, and
# the symptom was identical to the one the cache was meant to cure, which is why
# it came back four times.
#
# So: a success is cached forever (whether Tesseract is installed genuinely does
# not change while the service runs), and a FAILURE is cached only briefly, long
# enough to stop a per-call subprocess storm on an install that really has no
# Tesseract. A slow probe now costs one retry, not the rest of the process.
_version: str | None = None
_failed_at: float = 0.0
_RETRY_AFTER_S = 30.0


def tesseract_version() -> str | None:
    """First line of ``tesseract --version`` (e.g. ``tesseract 5.3.3``), or None.

    None means the binary is missing, not executable, or timed out - callers
    treat all three the same: OCR is unavailable. A None is NOT remembered for
    long; see the note above.
    """
    global _version, _failed_at
    if _version is not None:
        return _version
    if _failed_at and (time.monotonic() - _failed_at) < _RETRY_AFTER_S:
        return None

    cmd = get_settings().resolved_tesseract_cmd()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_S,
            env=_child_env(),
        )
    except subprocess.TimeoutExpired:
        # NOT remembered, not even briefly. A timeout means the machine was busy,
        # not that Tesseract is missing - a vendored tesseract.exe cold-starting
        # on a loaded PC is slow, and that is the whole failure mode this module
        # keeps being bitten by. Remembering it makes the next call lie too, and
        # three OCR calls in a row inside one busy minute then all fail together.
        return None
    except OSError:
        # A definite answer: no such binary, or it is not executable. Worth
        # remembering briefly so an install genuinely without Tesseract does not
        # spawn a subprocess per request.
        _failed_at = time.monotonic()
        return None
    if proc.returncode != 0:
        _failed_at = time.monotonic()
        return None
    first = (proc.stdout or proc.stderr).splitlines()
    if not first:
        _failed_at = time.monotonic()
        return None
    _version = first[0].strip()
    _failed_at = 0.0
    return _version


def _cache_clear() -> None:
    """Forget both the version and the last failure. For tests and for a probe
    that has to be re-run after installing Tesseract."""
    global _version, _failed_at
    _version = None
    _failed_at = 0.0


tesseract_version.cache_clear = _cache_clear   # type: ignore[attr-defined]


def is_available() -> bool:
    """True when the bundled (or PATH) Tesseract answers ``--version``."""
    return tesseract_version() is not None
