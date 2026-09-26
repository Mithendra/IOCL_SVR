"""Stock purchase paperwork for the Inventory Tracking Master.

Client, 2026-09-25: "this form should have a capability to upload the Stock
Purchase document uploaded like invoice in pdf, jpg any other supported format so
that we can see what we bought to keep track forever."

The file goes on disk under ``<data_dir>/stock-purchases``; the table holds the
record of it. There is deliberately no delete - "keep track forever" was the
word, and a purchase record that can be removed from the app is not a record.
Anything that has to go comes out of the folder by hand, and the row then reports
its file as missing rather than pretending it was never there.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from svr_backend.core.audit import record_write
from svr_backend.core.config import get_settings
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.owner_secret import check_passphrase

router = APIRouter(prefix="/stock-purchases", tags=["stock-purchases"])

# What a phone camera or a scanner actually produces, plus PDF. Deliberately a
# allow-list: an upload directory that will accept anything is a place to put a
# .exe where a later "open the invoice" click would run it.
ALLOWED: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/webp": ".webp",
    "image/tiff": ".tif",
}
MAX_BYTES = 15 * 1024 * 1024        # a scanned invoice, not a video

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
# Runs of dots, and any leading dot. Only the DISPLAY name goes through this -
# the stored path is a generated uuid and was never at risk - but "../../x.pdf"
# arriving as ".._.._x.pdf" in a filename column is the kind of thing that looks
# alarming in an audit and gets pasted somewhere that does resolve it.
_DOTS = re.compile(r"\.{2,}")


def _upload_dir() -> Path:
    d = get_settings().resolved_upload_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _row_out(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "purchase_date": r["purchase_date"],
        "item_key": r["item_key"],
        "supplier": r["supplier"],
        "amount": r["amount"],
        "note": r["note"],
        "original_name": r["original_name"],
        "content_type": r["content_type"],
        "size_bytes": r["size_bytes"],
        "uploaded_by": r["uploaded_by"],
        "uploaded_at": r["uploaded_at"],
    }


@router.get("")
def list_documents(
    date_from: str | None = None,
    date_to: str | None = None,
    item_key: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    sql = "SELECT * FROM stock_purchase_document WHERE 1 = 1"
    args: list = []
    if date_from:
        sql += " AND purchase_date >= ?"
        args.append(date_from)
    if date_to:
        sql += " AND purchase_date <= ?"
        args.append(date_to)
    if item_key:
        sql += " AND item_key = ?"
        args.append(item_key)
    sql += " ORDER BY purchase_date DESC, id DESC"
    return [_row_out(r) for r in conn.execute(sql, args)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    purchase_date: str | None = Form(default=None),
    item_key: str | None = Form(default=None),
    supplier: str | None = Form(default=None),
    amount: float | None = Form(default=None),
    note: str | None = Form(default=None),
    passphrase: str | None = Form(default=None),
    # Manager or Owner may edit, but ONLY with the Owner's passphrase, and every
    # row records who did it (client, 2026-09-25: "Manager can be updated but
    # secert password is need from the owner"). The passphrase is the authority;
    # the role is just who is at the keyboard; last_updated_by is the answer to
    # "who changed this".
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Store one invoice and the record of it.

    Owner only, behind the Owner passphrase, like everything else on this form.
    """
    check_passphrase(conn, passphrase)
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"{content_type or 'that file type'} is not accepted. Upload a PDF or a "
            "photo (JPG, PNG, HEIC, WEBP, TIFF).",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"That file is {len(data) / 1_048_576:.1f} MB; the limit is "
            f"{MAX_BYTES // 1_048_576} MB. Scan it at a lower resolution.",
        )

    original = _SAFE.sub("_", (file.filename or "invoice").strip())
    original = _DOTS.sub(".", original).lstrip("._-")[:120] or "invoice"
    # Generated, never the uploaded name: a filename is user input and must not
    # be allowed to pick a path on disk.
    stored = f"{uuid.uuid4().hex}{ALLOWED[content_type]}"
    when = purchase_date or date.today().isoformat()

    path = _upload_dir() / stored
    path.write_bytes(data)

    try:
        with transaction(conn):
            cur = conn.execute(
                "INSERT INTO stock_purchase_document (purchase_date, item_key, supplier, "
                "amount, note, original_name, stored_name, content_type, size_bytes, "
                "uploaded_by, last_updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (when, item_key or None, supplier or None, amount, note or None,
                 original, stored, content_type, len(data),
                 principal.login_name, principal.login_name),
            )
            record_write(
                conn, table="stock_purchase_document", record_id=int(cur.lastrowid),
                action="create", actor=principal.login_name,
                new={"purchase_date": when, "original_name": original,
                     "size_bytes": len(data)},
            )
    except Exception:
        # Do not leave a file behind that nothing points at.
        path.unlink(missing_ok=True)
        raise

    row = conn.execute(
        "SELECT * FROM stock_purchase_document WHERE id = ?", (int(cur.lastrowid),)
    ).fetchone()
    return _row_out(row)


@router.get("/{doc_id}/file")
def download_document(
    doc_id: int,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> FileResponse:
    row = conn.execute(
        "SELECT * FROM stock_purchase_document WHERE id = ?", (doc_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such document")
    path = _upload_dir() / row["stored_name"]
    if not path.exists():
        raise HTTPException(
            status.HTTP_410_GONE,
            f"The record is here but the file is missing from {path.parent}. "
            "It was probably moved or restored from a backup that skipped it.",
        )
    return FileResponse(
        path, media_type=row["content_type"], filename=row["original_name"]
    )
