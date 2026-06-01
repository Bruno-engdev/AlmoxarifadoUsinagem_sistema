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


def _cmd_import_price_history(args: argparse.Namespace) -> int:
    """Importa histórico de preços a partir de planilha/XML do TOTVS."""
    from pathlib import Path
    from app.database import SessionLocal
    from app.services.price_history_xlsx import read_totvs_price_file
    from app.services.price_history_import import import_price_history

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[cli] import-price-history: arquivo não encontrado: {file_path}")
        return 2

    print(f"[cli] import-price-history: lendo {file_path}...")
    try:
        rows = read_totvs_price_file(file_path, sheet_name=args.sheet)
    except Exception as exc:
        print(f"[cli] import-price-history: falha ao ler arquivo: {exc}")
        return 2
    print(f"[cli] import-price-history: {len(rows)} linha(s) lida(s).")

    db = SessionLocal()
    try:
        result = import_price_history(
            db, rows,
            source=args.source,
            file_name=file_path.name,
            dry_run=args.dry_run,
        )
    finally:
        db.close()

    print(f"[cli] import-price-history: {result.summary()}")
    if result.errors and args.verbose:
        for err in result.errors[:50]:
            print(f"    - {err}")
        if len(result.errors) > 50:
            print(f"    ... (+{len(result.errors) - 50} erros)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Seed default tool types, machines and admin user")
    sub.add_parser("init-sqlite", help="Create tables via SQLAlchemy (SQLite fallback)")
    sub.add_parser("scan-alerts", help="Rebuild missing stock alerts")

    p_imp = sub.add_parser(
        "import-price-history",
        help="Importa histórico de preços do TOTVS (xlsx ou XML Spreadsheet 2003)",
    )
    p_imp.add_argument("--file", required=True, help="Caminho do arquivo TOTVS (.xlsx ou .xml)")
    p_imp.add_argument("--sheet", default=None, help="Nome da planilha (opcional)")
    p_imp.add_argument("--source", default="TOTVS", help="Rótulo de origem (default: TOTVS)")
    p_imp.add_argument("--dry-run", action="store_true", help="Não persiste no banco")
    p_imp.add_argument("--verbose", action="store_true", help="Lista erros de parsing")

    args = parser.parse_args(argv)
    if args.command == "seed":
        return _cmd_seed()
    if args.command == "init-sqlite":
        return _cmd_init_sqlite()
    if args.command == "scan-alerts":
        return _cmd_scan_alerts()
    if args.command == "import-price-history":
        return _cmd_import_price_history(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
