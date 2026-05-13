"""
Operational CLI for AlmoxarifadoUsinagem.

Usage:
    python -m app.cli seed           # seed default tool types, machines, admin user
    python -m app.cli init-sqlite    # SQLite-only: create tables via SQLAlchemy (legacy fallback)
    python -m app.cli scan-alerts    # rebuild missing stock alerts

Schema management for PostgreSQL is handled by Alembic, not by this CLI:
    alembic upgrade head
"""

from __future__ import annotations

import argparse
import sys


def _cmd_seed() -> int:
    from app.database import seed_defaults, SessionLocal
    from app.auth import seed_admin
    seed_defaults()
    seed_admin()
    print("[cli] seed: defaults and admin ensured.")
    return 0


def _cmd_init_sqlite() -> int:
    from app.database import init_db, IS_SQLITE
    if not IS_SQLITE:
        print("[cli] init-sqlite is a no-op on non-SQLite backends. Use Alembic.")
        return 0
    init_db()
    print("[cli] init-sqlite: schema created.")
    return 0


def _cmd_scan_alerts() -> int:
    from app.database import SessionLocal
    from app.services.notifications import scan_all_tools
    db = SessionLocal()
    try:
        count = scan_all_tools(db)
        print(f"[cli] scan-alerts: created {count} alert(s).")
    finally:
        db.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Seed default tool types, machines and admin user")
    sub.add_parser("init-sqlite", help="Create tables via SQLAlchemy (SQLite fallback)")
    sub.add_parser("scan-alerts", help="Rebuild missing stock alerts")

    args = parser.parse_args(argv)
    if args.command == "seed":
        return _cmd_seed()
    if args.command == "init-sqlite":
        return _cmd_init_sqlite()
    if args.command == "scan-alerts":
        return _cmd_scan_alerts()
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
