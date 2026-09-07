"""FastAPI application - the local loopback API the Electron frontend calls (SDD 7.2).

Bound to 127.0.0.1 only. Never exposed on a routable interface.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from svr_backend import __version__
from svr_backend.api import (
    auth,
    credit_master,
    daily_sales_entry,
    daily_sales_summary,
    daily_trial_balance,
    employees,
    expenses,
    inventory,
    pages,
    rate_master,
    receipts,
    reports,
    users,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="SVR IOCL Station - Backend API",
        version=__version__,
        summary="Loopback API for the SVR Indian Oil Service Station desktop app",
    )

    # The API is bound to 127.0.0.1 only (SDD 7.2), so any local origin is trusted:
    # the Electron renderer runs from file:// and the Playwright page-mode tests
    # from a localhost static server. Auth is bearer-token in a header, not a
    # cookie, so credentials need not be allowed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        # so the renderer's fetch() can read the download filename (Excel export)
        expose_headers=["Content-Disposition"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    app.include_router(auth.router)
    app.include_router(pages.router)
    app.include_router(rate_master.router)
    app.include_router(daily_sales_entry.router)
    app.include_router(daily_sales_summary.router)
    app.include_router(daily_trial_balance.router)
    app.include_router(inventory.router)
    app.include_router(users.router)
    app.include_router(credit_master.router)
    app.include_router(expenses.router)
    app.include_router(employees.router)
    app.include_router(employees.payroll_router)
    app.include_router(receipts.router)
    app.include_router(reports.router)
    return app


app = create_app()
