"""
Notification API endpoints – consumed by the topbar bell / modal via fetch().
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_login
from app.services.notifications import get_alerts, get_unread_count, mark_all_read

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(db: Session = Depends(get_db), _=Depends(require_login)):
    """Return the latest alerts as JSON (newest first)."""
    alerts = get_alerts(db)
    return [
        {
            "id": a.id,
            "tool_name": a.tool.name if a.tool else f"Tool #{a.tool_id}",
            "current_stock": a.current_stock,
            "min_stock": a.min_stock,
            "is_critical": bool(a.is_critical),
            "is_read": bool(a.is_read),
            "cleared_at": a.cleared_at.strftime("%d/%m %H:%M") if a.cleared_at else None,
            "created_at": a.created_at.strftime("%d/%m %H:%M") if a.created_at else "",
        }
        for a in alerts
    ]


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), _=Depends(require_login)):
    return {"count": get_unread_count(db)}


@router.post("/mark-all-read")
def mark_read(db: Session = Depends(get_db), _=Depends(require_login)):
    mark_all_read(db)
    return {"ok": True}
