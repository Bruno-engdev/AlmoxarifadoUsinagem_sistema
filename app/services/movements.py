"""
Movement service – handles all stock IN / OUT operations.
Ensures current_stock is always kept in sync.
"""

from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Movement, Tool
from app.services.notifications import check_and_create_alert


def register_movement(
    db: Session,
    tool_id: int,
    employee_id: int | None,
    movement_type: str,
    quantity: int,
    notes: str = "",
    category: str = "EMPRESTIMO",
    machine_id: int | None = None,
    unit_cost: float | None = None,
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

    # Determine unit cost for this movement
    if movement_type == "IN":
        if unit_cost is None or unit_cost < 0:
            raise ValueError("Unit cost is required for stock entry and must be >= 0.")
        mv_cost = unit_cost
        tool.unit_cost = unit_cost  # cache latest entry cost on tool
    else:
        mv_cost = tool.unit_cost or 0.0  # snapshot current cost for OUT

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
        unit_cost=mv_cost,
    )
    db.add(movement)

    # Update stock
    if movement_type == "IN":
        tool.current_stock += quantity
    else:
        tool.current_stock -= quantity

    # Check stock threshold and create/clear alert
    check_and_create_alert(db, tool)

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
        # Check stock threshold and clear alert if recovered
        check_and_create_alert(db, tool)

    db.commit()
    db.refresh(movement)
    return movement


# ---------------------------------------------------------------------------
# Admin-only operations: manual entry, edit, delete (with stock compensation)
# ---------------------------------------------------------------------------

def _net_stock_delta(movement_type: str, category: str, loan_status: str | None,
                     quantity: int) -> int:
    """
    Net effect of a movement on tool.current_stock, considering its current state.
    - IN: +qty
    - OUT / REPOSICAO: -qty
    - OUT / EMPRESTIMO / PENDENTE: -qty
    - OUT / EMPRESTIMO / ENTREGUE: 0  (the OUT subtracted, the return added it back)
    """
    if movement_type == "IN":
        return quantity
    # OUT
    if category == "EMPRESTIMO" and loan_status == "ENTREGUE":
        return 0
    return -quantity


def create_manual_movement(
    db: Session,
    tool_id: int,
    movement_type: str,
    category: str,
    quantity: int,
    timestamp: datetime,
    employee_id: int | None = None,
    machine_id: int | None = None,
    notes: str = "",
    unit_cost: float | None = None,
    loan_status: str | None = None,
    return_timestamp: datetime | None = None,
) -> Movement:
    """
    Admin-only: create a movement with an explicit timestamp (retroactive entry).
    Applies the correct stock delta and recomputes the stock alert.
    """
    if quantity <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")
    movement_type = movement_type.upper()
    if movement_type not in ("IN", "OUT"):
        raise ValueError("Tipo de movimentação inválido.")
    category = category.upper()
    if category not in ("EMPRESTIMO", "REPOSICAO"):
        raise ValueError("Categoria inválida.")
    if not isinstance(timestamp, datetime):
        raise ValueError("Data/hora inválida.")
    if timestamp > datetime.utcnow():
        raise ValueError("Data/hora não pode ser futura.")

    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if tool is None:
        raise ValueError("Ferramenta não encontrada.")

    # Determine loan status
    if category == "EMPRESTIMO" and movement_type == "OUT":
        if loan_status not in ("PENDENTE", "ENTREGUE"):
            loan_status = "PENDENTE"
        if loan_status == "ENTREGUE" and return_timestamp is None:
            return_timestamp = datetime.utcnow()
    else:
        loan_status = None
        return_timestamp = None

    # Cost handling
    if movement_type == "IN":
        if unit_cost is None or unit_cost < 0:
            raise ValueError("Custo unitário é obrigatório para entrada e deve ser >= 0.")
        mv_cost = unit_cost
        tool.unit_cost = unit_cost
    else:
        mv_cost = unit_cost if (unit_cost is not None and unit_cost >= 0) else (tool.unit_cost or 0.0)

    # Stock validation: simulate net delta first
    delta = _net_stock_delta(movement_type, category, loan_status, quantity)
    if tool.current_stock + delta < 0:
        raise ValueError(
            f"Estoque insuficiente. Atual: {tool.current_stock}, delta: {delta}"
        )

    movement = Movement(
        tool_id=tool_id,
        employee_id=employee_id if category == "EMPRESTIMO" else None,
        machine_id=machine_id if category == "REPOSICAO" else None,
        movement_type=movement_type,
        category=category,
        quantity=quantity,
        timestamp=timestamp,
        return_timestamp=return_timestamp,
        loan_status=loan_status,
        notes=notes or "",
        unit_cost=mv_cost,
    )
    db.add(movement)
    tool.current_stock += delta
    check_and_create_alert(db, tool)

    db.commit()
    db.refresh(movement)
    return movement


