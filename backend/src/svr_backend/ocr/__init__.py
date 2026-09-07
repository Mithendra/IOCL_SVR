"""OCR support for the Scan / Upload entry path.

Only the *runtime resolver* lives here today (SDD ADR-6): it locates the
Tesseract binary the installer bundles under ``<INSTDIR>\\resources\\tesseract\\``
and reports whether it is usable. The recognition pipeline itself (image
pre-processing, field extraction, the recompute-and-flag review step per SDD
ADR-5) is a separate, not-yet-built module.
"""

from svr_backend.ocr.runtime import is_available, tesseract_version

__all__ = ["is_available", "tesseract_version"]
