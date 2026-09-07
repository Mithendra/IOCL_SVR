"""OCR packaging (SDD ADR-6): the engine is bundled, the pipeline is not built.

These cover the *resolver* and the status endpoint - not recognition, which is a
separate module. `tesseract_version` is monkeypatched so the result does not
depend on whether the CI box happens to have Tesseract on PATH.
"""

from __future__ import annotations

from pathlib import Path

from svr_backend.core.config import Settings
from svr_backend.ocr import runtime


def test_resolved_tesseract_cmd_falls_back_to_path():
    assert Settings(tesseract_cmd=None).resolved_tesseract_cmd() == "tesseract"


def test_resolved_tesseract_cmd_uses_configured_path():
    p = Path(r"C:\App\resources\tesseract\tesseract.exe")
    assert Settings(tesseract_cmd=p).resolved_tesseract_cmd() == str(p)


def test_ocr_status_reports_unavailable(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "svr_backend.api.daily_sales_entry.tesseract_version", lambda: None
    )
    r = client.get("/daily-sales-entry/ocr/status", headers=auth_headers("Sales"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bundled"] is False
    assert body["version"] is None
    assert body["pipeline"] == "not-implemented"


def test_ocr_status_reports_bundled(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "svr_backend.api.daily_sales_entry.tesseract_version",
        lambda: "tesseract 5.3.3",
    )
    r = client.get("/daily-sales-entry/ocr/status", headers=auth_headers("Manager"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bundled"] is True
    assert body["version"] == "tesseract 5.3.3"


def test_ocr_status_requires_auth(client):
    assert client.get("/daily-sales-entry/ocr/status").status_code == 401


def test_ocr_upload_still_501_but_message_points_at_bundled_engine(client, auth_headers):
    r = client.post("/daily-sales-entry/ocr", headers=auth_headers("Sales"))
    assert r.status_code == 501
    assert "bundled" in r.json()["detail"]


def test_runtime_version_none_when_binary_missing(monkeypatch):
    """A bad command yields None, not an exception (OSError path)."""
    monkeypatch.setattr(
        runtime, "get_settings", lambda: Settings(tesseract_cmd=Path("nonexistent-xyz"))
    )
    assert runtime.tesseract_version() is None
    assert runtime.is_available() is False
