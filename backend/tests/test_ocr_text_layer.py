"""OCR pipeline on a machine-generated / typed PDF - it reads the PDF's own text
layer (no Tesseract), so this runs everywhere.

Sample: docs/.../ocr-samples/SVR-daily-sales-2026-09-09-typed-bw.pdf - a
handwritten sheet transcribed into the SVR template as a typed B&W PDF.
"""

from __future__ import annotations

from pathlib import Path

from svr_backend.calc.daily_sales_entry import compute_payload
from svr_backend.ocr.pipeline import extract

_TYPED = (
    Path(__file__).resolve().parents[2]
    / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"
    / "SVR-daily-sales-2026-09-09-typed-bw.pdf"
)

_TRUTH = {
    "hs.current": "1487828.110", "hs.last": "1487517.430", "hs.rate": "105.36",
    "ms.current": "661164.690", "ms.last": "660581.140", "ms.rate": "117.70",
    "phone_pay_settled": "8560", "night_cash": "36980.30",
}


def test_typed_pdf_read_from_text_layer():
    res = extract(_TYPED.read_bytes(), _TYPED.name)
    assert res.engine == "PDF text layer"
    got = {f.key: f.value for f in res.fields}
    for key, want in _TRUTH.items():
        assert got[key] == want, f"{key}: got {got[key]!r}, want {want!r}"


def test_typed_pdf_recomputes_to_the_paper_figures():
    res = extract(_TYPED.read_bytes(), _TYPED.name)
    calc = compute_payload(res.payload)
    assert calc["hs"]["cons"] == 310.68          # 1487828.110 - 1487517.430
    assert calc["ms"]["cons"] == 583.55
    assert round(calc["hs"]["amount"], 2) == 32733.24
    assert round(calc["ms"]["amount"], 2) == 68683.84


def test_text_layer_warning_is_not_the_handwriting_one():
    res = extract(_TYPED.read_bytes(), _TYPED.name)
    joined = " ".join(res.warnings)
    assert "text layer" in joined and "OCR DRAFT" not in joined


def test_endpoint_on_typed_pdf(client, auth_headers):
    r = client.post(
        "/daily-sales-entry/ocr",
        files={"file": (_TYPED.name, _TYPED.read_bytes(), "application/pdf")},
        headers=auth_headers("Sales"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "PDF text layer"
    assert body["payload"]["hs"]["current"] == "1487828.110"
    assert body["result"]["hs"]["cons"] == 310.68
