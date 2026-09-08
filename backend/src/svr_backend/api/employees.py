"""Employee Master + Payroll Run (SDD 5.16 / 5.18 / 5.19). Manager + Owner only
(SDD 4.2) - holds sensitive bank data.

Bank account / IFSC / branch are encrypted at rest (SDD 13.3). The list endpoint
returns them masked (``****1234``); the single-employee endpoint decrypts in full
(the module is already role-gated, so every reader here is authorised).

Payroll Run: gross = days_worked x daily_wage; net = gross - advance_deduction.
The run total feeds Monthly Expenses' Bi-weekly Salary category (SDD 5.15).

Insurance (mockup sections 3-5): two yearly-premium registers (accidental /
health) plus a computed Annual Premium Summary. ``insurance_router`` below.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from svr_backend.core.audit import record_write
from svr_backend.core.crypto import decrypt, encrypt, mask
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal

router = APIRouter(prefix="/employees", tags=["employees"])
# Separate prefix so /payroll-runs/list etc. never collide with /employees/{id}.
payroll_router = APIRouter(prefix="/payroll-runs", tags=["payroll"])
insurance_router = APIRouter(prefix="/employee-insurance", tags=["employee-insurance"])

INSURANCE_KINDS = ("accidental", "health")


class EmployeeIn(BaseModel):
    name: str = Field(min_length=1)
    designation: str | None = None
    daily_wage: float = Field(ge=0, default=0)
    bank_name: str | None = None
    account_number: str | None = None
    ifsc: str | None = None
    bank_branch: str | None = None
    status: str = "Active"


class EmployeeUpdate(BaseModel):
    name: str | None = None
    designation: str | None = None
    daily_wage: float | None = Field(default=None, ge=0)
    bank_name: str | None = None
    account_number: str | None = None
    ifsc: str | None = None
    bank_branch: str | None = None
    status: str | None = None


class PayrollLineIn(BaseModel):
    employee_id: int
    days_worked: float = Field(gt=0)
    advance_deduction: float = Field(default=0, ge=0)


class PayrollRunIn(BaseModel):
    period_start: str
    period_end: str
    pay_date: str | None = None
    lines: list[PayrollLineIn]


class InsuranceIn(BaseModel):
    kind: str  # 'accidental' | 'health'
    employee_name: str = Field(min_length=1)
    provider: str | None = None
    policy_number: str | None = None
    yearly_premium: float = Field(ge=0, default=0)
    renewal_date: str | None = None


class InsuranceUpdate(BaseModel):
    employee_name: str | None = None
    provider: str | None = None
    policy_number: str | None = None
    yearly_premium: float | None = Field(default=None, ge=0)
    renewal_date: str | None = None


def _emp_public(row: sqlite3.Row, *, reveal: bool) -> dict:
    acct = decrypt(row["account_number_enc"])
    ifsc = decrypt(row["ifsc_enc"])
    branch = decrypt(row["bank_branch_enc"])
    return {
        "id": row["id"],
        "name": row["name"],
        "designation": row["designation"],
        "daily_wage": row["daily_wage"],
        "bank_name": row["bank_name"],
        "account_number": acct if reveal else mask(acct),
        "ifsc": ifsc if reveal else mask(ifsc, keep=2),
        "bank_branch": branch if reveal else (branch and "•••"),
        "status": row["status"],
        "last_updated_by": row["last_updated_by"],
        "last_updated_at": row["last_updated_at"],
    }


@router.get("")
def list_employees(
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    rows = conn.execute("SELECT * FROM employee ORDER BY status, name").fetchall()
    return [_emp_public(r, reveal=False) for r in rows]


@router.get("/{employee_id}")
def get_employee(
    employee_id: int,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute("SELECT * FROM employee WHERE id = ?", (employee_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    return _emp_public(row, reveal=True)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_employee(
    body: EmployeeIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    if body.status not in ("Active", "Inactive"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "status must be Active/Inactive")
    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO employee
                (name, designation, daily_wage, bank_name,
                 account_number_enc, ifsc_enc, bank_branch_enc, status, last_updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.name, body.designation, body.daily_wage, body.bank_name,
                encrypt(body.account_number), encrypt(body.ifsc), encrypt(body.bank_branch),
                body.status, principal.login_name,
            ),
        )
        record_write(
            conn, table="employee", record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"name": body.name, "designation": body.designation, "status": body.status},
        )
    row = conn.execute("SELECT * FROM employee WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _emp_public(row, reveal=True)


@router.put("/{employee_id}")
def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute("SELECT * FROM employee WHERE id = ?", (employee_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")

    plain = {
        "name": body.name,
        "designation": body.designation,
        "daily_wage": body.daily_wage,
        "bank_name": body.bank_name,
        "status": body.status,
    }
    enc = {
        "account_number_enc": (
            encrypt(body.account_number) if body.account_number is not None else None
        ),
        "ifsc_enc": encrypt(body.ifsc) if body.ifsc is not None else None,
        "bank_branch_enc": encrypt(body.bank_branch) if body.bank_branch is not None else None,
    }
    updates = {k: v for k, v in {**plain, **enc}.items() if v is not None}
    if not updates:
        return _emp_public(row, reveal=True)

    set_sql = ", ".join(f"{k} = ?" for k in updates)
    with transaction(conn):
        conn.execute(
            f"UPDATE employee SET {set_sql}, last_updated_by = ?, "
            f"last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (*updates.values(), principal.login_name, employee_id),
        )
        record_write(
            conn, table="employee", record_id=employee_id, action="update",
            actor=principal.login_name,
            # never log the ciphertext or plaintext of sensitive fields
            new={k: ("<updated>" if k.endswith("_enc") else v) for k, v in updates.items()},
        )
    updated = conn.execute("SELECT * FROM employee WHERE id = ?", (employee_id,)).fetchone()
    return _emp_public(updated, reveal=True)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    employee_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute("SELECT * FROM employee WHERE id = ?", (employee_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    with transaction(conn):
        conn.execute("DELETE FROM employee WHERE id = ?", (employee_id,))
        record_write(
            conn, table="employee", record_id=employee_id, action="delete",
            actor=principal.login_name, old={"name": row["name"]},
        )


# --------------------------------------------------------------------- payroll run


@payroll_router.get("/list")
def list_payroll_runs(
    start: str | None = None,
    end: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    clauses, params = [], []
    if start:
        clauses.append("pay_date >= ?")
        params.append(start)
    if end:
        clauses.append("pay_date <= ?")
        params.append(end)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM payroll_run{where} ORDER BY pay_date DESC, id DESC", params
    ).fetchall()
    return [dict(r) for r in rows]


@payroll_router.get("/{run_id}")
def get_payroll_run(
    run_id: int,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    run = conn.execute("SELECT * FROM payroll_run WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payroll run not found")
    lines = conn.execute(
        "SELECT * FROM payroll_run_line WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    return {**dict(run), "lines": [dict(x) for x in lines]}


@payroll_router.post("", status_code=status.HTTP_201_CREATED)
def create_payroll_run(
    body: PayrollRunIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    if not body.lines:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At least one line is required")

    computed = []
    for line in body.lines:
        emp = conn.execute(
            "SELECT id, name, daily_wage FROM employee WHERE id = ?", (line.employee_id,)
        ).fetchone()
        if emp is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown employee_id {line.employee_id}"
            )
        gross = round(line.days_worked * emp["daily_wage"], 4)
        net = round(gross - line.advance_deduction, 4)
        computed.append(
            {
                "employee_id": emp["id"],
                "employee_name": emp["name"],
                "days_worked": line.days_worked,
                "daily_wage": emp["daily_wage"],
                "gross_salary": gross,
                "advance_deduction": line.advance_deduction,
                "net_pay": net,
            }
        )

    gross_total = round(sum(c["gross_salary"] for c in computed), 4)
    advance_total = round(sum(c["advance_deduction"] for c in computed), 4)
    net_total = round(sum(c["net_pay"] for c in computed), 4)
    pay_date = body.pay_date or date.today().isoformat()

    with transaction(conn):
        run_cur = conn.execute(
            """
            INSERT INTO payroll_run
                (period_start, period_end, pay_date,
                 gross_total, advance_total, net_total, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (body.period_start, body.period_end, pay_date, gross_total, advance_total,
             net_total, principal.login_name),
        )
        run_id = run_cur.lastrowid
        for c in computed:
            conn.execute(
                """
                INSERT INTO payroll_run_line
                    (run_id, employee_id, employee_name, days_worked, daily_wage,
                     gross_salary, advance_deduction, net_pay)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, c["employee_id"], c["employee_name"], c["days_worked"],
                 c["daily_wage"], c["gross_salary"], c["advance_deduction"], c["net_pay"]),
            )
        record_write(
            conn, table="payroll_run", record_id=run_id, action="create",
            actor=principal.login_name,
            new={"pay_date": pay_date, "net_total": net_total, "lines": len(computed)},
        )
    return get_payroll_run(run_id, principal, conn)


# ------------------------------------------------------ insurance (mockup 3-5)


_INS_TABLE = "employee_insurance"


def _insurance_public(row: sqlite3.Row) -> dict:
    return dict(row)


def _resolve_employee_id(conn: sqlite3.Connection, name: str) -> int | None:
    hit = conn.execute(
        "SELECT id FROM employee WHERE name = ? COLLATE NOCASE", (name.strip(),)
    ).fetchone()
    return hit["id"] if hit else None


@insurance_router.get("")
def list_insurance(
    kind: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    if kind is not None and kind not in INSURANCE_KINDS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"kind must be one of {INSURANCE_KINDS}"
        )
    clause = " WHERE kind = ?" if kind else ""
    params = [kind] if kind else []
    rows = conn.execute(
        f"SELECT * FROM {_INS_TABLE}{clause} ORDER BY kind, employee_name, id", params
    ).fetchall()
    return [_insurance_public(r) for r in rows]


@insurance_router.get("/summary")
def insurance_summary(
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Mockup section 5 - Annual Premium Summary."""
    rows = conn.execute(
        f"SELECT kind, COALESCE(SUM(yearly_premium), 0) AS total FROM {_INS_TABLE} GROUP BY kind"
    ).fetchall()
    by_kind = {r["kind"]: round(r["total"], 4) for r in rows}
    accidental = by_kind.get("accidental", 0.0)
    health = by_kind.get("health", 0.0)
    return {
        "accidental_total": accidental,
        "health_total": health,
        "grand_total": round(accidental + health, 4),
    }


@insurance_router.post("", status_code=status.HTTP_201_CREATED)
def create_insurance(
    body: InsuranceIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    if body.kind not in INSURANCE_KINDS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"kind must be one of {INSURANCE_KINDS}"
        )
    emp_id = _resolve_employee_id(conn, body.employee_name)
    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {_INS_TABLE}
                (kind, employee_id, employee_name, provider, policy_number,
                 yearly_premium, renewal_date, last_updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.kind, emp_id, body.employee_name.strip(), body.provider,
                body.policy_number, body.yearly_premium, body.renewal_date,
                principal.login_name,
            ),
        )
        record_write(
            conn, table=_INS_TABLE, record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"kind": body.kind, "employee_name": body.employee_name,
                 "yearly_premium": body.yearly_premium},
        )
    row = conn.execute(f"SELECT * FROM {_INS_TABLE} WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _insurance_public(row)


@insurance_router.put("/{insurance_id}")
def update_insurance(
    insurance_id: int,
    body: InsuranceUpdate,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute(
        f"SELECT * FROM {_INS_TABLE} WHERE id = ?", (insurance_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Insurance record not found")

    fields = {
        "employee_name": body.employee_name.strip() if body.employee_name else None,
        "provider": body.provider,
        "policy_number": body.policy_number,
        "yearly_premium": body.yearly_premium,
        "renewal_date": body.renewal_date,
    }
    updates = {k: v for k, v in fields.items() if v is not None}
    if "employee_name" in updates:
        updates["employee_id"] = _resolve_employee_id(conn, updates["employee_name"])
    if not updates:
        return _insurance_public(row)

    set_sql = ", ".join(f"{k} = ?" for k in updates)
    with transaction(conn):
        conn.execute(
            f"UPDATE {_INS_TABLE} SET {set_sql}, last_updated_by = ?, "
            f"last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (*updates.values(), principal.login_name, insurance_id),
        )
        record_write(
            conn, table=_INS_TABLE, record_id=insurance_id, action="update",
            actor=principal.login_name,
            old={k: row[k] for k in updates}, new=updates,
        )
    updated = conn.execute(
        f"SELECT * FROM {_INS_TABLE} WHERE id = ?", (insurance_id,)
    ).fetchone()
    return _insurance_public(updated)


@insurance_router.delete("/{insurance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_insurance(
    insurance_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute(
        f"SELECT * FROM {_INS_TABLE} WHERE id = ?", (insurance_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Insurance record not found")
    with transaction(conn):
        conn.execute(f"DELETE FROM {_INS_TABLE} WHERE id = ?", (insurance_id,))
        record_write(
            conn, table=_INS_TABLE, record_id=insurance_id, action="delete",
            actor=principal.login_name,
            old={"kind": row["kind"], "employee_name": row["employee_name"]},
        )
