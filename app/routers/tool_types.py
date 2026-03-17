"""
Tool Types router – manage tool categories.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ToolType
from app.auth import require_admin

router = APIRouter(prefix="/tool-types", tags=["tool_types"], dependencies=[Depends(require_admin)])


@router.get("/")
def tool_types_list(request: Request, db: Session = Depends(get_db)):
    types = db.query(ToolType).order_by(ToolType.name).all()
    return request.app.state.templates.TemplateResponse(
        "tool_types/index.html",
        {"request": request, "tool_types": types},
    )


@router.post("/create")
async def tool_type_create(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        existing = db.query(ToolType).filter(ToolType.name == name).first()
        if not existing:
            db.add(ToolType(name=name))
            db.commit()
    return RedirectResponse(url="/tool-types", status_code=303)


@router.post("/{type_id}/delete")
def tool_type_delete(type_id: int, db: Session = Depends(get_db)):
    tt = db.query(ToolType).filter(ToolType.id == type_id).first()
    if tt:
        db.delete(tt)
        db.commit()
    return RedirectResponse(url="/tool-types", status_code=303)
