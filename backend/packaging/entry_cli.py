"""Frozen-backend entrypoint: ``svr-backend <subcommand> [args...]``.

PyInstaller bundles this into ``svr-backend.exe`` (see ``svr_backend.spec``). Each
subcommand maps 1:1 onto a console-script function in :mod:`svr_backend.cli`, so the
frozen build and a dev ``pip install -e .`` behave identically:

    svr-backend migrate [--db PATH] [--seed-demo]   -> svr_backend.cli:run_migrate
    svr-backend serve   [--host H] [--port N]        -> svr_backend.cli:run_backend
    svr-backend scheduler                            -> svr_backend.cli:run_scheduler
    svr-backend create-user --name .. [--role ..]    -> svr_backend.cli:run_create_user
    svr-backend gen-key                              -> a fresh Fernet key for SVR_FIELD_KEY
    svr-backend selfcheck                            -> import the full app graph, exit 0

``selfcheck`` exists so the freeze build (packaging/build-backend.ps1, and CI)
can force every router + dependency to import inside the frozen exe - turning a
missing PyInstaller hidden-import into a build failure instead of a dead install
on the station PC.

The two Windows Services are separate exes (``svr-backend-service.exe`` /
``svr-scheduler-service.exe``) built from the same spec.
"""

from __future__ import annotations

import sys

_USAGE = "usage: svr-backend {migrate|serve|scheduler|create-user|gen-key|selfcheck} [args...]"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(_USAGE, file=sys.stderr)
        return 2
    if args[0] in ("-h", "--help"):
        print(_USAGE)
        return 0

    cmd, rest = args[0], args[1:]

    if cmd == "migrate":
        from svr_backend.cli import run_migrate

        return run_migrate(rest)
    if cmd == "serve":
        from svr_backend.cli import run_backend

        return run_backend(rest)
    if cmd == "scheduler":
        from svr_backend.cli import run_scheduler

        return run_scheduler(rest)
    if cmd == "create-user":
        from svr_backend.cli import run_create_user

        return run_create_user(rest)
    if cmd == "gen-key":
        from svr_backend.core.crypto import generate_key

        print(generate_key())
        return 0
    if cmd == "selfcheck":
        import importlib

        app = importlib.import_module("svr_backend.app").app
        n = len(getattr(app, "routes", []))
        print(f"selfcheck ok: svr_backend.app imported, {n} routes")
        return 0

    print(f"svr-backend: unknown subcommand {cmd!r}\n{_USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
