"""Windows Service hosts (SDD 7.1 / 14).

Two services only - Backend and Scheduler. SQLite gets none (it is a file opened
in-process) and Tesseract gets none (a binary shelled out to on demand) - SDD
ADR-2 / ADR-6.
The Electron frontend is registered as a per-user startup item, not a service
(SDD 19 item 23).

These modules import ``pywin32`` and are meant to run on the deployment target via
``python -m svr_backend.services.backend_service install``. They are never imported
by the application or the test suite.
"""
