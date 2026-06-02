"""
Analytics service – monthly consumption, top consumed tools, history,
stock-by-type, entries vs exits, idle tools, recent movements.
"""

from datetime import datetime, timedelta, date
from collections import defaultdict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract, and_, case

from app.models import Movement, Tool, ToolType, ToolPriceHistory


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


def _apply_tool_filters(query, tool_type_id=None, tool_name=None):
    """Apply common type / name filters to a Tool-based query."""
    if tool_type_id:
        query = query.filter(Tool.tool_type_id == tool_type_id)
    if tool_name:
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

def get_stock_by_type(db: Session, *, tool_type_id=None,
                      tool_name=None) -> list[dict]:
    """Return [{type_name, total_stock, tool_count}, …]."""
    q = (
        db.query(
            ToolType.name,
            func.sum(Tool.current_stock).label("total_stock"),
            func.count(Tool.id).label("tool_count"),
        )
        .join(Tool, Tool.tool_type_id == ToolType.id)
    )
    q = _apply_tool_filters(q, tool_type_id=tool_type_id, tool_name=tool_name)
    rows = q.group_by(ToolType.name).order_by(ToolType.name).all()
    return [{"type_name": r.name,
             "total_stock": int(r.total_stock or 0),
             "tool_count": int(r.tool_count)} for r in rows]


# ---------------------------------------------------------------------------
# Tools below minimum
# ---------------------------------------------------------------------------

def get_tools_below_minimum(db: Session, *, tool_type_id=None,
                            tool_name=None) -> list[Tool]:
    q = (
        db.query(Tool)
        .filter(Tool.current_stock < Tool.min_stock, Tool.min_stock > 0)
    )
    q = _apply_tool_filters(q, tool_type_id=tool_type_id, tool_name=tool_name)
    return q.order_by(Tool.current_stock).all()


# ---------------------------------------------------------------------------
# Tools with no movement for N days
# ---------------------------------------------------------------------------

def get_idle_tools(db: Session, days: int = 90, *, tool_type_id=None,
                   tool_name=None) -> list[dict]:
    """Tools that had zero movements in the last *days* days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    # sub-query: tools that DO have recent movements
    active_ids = (
        db.query(Movement.tool_id)
        .filter(Movement.timestamp >= cutoff)
        .distinct()
        .subquery()
    )
    q = db.query(Tool).filter(~Tool.id.in_(db.query(active_ids.c.tool_id)))
    q = _apply_tool_filters(q, tool_type_id=tool_type_id, tool_name=tool_name)
    idle = q.order_by(Tool.name).all()
    return [{"id": t.id, "name": t.name, "current_stock": t.current_stock,
             "type": t.tool_type.name if t.tool_type else "—"} for t in idle]


# ---------------------------------------------------------------------------
# Recent movements
# ---------------------------------------------------------------------------

def get_recent_movements(db: Session, limit: int = 10, *, date_from=None,
                         date_to=None, tool_type_id=None,
                         tool_name=None) -> list[Movement]:
    q = (
        db.query(Movement)
        .options(
            joinedload(Movement.tool),
            joinedload(Movement.employee),
            joinedload(Movement.machine),
        )
    )
    q = _apply_filters(
        q,
        date_from=date_from,
        date_to=date_to,
        tool_type_id=tool_type_id,
        tool_name=tool_name,
    )
    return q.order_by(Movement.timestamp.desc()).limit(limit).all()


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

def get_avg_tool_lifespan(db: Session, *, tool_type_id=None,
                          tool_name=None) -> float:
    """Average lifespan (hours) across tools that have it set (> 0)."""
    q = db.query(func.avg(Tool.avg_lifespan_hours)).filter(Tool.avg_lifespan_hours > 0)
    q = _apply_tool_filters(q, tool_type_id=tool_type_id, tool_name=tool_name)
    val = q.scalar()
    return round(val, 1) if val else 0.0


def get_capital_tied_idle(db: Session, days: int = 90, *, tool_type_id=None,
                          tool_name=None) -> float:
    """Total R$ value (unit_cost × current_stock) of idle tools."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    active_ids = (
        db.query(Movement.tool_id)
        .filter(Movement.timestamp >= cutoff)
        .distinct()
        .subquery()
    )
    q = (
        db.query(func.sum(Tool.unit_cost * Tool.current_stock))
        .filter(~Tool.id.in_(db.query(active_ids.c.tool_id)))
        .filter(Tool.current_stock > 0)
    )
    q = _apply_tool_filters(q, tool_type_id=tool_type_id, tool_name=tool_name)
    val = q.scalar()
    return round(val, 2) if val else 0.0


