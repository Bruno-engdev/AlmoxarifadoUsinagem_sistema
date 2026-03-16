"""
Authentication router – login / logout pages.
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import verify_password

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    """Render the login page."""
    return request.app.state.templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": None},
    )


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Validate credentials and create session."""
    user = db.query(User).filter(User.username == username, User.active == 1).first()

    if user is None or not verify_password(password, user.password_hash):
        return request.app.state.templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Usuário ou senha inválidos."},
            status_code=401,
        )

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
def logout(request: Request):
    """Clear session and redirect to login."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
