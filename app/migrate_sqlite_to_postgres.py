"""
One-shot data migration from SQLite to PostgreSQL (or any other SQLAlchemy backend).

Preserves primary keys and resets sequences after load. Idempotency is NOT
guaranteed: the target schema must be empty (or the relevant tables empty).

Usage:
    python -m app.migrate_sqlite_to_postgres \
        --source sqlite:///./toolcrib.db \
        --target postgresql+psycopg://toolcrib:toolcrib@localhost:5432/toolcrib

If --target is omitted, DATABASE_URL from the environment is used.

Pre-requisites on target:
    alembic upgrade head   # create the schema first

The script copies tables in FK-safe order, preserves IDs, and on PostgreSQL
resets the sequence of every table to MAX(id)+1.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable

from sqlalchemy import create_engine, MetaData, Table, select, insert, text
from sqlalchemy.engine import Engine


# Order respects FK dependencies: parents first, children last.
TABLE_ORDER: list[str] = [
    "users",
    "machines",
    "tool_types",
    "employees",
    "tools",
    "tool_parameters",
    "movements",
    "tool_stock_alerts",
]


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


def _reflect(engine: Engine) -> MetaData:
    md = MetaData()
    md.reflect(bind=engine)
    return md


def _copy_table(src_engine: Engine, dst_engine: Engine, table_name: str,
                src_md: MetaData, dst_md: MetaData, batch: int = 500) -> int:
    if table_name not in src_md.tables:
        print(f"  [skip] {table_name}: not present in source")
        return 0
    if table_name not in dst_md.tables:
        print(f"  [skip] {table_name}: not present in target")
        return 0

    src_table: Table = src_md.tables[table_name]
    dst_table: Table = dst_md.tables[table_name]

    # Restrict to columns that exist in BOTH schemas (defensive against drift).
    common_cols = [c.name for c in src_table.columns if c.name in dst_table.columns]
    if not common_cols:
        print(f"  [skip] {table_name}: no overlapping columns")
        return 0

    total = 0
    with src_engine.connect() as src_conn, dst_engine.begin() as dst_conn:
        result = src_conn.execution_options(stream_results=True).execute(
            select(*[src_table.c[name] for name in common_cols])
        )
        rows: list[dict] = []
        for row in result:
            rows.append({col: row[i] for i, col in enumerate(common_cols)})
            if len(rows) >= batch:
                dst_conn.execute(insert(dst_table), rows)
                total += len(rows)
                rows.clear()
        if rows:
            dst_conn.execute(insert(dst_table), rows)
            total += len(rows)

    print(f"  [ok]   {table_name}: copied {total} row(s)")
    return total


def _reset_sequences_postgres(dst_engine: Engine, table_names: Iterable[str]) -> None:
    """For each table with an `id` column, set its sequence to MAX(id)."""
    with dst_engine.begin() as conn:
        for table in table_names:
            seq_q = text(
                "SELECT pg_get_serial_sequence(:t, 'id')"
            )
            seq_name = conn.execute(seq_q, {"t": table}).scalar()
            if not seq_name:
                continue
            max_id = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")).scalar() or 0
            # setval(seq, max_id, true) -> next nextval() returns max_id+1.
            # If table is empty, use setval(seq, 1, false) so next id is 1.
            if max_id > 0:
                conn.execute(text("SELECT setval(:s, :v, true)"),
                             {"s": seq_name, "v": int(max_id)})
            else:
                conn.execute(text("SELECT setval(:s, 1, false)"), {"s": seq_name})
            print(f"  [seq]  {table}: setval({seq_name!r}, {max_id})")


def _verify_counts(src_engine: Engine, dst_engine: Engine,
                   table_names: Iterable[str]) -> bool:
    print("\nVerification (source vs target counts):")
    ok = True
    with src_engine.connect() as s, dst_engine.connect() as d:
        for table in table_names:
            try:
                src_count = s.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            except Exception:
                src_count = None
            try:
                dst_count = d.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            except Exception:
                dst_count = None
            marker = "OK " if src_count == dst_count else "DIFF"
            if src_count != dst_count:
                ok = False
            print(f"  [{marker}] {table}: src={src_count} dst={dst_count}")
    return ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Copy data from SQLite to PostgreSQL.")
    p.add_argument("--source", default=None,
                   help="Source SQLAlchemy URL (default: sqlite:///./toolcrib.db)")
    p.add_argument("--target", default=None,
                   help="Target SQLAlchemy URL (default: $DATABASE_URL)")
    p.add_argument("--batch", type=int, default=500)
    p.add_argument("--allow-non-empty-target", action="store_true",
                   help="Skip the safety check that the target tables are empty.")
    args = p.parse_args(argv)

    source_url = args.source or "sqlite:///./toolcrib.db"
    target_url = args.target or os.getenv("DATABASE_URL")
    if not target_url:
        print("ERROR: --target not provided and DATABASE_URL is unset.", file=sys.stderr)
        return 2
    if source_url == target_url:
        print("ERROR: source and target URLs are identical.", file=sys.stderr)
        return 2

    print(f"Source: {source_url}")
    print(f"Target: {target_url}")

    src_engine = _make_engine(source_url)
    dst_engine = _make_engine(target_url)

    src_md = _reflect(src_engine)
    dst_md = _reflect(dst_engine)

    # Safety: ensure target tables are empty unless explicitly overridden.
    if not args.allow_non_empty_target:
        with dst_engine.connect() as conn:
            for table in TABLE_ORDER:
                if table not in dst_md.tables:
                    continue
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                if count > 0:
                    print(f"ERROR: target table {table} is not empty ({count} rows). "
                          f"Use --allow-non-empty-target to override.", file=sys.stderr)
                    return 3

    print("\nCopying tables:")
    for table in TABLE_ORDER:
        _copy_table(src_engine, dst_engine, table, src_md, dst_md, batch=args.batch)

    # Reset sequences only on PostgreSQL.
    if dst_engine.dialect.name == "postgresql":
        print("\nResetting PostgreSQL sequences:")
        _reset_sequences_postgres(dst_engine, TABLE_ORDER)

    ok = _verify_counts(src_engine, dst_engine, TABLE_ORDER)
    print("\nDone." if ok else "\nDone WITH MISMATCHES — review above.")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
