"""Credit / Remittance Master (SDD 5.17). Manager + Owner only (SDD 4.2).

Section 1 (New Credit) and Section 2 (Remittance) both write ``credit_transaction``
rows; Section 3 (Creditor Balance Summary) groups them by ``creditor_name`` -
``outstanding = total_credit - total_remitted``, pending (largest outstanding)
first.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from svr_backend import posting
from svr_backend.core.audit import record_write
from svr_backend.core.config import get_settings
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal

router = APIRouter(prefix="/credit-master", tags=["credit-master"])

TABLE = "credit_transaction"

# Same allow-list as Stock Purchases (api/stock_purchases.py) - an old
# agreement, a handwritten ledger scan, a PDF statement.
_ALLOWED_DOCS: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/webp": ".webp",
    "image/tiff": ".tif",
}
_MAX_DOC_BYTES = 15 * 1024 * 1024
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_DOTS = re.compile(r"\.{2,}")


def _doc_dir() -> Path:
    d = get_settings().resolved_creditor_documents_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


class CreditIn(BaseModel):
    creditor_name: str = Field(min_length=1)
    phone: str | None = None
    fuel_type: str | None = None
    ltrs: float | None = Field(default=None, gt=0)
    rate: float | None = Field(default=None, gt=0)
    amount: float | None = Field(default=None, gt=0)
    txn_date: str | None = None
    given_by: str | None = None
    payment_mode: str | None = None
    note: str | None = None


class RemittanceIn(BaseModel):
    creditor_name: str = Field(min_length=1)
    amount: float = Field(gt=0)
    txn_date: str | None = None
    source: str | None = None
    pump_sales_man: str | None = None
    payment_mode: str | None = None
    payment: str | None = None
    remittance_entered: str | None = None
    collected_by: str | None = None
    given_on_date: str | None = None
    note: str | None = None


class CreditorIn(BaseModel):
    name: str = Field(min_length=1)
    phone: str | None = None
    credit_type: str = Field(default="new", pattern="^(old|new)$")
    note: str | None = None


class CreditorPatch(BaseModel):
    phone: str | None = None
    credit_type: str | None = Field(default=None, pattern="^(old|new)$")
    note: str | None = None


def _row(r: sqlite3.Row) -> dict:
    return {k: r[k] for k in r.keys()}


@router.get("/transactions")
def list_transactions(
    creditor: str | None = None,
    kind: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    clauses, params = [], []
    if creditor:
        clauses.append("creditor_name = ?")
        params.append(creditor)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if date_from:
        clauses.append("txn_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("txn_date <= ?")
        params.append(date_to)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM {TABLE}{where} ORDER BY txn_date DESC, id DESC", params
    ).fetchall()
    return [_row(r) for r in rows]


@router.get("/summary")
def creditor_summary(
    date_from: str | None = None,
    date_to: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """Every name from EITHER source, not just `creditor` - a name posted
    straight from Daily Trial Balance (posting.py post_line()) has a
    credit_transaction row but was never "+ Added" here, and dropping it from
    the summary would be a real regression, not a cosmetic one: it is the
    balance the client actually asked this section to track. "+ Add Creditor"
    (client, 2026-09-27) is for the OTHER direction - a name that exists here
    before its first transaction, so it shows at zero rather than not at all.

    `date_from`/`date_to` (client: "Search Button for a given Date range") is
    a transaction search: with no range, every known creditor shows (including
    a zero-transaction one from "+ Add Creditor"), but a range narrows the
    NAME LIST ITSELF to creditors with a transaction inside it - a creditor
    with nothing there shouldn't appear at zero, it shouldn't appear at all,
    or "Search" would return everyone every time."""
    txn_where = "1 = 1"
    args: list = []
    if date_from:
        txn_where += " AND t.txn_date >= ?"
        args.append(date_from)
    if date_to:
        txn_where += " AND t.txn_date <= ?"
        args.append(date_to)
    if date_from or date_to:
        names_cte = f"SELECT DISTINCT creditor_name AS name FROM {TABLE} t WHERE {txn_where}"
        names_args = list(args)
    else:
        names_cte = f"SELECT name FROM creditor UNION SELECT DISTINCT creditor_name FROM {TABLE}"
        names_args = []
    rows = conn.execute(
        f"""
        WITH names AS (
            {names_cte}
        )
        SELECT
            n.name AS creditor_name,
            COALESCE(c.phone, (SELECT phone FROM {TABLE} t2
             WHERE t2.creditor_name = n.name AND t2.phone IS NOT NULL
             ORDER BY id DESC LIMIT 1)) AS phone,
            COALESCE(c.credit_type, 'new') AS credit_type, c.note,
            COALESCE(SUM(CASE WHEN t.kind = 'credit' THEN t.amount END), 0)     AS total_credit,
            COALESCE(SUM(CASE WHEN t.kind = 'remittance' THEN t.amount END), 0) AS total_remitted,
            -- Most recent touch across EITHER the creditor record itself or
            -- any of their transactions - a rollup row has no one save of
            -- its own, so "Updated On/By" here means "the last thing that
            -- moved this creditor's balance or notes" (client, 2026-09-27:
            -- "CM must have Updated On Updated By... critical").
            (SELECT x.last_updated_by FROM (
                SELECT last_updated_by, last_updated_at FROM {TABLE} t
                 WHERE t.creditor_name = n.name AND {txn_where}
                UNION ALL
                SELECT last_updated_by, last_updated_at FROM creditor WHERE name = n.name
             ) x ORDER BY x.last_updated_at DESC LIMIT 1) AS last_updated_by,
            (SELECT x.last_updated_at FROM (
                SELECT last_updated_by, last_updated_at FROM {TABLE} t
                 WHERE t.creditor_name = n.name AND {txn_where}
                UNION ALL
                SELECT last_updated_by, last_updated_at FROM creditor WHERE name = n.name
             ) x ORDER BY x.last_updated_at DESC LIMIT 1) AS last_updated_at
        FROM names n
        LEFT JOIN creditor c ON c.name = n.name
        LEFT JOIN {TABLE} t ON t.creditor_name = n.name AND {txn_where}
        GROUP BY n.name
        ORDER BY (COALESCE(SUM(CASE WHEN t.kind = 'credit' THEN t.amount END), 0)
                  - COALESCE(SUM(CASE WHEN t.kind = 'remittance' THEN t.amount END), 0)) DESC,
                 n.name
        """,
        names_args + args + args + args,
    ).fetchall()
    out = []
    for r in rows:
        outstanding = round(r["total_credit"] - r["total_remitted"], 4)
        out.append({
            "creditor_name": r["creditor_name"], "phone": r["phone"],
            "credit_type": r["credit_type"], "note": r["note"],
            "total_credit": round(r["total_credit"], 4),
            "total_remitted": round(r["total_remitted"], 4),
            "outstanding": outstanding,
            "last_updated_by": r["last_updated_by"],
            "last_updated_at": r["last_updated_at"],
        })
    return out


def _creditor_row(r: sqlite3.Row) -> dict:
    return {
        "name": r["name"], "phone": r["phone"], "credit_type": r["credit_type"],
        "note": r["note"], "created_by": r["created_by"],
        "last_updated_by": r["last_updated_by"], "last_updated_at": r["last_updated_at"],
        "created_at": r["created_at"],
    }


def _add_to_option_lists(conn: sqlite3.Connection, name: str, actor: str) -> None:
    """The same name Daily Sales Entry's Sections 5/6 offer - added there too,
    so a creditor taken on here doesn't need typing a second time at the pump.
    Silently skipped if already present; this is a convenience, not the
    system of record for the option lists."""
    for list_key in ("customers", "creditors"):
        exists = conn.execute(
            "SELECT 1 FROM trial_balance_option WHERE list_key = ? AND value = ?",
            (list_key, name),
        ).fetchone()
        if exists:
            continue
        nxt = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM trial_balance_option "
            "WHERE list_key = ?", (list_key,),
        ).fetchone()["n"]
        conn.execute(
            "INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) "
            "VALUES (?, ?, ?, ?)",
            (list_key, name, nxt, actor),
        )


@router.get("/creditors")
def list_creditors(
    creditor: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """Every creditor on file, whether or not they have a transaction yet."""
    sql = "SELECT * FROM creditor"
    args: list = []
    if creditor:
        sql += " WHERE name = ?"
        args.append(creditor)
    sql += " ORDER BY name"
    return [_creditor_row(r) for r in conn.execute(sql, args)]


@router.post("/creditors", status_code=status.HTTP_201_CREATED)
def add_creditor(
    body: CreditorIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    name = " ".join(body.name.split())
    existing = conn.execute("SELECT 1 FROM creditor WHERE name = ?", (name,)).fetchone()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f'"{name}" is already on file')
    with transaction(conn):
        conn.execute(
            "INSERT INTO creditor (name, phone, credit_type, note, created_by, "
            "last_updated_by) VALUES (?, ?, ?, ?, ?, ?)",
            (name, body.phone, body.credit_type, body.note,
             principal.login_name, principal.login_name),
        )
        _add_to_option_lists(conn, name, principal.login_name)
        record_write(conn, table="creditor", record_id=name, action="create",
                     actor=principal.login_name, new={"name": name})
    return _creditor_row(conn.execute("SELECT * FROM creditor WHERE name = ?", (name,)).fetchone())


@router.patch("/creditors/{name}")
def update_creditor(
    name: str,
    body: CreditorPatch,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute("SELECT * FROM creditor WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such creditor")
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return _creditor_row(row)
    with transaction(conn):
        conn.execute(
            f"UPDATE creditor SET {', '.join(f'{k} = ?' for k in fields)}, "
            "last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE name = ?",
            (*fields.values(), principal.login_name, name),
        )
        record_write(conn, table="creditor", record_id=name, action="update",
                     actor=principal.login_name, new=fields)
    return _creditor_row(conn.execute("SELECT * FROM creditor WHERE name = ?", (name,)).fetchone())


@router.post("/credit", status_code=status.HTTP_201_CREATED)
def add_credit(
    body: CreditIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    if body.ltrs is not None and body.rate is not None:
        amount = round(body.ltrs * body.rate, 4)
    elif body.amount is not None:
        amount = body.amount
    else:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Provide either (ltrs and rate) or an explicit amount",
        )
    when = body.txn_date or date.today().isoformat()
    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {TABLE}
                (kind, creditor_name, phone, fuel_type, ltrs, rate, amount, txn_date,
                 pump_sales_man, payment_mode, note, status, created_by, last_updated_by)
            VALUES ('credit', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
            """,
            (
                body.creditor_name, body.phone, body.fuel_type, body.ltrs, body.rate,
                amount, when, body.given_by, body.payment_mode, body.note,
                principal.login_name, principal.login_name,
            ),
        )
        record_write(
            conn, table=TABLE, record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"kind": "credit", "creditor_name": body.creditor_name, "amount": amount},
        )
    return _row(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.post("/remittance", status_code=status.HTTP_201_CREATED)
def add_remittance(
    body: RemittanceIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    when = body.txn_date or date.today().isoformat()
    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {TABLE}
                (kind, creditor_name, amount, txn_date, source, pump_sales_man,
                 payment_mode, payment, remittance_entered, collected_by, given_on_date,
                 note, status, created_by, last_updated_by)
            VALUES ('remittance', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
            """,
            (
                body.creditor_name, body.amount, when, body.source, body.pump_sales_man,
                body.payment_mode, body.payment, body.remittance_entered,
                body.collected_by, body.given_on_date,
                body.note, principal.login_name, principal.login_name,
            ),
        )
        record_write(
            conn, table=TABLE, record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"kind": "remittance", "creditor_name": body.creditor_name, "amount": body.amount},
        )
        # Settle immediately - a Manager typing this straight onto the ledger
        # IS the confirmation the payment happened (client, 2026-09-27: "who
        # to clear the entry in DT" - either this path or Trial Balance's own
        # Post pipeline reaches the same settle_credit_transactions()).
        posting.settle_credit_transactions(
            conn, body.creditor_name, body.amount, principal.login_name
        )
    return _row(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/transactions/{txn_id}")
def update_transaction_note(
    txn_id: int,
    body: dict,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Notes are the one thing worth editing on a row that arrived already
    posted (client, 2026-09-27: "Notes text Column") - a Manager annotating
    why a credit is unusual, after the fact, without touching anything the
    posting pipeline itself is responsible for."""
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (txn_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    note = body.get("note")
    with transaction(conn):
        conn.execute(
            f"UPDATE {TABLE} SET note = ?, last_updated_by = ?, "
            "last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (note, principal.login_name, txn_id),
        )
        record_write(conn, table=TABLE, record_id=txn_id, action="update",
                     actor=principal.login_name, new={"note": note})
    return _row(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (txn_id,)).fetchone())


class ClearIn(BaseModel):
    ids: list[int] = Field(min_length=1)


@router.post("/transactions/clear")
def clear_transactions(
    body: ClearIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Month-end tidy-up, reachable straight from this screen (client,
    2026-09-27) - only a row already 'paid' actually clears; anything else
    in `ids` is silently left alone, same gate as Trial Balance's own
    Clear buttons."""
    with transaction(conn):
        cleared = posting.clear_credit_transactions(conn, body.ids, principal.login_name)
    return {"cleared": cleared}


@router.delete("/transactions/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    txn_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (txn_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    with transaction(conn):
        conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (txn_id,))
        record_write(
            conn, table=TABLE, record_id=txn_id, action="delete",
            actor=principal.login_name,
            old={
                "kind": row["kind"],
                "creditor_name": row["creditor_name"],
                "amount": row["amount"],
            },
        )


# --------------------------------------------------------- creditor documents
#
# Same pattern as Stock Purchases (api/stock_purchases.py): file on disk,
# generated stored_name, kept indefinitely, no delete endpoint - "keep track
# forever" applies here just as much as it does to a purchase invoice.

def _doc_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "creditor_name": r["creditor_name"], "note": r["note"],
        "original_name": r["original_name"], "content_type": r["content_type"],
        "size_bytes": r["size_bytes"], "uploaded_by": r["uploaded_by"],
        "uploaded_at": r["uploaded_at"],
    }


@router.get("/creditors/{name}/documents")
def list_creditor_documents(
    name: str,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM creditor_document WHERE creditor_name = ? "
        "ORDER BY uploaded_at DESC, id DESC", (name,),
    ).fetchall()
    return [_doc_row(r) for r in rows]


@router.post("/creditors/{name}/documents", status_code=status.HTTP_201_CREATED)
async def upload_creditor_document(
    name: str,
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    if conn.execute("SELECT 1 FROM creditor WHERE name = ?", (name,)).fetchone() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such creditor")

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_DOCS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"{content_type or 'that file type'} is not accepted. Upload a PDF or a "
            "photo (JPG, PNG, HEIC, WEBP, TIFF).",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is empty.")
    if len(data) > _MAX_DOC_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"That file is {len(data) / 1_048_576:.1f} MB; the limit is "
            f"{_MAX_DOC_BYTES // 1_048_576} MB.",
        )

    original = _SAFE.sub("_", (file.filename or "document").strip())
    original = _DOTS.sub(".", original).lstrip("._-")[:120] or "document"
    stored = f"{uuid.uuid4().hex}{_ALLOWED_DOCS[content_type]}"
    path = _doc_dir() / stored
    path.write_bytes(data)

    try:
        with transaction(conn):
            cur = conn.execute(
                "INSERT INTO creditor_document (creditor_name, note, original_name, "
                "stored_name, content_type, size_bytes, uploaded_by, last_updated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, note or None, original, stored, content_type, len(data),
                 principal.login_name, principal.login_name),
            )
            record_write(
                conn, table="creditor_document", record_id=int(cur.lastrowid),
                action="create", actor=principal.login_name,
                new={"creditor_name": name, "original_name": original, "size_bytes": len(data)},
            )
    except Exception:
        path.unlink(missing_ok=True)
        raise

    row = conn.execute(
        "SELECT * FROM creditor_document WHERE id = ?", (int(cur.lastrowid),)
    ).fetchone()
    return _doc_row(row)


@router.get("/creditors/{name}/documents/{doc_id}/file")
def download_creditor_document(
    name: str,
    doc_id: int,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> FileResponse:
    row = conn.execute(
        "SELECT * FROM creditor_document WHERE id = ? AND creditor_name = ?",
        (doc_id, name),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such document")
    path = _doc_dir() / row["stored_name"]
    if not path.exists():
        raise HTTPException(
            status.HTTP_410_GONE,
            f"The record is here but the file is missing from {path.parent}.",
        )
    return FileResponse(path, media_type=row["content_type"], filename=row["original_name"])