def update_movement_admin(
    db: Session,
    movement_id: int,
    *,
    quantity: int | None = None,
    timestamp: datetime | None = None,
    employee_id: int | None = None,
    machine_id: int | None = None,
    notes: str | None = None,
    unit_cost: float | None = None,
    loan_status: str | None = None,
    return_timestamp: datetime | None = None,
) -> Movement:
    """
    Admin-only: update editable fields of a movement, recomputing stock impact safely.
    Does NOT allow changing tool_id, movement_type or category (would change the
    nature of the audit record — use delete + create instead).
    """
    movement = db.query(Movement).filter(Movement.id == movement_id).first()
    if movement is None:
        raise ValueError("Movimentação não encontrada.")

    tool = db.query(Tool).filter(Tool.id == movement.tool_id).first()
    if tool is None:
        raise ValueError("Ferramenta da movimentação não encontrada.")

    # Compute current net effect (before changes) to undo it
    old_delta = _net_stock_delta(
        movement.movement_type, movement.category, movement.loan_status, movement.quantity
    )

    # Apply field updates
    if quantity is not None:
        if quantity <= 0:
            raise ValueError("Quantidade deve ser maior que zero.")
        movement.quantity = quantity
    if timestamp is not None:
        if not isinstance(timestamp, datetime):
            raise ValueError("Data/hora inválida.")
        if timestamp > datetime.utcnow():
            raise ValueError("Data/hora não pode ser futura.")
        movement.timestamp = timestamp
    if notes is not None:
        movement.notes = notes
    if unit_cost is not None:
        if unit_cost < 0:
            raise ValueError("Custo unitário não pode ser negativo.")
        movement.unit_cost = unit_cost

    if movement.category == "EMPRESTIMO":
        if employee_id is not None:
            movement.employee_id = employee_id or None
        if movement.movement_type == "OUT" and loan_status is not None:
            if loan_status not in ("PENDENTE", "ENTREGUE"):
                raise ValueError("Status de empréstimo inválido.")
            # If transitioning ENTREGUE -> PENDENTE, drop return_timestamp
            if loan_status == "PENDENTE":
                movement.return_timestamp = None
            else:
                movement.return_timestamp = return_timestamp or movement.return_timestamp or datetime.utcnow()
            movement.loan_status = loan_status
    else:  # REPOSICAO
        if machine_id is not None:
            movement.machine_id = machine_id or None

    # Recompute and apply new delta
    new_delta = _net_stock_delta(
        movement.movement_type, movement.category, movement.loan_status, movement.quantity
    )
    projected = tool.current_stock - old_delta + new_delta
    if projected < 0:
        raise ValueError(
            f"Alteração resultaria em estoque negativo (projetado: {projected})."
        )
    tool.current_stock = projected
    check_and_create_alert(db, tool)

    db.commit()
    db.refresh(movement)
    return movement


def delete_movement_admin(db: Session, movement_id: int) -> int:
    """
    Admin-only: physically delete a movement and reverse its net stock impact.
    Returns the affected tool_id.
    """
    movement = db.query(Movement).filter(Movement.id == movement_id).first()
    if movement is None:
        raise ValueError("Movimentação não encontrada.")

    tool = db.query(Tool).filter(Tool.id == movement.tool_id).first()
    if tool is None:
        raise ValueError("Ferramenta da movimentação não encontrada.")

    delta = _net_stock_delta(
        movement.movement_type, movement.category, movement.loan_status, movement.quantity
    )
    # Undo the net effect on stock
    projected = tool.current_stock - delta
    if projected < 0:
        raise ValueError(
            f"Exclusão resultaria em estoque negativo (projetado: {projected})."
        )
    tool.current_stock = projected

    tool_id = movement.tool_id
    db.delete(movement)
    check_and_create_alert(db, tool)
    db.commit()
    return tool_id
