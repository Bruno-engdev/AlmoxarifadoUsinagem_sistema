"""
Tools router – CRUD, stock add/remove, search, tool registration.
"""

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tool, ToolType, ToolParameter, Employee, Machine
from app.auth import require_login
from app.services.movements import register_movement

router = APIRouter(prefix="/tools", tags=["tools"], dependencies=[Depends(require_login)])


@router.get("/")
def tools_list(
    request: Request,
    search: str = Query("", alias="search"),
    db: Session = Depends(get_db),
):
    """Display tools table with search and status highlighting."""
    query = db.query(Tool).join(ToolType)

    if search:
        like = f"%{search}%"
        query = query.filter(
            (Tool.name.ilike(like)) | (ToolType.name.ilike(like))
        )

    tools = query.order_by(Tool.name).all()

    employees = db.query(Employee).order_by(Employee.name).all()
    machines = db.query(Machine).order_by(Machine.name).all()

    return request.app.state.templates.TemplateResponse(
        "tools/index.html",
        {
            "request": request,
            "tools": tools,
            "employees": employees,
            "machines": machines,
            "search": search,
        },
    )


@router.get("/create")
def tool_create_form(request: Request, db: Session = Depends(get_db)):
    tool_types = db.query(ToolType).order_by(ToolType.name).all()
    return request.app.state.templates.TemplateResponse(
        "tools/create.html",
        {"request": request, "tool_types": tool_types},
    )


@router.post("/create")
async def tool_create(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "")
    origin_id = form.get("origin_id", "")
    tool_type_id = int(form.get("tool_type_id", 0))
    description = form.get("description", "")
    min_stock = int(form.get("min_stock", 0))
    max_stock = int(form.get("max_stock", 0))

    gaveta = form.get("gaveta", "")
    divisoria = form.get("divisoria", "")
    location = f"G{gaveta}D{divisoria}" if gaveta and divisoria else ""

    tool = Tool(
        name=name,
        origin_id=origin_id,
        tool_type_id=tool_type_id,
        description=description,
        location=location,
        min_stock=min_stock,
        max_stock=max_stock,
        current_stock=0,
    )
    db.add(tool)
    db.flush()  # get tool.id

    # Dynamic parameters
    param_names = form.getlist("param_name")
    param_values = form.getlist("param_value")
    for pn, pv in zip(param_names, param_values):
        if pn.strip():
            db.add(ToolParameter(tool_id=tool.id, parameter_name=pn.strip(), parameter_value=pv.strip()))

    db.commit()
    return RedirectResponse(url="/tools", status_code=303)


@router.post("/movement")
async def tool_movement(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Add Stock (IN) or Remove Stock (OUT) via form submission."""
    form = await request.form()
    tool_id = int(form.get("tool_id", 0))
    movement_type = form.get("movement_type", "IN").upper()
    quantity = int(form.get("quantity", 0))
    notes = form.get("notes", "")
    category = form.get("category", "EMPRESTIMO").upper()

    employee_id = None
    machine_id = None
    if category == "REPOSICAO" and movement_type == "OUT":
        machine_id = int(form.get("machine_id", 0)) or None
    else:
        employee_id = int(form.get("employee_id", 0)) or None

    try:
        register_movement(
            db, tool_id, employee_id, movement_type, quantity, notes,
            category=category, machine_id=machine_id,
        )
    except ValueError:
        pass  # Silently redirect – in production add flash messages

    return RedirectResponse(url="/tools", status_code=303)


@router.get("/{tool_id}")
def tool_detail(tool_id: int, request: Request, db: Session = Depends(get_db)):
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        return RedirectResponse(url="/tools", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "tools/detail.html",
        {"request": request, "tool": tool},
    )
