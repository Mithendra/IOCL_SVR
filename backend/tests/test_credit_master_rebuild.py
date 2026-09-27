"""Credit/Remittance Master rebuild (client, 2026-09-26/27): the creditor
master table, its documents, and the new columns/search on transactions.

The posting-pipeline half (Daily Sales Entry -> Daily Trial Balance -> Credit
Master, and the 3.13 split) is covered in test_trial_balance_posting.py.
"""

from __future__ import annotations

PDF = b"%PDF-1.4\n%fake agreement for the test\n"


def test_add_creditor_also_updates_the_option_lists(client, auth_headers):
    h = auth_headers("Manager")
    r = client.post("/credit-master/creditors",
                    json={"name": "Ramana Transports", "credit_type": "old",
                          "note": "Pre-app legacy balance"}, headers=h)
    assert r.status_code == 201, r.text[:300]
    assert r.json()["credit_type"] == "old"

    lists = client.get("/daily-trial-balance/options", headers=h).json()
    assert "Ramana Transports" in lists["customers"]
    assert "Ramana Transports" in lists["creditors"]


def test_adding_the_same_creditor_twice_is_refused(client, auth_headers):
    h = auth_headers("Manager")
    client.post("/credit-master/creditors", json={"name": "Anil/Nani"}, headers=h)
    r = client.post("/credit-master/creditors", json={"name": "Anil/Nani"}, headers=h)
    assert r.status_code == 409


def test_summary_shows_a_creditor_with_no_transactions_yet(client, auth_headers):
    h = auth_headers("Manager")
    client.post("/credit-master/creditors", json={"name": "Sajja Function Hall"}, headers=h)
    rows = client.get("/credit-master/summary", headers=h).json()
    row = next(r for r in rows if r["creditor_name"] == "Sajja Function Hall")
    assert row["total_credit"] == 0
    assert row["outstanding"] == 0


def test_update_creditor_patches_only_the_given_fields(client, auth_headers):
    client.post("/credit-master/creditors", json={"name": "Ramana Transports"},
                headers=auth_headers("Manager"))
    r = client.patch("/credit-master/creditors/Ramana Transports",
                     json={"credit_type": "old"}, headers=auth_headers("Owner"))
    assert r.status_code == 200
    assert r.json()["credit_type"] == "old"
    assert r.json()["phone"] is None