def get_critical_availability(db: Session, *, tool_type_id=None,
                              tool_name=None) -> dict:
    """Count of critical tools vs how many are at healthy stock."""
    q_total = db.query(func.count(Tool.id)).filter(Tool.is_critical == 1)
    q_total = _apply_tool_filters(q_total, tool_type_id=tool_type_id, tool_name=tool_name)
    total = q_total.scalar() or 0

    q_ok = (
        db.query(func.count(Tool.id))
        .filter(Tool.is_critical == 1, Tool.current_stock >= Tool.min_stock)
    )
    q_ok = _apply_tool_filters(q_ok, tool_type_id=tool_type_id, tool_name=tool_name)
    ok = q_ok.scalar() or 0
    return {"total": total, "ok": ok, "pct": round(ok / total * 100, 1) if total else 100.0}


def get_high_maintenance_tools(db: Session, months: int = 6,
                               threshold: int = 10, *, date_from=None,
                               date_to=None, tool_type_id=None,
                               tool_name=None) -> list[dict]:
    """Tools with more than *threshold* OUT movements in the last *months* months."""
    cutoff = date_from or (datetime.utcnow() - timedelta(days=months * 30))
    q = (
        db.query(
            Tool.id, Tool.name,
            func.sum(Movement.quantity).label("total_out"),
        )
        .join(Movement, Movement.tool_id == Tool.id)
        .filter(Movement.movement_type == "OUT", Movement.timestamp >= cutoff)
    )
    if date_to:
        q = q.filter(Movement.timestamp < date_to + timedelta(days=1))
    q = _apply_tool_filters(q, tool_type_id=tool_type_id, tool_name=tool_name)
    rows = (q.group_by(Tool.id, Tool.name)
             .having(func.sum(Movement.quantity) >= threshold)
             .order_by(func.sum(Movement.quantity).desc())
             .all())
    return [{"id": r.id, "name": r.name, "total_out": int(r.total_out)} for r in rows]


def get_rarely_used_tools(db: Session, months: int = 6, *, date_from=None,
                          date_to=None, tool_type_id=None,
                          tool_name=None) -> list[dict]:
    """Tools with stock > 0 but zero OUT movements in the last *months* months.
    Candidate for obsolescence review."""
    cutoff = date_from or (datetime.utcnow() - timedelta(days=months * 30))
    active_ids = (
        db.query(Movement.tool_id)
        .filter(Movement.movement_type == "OUT")
    )
    active_ids = _apply_filters(
        active_ids,
        date_from=cutoff,
        date_to=date_to,
        tool_type_id=tool_type_id,
        tool_name=tool_name,
    )
    active_ids = (
        active_ids
        .distinct()
        .subquery()
    )
    q = db.query(Tool).filter(
        Tool.current_stock > 0,
        ~Tool.id.in_(db.query(active_ids.c.tool_id)),
    )
    q = _apply_tool_filters(q, tool_type_id=tool_type_id, tool_name=tool_name)
    tools = q.order_by(Tool.name).all()
    return [
        {"id": t.id, "name": t.name, "current_stock": t.current_stock,
         "unit_cost": t.unit_cost, "value": round(t.unit_cost * t.current_stock, 2),
         "type": t.tool_type.name if t.tool_type else "—"}
        for t in tools
    ]


