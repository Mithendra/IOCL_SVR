"""Console entrypoints (see [project.scripts] in pyproject.toml).

* ``svr-backend``   - run the loopback API (Backend Service).
* ``svr-scheduler`` - run the carry-forward + backup scheduler (Scheduler Service).
* ``svr-migrate``   - apply pending SQL migrations; ``--seed-demo`` adds one user per role.
"""

from __future__ import annotations

import argparse
import sys
import time

from svr_backend.core.config import get_settings


def run_migrate(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="svr-migrate", description="Apply SQL migrations.")
    parser.add_argument("--db", help="SQLite path (default: from SVR_DB_PATH / config)")
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Create demo users (sales/manager/owner, password 'demo1234') if absent.",
    )
    args = parser.parse_args(argv)

    from svr_backend.core.db import connect
    from svr_backend.migrations.runner import migrate

    db_path = args.db or str(get_settings().resolved_db_path())
    conn = connect(db_path)
    try:
        applied = migrate(conn)
        print(f"Applied {len(applied)} migration(s): {applied or '(up to date)'}")
        if args.seed_demo:
            _seed_demo_users(conn)
    finally:
        conn.close()
    return 0


def _seed_demo_users(conn) -> None:
    from svr_backend.core.security import hash_password

    demo = [
        ("gsales", "G Sales", "Sales"),
        ("mmanager", "M Manager", "Manager"),
        ("oowner", "O Owner", "Owner"),
    ]
    pw = hash_password("demo1234")
    for login_name, full_name, role in demo:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE login_name = ?", (login_name,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO users (login_name, full_name, email, role, password_hash, last_updated_by)
            VALUES (?, ?, ?, ?, ?, 'seed')
            """,
            (login_name, full_name, f"{login_name}@example.test", role, pw),
        )
        print(f"seeded user {login_name} ({role})")


def run_create_user(argv: list[str] | None = None) -> int:
    """Create a user from the command line.

    The only way to make the FIRST account on a fresh production install - the
    installer runs ``migrate`` with no demo seed, so ``users`` is empty and the
    authenticated ``POST /users`` path can't be reached (SDD 4.1). Run once,
    elevated, right after install:

        svr-backend create-user --role Owner --name "R Owner" --login rowner
    """
    parser = argparse.ArgumentParser(
        prog="svr-create-user", description="Create a user (bootstrap the first Owner)."
    )
    parser.add_argument("--name", required=True, help="Full name.")
    parser.add_argument("--role", default="Owner", choices=("Sales", "Manager", "Owner"))
    parser.add_argument("--login", help="Login name (default: derived from --name).")
    parser.add_argument("--email", default="", help="Email (optional).")
    parser.add_argument(
        "--password",
        help="Password. Omit to be prompted (not echoed); '-' reads one line from stdin.",
    )
    parser.add_argument("--db", help="SQLite path (default: from SVR_DB_PATH / config).")
    args = parser.parse_args(argv)

    import getpass

    from svr_backend.core.audit import record_write
    from svr_backend.core.db import connect, transaction
    from svr_backend.core.security import hash_password
    from svr_backend.users import derive_login_name, unique_login_name

    if args.password == "-":
        password = sys.stdin.readline().rstrip("\n")
    elif args.password:
        password = args.password
    else:
        password = getpass.getpass("Password: ")
        if getpass.getpass("Confirm password: ") != password:
            print("Passwords do not match.", file=sys.stderr)
            return 2
    if len(password) < get_settings().min_password_length:
        print(
            f"Password too short (min {get_settings().min_password_length}).", file=sys.stderr
        )
        return 2

    db_path = args.db or str(get_settings().resolved_db_path())
    conn = connect(db_path)
    try:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone():
            print(
                f"Database at {db_path} is not initialised - run 'svr-backend migrate' first.",
                file=sys.stderr,
            )
            return 1
        base = args.login or derive_login_name(args.name)
        if conn.execute("SELECT 1 FROM users WHERE login_name = ?", (base,)).fetchone():
            print(f"Login name {base!r} already exists.", file=sys.stderr)
            return 1
        login_name = base if args.login else unique_login_name(conn, base)

        cols = "login_name, full_name, email, role, password_hash, last_updated_by"
        with transaction(conn):
            cur = conn.execute(
                f"INSERT INTO users ({cols}) VALUES (?, ?, ?, ?, ?, 'bootstrap')",
                (login_name, args.name, args.email, args.role, hash_password(password)),
            )
            record_write(
                conn,
                table="users",
                record_id=cur.lastrowid,
                action="create",
                actor="bootstrap",
                new={"login_name": login_name, "full_name": args.name, "role": args.role},
            )
    finally:
        conn.close()

    print(f"Created {args.role} user: {login_name}")
    return 0


def run_backend(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="svr-backend", description="Run the loopback API.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)

    import uvicorn

    settings = get_settings()
    try:
        from svr_backend.logging_setup import configure

        configure("backend")
    except Exception:  # logging is best-effort; never block startup
        pass

    uvicorn.run(
        "svr_backend.app:app",
        host=args.host or settings.api_host,
        port=args.port or settings.api_port,
        log_level="info",
    )
    return 0


def run_scheduler(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="svr-scheduler", description="Run the scheduler.").parse_args(argv)

    from svr_backend.scheduler import build_scheduler, startup_catch_up

    try:
        from svr_backend.logging_setup import configure

        configure("scheduler")
    except Exception:
        pass

    startup_catch_up()  # catch-up-on-startup for a missed 23:59 rollover (SDD 7.7)
    sched = build_scheduler()
    sched.start()
    print("svr-scheduler running; Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_backend())
