"""
Dashboard router – main landing page with summary cards and charts.
"""

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tool
from app.services.analytics import (
    get_monthly_consumption,
    get_top_consumed_tools,
    get_tools_below_minimum,
    get_total_movements_this_month,
    get_total_consumption_this_month,
)
from app.services.forecasting import get_all_predictions

router = APIRouter()


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    total_tools = db.query(Tool).count()
    tools_below = get_tools_below_minimum(db)
    movements_month = get_total_movements_this_month(db)
    consumption_month = get_total_consumption_this_month(db)
    monthly = get_monthly_consumption(db)
    top_consumed = get_top_consumed_tools(db)
    predictions = get_all_predictions(db)

    # Format month labels for chart
    month_names = [
        "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    chart_labels = [f"{month_names[m['month']]} {m['year']}" for m in monthly]
    chart_data = [m["total"] for m in monthly]

    top_labels = [t["name"][:25] for t in top_consumed]
    top_data = [t["total"] for t in top_consumed]

    # Tools approaching minimum stock (within 10%)
    approaching = []
    for tool in db.query(Tool).filter(Tool.min_stock > 0).all():
        if tool.current_stock > tool.min_stock and tool.current_stock <= tool.min_stock * 1.1:
            approaching.append(tool)

    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_tools": total_tools,
            "tools_below": tools_below,
            "tools_below_count": len(tools_below),
            "movements_month": movements_month,
            "consumption_month": consumption_month,
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "top_labels": top_labels,
            "top_data": top_data,
            "predictions": predictions,
            "approaching": approaching,
        },
    )
