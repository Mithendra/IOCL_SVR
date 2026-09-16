"""SVR Indian Oil Service Station - backend package.

Authoritative spec: docs/02-System-Design-Architecture/. This package hosts the
FastAPI loopback API, the calculation engine (single source of truth for every
formula), RBAC/audit enforcement, and the 23:59 IST carry-forward scheduler.
"""

__version__ = "0.1.1"