def get_monthly_cost(db: Session, months: int = 12, *, date_from=None,
                     date_to=None, tool_type_id=None,
                     tool_name=None) -> list[dict]:
    """Monthly cost of consumed tools (OUT qty × movement unit_cost)."""
    cutoff = date_from or (datetime.utcnow() - timedelta(days=months * 30))
    q = (
        db.query(
            extract("year", Movement.timestamp).label("year"),
            extract("month", Movement.timestamp).label("month"),
            func.sum(Movement.quantity * func.coalesce(Movement.unit_cost, 0)).label("cost"),
        )
        .filter(Movement.movement_type == "OUT")
    )
    q = _apply_filters(
        q,
        date_from=cutoff,
        date_to=date_to,
        tool_type_id=tool_type_id,
        tool_name=tool_name,
    )
    rows = q.group_by("year", "month").order_by("year", "month").all()
    return [{"year": int(r.year), "month": int(r.month),
             "cost": round(float(r.cost or 0), 2)} for r in rows]


def get_total_stock_value(db: Session, *, tool_type_id=None,
                          tool_name=None) -> float:
    """Total value of all stock (unit_cost × current_stock)."""
    q = db.query(func.sum(Tool.unit_cost * Tool.current_stock)).filter(Tool.current_stock > 0)
    q = _apply_tool_filters(q, tool_type_id=tool_type_id, tool_name=tool_name)
    val = q.scalar()
    return round(val, 2) if val else 0.0


# ---------------------------------------------------------------------------
# Financial analytics — consumed cost (Movement.unit_cost based)
# ---------------------------------------------------------------------------

def _resolve_financial_window(date_from, date_to, default_months: int = 12):
    """Return (start, end) dates for financial queries, defaulting to last N months."""
    today = datetime.utcnow().date()
    end = date_to or today
    start = date_from or (end - timedelta(days=default_months * 30))
    if start > end:
        start, end = end, start
    return start, end


def _previous_window(start, end):
    """Return the equivalent window immediately before (start, end)."""
    duration = end - start
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - duration
    return prev_start, prev_end


def _month_window(value: date) -> tuple[date, date]:
    """Return the first and last day of the month for a given date."""
    month_start = value.replace(day=1)
    if value.month == 12:
        next_month = date(value.year + 1, 1, 1)
    else:
        next_month = date(value.year, value.month + 1, 1)
    return month_start, next_month - timedelta(days=1)


def _iter_month_endpoints(start: date, end: date):
    """Yield (year, month, effective_month_end) across the closed date window."""
    cursor, _ = _month_window(start)
    _, end_month = _month_window(end)
    last_cursor = end_month.replace(day=1)

    while cursor <= last_cursor:
        _, cursor_month_end = _month_window(cursor)
        yield cursor.year, cursor.month, min(cursor_month_end, end)

        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)


def get_total_consumed_value(db: Session, *,
                             date_from=None, date_to=None,
                             tool_type_id=None, tool_name=None) -> float:
    """Total consumed value (sum of OUT quantity × movement unit_cost)."""
    q = db.query(
        func.coalesce(
            func.sum(Movement.quantity * func.coalesce(Movement.unit_cost, 0)), 0
        )
    ).filter(Movement.movement_type == "OUT")
    q = _apply_filters(q, date_from=date_from, date_to=date_to,
                       tool_type_id=tool_type_id, tool_name=tool_name)
    return round(float(q.scalar() or 0), 2)


def get_monthly_consumed_value(db: Session, *,
                               date_from=None, date_to=None,
                               tool_type_id=None, tool_name=None) -> list[dict]:
    """Monthly consumed value (OUT) respecting all filters."""
    q = (
        db.query(
            extract("year", Movement.timestamp).label("year"),
            extract("month", Movement.timestamp).label("month"),
            func.sum(Movement.quantity * func.coalesce(Movement.unit_cost, 0)).label("cost"),
        )
        .filter(Movement.movement_type == "OUT")
    )
    q = _apply_filters(q, date_from=date_from, date_to=date_to,
                       tool_type_id=tool_type_id, tool_name=tool_name)
    rows = q.group_by("year", "month").order_by("year", "month").all()
    return [{"year": int(r.year), "month": int(r.month),
             "cost": round(float(r.cost or 0), 2)} for r in rows]


