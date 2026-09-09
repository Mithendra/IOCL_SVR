"""OCR draft-assist for the Scan / Upload path (SDD ADR-5).

Rasterise a scanned/photographed SVR Daily Sales Report, run the bundled
Tesseract, and map what it reads onto a Daily Sales Entry payload for **human
review** - the pipeline never saves and every field it fills is flagged.

Reality (measured 2026-09-09 on real station scans, see
docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md): Tesseract reads
the *printed* template well but the *handwritten* numbers poorly. So this is a
typing accelerator with a mandatory verify step, not automatic capture.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from svr_backend.core.config import get_settings
from svr_backend.ocr.layout import DAILY_SALES_FIELDS

_RASTER_DPI = 300
_TIMEOUT_S = 60
_IMG_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"BM", b"II*\x00", b"MM\x00*")


@dataclass
class Word:
    text: str
    conf: float          # 0..1
    cx: float            # centre, page-fraction 0..1
    cy: float


@dataclass
class FieldGuess:
    key: str
    value: str | None
    confidence: float
    raw: str


@dataclass
class ExtractResult:
    payload: dict = field(default_factory=dict)
    fields: list[FieldGuess] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    page_text: str = ""
    engine: str = ""


# --------------------------------------------------------------------- rasterise


def _pages_to_png(data: bytes) -> list[bytes]:
    if data[:4] in _IMG_MAGIC or data[:3] in _IMG_MAGIC or data[:2] in _IMG_MAGIC:
        return [data]  # already an image
    import pymupdf  # lazy - keeps import cost off the hot path

    out: list[bytes] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=_RASTER_DPI, colorspace=pymupdf.csGRAY)
            out.append(pix.tobytes("png"))
    return out


# ------------------------------------------------------------------------- tsv


def _tesseract_tsv(png: bytes) -> tuple[list[Word], str]:
    """Run the bundled Tesseract and return (words with page-relative boxes, page text).

    Uses ``-c tessedit_create_tsv=1`` to a file rather than the ``tsv`` stdout
    config, so it does not depend on ``tessdata/configs/`` being present.
    """
    cmd = get_settings().resolved_tesseract_cmd()
    env = None
    prefix = get_settings().tessdata_prefix
    if prefix:
        env = {**os.environ, "TESSDATA_PREFIX": str(prefix)}
    tmp = Path(tempfile.mkdtemp(prefix="svr-ocr-"))
    img, base = tmp / "page.png", tmp / "out"
    img.write_bytes(png)
    try:
        subprocess.run(  # noqa: S603 - fixed argv
            [cmd, str(img), str(base), "--psm", "6", "-c", "tessedit_create_tsv=1"],
            capture_output=True, timeout=_TIMEOUT_S, env=env, check=False,
        )
        tsv_path = base.with_suffix(".tsv")
        tsv = tsv_path.read_text(encoding="utf-8", errors="replace") if tsv_path.exists() else ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return _parse_tsv(tsv)


def _parse_tsv(tsv: str) -> tuple[list[Word], str]:
    lines = tsv.splitlines()
    if not lines or not lines[0].startswith("level"):
        # tesseract wrote plain text (no tsv) - return it as page_text only
        return [], tsv.strip()
    header = lines[0].split("\t")
    ix = {name: i for i, name in enumerate(header)}
    words: list[Word] = []
    pw = ph = 1.0
    text_parts: list[str] = []
    for ln in lines[1:]:
        c = ln.split("\t")
        if len(c) <= ix["text"]:
            continue
        try:
            level = int(c[ix["level"]])
            left, top = float(c[ix["left"]]), float(c[ix["top"]])
            w, h = float(c[ix["width"]]), float(c[ix["height"]])
            conf = float(c[ix["conf"]])
        except ValueError:
            continue
        if level == 1:  # page
            pw, ph = max(w, 1.0), max(h, 1.0)
            continue
        txt = c[ix["text"]].strip()
        if not txt or conf < 0:
            continue
        text_parts.append(txt)
        words.append(
            Word(text=txt, conf=conf / 100.0, cx=(left + w / 2) / pw, cy=(top + h / 2) / ph)
        )
    return words, " ".join(text_parts)


# --------------------------------------------------------------- field mapping


_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def _clean_number(raw: str) -> str | None:
    m = _NUM_RE.findall(raw.replace(" ", ""))
    if not m:
        return None
    return max(m, key=len).replace(",", "")


def _guess_field(spec, words: list[Word]) -> FieldGuess:
    row = _band(words, spec.row_anchors, axis="y", tol=spec.row_tol)
    if not row:
        return FieldGuess(spec.key, None, 0.0, "")
    # within the row, keep words to the right of the column anchor (or all of it)
    x0 = _anchor_x(words, spec.col_anchors) if spec.col_anchors else 0.0
    cand = sorted((w for w in row if w.cx > x0 + 0.01), key=lambda w: w.cx)[: spec.max_words]
    if not cand:
        return FieldGuess(spec.key, None, 0.0, "")
    raw = " ".join(w.text for w in cand)
    value = _clean_number(raw) if spec.numeric else (raw.strip() or None)
    conf = sum(w.conf for w in cand) / len(cand)
    if value is not None and spec.numeric and not _plausible(value, spec):
        value = None  # keep the raw text visible, but don't pre-fill an implausible number
    return FieldGuess(spec.key, value, round(conf, 2), raw)


def _plausible(value: str, spec) -> bool:
    digits = sum(c.isdigit() for c in value)
    if spec.min_digits and digits < spec.min_digits:
        return False
    if spec.lo is not None or spec.hi is not None:
        try:
            n = float(value)
        except ValueError:
            return False
        if spec.lo is not None and n < spec.lo:
            return False
        if spec.hi is not None and n > spec.hi:
            return False
    return True


def _band(words, anchors, *, axis, tol):
    a = _find(words, anchors)
    if a is None:
        return []
    centre = a.cy if axis == "y" else a.cx
    return [w for w in words if abs((w.cy if axis == "y" else w.cx) - centre) <= tol]


def _anchor_x(words, anchors) -> float:
    a = _find(words, anchors)
    return a.cx if a else 0.0


def _find(words, anchors):
    frags = [s.lower() for s in anchors]
    for w in words:
        lw = w.text.lower()
        if any(f in lw for f in frags):
            return w
    return None


def _apply(payload: dict, key: str, value) -> None:
    cur = payload
    parts = key.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


# --------------------------------------------------------------------- extract


def extract(data: bytes, filename: str = "") -> ExtractResult:
    if not data:
        raise ValueError("empty upload")
    res = ExtractResult(engine=_engine_line())
    try:
        pages = _pages_to_png(data)
    except Exception as exc:  # noqa: BLE001 - surface any rasterise failure
        raise ValueError(f"could not read {filename or 'the file'} as PDF or image: {exc}") from exc

    words, res.page_text = _tesseract_tsv(pages[0])
    if not words:
        res.warnings.append("Tesseract could not segment the page - fill the form by hand.")
        return res

    payload: dict = {"hs": {}, "ms": {}, "oils": []}
    for spec in DAILY_SALES_FIELDS:
        g = _guess_field(spec, words)
        res.fields.append(g)
        if g.value not in (None, ""):
            _apply(payload, spec.key, g.value)
    res.payload = payload
    res.warnings.append(
        "OCR DRAFT - Tesseract cannot read handwriting reliably. Check every value "
        "against the scan before saving."
    )
    return res


def _engine_line() -> str:
    try:
        p = subprocess.run(  # noqa: S603
            [get_settings().resolved_tesseract_cmd(), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return (p.stdout or p.stderr).splitlines()[0].strip()
    except (OSError, subprocess.SubprocessError, IndexError):
        return "tesseract (version unknown)"


def rasterize_first_page(data: bytes) -> bytes:
    """Exposed for tests / previews."""
    return _pages_to_png(data)[0]
