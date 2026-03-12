"""
Employees router – CRUD for employees.
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/")
def employee_list(request: Request, db: Session = Depends(get_db)):
    employees = db.query(Employee).order_by(Employee.name).all()
    return request.app.state.templates.TemplateResponse(
        "employees/index.html",
        {"request": request, "employees": employees},
    )


@router.post("/create")
async def employee_create(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    department = form.get("department", "").strip()
    if name:
        db.add(Employee(name=name, department=department))
        db.commit()
    return RedirectResponse(url="/employees", status_code=303)


@router.get("/{employee_id}/edit")
def employee_edit_form(employee_id: int, request: Request, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        return RedirectResponse(url="/employees", status_code=303)
    employees = db.query(Employee).order_by(Employee.name).all()
    return request.app.state.templates.TemplateResponse(
        "employees/index.html",
        {"request": request, "employees": employees, "editing": emp},
    )


@router.post("/{employee_id}/edit")
async def employee_update(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if emp:
        emp.name = form.get("name", emp.name).strip()
        emp.department = form.get("department", emp.department).strip()
        db.commit()
    return RedirectResponse(url="/employees", status_code=303)


@router.post("/{employee_id}/delete")
def employee_delete(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if emp:
        db.delete(emp)
        db.commit()
    return RedirectResponse(url="/employees", status_code=303)
