"""
Movements log router – read-only audit trail with filtering.
"""

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Movement, Tool
from app.auth import require_login
from app.services.movements import return_loan

router = APIRouter(prefix="/movements", tags=["movements"], dependencies=[Depends(require_login)])


@router.get("/")
def movements_list(
    request: Request,
    tool_id: int = Query(0),
    sort: str = Query("desc"),
    category: str = Query("EMPRESTIMO"),
    db: Session = Depends(get_db),
):
    query = db.query(Movement)

    # Filter by category
    category = category.upper()
    if category not in ("EMPRESTIMO", "REPOSICAO"):
        category = "EMPRESTIMO"
    query = query.filter(Movement.category == category)

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
            "category": category,
        },
    )


@router.post("/{movement_id}/return")
def movement_return(
    movement_id: int,
    db: Session = Depends(get_db),
):
    """Mark a loan as returned."""
    try:
        return_loan(db, movement_id)
    except ValueError:
        pass
    return RedirectResponse(url="/movements?category=EMPRESTIMO", status_code=303)
