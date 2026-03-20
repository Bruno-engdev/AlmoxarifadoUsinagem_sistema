"""
Tool Crib Management System – FastAPI entry point.

Start with:
    uvicorn app.main:app --reload
"""

import secrets
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.auth import (
    get_current_user,
    seed_admin,
    _LoginRequired,
    _AdminRequired,
)
from app.routers import dashboard, tools, employees, movements_router, tool_types, machines
from app.routers import auth as auth_router, admin as admin_router
from app.routers import notifications as notifications_router

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Tool Crib – Internal Tooling Warehouse")

# Secret key – fixed per process so sessions survive reloads within the same run
_SECRET_KEY = secrets.token_urlsafe(32)

BASE_DIR = Path(__file__).resolve().parent

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates

# ---------------------------------------------------------------------------
# Auth exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(_LoginRequired)
async def login_required_handler(request: Request, exc: _LoginRequired):
    return RedirectResponse(url="/login", status_code=302)


@app.exception_handler(_AdminRequired)
async def admin_required_handler(request: Request, exc: _AdminRequired):
    return RedirectResponse(url="/", status_code=302)


# ---------------------------------------------------------------------------
# Middleware stack (add_middleware uses LIFO: last added = outermost)
# We need SessionMiddleware to run BEFORE our user-injection middleware,
# so we register the user middleware FIRST, then SessionMiddleware on top.
# Request flow: SessionMiddleware → InjectUserMiddleware → Router
# ---------------------------------------------------------------------------

from starlette.middleware.base import BaseHTTPMiddleware

class _InjectUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.current_user = get_current_user(request)
        return await call_next(request)

app.add_middleware(_InjectUserMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=_SECRET_KEY,
    session_cookie="toolcrib_session",
    max_age=60 * 60 * 8,  # 8 hours
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(dashboard.router)
app.include_router(tools.router)
app.include_router(employees.router)
app.include_router(movements_router.router)
app.include_router(tool_types.router)
app.include_router(machines.router)
app.include_router(notifications_router.router)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    """Initialize the database, seed defaults, and scan stock for missing alerts."""
    init_db()
    seed_admin()

    # Scan all tools for missing stock alerts
    from app.database import SessionLocal
    from app.services.notifications import scan_all_tools
    db = SessionLocal()
    try:
        count = scan_all_tools(db)
        if count:
            print(f"[startup] Created {count} missing stock alert(s).")
    finally:
        db.close()
