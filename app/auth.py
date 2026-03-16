"""
Authentication utilities: password hashing, session helpers, dependencies.
"""

import hashlib
import secrets
from fastapi import Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import User


# ---------------------------------------------------------------------------
# Password hashing (SHA-256 + salt, no extra dependencies)
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str | None = None) -> str:
    """Hash a password with a random salt using SHA-256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}${password}".encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(plain: str, stored_hash: str) -> bool:
    """Verify a plain password against a stored hash."""
    salt = stored_hash.split("$")[0]
    return _hash_password(plain, salt) == stored_hash


def hash_password(password: str) -> str:
    return _hash_password(password)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def get_current_user(request: Request) -> User | None:
    """Return the logged-in User or None."""
    try:
        user_id = request.session.get("user_id")
    except AssertionError:
        return None
    if not user_id:
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.active == 1).first()
        return user
    finally:
        db.close()


def require_login(request: Request):
    """Dependency: redirect to /login if not authenticated."""
    user = get_current_user(request)
    if user is None:
        raise _LoginRequired()
    request.state.current_user = user
    return user


def require_admin(request: Request):
    """Dependency: redirect to / if not admin."""
    user = require_login(request)
    if user.role != "ADMIN":
        raise _AdminRequired()
    return user


# ---------------------------------------------------------------------------
# Custom exceptions handled by middleware
# ---------------------------------------------------------------------------

class _LoginRequired(Exception):
    pass


class _AdminRequired(Exception):
    pass


# ---------------------------------------------------------------------------
# Seed default admin
# ---------------------------------------------------------------------------

def seed_admin():
    """Create default admin user if no users exist."""
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                username="admin",
                full_name="Administrador",
                password_hash=hash_password("admin"),
                role="ADMIN",
                active=1,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()