def test_a_manual_credit_carries_the_new_columns_and_is_tagged_manual(
    client, auth_headers, conn
):
    r = client.post(
        "/credit-master/credit",
        json={"creditor_name": "AirTel Hari", "ltrs": 10, "rate": 105.36,
              "payment_mode": "Credit (CR)"},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 201, r.text[:300]
    row = r.json()
    assert row["status"] == "manual"
    assert row["payment_mode"] == "Credit (CR)"


def test_a_manual_remittance_carries_the_new_columns(client, auth_headers):
    r = client.post(
        "/credit-master/remittance",
        json={"creditor_name": "Anil/Nani", "amount": 2000,
              "payment": "Full", "remittance_entered": "Yes",
              "collected_by": "Sriharsha", "payment_mode": "Cash",
              "given_on_date": "2026-09-01"},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 201, r.text[:300]
    row = r.json()
    assert row["status"] == "manual"
    assert row["payment"] == "Full"
    assert row["collected_by"] == "Sriharsha"
    assert row["given_on_date"] == "2026-09-01"


def test_transactions_search_by_date_range(client, auth_headers):
    h = auth_headers("Manager")
    client.post("/credit-master/credit",
                json={"creditor_name": "AirTel Hari", "amount": 500,
                      "txn_date": "2026-09-01"}, headers=h)
    client.post("/credit-master/credit",
                json={"creditor_name": "AirTel Hari", "amount": 600,
                      "txn_date": "2026-09-20"}, headers=h)

    only_early = client.get(
        "/credit-master/transactions?date_from=2026-09-01&date_to=2026-09-10",
        headers=h,
    ).json()
    amounts = [r["amount"] for r in only_early if r["creditor_name"] == "AirTel Hari"]
    assert amounts == [500]


def test_document_upload_list_and_download_round_trip(client, auth_headers):
    h = auth_headers("Manager")
    client.post("/credit-master/creditors", json={"name": "Ramana Transports"}, headers=h)
    up = client.post(
        "/credit-master/creditors/Ramana Transports/documents",
        headers=h,
        files={"file": ("Old Ledger Scan.pdf", PDF, "application/pdf")},
        data={"note": "pre-app balance, page 1"},
    )
    assert up.status_code == 201, up.text[:300]
    doc = up.json()
    assert doc["original_name"].startswith("Old")

    listed = client.get("/credit-master/creditors/Ramana Transports/documents",
                        headers=h).json()
    assert any(d["id"] == doc["id"] for d in listed)

    got = client.get(
        f"/credit-master/creditors/Ramana Transports/documents/{doc['id']}/file",
        headers=h,
    )
    assert got.status_code == 200
    assert got.content == PDF


def test_the_stored_filename_cannot_be_chosen_by_the_upload(client, auth_headers, conn):
    h = auth_headers("Manager")
    client.post("/credit-master/creditors", json={"name": "Sajja Function Hall"}, headers=h)
    r = client.post(
        "/credit-master/creditors/Sajja Function Hall/documents",
        headers=h,
        files={"file": ("../../evil .pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 201, r.text[:300]
    row = conn.execute(
        "SELECT original_name, stored_name FROM creditor_document WHERE id = ?",
        (r.json()["id"],),
    ).fetchone()
    assert "/" not in row["original_name"] and ".." not in row["original_name"]
    assert row["stored_name"].endswith(".pdf")
    assert "evil" not in row["stored_name"]


def test_document_upload_refuses_an_unknown_creditor(client, auth_headers):
    r = client.post(
        "/credit-master/creditors/Nobody At All/documents",
        headers=auth_headers("Manager"),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 404


def test_sales_cannot_reach_credit_master_at_all(client, auth_headers):
    h = auth_headers("Sales")
    assert client.get("/credit-master/summary", headers=h).status_code == 403
    assert client.get("/credit-master/creditors", headers=h).status_code == 403
    assert client.post("/credit-master/creditors", json={"name": "X"},
                       headers=h).status_code == 403


# ------------------------------------------------------------------------
# Paid / Cleared (client, 2026-09-27): "once the Payment is entered in
# Remittance it should show Posted as Paid and then should be able to
# clear" - settlement has to fire the same way regardless of which screen
# collects the payment, so these hit Credit Master directly (no Trial
# Balance in the loop at all) - see test_trial_balance_posting.py for the
# DSE -> TB -> Post side of the same engine.

def test_a_remittance_typed_here_settles_the_matching_credit_to_paid(
    client, auth_headers
):
    h = auth_headers("Manager")
    credit = client.post(
        "/credit-master/credit",
        json={"creditor_name": "AirTel Hari", "amount": 4214.40,
              "txn_date": "2026-11-01"},
        headers=h,
    ).json()
    assert credit["status"] == "manual"

    client.post(
        "/credit-master/remittance",
        json={"creditor_name": "AirTel Hari", "amount": 4214.40,
              "txn_date": "2026-11-02"},
        headers=h,
    )

    refreshed = client.get(
        "/credit-master/transactions?creditor=AirTel Hari&kind=credit", headers=h
    ).json()
    settled = next(r for r in refreshed if r["id"] == credit["id"])
    assert settled["status"] == "paid"
    assert settled["paid_by"] == "manager"
    assert settled["paid_at"]


def test_a_part_payment_leaves_the_credit_outstanding(client, auth_headers):
    h = auth_headers("Manager")
    credit = client.post(
        "/credit-master/credit",
        json={"creditor_name": "Sajja Function Hall", "amount": 5000,
              "txn_date": "2026-11-01"},
        headers=h,
    ).json()
    client.post(
        "/credit-master/remittance",
        json={"creditor_name": "Sajja Function Hall", "amount": 2000,
              "txn_date": "2026-11-02"},
        headers=h,
    )
    refreshed = client.get(
        "/credit-master/transactions?creditor=Sajja Function Hall&kind=credit",
        headers=h,
    ).json()
    still_owed = next(r for r in refreshed if r["id"] == credit["id"])
    assert still_owed["status"] == "manual"


def test_oldest_credit_settles_first(client, auth_headers):
    h = auth_headers("Manager")
    older = client.post(
        "/credit-master/credit",
        json={"creditor_name": "Anil/Nani", "amount": 1000, "txn_date": "2026-10-01"},
        headers=h,
    ).json()
    newer = client.post(
        "/credit-master/credit",
        json={"creditor_name": "Anil/Nani", "amount": 1000, "txn_date": "2026-10-15"},
        headers=h,
    ).json()
    client.post(
        "/credit-master/remittance",
        json={"creditor_name": "Anil/Nani", "amount": 1000, "txn_date": "2026-10-20"},
        headers=h,
    )
    rows = {r["id"]: r for r in client.get(
        "/credit-master/transactions?creditor=Anil/Nani&kind=credit", headers=h
    ).json()}
    assert rows[older["id"]]["status"] == "paid"
    assert rows[newer["id"]]["status"] == "manual"


def test_clear_only_works_on_a_paid_credit(client, auth_headers):
    h = auth_headers("Manager")
    unpaid = client.post(
        "/credit-master/credit",
        json={"creditor_name": "AirTel Hari", "amount": 300, "txn_date": "2026-11-01"},
        headers=h,
    ).json()
    r = client.post("/credit-master/transactions/clear", json={"ids": [unpaid["id"]]},
                    headers=h)
    assert r.status_code == 200
    assert r.json()["cleared"] == 0

    client.post(
        "/credit-master/remittance",
        json={"creditor_name": "AirTel Hari", "amount": 300, "txn_date": "2026-11-02"},
        headers=h,
    )
    r = client.post("/credit-master/transactions/clear", json={"ids": [unpaid["id"]]},
                    headers=h)
    assert r.json()["cleared"] == 1
    row = client.get(
        "/credit-master/transactions?creditor=AirTel Hari&kind=credit", headers=h
    ).json()
    cleared = next(x for x in row if x["id"] == unpaid["id"])
    assert cleared["status"] == "cleared"
    assert cleared["cleared_by"] == "manager"


def test_summary_carries_updated_on_and_by(client, auth_headers):
    h = auth_headers("Manager")
    client.post("/credit-master/credit",
                json={"creditor_name": "AirTel Hari", "amount": 700}, headers=h)
    row = next(
        r for r in client.get("/credit-master/summary", headers=h).json()
        if r["creditor_name"] == "AirTel Hari"
    )
    assert row["last_updated_by"] == "manager"
    assert row["last_updated_at"]
