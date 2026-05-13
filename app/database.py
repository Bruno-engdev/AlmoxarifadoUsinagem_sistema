"""
Database configuration and session management.

Supports both SQLite (default for local development) and PostgreSQL
(default for Docker / production). Dialect is inferred from DATABASE_URL.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "toolcrib.db"

# Prefer an explicit DATABASE_URL, otherwise bind SQLite to the repository root.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

# ---------------------------------------------------------------------------
# Dialect-aware engine configuration
# ---------------------------------------------------------------------------

_url = make_url(DATABASE_URL)
DIALECT = _url.get_backend_name()  # "sqlite", "postgresql", "mysql", ...
IS_SQLITE = DIALECT == "sqlite"
IS_POSTGRES = DIALECT in ("postgresql", "postgres")


def _build_engine_kwargs() -> dict:
    """Engine options tailored per backend."""
    if IS_SQLITE:
        return {
            "connect_args": {"check_same_thread": False},
            "echo": False,
        }
    # PostgreSQL / others: enable pre-ping to survive idle disconnects,
    # and a modest pool sized for a small internal app.
    return {
        "pool_pre_ping": True,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
        "echo": False,
    }


engine = create_engine(DATABASE_URL, **_build_engine_kwargs())

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Schema bootstrap
#
# As of the PostgreSQL migration, the canonical schema lifecycle is managed by
# Alembic (see alembic/ at the repository root). The functions below remain as
# a fallback for the SQLite local-dev flow when Alembic was not run, and are
# no-ops on PostgreSQL.
# ---------------------------------------------------------------------------

def init_db():
    """
    Create all tables (SQLite fallback only).

    On PostgreSQL this is a no-op: schema must be applied via
    `alembic upgrade head`.
    """
    if not IS_SQLITE:
        return

    from app.models import (  # noqa: F401
        ToolType, Tool, Employee, Machine, User, ToolStockAlert,
        ToolParameter, Movement,
    )
    Base.metadata.create_all(bind=engine)
    _migrate_columns_sqlite()


def _migrate_columns_sqlite():
    """Ad-hoc column additions for legacy SQLite databases."""
    if not IS_SQLITE:
        return

    migrations = [
        ("tools", "unit_cost",           "REAL DEFAULT 0"),
        ("tools", "is_critical",         "INTEGER DEFAULT 0"),
        ("tools", "avg_lifespan_hours",  "REAL DEFAULT 0"),
        ("tools", "origin_id",           "TEXT DEFAULT ''"),
        ("movements", "unit_cost",       "REAL DEFAULT 0"),
    ]
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        newly_added = set()
        for table, column, col_type in migrations:
            if table not in existing_tables:
                continue
            existing = [c["name"] for c in insp.get_columns(table)]
            if column not in existing:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                ))
                newly_added.add((table, column))

        if ("movements", "unit_cost") in newly_added:
            conn.execute(text(
                "UPDATE movements SET unit_cost = ("
                "  SELECT unit_cost FROM tools WHERE tools.id = movements.tool_id"
                ") WHERE EXISTS ("
                "  SELECT 1 FROM tools WHERE tools.id = movements.tool_id"
                "  AND tools.unit_cost > 0"
                ")"
            ))


def seed_defaults():
    """
    Insert default tool types and machines if the tables are empty.

    Idempotent and safe to call on any backend. Invoked by the CLI / entrypoint
    rather than at app startup.
    """
    from app.models import ToolType, Machine

    db = SessionLocal()
    try:
        if db.query(ToolType).count() == 0:
            defaults = [
                "Drill", "End Mill", "Insert", "Tap", "Reamer", "Indexable Insert",
            ]
            for name in defaults:
                db.add(ToolType(name=name))
            db.commit()

        if db.query(Machine).count() == 0:
            machines = [
                "Fresadora 1", "Fresadora 2", "Fresadora 3",
                "Torno Convencional 1", "Torno Convencional 2", "Torno Convencional 3",
                "Eletroerosão a Fio", "Ajustagem", "Torno CNC 1", "Torno CNC 2",
                "Centro de Torneamento", "Centro de Usinagem 1", "Centro de Usinagem 2",
                "Centro de Usinagem 3", "Centro de Usinagem 4", "Portal",
            ]
            for name in machines:
                db.add(Machine(name=name))
            db.commit()
    finally:
        db.close()


# Backwards-compat alias for any caller still using the old private name.
_seed_defaults = seed_defaults
