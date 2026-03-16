"""
Analytics service – monthly consumption, top consumed tools, history,
stock-by-type, entries vs exits, idle tools, recent movements.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract, and_

from app.models import Movement, Tool, ToolType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_filters(query, date_from=None, date_to=None,
                   tool_type_id=None, tool_name=None):
    """Apply common date / type / name filters to a Movement query."""
    if date_from:
        query = query.filter(Movement.timestamp >= date_from)
    if date_to:
        # include the whole end-day
        query = query.filter(Movement.timestamp < date_to + timedelta(days=1))
    if tool_type_id:
        query = query.join(Tool, Tool.id == Movement.tool_id).filter(
            Tool.tool_type_id == tool_type_id
        )
    if tool_name:
        if not tool_type_id:
            query = query.join(Tool, Tool.id == Movement.tool_id)
        query = query.filter(Tool.name.ilike(f"%{tool_name}%"))
    return query


# ---------------------------------------------------------------------------
# Monthly consumption  (OUT movements)
# ---------------------------------------------------------------------------

def get_monthly_consumption(db: Session, months: int = 12, *,
                            date_from=None, date_to=None,
                            tool_type_id=None, tool_name=None) -> list[dict]:
    cutoff = date_from or (datetime.utcnow() - timedelta(days=months * 30))
    q = (
        db.query(
            extract("year", Movement.timestamp).label("year"),
            extract("month", Movement.timestamp).label("month"),
            func.sum(Movement.quantity).label("total"),
        )
        .filter(Movement.movement_type == "OUT", Movement.timestamp >= cutoff)
    )
    if date_to:
        q = q.filter(Movement.timestamp < date_to + timedelta(days=1))
    if tool_type_id:
        q = q.join(Tool, Tool.id == Movement.tool_id).filter(
            Tool.tool_type_id == tool_type_id)
    if tool_name:
        if not tool_type_id:
            q = q.join(Tool, Tool.id == Movement.tool_id)
        q = q.filter(Tool.name.ilike(f"%{tool_name}%"))

    rows = q.group_by("year", "month").order_by("year", "month").all()
    return [{"year": int(r.year), "month": int(r.month),
             "total": int(r.total)} for r in rows]


# ---------------------------------------------------------------------------
# Monthly entries vs exits
# ---------------------------------------------------------------------------

def get_monthly_in_out(db: Session, months: int = 12, *,
                       date_from=None, date_to=None,
                       tool_type_id=None, tool_name=None) -> list[dict]:
    """Return [{month, year, total_in, total_out}, …]."""
    cutoff = date_from or (datetime.utcnow() - timedelta(days=months * 30))

    q = (
        db.query(
            extract("year", Movement.timestamp).label("year"),
            extract("month", Movement.timestamp).label("month"),
            Movement.movement_type,
            func.sum(Movement.quantity).label("total"),
        )
        .filter(Movement.timestamp >= cutoff)
    )
    if date_to:
        q = q.filter(Movement.timestamp < date_to + timedelta(days=1))
    if tool_type_id:
        q = q.join(Tool, Tool.id == Movement.tool_id).filter(
            Tool.tool_type_id == tool_type_id)
    if tool_name:
        if not tool_type_id:
            q = q.join(Tool, Tool.id == Movement.tool_id)
        q = q.filter(Tool.name.ilike(f"%{tool_name}%"))

    rows = q.group_by("year", "month", Movement.movement_type)\
            .order_by("year", "month").all()

    combined: dict[tuple, dict] = {}
    for r in rows:
        key = (int(r.year), int(r.month))
        if key not in combined:
            combined[key] = {"year": key[0], "month": key[1],
                             "total_in": 0, "total_out": 0}
        if r.movement_type == "IN":
            combined[key]["total_in"] = int(r.total)
        else:
            combined[key]["total_out"] = int(r.total)
    return sorted(combined.values(), key=lambda x: (x["year"], x["month"]))


# ---------------------------------------------------------------------------
# Top consumed tools
# ---------------------------------------------------------------------------

def get_top_consumed_tools(db: Session, limit: int = 10, *,
                           date_from=None, date_to=None,
                           tool_type_id=None, tool_name=None) -> list[dict]:
    q = (
        db.query(
            Tool.id, Tool.name,
            func.sum(Movement.quantity).label("total"),
        )
        .join(Movement, Movement.tool_id == Tool.id)
        .filter(Movement.movement_type == "OUT")
    )
    if date_from:
        q = q.filter(Movement.timestamp >= date_from)
    if date_to:
        q = q.filter(Movement.timestamp < date_to + timedelta(days=1))
    if tool_type_id:
        q = q.filter(Tool.tool_type_id == tool_type_id)
    if tool_name:
        q = q.filter(Tool.name.ilike(f"%{tool_name}%"))

    rows = (q.group_by(Tool.id, Tool.name)
             .order_by(func.sum(Movement.quantity).desc())
             .limit(limit).all())
    return [{"id": r.id, "name": r.name, "total": int(r.total)} for r in rows]


# ---------------------------------------------------------------------------
# Stock by tool type
# ---------------------------------------------------------------------------

def get_stock_by_type(db: Session) -> list[dict]:
    """Return [{type_name, total_stock, tool_count}, …]."""
    rows = (
        db.query(
            ToolType.name,
            func.sum(Tool.current_stock).label("total_stock"),
            func.count(Tool.id).label("tool_count"),
        )
        .join(Tool, Tool.tool_type_id == ToolType.id)
        .group_by(ToolType.name)
        .order_by(ToolType.name)
        .all()
    )
    return [{"type_name": r.name,
             "total_stock": int(r.total_stock or 0),
             "tool_count": int(r.tool_count)} for r in rows]


# ---------------------------------------------------------------------------
# Tools below minimum
# ---------------------------------------------------------------------------

def get_tools_below_minimum(db: Session) -> list[Tool]:
    return (
        db.query(Tool)
        .filter(Tool.current_stock < Tool.min_stock, Tool.min_stock > 0)
        .order_by(Tool.current_stock)
        .all()
    )


# ---------------------------------------------------------------------------
# Tools with no movement for N days
# ---------------------------------------------------------------------------

def get_idle_tools(db: Session, days: int = 90) -> list[dict]:
    """Tools that had zero movements in the last *days* days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    # sub-query: tools that DO have recent movements
    active_ids = (
        db.query(Movement.tool_id)
        .filter(Movement.timestamp >= cutoff)
        .distinct()
        .subquery()
    )
    idle = (
        db.query(Tool)
        .filter(~Tool.id.in_(db.query(active_ids.c.tool_id)))
        .order_by(Tool.name)
        .all()
    )
    return [{"id": t.id, "name": t.name, "current_stock": t.current_stock,
             "type": t.tool_type.name if t.tool_type else "—"} for t in idle]


