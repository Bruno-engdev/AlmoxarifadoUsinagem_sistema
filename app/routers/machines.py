"""
Machines router – manage machines in the machining sector.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Machine
from app.auth import require_login

router = APIRouter(prefix="/machines", tags=["machines"], dependencies=[Depends(require_login)])


@router.get("/")
def machines_list(request: Request, db: Session = Depends(get_db)):
    machines = db.query(Machine).order_by(Machine.name).all()
    return request.app.state.templates.TemplateResponse(
        "machines/index.html",
        {"request": request, "machines": machines},
    )


@router.post("/create")
async def machine_create(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        existing = db.query(Machine).filter(Machine.name == name).first()
        if not existing:
            db.add(Machine(name=name))
            db.commit()
    return RedirectResponse(url="/machines", status_code=303)


@router.post("/{machine_id}/delete")
def machine_delete(machine_id: int, db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if machine:
        db.delete(machine)
        db.commit()
    return RedirectResponse(url="/machines", status_code=303)
