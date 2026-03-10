"""
Movements log router – read-only audit trail with filtering.
"""

from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Movement, Tool

router = APIRouter(prefix="/movements", tags=["movements"])


@router.get("/")
def movements_list(
    request: Request,
    tool_id: int = Query(0),
    sort: str = Query("desc"),
    db: Session = Depends(get_db),
):
    query = db.query(Movement)

    if tool_id:
        query = query.filter(Movement.tool_id == tool_id)

    if sort == "asc":
        query = query.order_by(Movement.timestamp.asc())
    else:
        query = query.order_by(Movement.timestamp.desc())

    movements = query.all()
    tools = db.query(Tool).order_by(Tool.name).all()

    return request.app.state.templates.TemplateResponse(
        "movements/index.html",
        {
            "request": request,
            "movements": movements,
            "tools": tools,
            "selected_tool_id": tool_id,
            "sort": sort,
        },
    )