# ---------------------------------------------------------------------------
# Recent movements
# ---------------------------------------------------------------------------

def get_recent_movements(db: Session, limit: int = 10) -> list[Movement]:
    return (
        db.query(Movement)
        .options(
            joinedload(Movement.tool),
            joinedload(Movement.employee),
            joinedload(Movement.machine),
        )
        .order_by(Movement.timestamp.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Aggregated totals (with optional filters)
# ---------------------------------------------------------------------------

def get_total_movements_this_month(db: Session) -> int:
    now = datetime.utcnow()
    return (
        db.query(func.count(Movement.id))
        .filter(
            extract("year", Movement.timestamp) == now.year,
            extract("month", Movement.timestamp) == now.month,
        )
        .scalar() or 0
    )


def get_total_consumption_this_month(db: Session) -> int:
    now = datetime.utcnow()
    return (
        db.query(func.coalesce(func.sum(Movement.quantity), 0))
        .filter(
            Movement.movement_type == "OUT",
            extract("year", Movement.timestamp) == now.year,
            extract("month", Movement.timestamp) == now.month,
        )
        .scalar() or 0
    )


def get_total_consumption_period(db: Session, date_from=None, date_to=None,
                                 tool_type_id=None, tool_name=None) -> int:
    """Total OUT quantity within filters."""
    q = db.query(func.coalesce(func.sum(Movement.quantity), 0)).filter(
        Movement.movement_type == "OUT")
    if date_from:
        q = q.filter(Movement.timestamp >= date_from)
    if date_to:
        q = q.filter(Movement.timestamp < date_to + timedelta(days=1))
    if tool_type_id or tool_name:
        q = q.join(Tool, Tool.id == Movement.tool_id)
        if tool_type_id:
            q = q.filter(Tool.tool_type_id == tool_type_id)
        if tool_name:
            q = q.filter(Tool.name.ilike(f"%{tool_name}%"))
    return q.scalar() or 0


def get_total_movements_period(db: Session, date_from=None, date_to=None,
                               tool_type_id=None, tool_name=None) -> int:
    """Count of all movements within filters."""
    q = db.query(func.count(Movement.id))
    if date_from:
        q = q.filter(Movement.timestamp >= date_from)
    if date_to:
        q = q.filter(Movement.timestamp < date_to + timedelta(days=1))
    if tool_type_id or tool_name:
        q = q.join(Tool, Tool.id == Movement.tool_id)
        if tool_type_id:
            q = q.filter(Tool.tool_type_id == tool_type_id)
        if tool_name:
            q = q.filter(Tool.name.ilike(f"%{tool_name}%"))
    return q.scalar() or 0


def get_tool_consumption_history(
    db: Session, tool_id: int, months: int = 12
) -> list[dict]:
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
    return [{"year": int(r.year), "month": int(r.month),
             "total": int(r.total)} for r in rows]


# ---------------------------------------------------------------------------
# Strategic KPIs
# ---------------------------------------------------------------------------

def get_avg_tool_lifespan(db: Session) -> float:
    """Average lifespan (hours) across tools that have it set (> 0)."""
    val = (
        db.query(func.avg(Tool.avg_lifespan_hours))
        .filter(Tool.avg_lifespan_hours > 0)
        .scalar()
    )
    return round(val, 1) if val else 0.0


def get_capital_tied_idle(db: Session, days: int = 90) -> float:
    """Total R$ value (unit_cost × current_stock) of idle tools."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    active_ids = (
        db.query(Movement.tool_id)
        .filter(Movement.timestamp >= cutoff)
        .distinct()
        .subquery()
    )
    val = (
        db.query(func.sum(Tool.unit_cost * Tool.current_stock))
        .filter(~Tool.id.in_(db.query(active_ids.c.tool_id)))
        .filter(Tool.current_stock > 0)
        .scalar()
    )
    return round(val, 2) if val else 0.0


def get_critical_availability(db: Session) -> dict:
    """Count of critical tools vs how many are at healthy stock."""
    total = db.query(func.count(Tool.id)).filter(Tool.is_critical == 1).scalar() or 0
    ok = (
        db.query(func.count(Tool.id))
        .filter(Tool.is_critical == 1, Tool.current_stock >= Tool.min_stock)
        .scalar() or 0
    )
    return {"total": total, "ok": ok, "pct": round(ok / total * 100, 1) if total else 100.0}


def get_high_maintenance_tools(db: Session, months: int = 6,
                               threshold: int = 10) -> list[dict]:
    """Tools with more than *threshold* OUT movements in the last *months* months."""
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    rows = (
        db.query(
            Tool.id, Tool.name,
            func.sum(Movement.quantity).label("total_out"),
        )
        .join(Movement, Movement.tool_id == Tool.id)
        .filter(Movement.movement_type == "OUT", Movement.timestamp >= cutoff)
        .group_by(Tool.id, Tool.name)
        .having(func.sum(Movement.quantity) >= threshold)
        .order_by(func.sum(Movement.quantity).desc())
        .all()
    )
    return [{"id": r.id, "name": r.name, "total_out": int(r.total_out)} for r in rows]


def get_rarely_used_tools(db: Session, months: int = 6) -> list[dict]:
    """Tools with stock > 0 but zero OUT movements in the last *months* months.
    Candidate for obsolescence review."""
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    active_ids = (
        db.query(Movement.tool_id)
        .filter(Movement.movement_type == "OUT", Movement.timestamp >= cutoff)
        .distinct()
        .subquery()
    )
    tools = (
        db.query(Tool)
        .filter(Tool.current_stock > 0, ~Tool.id.in_(db.query(active_ids.c.tool_id)))
        .order_by(Tool.name)
        .all()
    )
    return [
        {"id": t.id, "name": t.name, "current_stock": t.current_stock,
         "unit_cost": t.unit_cost, "value": round(t.unit_cost * t.current_stock, 2),
         "type": t.tool_type.name if t.tool_type else "—"}
        for t in tools
    ]


def get_monthly_cost(db: Session, months: int = 12) -> list[dict]:
    """Monthly cost of consumed tools (OUT qty × unit_cost)."""
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    rows = (
        db.query(
            extract("year", Movement.timestamp).label("year"),
            extract("month", Movement.timestamp).label("month"),
            func.sum(Movement.quantity * Tool.unit_cost).label("cost"),
        )
        .join(Tool, Tool.id == Movement.tool_id)
        .filter(Movement.movement_type == "OUT", Movement.timestamp >= cutoff)
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )
    return [{"year": int(r.year), "month": int(r.month),
             "cost": round(float(r.cost or 0), 2)} for r in rows]


def get_total_stock_value(db: Session) -> float:
    """Total value of all stock (unit_cost × current_stock)."""
    val = (
        db.query(func.sum(Tool.unit_cost * Tool.current_stock))
        .filter(Tool.current_stock > 0)
        .scalar()
    )
    return round(val, 2) if val else 0.0
