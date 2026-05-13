"""Baseline schema.

Mirrors the current SQLAlchemy models, including all columns previously
added ad-hoc by `_migrate_columns_sqlite` (tools.unit_cost, tools.is_critical,
tools.avg_lifespan_hours, tools.origin_id, movements.unit_cost).

Designed to be applied on an empty database. For an existing SQLite database
already containing the schema, stamp this revision instead of running upgrade:

    alembic stamp 0001_baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False, server_default="USER"),
        sa.Column("active", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_id", "users", ["id"])

    op.create_table(
        "machines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
    )
    op.create_index("ix_machines_id", "machines", ["id"])

    op.create_table(
        "tool_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
    )
    op.create_index("ix_tool_types_id", "tool_types", ["id"])

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=200), server_default=""),
    )
    op.create_index("ix_employees_id", "employees", ["id"])

    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("origin_id", sa.String(length=100), server_default=""),
        sa.Column("tool_type_id", sa.Integer(), sa.ForeignKey("tool_types.id"), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("location", sa.String(length=10), server_default=""),
        sa.Column("min_stock", sa.Integer(), server_default="0"),
        sa.Column("max_stock", sa.Integer(), server_default="0"),
        sa.Column("current_stock", sa.Integer(), server_default="0"),
        sa.Column("unit_cost", sa.Float(), server_default="0"),
        sa.Column("is_critical", sa.Integer(), server_default="0"),
        sa.Column("avg_lifespan_hours", sa.Float(), server_default="0"),
    )
    op.create_index("ix_tools_id", "tools", ["id"])

    op.create_table(
        "tool_parameters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column("parameter_name", sa.String(length=100), nullable=False),
        sa.Column("parameter_value", sa.String(length=255), server_default=""),
    )
    op.create_index("ix_tool_parameters_id", "tool_parameters", ["id"])

    op.create_table(
        "movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("machine_id", sa.Integer(), sa.ForeignKey("machines.id"), nullable=True),
        sa.Column("movement_type", sa.String(length=3), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="EMPRESTIMO"),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("return_timestamp", sa.DateTime(), nullable=True),
        sa.Column("loan_status", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("unit_cost", sa.Float(), server_default="0"),
    )
    op.create_index("ix_movements_id", "movements", ["id"])

    op.create_table(
        "tool_stock_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column("current_stock", sa.Integer(), nullable=False),
        sa.Column("min_stock", sa.Integer(), nullable=False),
        sa.Column("is_critical", sa.Integer(), server_default="0"),
        sa.Column("is_read", sa.Integer(), server_default="0"),
        sa.Column("cleared_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tool_stock_alerts_id", "tool_stock_alerts", ["id"])


def downgrade() -> None:
    op.drop_index("ix_tool_stock_alerts_id", table_name="tool_stock_alerts")
    op.drop_table("tool_stock_alerts")
    op.drop_index("ix_movements_id", table_name="movements")
    op.drop_table("movements")
    op.drop_index("ix_tool_parameters_id", table_name="tool_parameters")
    op.drop_table("tool_parameters")
    op.drop_index("ix_tools_id", table_name="tools")
    op.drop_table("tools")
    op.drop_index("ix_employees_id", table_name="employees")
    op.drop_table("employees")
    op.drop_index("ix_tool_types_id", table_name="tool_types")
    op.drop_table("tool_types")
    op.drop_index("ix_machines_id", table_name="machines")
    op.drop_table("machines")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
