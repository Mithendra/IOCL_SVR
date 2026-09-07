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

from svr_backend.core.config import get_settings

_VERSION_TIMEOUT_S = 10


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    prefix = get_settings().tessdata_prefix
    if prefix:
        env["TESSDATA_PREFIX"] = str(prefix)
    return env


def tesseract_version() -> str | None:
    """First line of ``tesseract --version`` (e.g. ``tesseract 5.3.3``), or None.

    None means the binary is missing, not executable, or timed out - callers
    treat all three the same: OCR is unavailable.
    """
    cmd = get_settings().resolved_tesseract_cmd()
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_S,
            env=_child_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    first = (proc.stdout or proc.stderr).splitlines()
    return first[0].strip() if first else None


def is_available() -> bool:
    """True when the bundled (or PATH) Tesseract answers ``--version``."""
    return tesseract_version() is not None
