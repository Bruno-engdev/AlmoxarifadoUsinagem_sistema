"""
Database configuration and session management.
Uses SQLite with SQLAlchemy ORM.
"""

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite database file stored alongside the app
DATABASE_URL = "sqlite:///./toolcrib.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and seed initial data if needed."""
    from app.models import ToolType, Tool, Employee, Machine, User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_columns()
    _seed_defaults()


def _migrate_columns():
    """Add columns that were introduced after the initial schema."""
    migrations = [
        ("tools", "unit_cost",           "REAL DEFAULT 0"),
        ("tools", "is_critical",         "INTEGER DEFAULT 0"),
        ("tools", "avg_lifespan_hours",  "REAL DEFAULT 0"),
    ]
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, column, col_type in migrations:
            existing = [c["name"] for c in insp.get_columns(table)]
            if column not in existing:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                ))


def _seed_defaults():
    """Insert default tool types and machines if the tables are empty."""
    from app.models import ToolType, Machine

    db = SessionLocal()
    try:
        if db.query(ToolType).count() == 0:
            defaults = [
                "Drill",
                "End Mill",
                "Insert",
                "Tap",
                "Reamer",
                "Indexable Insert",
            ]
            for name in defaults:
                db.add(ToolType(name=name))
            db.commit()

        if db.query(Machine).count() == 0:
            machines = [
                "Fresadora 1",
                "Fresadora 2",
                "Fresadora 3",
                "Torno Convencional 1",
                "Torno Convencional 2",
                "Torno Convencional 3",
                "Eletroerosão a Fio",
                "Ajustagem",
                "Torno CNC 1",
                "Torno CNC 2",
                "Centro de Torneamento",
                "Centro de Usinagem 1",
                "Centro de Usinagem 2",
                "Centro de Usinagem 3",
                "Centro de Usinagem 4",
                "Portal",
            ]
            for name in machines:
                db.add(Machine(name=name))
            db.commit()
    finally:
        db.close()
