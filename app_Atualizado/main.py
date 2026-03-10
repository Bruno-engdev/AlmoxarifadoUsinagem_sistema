"""
Tool Crib Management System – FastAPI entry point.

Start with:
    uvicorn app.main:app --reload
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.routers import dashboard, tools, employees, movements_router, tool_types

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
# Routers
# ---------------------------------------------------------------------------

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
