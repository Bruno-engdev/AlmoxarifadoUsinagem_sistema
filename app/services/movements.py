"""
Movement service – handles all stock IN / OUT operations.
Ensures current_stock is always kept in sync.
"""

from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Movement, Tool


def register_movement(
    db: Session,
    tool_id: int,
    employee_id: int,
    movement_type: str,
    quantity: int,
    notes: str = "",
) -> Movement:
    """
    Create a movement record and update the tool's current_stock.

    Raises ValueError if:
      - quantity <= 0
      - movement_type is invalid
      - an OUT movement would result in negative stock
    """
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    movement_type = movement_type.upper()
    if movement_type not in ("IN", "OUT"):
        raise ValueError("Movement type must be IN or OUT.")

    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if tool is None:
        raise ValueError(f"Tool with id {tool_id} not found.")

    if movement_type == "OUT" and tool.current_stock < quantity:
        raise ValueError(
            f"Insufficient stock. Current: {tool.current_stock}, Requested: {quantity}"
        )

    # Create the movement record (never deleted – audit trail)
    movement = Movement(
        tool_id=tool_id,
        employee_id=employee_id,
        movement_type=movement_type,
        quantity=quantity,
        timestamp=datetime.utcnow(),
        notes=notes,
    )
    db.add(movement)

    # Update stock
    if movement_type == "IN":
        tool.current_stock += quantity
    else:
        tool.current_stock -= quantity

    db.commit()
    db.refresh(movement)
    return movement
