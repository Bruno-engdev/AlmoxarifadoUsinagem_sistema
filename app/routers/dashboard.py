"""
Dashboard router – main landing page with KPI cards, charts, and tables.
Supports query-string filters: date_from, date_to, tool_type_id, tool_name.
"""

from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tool, ToolType
from app.auth import require_login
from app.services.analytics import (
    get_monthly_consumption,
    get_monthly_in_out,
    get_top_consumed_tools,
    get_tools_below_minimum,
    get_stock_by_type,
    get_idle_tools,
    get_recent_movements,
    get_total_consumption_period,
    get_total_movements_period,
    get_avg_tool_lifespan,
    get_capital_tied_idle,
    get_critical_availability,
    get_high_maintenance_tools,
    get_rarely_used_tools,
    get_monthly_cost,
    get_total_stock_value,
)
from app.services.forecasting import get_all_predictions

router = APIRouter(dependencies=[Depends(require_login)])

MONTH_NAMES = [
    "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("/")
def dashboard(
    request: Request,
    date_from: str = Query("", alias="date_from"),
    date_to: str = Query("", alias="date_to"),
    tool_type_id: int = Query(0, alias="tool_type_id"),
    tool_name: str = Query("", alias="tool_name"),
    idle_days: int = Query(90, alias="idle_days"),
    db: Session = Depends(get_db),
):
    # Parse filter values
    d_from = _parse_date(date_from) if date_from else None
    d_to = _parse_date(date_to) if date_to else None
    tt_id = tool_type_id if tool_type_id else None
    t_name = tool_name.strip() if tool_name else None

    # Shared filter kwargs
    flt = dict(date_from=d_from, date_to=d_to,
               tool_type_id=tt_id, tool_name=t_name)

    # ---- KPI totals ----
    consumption_period = get_total_consumption_period(db, **flt)
    movements_period = get_total_movements_period(db, **flt)
    tools_below = get_tools_below_minimum(db)
    total_tools = db.query(Tool).count()

    # ---- Charts data ----
    monthly = get_monthly_consumption(db, **flt)
    in_out = get_monthly_in_out(db, **flt)
    top_consumed = get_top_consumed_tools(db, **flt)
    stock_by_type = get_stock_by_type(db)

    # Format chart labels
    chart_labels = [f"{MONTH_NAMES[m['month']]} {m['year']}" for m in monthly]
    chart_data = [m["total"] for m in monthly]

    io_labels = [f"{MONTH_NAMES[m['month']]} {m['year']}" for m in in_out]
    io_in = [m["total_in"] for m in in_out]
    io_out = [m["total_out"] for m in in_out]

    top_labels = [t["name"][:30] for t in top_consumed]
    top_data = [t["total"] for t in top_consumed]

    sbt_labels = [s["type_name"] for s in stock_by_type]
    sbt_data = [s["total_stock"] for s in stock_by_type]

    # ---- Tables ----
    idle_tools = get_idle_tools(db, days=idle_days)
    recent = get_recent_movements(db, limit=10)
    predictions = get_all_predictions(db)

    # Approaching minimum
    approaching = [
        t for t in db.query(Tool).filter(Tool.min_stock > 0).all()
        if t.current_stock > t.min_stock and t.current_stock <= t.min_stock * 1.1
    ]

    # ---- Strategic KPIs ----
    avg_lifespan = get_avg_tool_lifespan(db)
    capital_idle = get_capital_tied_idle(db, days=idle_days)
    critical_avail = get_critical_availability(db)
    high_maint = get_high_maintenance_tools(db)
    rarely_used = get_rarely_used_tools(db)
    total_stock_value = get_total_stock_value(db)
    cost_monthly = get_monthly_cost(db)

    cost_labels = [f"{MONTH_NAMES[c['month']]} {c['year']}" for c in cost_monthly]
    cost_data = [c["cost"] for c in cost_monthly]

    # Tool types for the filter dropdown
    tool_types = db.query(ToolType).order_by(ToolType.name).all()

    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_page": "dashboard",
            # KPIs
            "total_tools": total_tools,
            "consumption_period": consumption_period,
            "movements_period": movements_period,
            "tools_below": tools_below,
            "tools_below_count": len(tools_below),
            # Charts
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "io_labels": io_labels,
            "io_in": io_in,
            "io_out": io_out,
            "top_labels": top_labels,
            "top_data": top_data,
            "sbt_labels": sbt_labels,
            "sbt_data": sbt_data,
            # Tables
            "idle_tools": idle_tools,
            "recent": recent,
            "predictions": predictions,
            "approaching": approaching,
            # Strategic KPIs
            "avg_lifespan": avg_lifespan,
            "capital_idle": capital_idle,
            "critical_avail": critical_avail,
            "high_maint": high_maint,
            "rarely_used": rarely_used,
            "total_stock_value": total_stock_value,
            "cost_labels": cost_labels,
            "cost_data": cost_data,
            # Filter state (to keep inputs filled)
            "f_date_from": date_from,
            "f_date_to": date_to,
            "f_tool_type_id": tool_type_id,
            "f_tool_name": tool_name,
            "f_idle_days": idle_days,
            "tool_types": tool_types,
        },
    )


