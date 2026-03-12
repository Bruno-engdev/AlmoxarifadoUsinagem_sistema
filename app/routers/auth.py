"""
Authentication router – login, logout, and admin user management.
"""

import hashlib
from fastapi import APIRouter, Request, Depends, Form, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = "toolcrib-session-secret-2026"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _sign_cookie(user_id: int) -> str:
    """Create a signed session value."""
    import hmac
    msg = str(user_id).encode()
    sig = hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:16]
    return f"{user_id}:{sig}"


def _verify_cookie(value: str) -> int | None:
    """Verify the signed session cookie and return user_id or None."""
    import hmac
    if not value or ":" not in value:
        return None
    parts = value.split(":", 1)
    try:
        user_id = int(parts[0])
    except ValueError:
        return None
    sig = parts[1]
    expected = hmac.new(SECRET_KEY.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return None
    return user_id


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Dependency: retrieve the logged-in user from the session cookie."""
    session_val = request.cookies.get("session")
    if not session_val:
        return None
    user_id = _verify_cookie(session_val)
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id).first()


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

@router.get("/login")
def login_page(request: Request):
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
    user = db.query(User).filter(User.username == username).first()
    if not user or user.password_hash != _hash_password(password):
        return request.app.state.templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Usuário ou senha inválidos."},
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="session",
        value=_sign_cookie(user.id),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 12,  # 12 hours
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("session")
    return response


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------

@router.get("/admin")
def admin_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    users = db.query(User).order_by(User.id).all()
    return request.app.state.templates.TemplateResponse(
        "auth/admin.html",
        {
            "request": request,
            "users": users,
            "current_user": current_user,
            "success": None,
            "error": None,
        },
    )


@router.post("/admin/create")
def admin_create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_admin: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    # Validate
    username = username.strip()
    if len(username) < 3:
        users = db.query(User).order_by(User.id).all()
        return request.app.state.templates.TemplateResponse(
            "auth/admin.html",
            {
                "request": request,
                "users": users,
                "current_user": current_user,
                "success": None,
                "error": "Nome de usuário deve ter pelo menos 3 caracteres.",
            },
        )

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        users = db.query(User).order_by(User.id).all()
        return request.app.state.templates.TemplateResponse(
            "auth/admin.html",
            {
                "request": request,
                "users": users,
                "current_user": current_user,
                "success": None,
                "error": f"Usuário '{username}' já existe.",
            },
        )

    new_user = User(
        username=username,
        password_hash=_hash_password(password),
        is_admin=bool(is_admin),
    )
    db.add(new_user)
    db.commit()

    users = db.query(User).order_by(User.id).all()
    return request.app.state.templates.TemplateResponse(
        "auth/admin.html",
        {
            "request": request,
            "users": users,
            "current_user": current_user,
            "success": f"Usuário '{username}' criado com sucesso!",
            "error": None,
        },
    )


@router.post("/admin/delete/{user_id}")
def admin_delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/auth/admin", status_code=302)

    # Prevent deleting the default admin account
    if user.username == "admin":
        users = db.query(User).order_by(User.id).all()
        return request.app.state.templates.TemplateResponse(
            "auth/admin.html",
            {
                "request": request,
                "users": users,
                "current_user": current_user,
                "success": None,
                "error": "Não é possível excluir a conta admin padrão.",
            },
        )

    db.delete(user)
    db.commit()

    users = db.query(User).order_by(User.id).all()
    return request.app.state.templates.TemplateResponse(
        "auth/admin.html",
        {
            "request": request,
            "users": users,
            "current_user": current_user,
            "success": f"Usuário '{user.username}' excluído com sucesso!",
            "error": None,
        },
    )
