"""OCR draft-assist pipeline, exercised against the real station scans in
docs/01-BRD-Requirement-Gathering/ocr-samples/.

Skipped wherever the bundled Tesseract is not staged (CI backend job, most dev
boxes). The point of these tests is that the pipeline runs and stays
*conservative* on handwriting - not that it reads the numbers (it does not; see
docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from svr_backend.core.config import get_settings

_ROOT = Path(__file__).resolve().parents[2]
_VENDOR = _ROOT / "installer" / "vendor" / "tesseract"
_TESS = _VENDOR / "tesseract.exe"
_SAMPLES = _ROOT / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"
_SCAN = _SAMPLES / "SVR-daily-sales-2026-09-08-road-scan.pdf"
_PHOTO = _SAMPLES / "SVR-daily-sales-2026-09-07-road-photo.pdf"

pytestmark = pytest.mark.skipif(
    not _TESS.exists(),
    reason="bundled Tesseract not staged - run installer/fetch-tesseract.ps1",
)


@pytest.fixture(autouse=True)
def _bundled_tesseract(monkeypatch):
    monkeypatch.setenv("SVR_TESSERACT_CMD", str(_TESS))
    monkeypatch.setenv("SVR_TESSDATA_PREFIX", str(_VENDOR / "tessdata"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_extract_reads_the_printed_template():
    from svr_backend.ocr.pipeline import extract

    res = extract(_SCAN.read_bytes(), _SCAN.name)
    assert res.engine.lower().startswith("tesseract")
    # the printed labels come through even though the handwriting does not
    assert "service station" in res.page_text.lower()
    assert {f.key for f in res.fields} >= {"hs.current", "ms.last", "hs.rate"}


def test_pipeline_stays_conservative_on_handwriting():
    from svr_backend.ocr.pipeline import extract

    for sample in (_SCAN, _PHOTO):
        res = extract(sample.read_bytes(), sample.name)
        filled = [f for f in res.fields if f.value not in (None, "")]
        # implausible guesses are dropped; a couple may slip through, never many
        assert len(filled) <= 3, f"{sample.name}: {filled}"
        assert any("OCR DRAFT" in w for w in res.warnings)


def test_ocr_endpoint_returns_a_flagged_draft(client, auth_headers):
    with _SCAN.open("rb") as fh:
        r = client.post(
            "/daily-sales-entry/ocr",
            files={"file": (_SCAN.name, fh.read(), "application/pdf")},
            headers=auth_headers("Sales"),
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"].lower().startswith("tesseract")
    assert any("OCR DRAFT" in w for w in body["warnings"])
    assert "result" in body and "net_bal_hand_off" in body["result"]
    assert len(body["fields"]) == 9


def test_ocr_endpoint_rejects_non_document(client, auth_headers):
    r = client.post(
        "/daily-sales-entry/ocr",
        files={"file": ("x.pdf", b"not a pdf or image", "application/pdf")},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 400


def test_ocr_endpoint_requires_auth(client):
    assert client.post("/daily-sales-entry/ocr").status_code == 401
