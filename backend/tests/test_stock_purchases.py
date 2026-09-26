"""Stock purchase paperwork on the Inventory Tracking Master.

Client, 2026-09-25: "this form should have a capability to upload the Stock
Purchase document uploaded like invoice in pdf, jpg any other supported format so
that we can see what we bought to keep track forever."
"""

from __future__ import annotations

PDF = b"%PDF-1.4\n%fake invoice for the test\n"

# The whole Inventory Master form is behind the Owner passphrase; a Manager may
# make the change but not without it (client, 2026-09-25). Set per test: the
# db_path fixture is function-scoped, so every test starts on a fresh database
# and a cached "already set" flag would leave the next one with no passphrase.
SECRET = "purchase-docs-2026"


def _unlock(client, auth_headers, role="Manager"):
    r = client.post("/owner-reset/secret", json={"new_passphrase": SECRET},
                    headers=auth_headers("Owner"))
    assert r.status_code in (200, 400), r.text[:200]
    return auth_headers(role)



def test_a_manager_uploads_an_invoice_and_can_read_it_back(client, auth_headers):
    h = _unlock(client, auth_headers)
    r = client.post(
        "/stock-purchases",
        headers=h,
        files={"file": ("Bharat Oils inv 4471.pdf", PDF, "application/pdf")},
        data={"passphrase": SECRET, "purchase_date": "2026-09-20", "supplier": "Bharat Oils",
              "amount": "18400.50", "item_key": "oil1", "note": "20 cartons 2T"},
    )
    assert r.status_code == 201, r.text[:300]
    doc = r.json()
    assert doc["supplier"] == "Bharat Oils"
    assert doc["amount"] == 18400.50
    assert doc["size_bytes"] == len(PDF)
    # The name the operator gave it is kept for display...
    assert doc["original_name"].startswith("Bharat")
    # ...and the bytes come back exactly.
    got = client.get(f"/stock-purchases/{doc['id']}/file", headers=h)
    assert got.status_code == 200
    assert got.content == PDF

    listed = client.get("/stock-purchases", headers=h).json()
    assert any(d["id"] == doc["id"] for d in listed)


def test_the_stored_filename_cannot_be_chosen_by_the_upload(client, auth_headers, conn):
    """An uploaded filename is user input. It names the file for a human; it must
    not pick the path it is written to."""
    r = client.post(
        "/stock-purchases",
        headers=_unlock(client, auth_headers, "Owner"),
        files={"file": ("../../evil .pdf", PDF, "application/pdf")},
        data={"passphrase": SECRET, "purchase_date": "2026-09-21"},
    )
    assert r.status_code == 201, r.text[:300]
    row = conn.execute(
        "SELECT original_name, stored_name FROM stock_purchase_document "
        "WHERE id = ?", (r.json()["id"],)
    ).fetchone()
    assert "/" not in row["original_name"] and "\\\\" not in row["original_name"]
    assert ".." not in row["original_name"]
    # Generated, and nothing of the upload's choosing survives into it.
    assert row["stored_name"].endswith(".pdf")
    assert "evil" not in row["stored_name"]


def test_only_real_document_types_are_accepted(client, auth_headers):
    r = client.post(
        "/stock-purchases",
        headers=_unlock(client, auth_headers),
        files={"file": ("payload.exe", b"MZ\x90\x00", "application/x-msdownload")},
        data={"passphrase": SECRET, "purchase_date": "2026-09-21"},
    )
    assert r.status_code == 415, r.text[:200]
    assert "not accepted" in r.json()["detail"]


def test_an_empty_file_is_refused(client, auth_headers):
    r = client.post(
        "/stock-purchases",
        headers=_unlock(client, auth_headers),
        files={"file": ("blank.pdf", b"", "application/pdf")},
        data={"passphrase": SECRET},
    )
    assert r.status_code == 400


def test_sales_cannot_see_or_upload_purchase_paperwork(client, auth_headers):
    h = auth_headers("Sales")
    assert client.get("/stock-purchases", headers=h).status_code == 403
    assert client.post(
        "/stock-purchases", headers=h,
        files={"file": ("x.pdf", PDF, "application/pdf")},
        data={"passphrase": SECRET},
    ).status_code == 403


def test_a_missing_file_is_reported_rather_than_a_500(client, auth_headers, conn):
    """The row and the file can part company - a backup restored without the
    upload folder. Say so plainly instead of failing as a server error."""
    from pathlib import Path

    from svr_backend.core.config import get_settings

    h = _unlock(client, auth_headers, "Owner")
    doc = client.post(
        "/stock-purchases", headers=h,
        files={"file": ("gone.pdf", PDF, "application/pdf")},
        data={"passphrase": SECRET},
    ).json()
    stored = conn.execute(
        "SELECT stored_name FROM stock_purchase_document WHERE id = ?", (doc["id"],)
    ).fetchone()["stored_name"]
    Path(get_settings().resolved_upload_dir() / stored).unlink()

    r = client.get(f"/stock-purchases/{doc['id']}/file", headers=h)
    assert r.status_code == 410
    assert "missing" in r.json()["detail"]
