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
    employee_id: int | None,
    movement_type: str,
    quantity: int,
    notes: str = "",
    category: str = "EMPRESTIMO",
    machine_id: int | None = None,
) -> Movement:
    """
    Create a movement record and update the tool's current_stock.

    category: EMPRESTIMO or REPOSICAO
    - EMPRESTIMO: requires employee_id, sets loan_status to PENDENTE on OUT
    - REPOSICAO: requires machine_id

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

    category = category.upper()
    if category not in ("EMPRESTIMO", "REPOSICAO"):
        raise ValueError("Category must be EMPRESTIMO or REPOSICAO.")

    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if tool is None:
        raise ValueError(f"Tool with id {tool_id} not found.")

    if movement_type == "OUT" and tool.current_stock < quantity:
        raise ValueError(
            f"Insufficient stock. Current: {tool.current_stock}, Requested: {quantity}"
        )

    # Determine loan status for EMPRESTIMO OUT movements
    loan_status = None
    if category == "EMPRESTIMO" and movement_type == "OUT":
        loan_status = "PENDENTE"

    # Create the movement record (never deleted – audit trail)
    movement = Movement(
        tool_id=tool_id,
        employee_id=employee_id if category == "EMPRESTIMO" else None,
        machine_id=machine_id if category == "REPOSICAO" else None,
        movement_type=movement_type,
        category=category,
        quantity=quantity,
        timestamp=datetime.utcnow(),
        loan_status=loan_status,
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


def return_loan(db: Session, movement_id: int) -> Movement:
    """
    Mark a loan movement as returned (ENTREGUE) and register the return timestamp.
    Also adds stock back (IN movement).
    """
    movement = db.query(Movement).filter(Movement.id == movement_id).first()
    if movement is None:
        raise ValueError(f"Movement with id {movement_id} not found.")

    if movement.category != "EMPRESTIMO" or movement.loan_status != "PENDENTE":
        raise ValueError("This movement is not a pending loan.")

    movement.loan_status = "ENTREGUE"
    movement.return_timestamp = datetime.utcnow()

    # Return stock
    tool = db.query(Tool).filter(Tool.id == movement.tool_id).first()
    if tool:
        tool.current_stock += movement.quantity

    db.commit()
    db.refresh(movement)
    return movement
