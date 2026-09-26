"""Oil Sale(s) item list - add, rename, reorder, retire (client, 2026-09-13).

The list used to be a Python tuple, so selling a new product meant a code change
and a release. It is data now (``oil_item``, migration 0023) and the station owns
it.

Adding an item creates three things together, because an oil row is useless
without all three: the item itself, a Rate Master row (its Oil Rate), and an
Inventory Tracking row (its Opening Stock). That is exactly what migration 0017
had to do by hand for the two rows added on 2026-09-12.

Removing an item **deactivates** it. Days already recorded name it in their own
saved rows; deleting it would leave those pointing at nothing and silently change
historical totals. A retired item disappears from the entry form but still
resolves when an old record is read back, and can be reactivated.

Access: Manager and Owner. Sales enters the day's figures and does not decide what
the station sells.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from svr_backend import oil_items
from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.owner_secret import check_passphrase

router = APIRouter(prefix="/oil-items", tags=["oil-items"])

# A brand-new product has NO rate history to protect, so its first rate applies to
# every date. Filing it under the seed's own 2026-08-11 instead looked tidier and
# was wrong: latest_effective_rates() resolves by date, so a day earlier than that
# found no rate at all and the row priced itself at zero - silently, which is the
# exact failure mode migration 0015 was written to undo.
#
# Only the FIRST rate is back-dated like this. When the Owner changes it later,
# Rate Master files that under its own effective date and older days keep the
# figure that actually applied.
_RATE_EFFECTIVE_FROM = "2000-01-01"


class OilItemIn(BaseModel):
    passphrase: str | None = None
    label: str = Field(min_length=1, max_length=120)
    unit: str = Field(default="pcs", max_length=16)
    rate: float = Field(default=0.0, ge=0)
    opening_stock: float = Field(default=0.0, ge=0)
    reorder_level: float = Field(default=0.0, ge=0)


class OilItemPatch(BaseModel):
    passphrase: str | None = None
    label: str | None = Field(default=None, min_length=1, max_length=120)
    unit: str | None = Field(default=None, max_length=16)
    sort_order: int | None = None
    active: bool | None = None


def _out(item: oil_items.OilItem) -> dict:
    return {
        "item_key": item.key,
        "label": item.label,
        "unit": item.unit,
        "sort_order": item.sort_order,
        "active": item.active,
    }


@router.get("")
def list_oil_items(
    include_retired: bool = False,
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """Sales reads it too - it is what the Daily Sales Entry form is built from."""
    items = oil_items.all_items(conn) if include_retired else oil_items.active_items(conn)
    return [_out(i) for i in items]


@router.get("/aliases")
def list_aliases(
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, str]:
    """Every label the station has ever used -> the product it names.

    The renderer needs this to reopen a saved entry: each stored row carries the
    label it was sold under, and matching by position instead would put a row back
    against whatever item now sits there.
    """
    return oil_items.label_to_key(conn)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_oil_item(
    body: OilItemIn,
    # Manager or Owner may edit, but ONLY with the Owner's passphrase, and every
    # row records who did it (client, 2026-09-25: "Manager can be updated but
    # secert password is need from the owner"). The passphrase is the authority;
    # the role is just who is at the keyboard; last_updated_by is the answer to
    # "who changed this".
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    check_passphrase(conn, body.passphrase)
    label = body.label.strip()

    # A label the station has used before names a product that already exists -
    # reactivate it rather than minting a second key for the same thing, which
    # would split its rate history and its stock in two.
    existing_key = oil_items.label_to_key(conn).get(label)
    if existing_key is not None:
        row = conn.execute(
            "SELECT active, label FROM oil_item WHERE item_key = ?", (existing_key,)
        ).fetchone()
        if row is not None and row["active"]:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"'{label}' is already on the Oil Sale(s) list.",
            )
        with transaction(conn):
            conn.execute(
                "UPDATE oil_item SET active = 1, sort_order = ?, "
                "last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE item_key = ?",
                (oil_items.next_sort_order(conn), principal.login_name, existing_key),
            )
            record_write(
                conn, table="oil_item", record_id=existing_key, action="update",
                actor=principal.login_name,
                new={"active": 1, "label": label, "note": "reactivated an existing product"},
            )
        return _out(next(i for i in oil_items.all_items(conn) if i.key == existing_key))

    key = oil_items.next_key(conn)
    with transaction(conn):
        conn.execute(
            "INSERT INTO oil_item (item_key, label, unit, sort_order, active, last_updated_by) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (key, label, body.unit, oil_items.next_sort_order(conn), principal.login_name),
        )
        conn.execute("INSERT INTO oil_item_alias (label, item_key) VALUES (?, ?)", (label, key))
        # Its Oil Rate. rate_master is append-only by effective_date; buy_rate is
        # NULL for oils (no buy/sell split - SDD session log 49).
        conn.execute(
            "INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, "
            "effective_date, updated_by) VALUES (?, ?, NULL, ?, ?, ?)",
            (key, label, body.rate, _RATE_EFFECTIVE_FROM, principal.login_name),
        )
        # Its tracked stock, so Opening Stock has somewhere to come from.
        conn.execute(
            "INSERT INTO inventory_item (item_key, item_label, unit, on_hand, reorder_level, "
            "last_updated_by) VALUES (?, ?, ?, ?, ?, ?)",
            (key, label, body.unit, body.opening_stock, body.reorder_level,
             principal.login_name),
        )
        record_write(
            conn, table="oil_item", record_id=key, action="create",
            actor=principal.login_name,
            new={"label": label, "unit": body.unit, "rate": body.rate,
                   "opening_stock": body.opening_stock},
        )
    return _out(next(i for i in oil_items.all_items(conn) if i.key == key))


@router.patch("/{item_key}")
def update_oil_item(
    item_key: str,
    body: OilItemPatch,
    # Manager or Owner may edit, but ONLY with the Owner's passphrase, and every
    # row records who did it (client, 2026-09-25: "Manager can be updated but
    # secert password is need from the owner"). The passphrase is the authority;
    # the role is just who is at the keyboard; last_updated_by is the answer to
    # "who changed this".
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    check_passphrase(conn, body.passphrase)
    row = conn.execute("SELECT * FROM oil_item WHERE item_key = ?", (item_key,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No oil item '{item_key}'.")

    before = {"label": row["label"], "unit": row["unit"],
              "sort_order": row["sort_order"], "active": row["active"]}
    label = body.label.strip() if body.label is not None else row["label"]
    if label != row["label"]:
        clash = oil_items.label_to_key(conn).get(label)
        if clash is not None and clash != item_key:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"'{label}' already names a different oil item ({clash}).",
            )

    unit = body.unit if body.unit is not None else row["unit"]
    sort_order = body.sort_order if body.sort_order is not None else row["sort_order"]
    active = int(body.active) if body.active is not None else row["active"]

    with transaction(conn):
        conn.execute(
            "UPDATE oil_item SET label = ?, unit = ?, sort_order = ?, active = ?, "
            "last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE item_key = ?",
            (label, unit, sort_order, active, principal.login_name, item_key),
        )
        if label != row["label"]:
            # Keep the OLD label resolving to this product. A record saved under it
            # must still read back as the same item - that is what carried oil1,
            # oil4 and oil5 through the 2026-09-12 relabel.
            conn.execute(
                "INSERT OR IGNORE INTO oil_item_alias (label, item_key) VALUES (?, ?)",
                (label, item_key),
            )
            # Inventory shows the current name; its stock is untouched, because the
            # tins on the shelf did not move because the row was renamed.
            conn.execute(
                "UPDATE inventory_item SET item_label = ?, last_updated_by = ?, "
                "last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE item_key = ?",
                (label, principal.login_name, item_key),
            )
        record_write(
            conn, table="oil_item", record_id=item_key, action="update",
            actor=principal.login_name, old=before,
            new={"label": label, "unit": unit, "sort_order": sort_order, "active": active},
        )
    return _out(next(i for i in oil_items.all_items(conn) if i.key == item_key))


class RetireIn(BaseModel):
    passphrase: str | None = None


# POST, not DELETE. Retiring is a soft action - the row stays so past days keep
# their value - and it now carries the Owner passphrase in its body, which DELETE
# is a poor fit for: several HTTP clients refuse to send a body on a DELETE at
# all (the test client among them) and intermediaries may drop it.
@router.post("/{item_key}/retire")
def retire_oil_item(
    item_key: str,
    body: RetireIn,
    # Manager or Owner may edit, but ONLY with the Owner's passphrase, and every
    # row records who did it (client, 2026-09-25: "Manager can be updated but
    # secert password is need from the owner"). The passphrase is the authority;
    # the role is just who is at the keyboard; last_updated_by is the answer to
    # "who changed this".
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Retire an item. Never a hard delete - see the module docstring.

    The last active item cannot be retired: Oil Sale(s) with no rows at all is a
    broken form, not an empty one, and there would be no way back through the UI.
    """
    check_passphrase(conn, body.passphrase)
    row = conn.execute("SELECT * FROM oil_item WHERE item_key = ?", (item_key,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No oil item '{item_key}'.")
    if not row["active"]:
        return _out(next(i for i in oil_items.all_items(conn) if i.key == item_key))
    if len(oil_items.active_items(conn)) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This is the last Oil Sale(s) row - add another before retiring it.",
        )

    with transaction(conn):
        conn.execute(
            "UPDATE oil_item SET active = 0, last_updated_by = ?, "
            "last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE item_key = ?",
            (principal.login_name, item_key),
        )
        record_write(
            conn, table="oil_item", record_id=item_key, action="update",
            actor=principal.login_name, old={"active": 1},
            new={"active": 0, "note": "retired - kept so past records still resolve"},
        )
    return _out(next(i for i in oil_items.all_items(conn) if i.key == item_key))
