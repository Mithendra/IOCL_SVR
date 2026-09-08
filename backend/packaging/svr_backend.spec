# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-dir build of the SVR-IOCL backend.

Produces a single ``dist/svr-backend/`` folder holding three console exes that
share one copy of the Python runtime and dependencies (PyInstaller ``MERGE``):

    svr-backend.exe            CLI: migrate | serve | scheduler | gen-key
    svr-backend-service.exe    Windows Service host  (SVR-IOCL-Backend)
    svr-scheduler-service.exe  Windows Service host  (SVR-IOCL-Scheduler)

Build (from backend/, in an env with the [build] and [win] extras):

    pyinstaller --clean --noconfirm packaging/svr_backend.spec

The whole folder is bundled into the Electron installer as ``resources/backend/``
(see frontend/package.json > build.extraResources).
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# --- shared analysis inputs --------------------------------------------------

SRC = "../src"  # relative to this spec (backend/packaging/)

_datas = collect_data_files("svr_backend.migrations")  # the NNNN_*.sql files

_hiddenimports = [
    "svr_backend.app",
    *collect_submodules("svr_backend"),
    # uvicorn[standard] workers are imported by string at runtime
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.loops.asyncio",
    "uvicorn.lifespan.on",
    *collect_submodules("uvicorn"),
    # APScheduler resolves jobstores/executors/triggers by entry-point name
    *collect_submodules("apscheduler"),
    # openpyxl (.xlsx import/export) pulls writers lazily
    *collect_submodules("openpyxl"),
    "et_xmlfile",
    # pyotp (two-factor auth)
    *collect_submodules("pyotp"),
    # starlette runs on anyio; FastAPI form parsing needs python-multipart
    "anyio._backends._asyncio",
    "multipart",
    "python_multipart",
    # argon2-cffi password hashing (compiled backend)
    "argon2",
    # pywin32 service plumbing - the DLL-backed modules a frozen ServiceFramework
    # touches at install/start time, not just the obvious ones
    "win32timezone",
    "servicemanager",
    "win32serviceutil",
    "win32service",
    "win32event",
    "win32api",
    "win32con",
    "pywintypes",
    "pythoncom",
]

_common = dict(
    pathex=[SRC],
    binaries=[],
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "httpx"],
    noarchive=False,
)

a_cli = Analysis(["entry_cli.py"], **_common)
a_backend_svc = Analysis([SRC + "/svr_backend/services/backend_service.py"], **_common)
a_scheduler_svc = Analysis([SRC + "/svr_backend/services/scheduler_service.py"], **_common)

# De-duplicate shared deps: the CLI analysis owns them, the two service exes
# reference back into it.
MERGE(
    (a_cli, "svr-backend", "svr-backend"),
    (a_backend_svc, "svr-backend-service", "svr-backend-service"),
    (a_scheduler_svc, "svr-scheduler-service", "svr-scheduler-service"),
)

pyz_cli = PYZ(a_cli.pure)
pyz_backend_svc = PYZ(a_backend_svc.pure)
pyz_scheduler_svc = PYZ(a_scheduler_svc.pure)


def _exe(pyz, ana, name):
    return EXE(
        pyz,
        ana.scripts,
        [],
        exclude_binaries=True,
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
    )


exe_cli = _exe(pyz_cli, a_cli, "svr-backend")
exe_backend_svc = _exe(pyz_backend_svc, a_backend_svc, "svr-backend-service")
exe_scheduler_svc = _exe(pyz_scheduler_svc, a_scheduler_svc, "svr-scheduler-service")

COLLECT(
    exe_cli,
    a_cli.binaries,
    a_cli.zipfiles,
    a_cli.datas,
    exe_backend_svc,
    a_backend_svc.binaries,
    a_backend_svc.zipfiles,
    a_backend_svc.datas,
    exe_scheduler_svc,
    a_scheduler_svc.binaries,
    a_scheduler_svc.zipfiles,
    a_scheduler_svc.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="svr-backend",
)
