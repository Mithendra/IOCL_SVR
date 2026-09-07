"""`svr-backend create-user` - the only way to make the first account on a fresh
production install (installer runs `migrate` with no demo seed)."""

from __future__ import annotations

from svr_backend.cli import run_create_user
from svr_backend.core.db import connect


def _user(db_path, login):
    c = connect(db_path)
    try:
        return c.execute("SELECT * FROM users WHERE login_name = ?", (login,)).fetchone()
    finally:
        c.close()


def test_creates_owner_with_hashed_password(conn, db_path):
    rc = run_create_user(
        ["--name", "R Owner", "--login", "rowner", "--role", "Owner",
         "--password", "s3cret-pass-9", "--db", str(db_path)]
    )
    assert rc == 0
    row = _user(db_path, "rowner")
    assert row is not None
    assert row["role"] == "Owner"
    assert row["status"] == "Active"
    assert row["last_updated_by"] == "bootstrap"
    # never store the plaintext; argon2id hashes start with "$argon2"
    assert row["password_hash"].startswith("$argon2")
    assert "s3cret-pass-9" not in row["password_hash"]


def test_audit_row_written(conn, db_path):
    run_create_user(
        ["--name", "A Owner", "--login", "aowner", "--password", "another-pass-1", "--db", str(db_path)]
    )
    c = connect(db_path)
    try:
        a = c.execute(
            "SELECT * FROM audit_log WHERE table_name='users' AND action='create' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        c.close()
    assert a is not None
    assert a["actor"] == "bootstrap"
    assert "aowner" in a["new_value"]


def test_default_role_is_owner_and_login_derived(conn, db_path):
    rc = run_create_user(["--name", "Meera Nair", "--password", "derived-pass-7", "--db", str(db_path)])
    assert rc == 0
    assert _user(db_path, "mnair")["role"] == "Owner"


def test_duplicate_login_rejected(conn, db_path):
    args = ["--name", "R Owner", "--login", "dup", "--password", "first-pass-11", "--db", str(db_path)]
    assert run_create_user(args) == 0
    assert run_create_user(args) == 1  # second call: login already exists
    c = connect(db_path)
    try:
        n = c.execute("SELECT COUNT(*) c FROM users WHERE login_name='dup'").fetchone()["c"]
    finally:
        c.close()
    assert n == 1


def test_short_password_rejected(conn, db_path):
    rc = run_create_user(["--name", "X Y", "--login", "xy", "--password", "short", "--db", str(db_path)])
    assert rc == 2
    assert _user(db_path, "xy") is None


def test_invalid_role_rejected(conn, db_path):
    import pytest

    with pytest.raises(SystemExit):  # argparse choices=
        run_create_user(
            ["--name", "X Y", "--login", "xy", "--role", "Admin", "--password", "whatever-8", "--db", str(db_path)]
        )
