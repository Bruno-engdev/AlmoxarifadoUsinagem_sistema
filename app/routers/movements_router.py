"""
Movements log router – read-only audit trail with filtering.
"""

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Movement, Tool, Employee, Machine
from app.auth import require_login
from app.services.movements import return_loan

router = APIRouter(prefix="/movements", tags=["movements"], dependencies=[Depends(require_login)])


@router.get("/")
def movements_list(
    request: Request,
    tool_id: int = Query(0),
    sort: str = Query("desc"),
    category: str = Query("EMPRESTIMO"),
    search: str = Query(""),
    search_col: str = Query("all"),
    date_from: str = Query(""),
    date_to: str = Query(""),
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

    # Date range filter
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Movement.timestamp >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Movement.timestamp < dt_to)
        except ValueError:
            pass

    # Text search
    if search:
        term = f"%{search}%"
        if search_col == "tool":
            query = query.join(Tool).filter(Tool.name.ilike(term))
        elif search_col == "employee":
            query = query.join(Employee).filter(Employee.name.ilike(term))
        elif search_col == "machine":
            query = query.join(Machine).filter(Machine.name.ilike(term))
        elif search_col == "type":
            # map friendly text to DB value
            type_map = {"entrada": "IN", "saída": "OUT", "saida": "OUT"}
            db_val = type_map.get(search.strip().lower(), search)
            query = query.filter(Movement.movement_type.ilike(f"%{db_val}%"))
        elif search_col == "notes":
            query = query.filter(Movement.notes.ilike(term))
        elif search_col == "status":
            query = query.filter(Movement.loan_status.ilike(term))
        else:
            # "all" — search across tool name, employee name, machine name, notes
            query = (
                query
                .outerjoin(Tool, Movement.tool_id == Tool.id)
                .outerjoin(Employee, Movement.employee_id == Employee.id)
                .outerjoin(Machine, Movement.machine_id == Machine.id)
                .filter(
                    Tool.name.ilike(term)
                    | Employee.name.ilike(term)
                    | Machine.name.ilike(term)
                    | Movement.notes.ilike(term)
                )
            )

    if sort == "asc":
        query = query.order_by(Movement.timestamp.asc())
    else:
        query = query.order_by(Movement.timestamp.desc())

    movements = query.all()
    tools = db.query(Tool).order_by(Tool.name).all()

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="movements/index.html",
        context={
            "movements": movements,
            "tools": tools,
            "selected_tool_id": tool_id,
            "sort": sort,
            "category": category,
            "search": search,
            "search_col": search_col,
            "date_from": date_from,
            "date_to": date_to,
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
