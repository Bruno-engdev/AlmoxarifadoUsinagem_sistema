"""
Forecasting service – predicts when tools will reach minimum stock
based on historical consumption data.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Movement, Tool


def get_average_daily_usage(db: Session, tool_id: int, months: int = 6) -> float:
    """
    Calculate average daily usage over the last *months* months
    based on OUT movements.
    """
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    days_in_period = (datetime.utcnow() - cutoff).days or 1

    total_out = (
        db.query(func.coalesce(func.sum(Movement.quantity), 0))
        .filter(
            Movement.tool_id == tool_id,
            Movement.movement_type == "OUT",
            Movement.timestamp >= cutoff,
        )
        .scalar()
    ) or 0

    return total_out / days_in_period


def predict_days_until_min_stock(db: Session, tool: Tool) -> int | None:
    """
    Estimate how many days until the tool reaches its minimum stock level.

    Returns:
      - Number of days (int) if consumption is positive
      - None if there's no consumption history (infinite)
    """
    avg_daily = get_average_daily_usage(db, tool.id)
    if avg_daily <= 0:
        return None  # No consumption → stock won't deplete

    available = tool.current_stock - tool.min_stock
    if available <= 0:
        return 0  # Already at or below minimum

    return int(available / avg_daily)


def get_all_predictions(db: Session) -> list[dict]:
    """
    Return predictions for every tool that has min_stock > 0.
    """
    tools = db.query(Tool).filter(Tool.min_stock > 0).all()
    results = []
    for tool in tools:
        days = predict_days_until_min_stock(db, tool)
        results.append({
            "tool": tool,
            "days_remaining": days,
            "warning": days is not None and days < 30,
        })
    return results
