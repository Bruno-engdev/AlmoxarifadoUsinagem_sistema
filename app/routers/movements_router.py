"""
Movements log router – read-only audit trail with filtering.
Admin-only mutations (manual entry, edit, delete) are gated by require_admin.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Movement, Tool, Employee, Machine
from app.auth import require_login, require_admin
from app.services.movements import (
    return_loan,
    create_manual_movement,
    update_movement_admin,
    delete_movement_admin,
)

router = APIRouter(prefix="/movements", tags=["movements"], dependencies=[Depends(require_login)])


def _parse_form_int(form, key: str) -> int | None:
    raw = (form.get(key) or "").strip()
    if not raw:
        return None
    try:
        v = int(raw)
        return v or None
    except ValueError:
        return None


def _parse_form_float(form, key: str) -> float | None:
    raw = (form.get(key) or "").strip()
    if raw == "":
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def _parse_form_datetime(form, key: str) -> datetime | None:
    raw = (form.get(key) or "").strip()
    if not raw:
        return None
    # accept "YYYY-MM-DDTHH:MM" (datetime-local) or "YYYY-MM-DD HH:MM"
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"Data/hora inválida: {raw}")


def _redirect_back(form, *, flash: str | None = None, error: str | None = None) -> RedirectResponse:
    raw = (form.get("redirect_to") or "/movements").strip()
    if not raw.startswith("/"):
        raw = "/movements"
    qs: dict[str, str] = {}
    if flash:
        qs["flash"] = flash
    if error:
        qs["error"] = error
    if qs:
        sep = "&" if "?" in raw else "?"
        raw = f"{raw}{sep}{urlencode(qs)}"
    return RedirectResponse(url=raw, status_code=303)


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
    flash: str = Query(""),
    error: str = Query(""),
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
    employees = db.query(Employee).order_by(Employee.name).all()
    machines = db.query(Machine).order_by(Machine.name).all()

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="movements/index.html",
        context={
            "movements": movements,
            "tools": tools,
            "employees": employees,
            "machines": machines,
            "selected_tool_id": tool_id,
            "sort": sort,
            "category": category,
            "search": search,
            "search_col": search_col,
            "date_from": date_from,
            "date_to": date_to,
            "flash_message": flash,
            "error_message": error,
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


# ---------------------------------------------------------------------------
# Admin-only mutations
# ---------------------------------------------------------------------------

@router.post("/manual", dependencies=[Depends(require_admin)])
async def movement_manual_create(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        tool_id = int(form.get("tool_id") or 0)
        movement_type = (form.get("movement_type") or "").upper()
        category = (form.get("category") or "").upper()
        quantity = int(form.get("quantity") or 0)
        timestamp = _parse_form_datetime(form, "timestamp")
        if timestamp is None:
            raise ValueError("Informe a data/hora.")
        employee_id = _parse_form_int(form, "employee_id")
        machine_id = _parse_form_int(form, "machine_id")
        unit_cost = _parse_form_float(form, "unit_cost")
        notes = (form.get("notes") or "").strip()
        loan_status = (form.get("loan_status") or "").upper() or None

        create_manual_movement(
            db,
            tool_id=tool_id,
            movement_type=movement_type,
            category=category,
            quantity=quantity,
            timestamp=timestamp,
            employee_id=employee_id,
            machine_id=machine_id,
            notes=notes,
            unit_cost=unit_cost,
            loan_status=loan_status,
        )
    except ValueError as exc:
        return _redirect_back(form, error=str(exc))
    return _redirect_back(form, flash="Movimentação criada manualmente.")


@router.post("/{movement_id}/update", dependencies=[Depends(require_admin)])
async def movement_update(movement_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        kwargs: dict = {}
        if (form.get("quantity") or "").strip():
            kwargs["quantity"] = int(form.get("quantity"))
        ts = _parse_form_datetime(form, "timestamp")
        if ts is not None:
            kwargs["timestamp"] = ts
        if "notes" in form:
            kwargs["notes"] = (form.get("notes") or "").strip()
        uc = _parse_form_float(form, "unit_cost")
        if uc is not None:
            kwargs["unit_cost"] = uc
        if (form.get("employee_id") or "").strip():
            kwargs["employee_id"] = _parse_form_int(form, "employee_id")
        if (form.get("machine_id") or "").strip():
            kwargs["machine_id"] = _parse_form_int(form, "machine_id")
        ls = (form.get("loan_status") or "").upper().strip()
        if ls:
            kwargs["loan_status"] = ls
            rt = _parse_form_datetime(form, "return_timestamp")
            if rt is not None:
                kwargs["return_timestamp"] = rt

        update_movement_admin(db, movement_id, **kwargs)
    except ValueError as exc:
        return _redirect_back(form, error=str(exc))
    return _redirect_back(form, flash="Movimentação atualizada.")


@router.post("/{movement_id}/delete", dependencies=[Depends(require_admin)])
async def movement_delete(movement_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        delete_movement_admin(db, movement_id)
    except ValueError as exc:
        return _redirect_back(form, error=str(exc))
    return _redirect_back(form, flash="Movimentação excluída e estoque ajustado.")