def get_cost_share_by_tool(db: Session, *, limit: int = 10,
                           date_from=None, date_to=None,
                           tool_type_id=None, tool_name=None) -> list[dict]:
    """Top tools by consumed cost in the period with their participation share."""
    q = (
        db.query(
            Tool.id, Tool.name,
            func.sum(Movement.quantity * func.coalesce(Movement.unit_cost, 0)).label("cost"),
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

    rows = (
        q.group_by(Tool.id, Tool.name)
         .order_by(func.sum(Movement.quantity * func.coalesce(Movement.unit_cost, 0)).desc())
         .all()
    )
    total = sum(float(r.cost or 0) for r in rows)
    top = rows[:limit] if limit else rows
    return [
        {
            "id": r.id,
            "name": r.name,
            "cost": round(float(r.cost or 0), 2),
            "share_pct": round((float(r.cost or 0) / total * 100), 2) if total else 0.0,
        }
        for r in top
    ]


# ---------------------------------------------------------------------------
# Financial analytics — purchase price (ToolPriceHistory based)
# ---------------------------------------------------------------------------

def get_average_purchase_price_series(db: Session, *,
                                      date_from=None, date_to=None,
                                      tool_type_id=None, tool_name=None) -> list[dict]:
    """
    Monthly average price (R$) based on the last known price of each tool.

    For every month in the filtered window, each tool contributes with its latest
    known purchase price up to that month end. This avoids distorting the series
    toward only the tools that happened to be purchased in that specific month.
    """
    start, end = _resolve_financial_window(date_from, date_to)

    q = (
        db.query(
            ToolPriceHistory.tool_id.label("tool_id"),
            ToolPriceHistory.data_entrega.label("data_entrega"),
            ToolPriceHistory.preco_unitario.label("preco_unitario"),
            ToolPriceHistory.imported_at.label("imported_at"),
            ToolPriceHistory.id.label("id"),
        )
        .filter(ToolPriceHistory.data_entrega.isnot(None))
        .filter(ToolPriceHistory.data_entrega <= end)
    )
    if tool_type_id or tool_name:
        q = q.join(Tool, Tool.id == ToolPriceHistory.tool_id)
        if tool_type_id:
            q = q.filter(Tool.tool_type_id == tool_type_id)
        if tool_name:
            q = q.filter(Tool.name.ilike(f"%{tool_name}%"))

    rows = (
        q.order_by(
            ToolPriceHistory.tool_id,
            ToolPriceHistory.data_entrega,
            ToolPriceHistory.imported_at,
            ToolPriceHistory.id,
        )
        .all()
    )
    if not rows:
        return []

    history_by_tool: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for row in rows:
        history_by_tool[row.tool_id].append(
            (row.data_entrega, float(row.preco_unitario or 0))
        )

    last_index_by_tool = {tool_id: -1 for tool_id in history_by_tool}

    series = []
    for year, month, month_end in _iter_month_endpoints(start, end):
        month_prices = []
        for tool_id, history in history_by_tool.items():
            current_index = last_index_by_tool[tool_id]
            while current_index + 1 < len(history):
                hist_date, _ = history[current_index + 1]
                if hist_date and hist_date <= month_end:
                    current_index += 1
                else:
                    break

            last_index_by_tool[tool_id] = current_index
            if current_index >= 0:
                month_prices.append(history[current_index][1])

        if not month_prices:
            continue

        avg = round(sum(month_prices) / len(month_prices), 4)
        series.append({"year": year, "month": month, "avg_price": avg})
    return series


def get_latest_price_variation(db: Session, *,
                               date_from=None, date_to=None,
                               tool_type_id=None, tool_name=None,
                               limit: int | None = 50) -> list[dict]:
    """
    For each tool with at least 2 price history records, return the
    variation between the latest and the previous purchase price.

    Also enrich each row with consumed value participation in the filtered
    window (quantity consumed × movement unit cost).
    """
    q = (
        db.query(ToolPriceHistory, Tool, ToolType)
        .join(Tool, Tool.id == ToolPriceHistory.tool_id)
        .join(ToolType, ToolType.id == Tool.tool_type_id)
    )
    if tool_type_id:
        q = q.filter(Tool.tool_type_id == tool_type_id)
    if tool_name:
        q = q.filter(Tool.name.ilike(f"%{tool_name}%"))

    records = q.all()
    by_tool: dict[int, list] = defaultdict(list)
    tools_by_id: dict[int, dict] = {}
    for ph, tool, tool_type in records:
        by_tool[tool.id].append(ph)
        tools_by_id[tool.id] = {
            "name": tool.name,
            "tool_type_id": tool.tool_type_id,
            "tool_type_name": tool_type.name,
        }

    spend_map = {
        row["id"]: row
        for row in get_cost_share_by_tool(
            db,
            limit=0,
            date_from=date_from,
            date_to=date_to,
            tool_type_id=tool_type_id,
            tool_name=tool_name,
        )
    }

    def _sort_key(ph: ToolPriceHistory):
        return (
            ph.data_entrega or date.min,
            ph.imported_at or datetime.min,
            ph.id or 0,
        )

    results = []
    for tool_id, items in by_tool.items():
        if len(items) < 2:
            continue
        items.sort(key=_sort_key, reverse=True)
        last, prev = items[0], items[1]
        last_price = float(last.preco_unitario or 0)
        prev_price = float(prev.preco_unitario or 0)
        if prev_price == 0:
            continue
        var_abs = round(last_price - prev_price, 4)
        var_pct = round((var_abs / prev_price) * 100, 2)
        spend_info = spend_map.get(tool_id, {})
        results.append({
            "tool_id": tool_id,
            "name": tools_by_id[tool_id]["name"],
            "tool_type_id": tools_by_id[tool_id]["tool_type_id"],
            "tool_type_name": tools_by_id[tool_id]["tool_type_name"],
            "last_price": round(last_price, 4),
            "prev_price": round(prev_price, 4),
            "var_abs": var_abs,
            "var_pct": var_pct,
            "consumed_value": round(float(spend_info.get("cost", 0) or 0), 2),
            "spent_share_pct": round(float(spend_info.get("share_pct", 0) or 0), 2),
            "last_date": last.data_entrega.isoformat() if last.data_entrega else None,
            "prev_date": prev.data_entrega.isoformat() if prev.data_entrega else None,
        })

    # Sort by absolute percentage variation desc, then trim
    results.sort(key=lambda x: abs(x["var_pct"]), reverse=True)
    return results[:limit] if limit else results


def get_average_purchase_price_overall(db: Session, *,
                                       date_from=None, date_to=None,
                                       tool_type_id=None, tool_name=None) -> float:
    """Average of the monthly purchase-price series across the filtered scope."""
    series = get_average_purchase_price_series(
        db, date_from=date_from, date_to=date_to,
        tool_type_id=tool_type_id, tool_name=tool_name,
    )
    if not series:
        return 0.0
    return round(sum(s["avg_price"] for s in series) / len(series), 4)


def _average_cost_by_tool_map(db: Session, *, date_from, date_to,
                              tool_type_id=None, tool_name=None) -> dict[int, dict]:
    """
    Internal: returns the average monthly cost per tool across the window.

    Each tool contributes with its last known price at each month end within the
    window, so utilization and purchase quantity do not affect the result.
    """
    q = (
        db.query(
            ToolPriceHistory.tool_id.label("tool_id"),
            Tool.name.label("name"),
            ToolPriceHistory.data_entrega.label("data_entrega"),
            ToolPriceHistory.preco_unitario.label("preco_unitario"),
            ToolPriceHistory.imported_at.label("imported_at"),
            ToolPriceHistory.id.label("id"),
        )
        .join(Tool, Tool.id == ToolPriceHistory.tool_id)
        .filter(ToolPriceHistory.data_entrega.isnot(None))
        .filter(ToolPriceHistory.data_entrega <= date_to)
    )
    if tool_type_id:
        q = q.filter(Tool.tool_type_id == tool_type_id)
    if tool_name:
        q = q.filter(Tool.name.ilike(f"%{tool_name}%"))

    rows = (
        q.order_by(
            ToolPriceHistory.tool_id,
            ToolPriceHistory.data_entrega,
            ToolPriceHistory.imported_at,
            ToolPriceHistory.id,
        )
        .all()
    )
    if not rows:
        return {}

    history_by_tool: dict[int, dict] = {}
    for row in rows:
        tool_entry = history_by_tool.setdefault(
            row.tool_id,
            {"name": row.name, "history": []},
        )
        tool_entry["history"].append(
            (row.data_entrega, float(row.preco_unitario or 0))
        )

    index_by_tool = {tool_id: -1 for tool_id in history_by_tool}
    aggregates = {
        tool_id: {"name": data["name"], "sum": 0.0, "count": 0}
        for tool_id, data in history_by_tool.items()
    }

    for _, _, month_end in _iter_month_endpoints(date_from, date_to):
        for tool_id, data in history_by_tool.items():
            history = data["history"]
            current_index = index_by_tool[tool_id]
            while current_index + 1 < len(history):
                hist_date, _ = history[current_index + 1]
                if hist_date and hist_date <= month_end:
                    current_index += 1
                else:
                    break

            index_by_tool[tool_id] = current_index
            if current_index >= 0:
                aggregates[tool_id]["sum"] += history[current_index][1]
                aggregates[tool_id]["count"] += 1

    return {
        tool_id: {
            "name": data["name"],
            "cost": round(data["sum"] / data["count"], 4),
        }
        for tool_id, data in aggregates.items()
        if data["count"]
    }


def get_top_average_cost_impact_tools(db: Session, *,
                                      date_from=None, date_to=None,
                                      tool_type_id=None, tool_name=None,
                                      limit: int = 3) -> dict:
    """
    Compare average tool cost between the current and previous equivalent windows.

    This ranking ignores utilization and quantity. Each tool is compared by its
    average month-end price across each window.
    """
    start, end = _resolve_financial_window(date_from, date_to)
    prev_start, prev_end = _previous_window(start, end)

    current = _average_cost_by_tool_map(
        db, date_from=start, date_to=end,
        tool_type_id=tool_type_id, tool_name=tool_name,
    )
    previous = _average_cost_by_tool_map(
        db, date_from=prev_start, date_to=prev_end,
        tool_type_id=tool_type_id, tool_name=tool_name,
    )

    tool_ids = set(current.keys()) | set(previous.keys())
    impacts = []
    for tid in tool_ids:
        cur = current.get(tid, {"name": previous.get(tid, {}).get("name", ""), "cost": 0.0})
        prv = previous.get(tid, {"name": cur.get("name", ""), "cost": 0.0})
        name = cur.get("name") or prv.get("name") or ""
        cur_cost = float(cur.get("cost", 0.0))
        prv_cost = float(prv.get("cost", 0.0))
        delta_abs = cur_cost - prv_cost
        delta_pct = ((delta_abs / prv_cost) * 100) if prv_cost else (100.0 if cur_cost else 0.0)
        impacts.append({
            "tool_id": tid,
            "name": name,
            "current_cost": round(cur_cost, 4),
            "previous_cost": round(prv_cost, 4),
            "delta_abs": round(delta_abs, 4),
            "delta_pct": round(delta_pct, 2),
        })

    top_up = sorted(
        [item for item in impacts if item["delta_abs"] > 0],
        key=lambda item: item["delta_abs"],
        reverse=True,
    )[:limit]
    top_down = sorted(
        [item for item in impacts if item["delta_abs"] < 0],
        key=lambda item: item["delta_abs"],
    )[:limit]

    return {
        "current_window": {"start": start.isoformat(), "end": end.isoformat()},
        "previous_window": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
        "current_total": round(sum(item["current_cost"] for item in impacts), 4),
        "previous_total": round(sum(item["previous_cost"] for item in impacts), 4),
        "top_up": top_up,
        "top_down": top_down,
    }


# ---------------------------------------------------------------------------
# Financial analytics — impact ranking (current vs previous window)
# ---------------------------------------------------------------------------

def _cost_by_tool_map(db: Session, *, date_from, date_to,
                      tool_type_id=None, tool_name=None) -> dict[int, dict]:
    """Internal: returns {tool_id: {"name": ..., "cost": float}} for window."""
    q = (
        db.query(
            Tool.id, Tool.name,
            func.sum(Movement.quantity * func.coalesce(Movement.unit_cost, 0)).label("cost"),
        )
        .join(Movement, Movement.tool_id == Tool.id)
        .filter(Movement.movement_type == "OUT")
        .filter(Movement.timestamp >= date_from)
        .filter(Movement.timestamp < date_to + timedelta(days=1))
    )
    if tool_type_id:
        q = q.filter(Tool.tool_type_id == tool_type_id)
    if tool_name:
        q = q.filter(Tool.name.ilike(f"%{tool_name}%"))
    rows = q.group_by(Tool.id, Tool.name).all()
    return {
        r.id: {"name": r.name, "cost": float(r.cost or 0)}
        for r in rows
    }


def get_top_cost_impact_tools(db: Session, *,
                              date_from=None, date_to=None,
                              tool_type_id=None, tool_name=None,
                              limit: int = 3) -> dict:
    """
    Compare consumed cost between current window and the equivalent previous
    window. Returns top tools driving cost up and top driving cost down.
    """
    start, end = _resolve_financial_window(date_from, date_to)
    prev_start, prev_end = _previous_window(start, end)

    current = _cost_by_tool_map(
        db, date_from=start, date_to=end,
        tool_type_id=tool_type_id, tool_name=tool_name,
    )
    previous = _cost_by_tool_map(
        db, date_from=prev_start, date_to=prev_end,
        tool_type_id=tool_type_id, tool_name=tool_name,
    )

    tool_ids = set(current.keys()) | set(previous.keys())
    impacts = []
    for tid in tool_ids:
        cur = current.get(tid, {"name": previous.get(tid, {}).get("name", ""), "cost": 0.0})
        prv = previous.get(tid, {"name": cur.get("name", ""), "cost": 0.0})
        name = cur.get("name") or prv.get("name") or ""
        cur_cost = float(cur.get("cost", 0.0))
        prv_cost = float(prv.get("cost", 0.0))
        delta_abs = cur_cost - prv_cost
        delta_pct = ((delta_abs / prv_cost) * 100) if prv_cost else (100.0 if cur_cost else 0.0)
        impacts.append({
            "tool_id": tid,
            "name": name,
            "current_cost": round(cur_cost, 2),
            "previous_cost": round(prv_cost, 2),
            "delta_abs": round(delta_abs, 2),
            "delta_pct": round(delta_pct, 2),
        })

    top_up = sorted([i for i in impacts if i["delta_abs"] > 0],
                    key=lambda x: x["delta_abs"], reverse=True)[:limit]
    top_down = sorted([i for i in impacts if i["delta_abs"] < 0],
                      key=lambda x: x["delta_abs"])[:limit]

    return {
        "current_window": {"start": start.isoformat(), "end": end.isoformat()},
        "previous_window": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
        "current_total": round(sum(i["current_cost"] for i in impacts), 2),
        "previous_total": round(sum(i["previous_cost"] for i in impacts), 2),
        "top_up": top_up,
        "top_down": top_down,
    }
