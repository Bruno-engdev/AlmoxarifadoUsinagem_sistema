"""
Tool Crib Management System – FastAPI entry point.

Start with:
    uvicorn app.main:app --reload
"""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import init_db, SessionLocal
from app.models import User
from app.routers import dashboard, tools, employees, movements_router, tool_types
from app.routers import auth as auth_router
from app.routers.auth import _verify_cookie

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Tool Crib – Internal Tooling Warehouse")

BASE_DIR = Path(__file__).resolve().parent

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates


# ---------------------------------------------------------------------------
# Auth middleware – redirect unauthenticated users to login
# ---------------------------------------------------------------------------

# Paths that don't require authentication
PUBLIC_PATHS = {"/auth/login", "/static"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public paths
        if path.startswith("/static") or path.startswith("/auth/login"):
            return await call_next(request)

        # Check session cookie
        session_val = request.cookies.get("session")
        user_id = _verify_cookie(session_val) if session_val else None

        if user_id is None:
            return RedirectResponse(url="/auth/login", status_code=302)

        # Inject current_user into request state for templates
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            request.state.current_user = user
        finally:
            db.close()

        response = await call_next(request)
        return response


app.add_middleware(AuthMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router.router)
app.include_router(dashboard.router)
app.include_router(tools.router)
app.include_router(employees.router)
app.include_router(movements_router.router)
app.include_router(tool_types.router)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    """Initialize the database and seed defaults on first run."""
    init_db()
