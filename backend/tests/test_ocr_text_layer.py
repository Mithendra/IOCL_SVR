"""OCR pipeline on a machine-generated / typed PDF - it reads the PDF's own text
layer (no Tesseract), so this runs everywhere.

Sample: docs/.../ocr-samples/SVR-daily-sales-2026-09-09-typed-bw.pdf - a
handwritten sheet transcribed into the SVR template as a typed B&W PDF.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from svr_backend.calc.daily_sales_entry import compute_payload
from svr_backend.ocr.pipeline import extract

_SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"

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


# ------------------------------------------------------------- 2026-09-11 delivery
#
# Four more real typed PDFs, spanning the Road pump's repair gap (2026-09-09/10).
# Confirms Scan/Upload's text-layer path reads every one of them - gas readings
# are what carry-forward and the calc engine depend on, so these are the fields
# that matter most; see OCR-findings-2026-09-09.md for the Phone Pay Settled
# caveat found on the busier Office-pump forms (works via Excel import instead).

_REAL_PDFS = [
    ("SVR_Daily_Sales_09Sep2026_ 12BC4523V-OFF.pdf", "1487828.110", "1487517.430", "310.68"),
    ("SVR_Daily_Sales_09Sep2026_12BC4523V-RD_.pdf", "267841.930", "267841.930", "0.0"),
    ("SVR_Daily_Sales_10Sep2026_11CC2012V-OFF.pdf", "1488457.600", "1487828.110", "629.49"),
    ("SVR_Daily_Sales_10Sep2026_12BC4523V-RD.pdf", "267859.100", "267841.930", "17.17"),
]


@pytest.mark.parametrize("name,current,last,cons", _REAL_PDFS)
def test_real_sep_delivery_pdfs_read_from_the_text_layer(name, current, last, cons):
    path = _SAMPLES / name
    if not path.exists():
        pytest.skip("real client sample not present")
    res = extract(path.read_bytes(), name)
    assert res.engine == "PDF text layer"
    got = {f.key: f.value for f in res.fields}
    assert got["hs.current"] == current
    assert got["hs.last"] == last
    assert compute_payload(res.payload)["hs"]["cons"] == float(cons)
