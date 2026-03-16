"""
Admin router – user management panel (admin only).
"""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import require_admin, hash_password

router = APIRouter(prefix="/admin")


@router.get("/users")
def list_users(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all system users."""
    users = db.query(User).order_by(User.username).all()
    return request.app.state.templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "users": users,
            "current_user": admin,
            "active_page": "admin",
        },
    )


@router.post("/users/create")
def create_user(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    role: str = Form("USER"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new user."""
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        users = db.query(User).order_by(User.username).all()
        return request.app.state.templates.TemplateResponse(
            "admin/users.html",
            {
                "request": request,
                "users": users,
                "current_user": admin,
                "active_page": "admin",
                "error": f"Usuário '{username}' já existe.",
            },
        )

    user = User(
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
        role=role if role in ("ADMIN", "USER") else "USER",
        active=1,
    )
    db.add(user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/users/{user_id}/edit")
def edit_user_page(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Show edit form for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)
    return request.app.state.templates.TemplateResponse(
        "admin/edit_user.html",
        {
            "request": request,
            "edit_user": user,
            "current_user": admin,
            "active_page": "admin",
        },
    )


@router.post("/users/{user_id}/edit")
def edit_user_submit(
    user_id: int,
    request: Request,
    full_name: str = Form(""),
    role: str = Form("USER"),
    active: int = Form(1),
    new_password: str = Form(""),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update user data."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)

    user.full_name = full_name
    user.role = role if role in ("ADMIN", "USER") else "USER"
    user.active = 1 if active else 0

    if new_password.strip():
        user.password_hash = hash_password(new_password.strip())

    db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a user (soft delete)."""
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.id != admin.id:
        user.active = 0
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)
