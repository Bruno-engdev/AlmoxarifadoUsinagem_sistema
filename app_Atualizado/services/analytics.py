"""
Analytics service – monthly consumption, top consumed tools, history.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models import Movement, Tool, ToolType


def get_monthly_consumption(db: Session, months: int = 12) -> list[dict]:
    """
    Return a list of {month, year, total_out} for the last *months* months.
    Only counts OUT movements.
    """
    cutoff = datetime.utcnow() - timedelta(days=months * 30)

    rows = (
        db.query(
            extract("year", Movement.timestamp).label("year"),
            extract("month", Movement.timestamp).label("month"),
            func.sum(Movement.quantity).label("total"),
        )
        .filter(Movement.movement_type == "OUT", Movement.timestamp >= cutoff)
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    return [
        {"year": int(r.year), "month": int(r.month), "total": int(r.total)}
        for r in rows
    ]


def get_top_consumed_tools(db: Session, limit: int = 10) -> list[dict]:
    """
    Return the top *limit* tools by total OUT quantity (all time).
    """
    rows = (
        db.query(
            Tool.id,
            Tool.name,
            func.sum(Movement.quantity).label("total"),
        )
        .join(Movement, Movement.tool_id == Tool.id)
        .filter(Movement.movement_type == "OUT")
        .group_by(Tool.id, Tool.name)
        .order_by(func.sum(Movement.quantity).desc())
        .limit(limit)
        .all()
    )

    return [{"id": r.id, "name": r.name, "total": int(r.total)} for r in rows]


def get_tool_consumption_history(
    db: Session, tool_id: int, months: int = 12
) -> list[dict]:
    """
    Return monthly OUT totals for a single tool.
    """
    cutoff = datetime.utcnow() - timedelta(days=months * 30)

    rows = (
        db.query(
            extract("year", Movement.timestamp).label("year"),
            extract("month", Movement.timestamp).label("month"),
            func.sum(Movement.quantity).label("total"),
        )
        .filter(
            Movement.tool_id == tool_id,
            Movement.movement_type == "OUT",
            Movement.timestamp >= cutoff,
        )
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    return [
        {"year": int(r.year), "month": int(r.month), "total": int(r.total)}
        for r in rows
    ]


def get_tools_below_minimum(db: Session) -> list[Tool]:
    """Return all tools whose current_stock < min_stock."""
    return (
        db.query(Tool)
        .filter(Tool.current_stock < Tool.min_stock, Tool.min_stock > 0)
        .all()
    )


def get_total_movements_this_month(db: Session) -> int:
    """Count of all movements in the current calendar month."""
    now = datetime.utcnow()
    return (
        db.query(func.count(Movement.id))
        .filter(
            extract("year", Movement.timestamp) == now.year,
            extract("month", Movement.timestamp) == now.month,
        )
        .scalar()
        or 0
    )


def get_total_consumption_this_month(db: Session) -> int:
    """Sum of OUT quantities in the current calendar month."""
    now = datetime.utcnow()
    return (
        db.query(func.coalesce(func.sum(Movement.quantity), 0))
        .filter(
            Movement.movement_type == "OUT",
            extract("year", Movement.timestamp) == now.year,
            extract("month", Movement.timestamp) == now.month,
        )
        .scalar()
        or 0
    )
