"""
Notification service — manages ToolStockAlert lifecycle.

Alerts are created when a tool transitions from healthy stock to below-minimum.
They are NOT re-created on every movement while the tool remains below minimum.
When stock recovers above minimum, the alert is marked as cleared.
"""

from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Tool, ToolStockAlert


def check_and_create_alert(db: Session, tool: Tool) -> ToolStockAlert | None:
    """
    Check if a tool just crossed below its minimum stock and, if so,
    create a single unread alert.  Returns the new alert or None.

    Deduplication rule: only create a new alert if there is no existing
    unread+uncleared alert for the same tool.
    """
    if tool.min_stock <= 0:
        return None

    if tool.current_stock >= tool.min_stock:
        # Stock is healthy — clear any open alerts for this tool
        _clear_alerts(db, tool.id)
        return None

    # Check for an existing open (unread or uncleared) alert
    existing = (
        db.query(ToolStockAlert)
        .filter(
            ToolStockAlert.tool_id == tool.id,
            ToolStockAlert.cleared_at.is_(None),
        )
        .first()
    )
    if existing:
        # Update the snapshot values in case stock dropped further
        existing.current_stock = tool.current_stock
        return None

    alert = ToolStockAlert(
        tool_id=tool.id,
        current_stock=tool.current_stock,
        min_stock=tool.min_stock,
        is_critical=tool.is_critical,
    )
    db.add(alert)
    return alert


def _clear_alerts(db: Session, tool_id: int):
    """Mark all open alerts for this tool as cleared."""
    now = datetime.utcnow()
    (
        db.query(ToolStockAlert)
        .filter(
            ToolStockAlert.tool_id == tool_id,
            ToolStockAlert.cleared_at.is_(None),
        )
        .update({"cleared_at": now})
    )


def get_alerts(db: Session, unread_only: bool = False) -> list[ToolStockAlert]:
    """Return alerts ordered by most recent first."""
    q = db.query(ToolStockAlert).order_by(ToolStockAlert.created_at.desc())
    if unread_only:
        q = q.filter(ToolStockAlert.is_read == 0)
    return q.limit(100).all()


def get_unread_count(db: Session) -> int:
    return (
        db.query(ToolStockAlert)
        .filter(ToolStockAlert.is_read == 0)
        .count()
    )


def mark_all_read(db: Session):
    (
        db.query(ToolStockAlert)
        .filter(ToolStockAlert.is_read == 0)
        .update({"is_read": 1})
    )
    db.commit()