# ------------------------------------------------------------------
# AJAX API – return dashboard data as JSON for dynamic filtering
# ------------------------------------------------------------------

@router.get("/api/dashboard")
def api_dashboard(
    date_from: str = Query("", alias="date_from"),
    date_to: str = Query("", alias="date_to"),
    tool_type_id: int = Query(0, alias="tool_type_id"),
    tool_name: str = Query("", alias="tool_name"),
    idle_days: int = Query(90, alias="idle_days"),
    db: Session = Depends(get_db),
):
    d_from = _parse_date(date_from) if date_from else None
    d_to = _parse_date(date_to) if date_to else None
    tt_id = tool_type_id if tool_type_id else None
    t_name = tool_name.strip() if tool_name else None

    flt = dict(date_from=d_from, date_to=d_to,
               tool_type_id=tt_id, tool_name=t_name)

    consumption_period = get_total_consumption_period(db, **flt)
    movements_period = get_total_movements_period(db, **flt)
    tools_below = get_tools_below_minimum(db)
    total_tools = db.query(Tool).count()

    monthly = get_monthly_consumption(db, **flt)
    in_out = get_monthly_in_out(db, **flt)
    top_consumed = get_top_consumed_tools(db, **flt)
    stock_by_type = get_stock_by_type(db)
    cost_monthly = get_monthly_cost(db)

    return JSONResponse({
        "total_tools": total_tools,
        "consumption_period": consumption_period,
        "movements_period": movements_period,
        "tools_below_count": len(tools_below),
        # Charts
        "chart_labels": [f"{MONTH_NAMES[m['month']]} {m['year']}" for m in monthly],
        "chart_data": [m["total"] for m in monthly],
        "io_labels": [f"{MONTH_NAMES[m['month']]} {m['year']}" for m in in_out],
        "io_in": [m["total_in"] for m in in_out],
        "io_out": [m["total_out"] for m in in_out],
        "top_labels": [t["name"][:30] for t in top_consumed],
        "top_data": [t["total"] for t in top_consumed],
        "sbt_labels": [s["type_name"] for s in stock_by_type],
        "sbt_data": [s["total_stock"] for s in stock_by_type],
        # Strategic
        "avg_lifespan": get_avg_tool_lifespan(db),
        "capital_idle": get_capital_tied_idle(db, days=idle_days),
        "critical_avail": get_critical_availability(db),
        "total_stock_value": get_total_stock_value(db),
        "cost_labels": [f"{MONTH_NAMES[c['month']]} {c['year']}" for c in cost_monthly],
        "cost_data": [c["cost"] for c in cost_monthly],
    })
