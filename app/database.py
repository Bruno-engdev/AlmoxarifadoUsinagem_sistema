"""
Database configuration and session management.
Uses SQLite with SQLAlchemy ORM.
"""

from sqlalchemy import create_engine
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
    from app.models import ToolType, Tool, Employee  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _seed_defaults()


def _seed_defaults():
    """Insert default tool types if the table is empty."""
    from app.models import ToolType

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
    finally:
        db.close()
