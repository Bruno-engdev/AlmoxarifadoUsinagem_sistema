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


def _cmd_backfill_movement_costs(args: argparse.Namespace) -> int:
    """Atualiza Movement.unit_cost = 0/NULL usando o preço mais recente da TOTVS."""
    from app.database import SessionLocal
    from app.models import Movement, Tool, ToolPriceHistory

    db = SessionLocal()
    try:
        latest_rows = (
            db.query(ToolPriceHistory.tool_id, ToolPriceHistory.preco_unitario)
            .filter(ToolPriceHistory.is_latest.is_(True))
            .all()
        )
        latest_by_tool: dict[int, float] = {
            tid: float(price) for tid, price in latest_rows if price is not None
        }
        if not latest_by_tool:
            print("[cli] backfill-movement-costs: nenhum preço em ToolPriceHistory. Rode import-price-history antes.")
            return 1

        movements = (
            db.query(Movement)
            .filter(
                Movement.tool_id.in_(latest_by_tool.keys()),
                (Movement.unit_cost.is_(None)) | (Movement.unit_cost == 0),
            )
            .all()
        )
        print(f"[cli] backfill-movement-costs: {len(movements)} movimentações candidatas.")

        updated = 0
        for mv in movements:
            price = latest_by_tool.get(mv.tool_id)
            if price is None or price <= 0:
                continue
            mv.unit_cost = price
            updated += 1

        tool_ids = list(latest_by_tool.keys())
        tools_updated = 0
        if tool_ids:
            tools = db.query(Tool).filter(Tool.id.in_(tool_ids)).all()
            for t in tools:
                price = latest_by_tool.get(t.id)
                if price is None:
                    continue
                if float(t.unit_cost or 0) != price:
                    t.unit_cost = price
                    tools_updated += 1

        if args.dry_run:
            db.rollback()
            prefix = "[DRY-RUN] "
        else:
            db.commit()
            prefix = ""
        print(f"[cli] {prefix}backfill-movement-costs: {updated} movimentações atualizadas, {tools_updated} ferramentas sincronizadas.")
    finally:
        db.close()
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

    p_bf = sub.add_parser(
        "backfill-movement-costs",
        help="Preenche Movement.unit_cost vazio/zero usando o preço mais recente da TOTVS",
    )
    p_bf.add_argument("--dry-run", action="store_true", help="Não persiste no banco")

    args = parser.parse_args(argv)
    if args.command == "seed":
        return _cmd_seed()
    if args.command == "init-sqlite":
        return _cmd_init_sqlite()
    if args.command == "scan-alerts":
        return _cmd_scan_alerts()
    if args.command == "import-price-history":
        return _cmd_import_price_history(args)
    if args.command == "backfill-movement-costs":
        return _cmd_backfill_movement_costs(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
