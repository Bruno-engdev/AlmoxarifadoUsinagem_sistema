"""
SQLAlchemy ORM models for the Tool Crib system.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float,
    ForeignKey, DateTime, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class MovementType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"


class MovementCategory(str, enum.Enum):
    EMPRESTIMO = "EMPRESTIMO"
    REPOSICAO = "REPOSICAO"


class LoanStatus(str, enum.Enum):
    PENDENTE = "PENDENTE"
    ENTREGUE = "ENTREGUE"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    """System users with role-based access."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True)
    full_name = Column(String(200), nullable=False, default="")
    password_hash = Column(String(255), nullable=False)
    role = Column(String(10), nullable=False, default="USER")  # ADMIN or USER
    active = Column(Integer, default=1)  # 1=active, 0=disabled
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username}>"


class Machine(Base):
    """Machines in the machining sector."""
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)

    movements = relationship("Movement", back_populates="machine")

    def __repr__(self):
        return f"<Machine {self.name}>"


class ToolType(Base):
    """Categories of tools (Drill, End Mill, etc.)."""
    __tablename__ = "tool_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)

    tools = relationship("Tool", back_populates="tool_type")

    def __repr__(self):
        return f"<ToolType {self.name}>"


class Tool(Base):
    """A specific tool tracked in the warehouse."""
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    tool_type_id = Column(Integer, ForeignKey("tool_types.id"), nullable=False)
    description = Column(Text, default="")
    location = Column(String(10), default="")  # G<n>D<n> e.g. G1D27
    min_stock = Column(Integer, default=0)
    max_stock = Column(Integer, default=0)
    current_stock = Column(Integer, default=0)
    unit_cost = Column(Float, default=0.0)           # Cost per unit (R$)
    is_critical = Column(Integer, default=0)          # 1 = critical for production
    avg_lifespan_hours = Column(Float, default=0.0)   # Average life in hours before replacement

    tool_type = relationship("ToolType", back_populates="tools")
    parameters = relationship("ToolParameter", back_populates="tool", cascade="all, delete-orphan")
    movements = relationship("Movement", back_populates="tool")

    # ---------- computed helpers ----------
    @property
    def status(self) -> str:
        if self.current_stock <= 0:
            return "CRITICAL"
        if self.current_stock < self.min_stock:
            return "LOW STOCK"
        return "OK"

    @property
    def status_class(self) -> str:
        """Bootstrap CSS class for row highlighting."""
        if self.current_stock <= 0:
            return "table-danger"
        if self.current_stock < self.min_stock:
            return "table-danger"
        if self.min_stock > 0 and self.current_stock <= self.min_stock * 1.1:
            return "table-warning"
        return ""

    def __repr__(self):
        return f"<Tool {self.name}>"


class ToolParameter(Base):
    """Dynamic key-value parameters for a tool (diameter, coating, etc.)."""
    __tablename__ = "tool_parameters"

    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    parameter_name = Column(String(100), nullable=False)
    parameter_value = Column(String(255), default="")

    tool = relationship("Tool", back_populates="parameters")


class Employee(Base):
    """Employees who can checkout / return tools."""
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    department = Column(String(200), default="")

    movements = relationship("Movement", back_populates="employee")

    def __repr__(self):
        return f"<Employee {self.name}>"


class Movement(Base):
    """
    Audit log of every stock movement.
    Movements are NEVER deleted – they serve as the single source of truth.
    """
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    movement_type = Column(String(3), nullable=False)   # "IN" or "OUT"
    category = Column(String(20), nullable=False, default="EMPRESTIMO")  # EMPRESTIMO or REPOSICAO
    quantity = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    return_timestamp = Column(DateTime, nullable=True)
    loan_status = Column(String(20), nullable=True)  # PENDENTE or ENTREGUE
    notes = Column(Text, default="")

    tool = relationship("Tool", back_populates="movements")
    employee = relationship("Employee", back_populates="movements")
    machine = relationship("Machine", back_populates="movements")

    def __repr__(self):
        return f"<Movement {self.movement_type} qty={self.quantity}>"
