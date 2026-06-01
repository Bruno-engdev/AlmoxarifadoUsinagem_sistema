"""Add tool_price_history table.

Histórico de preços importado do TOTVS (CLI de import). Tabela única, com
deduplicação por row_hash e marcação de preço mais recente por ferramenta
em is_latest + latest_unit_price.

Revision ID: 0002_tool_price_history
Revises: 0001_baseline
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_tool_price_history"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column("origin_id_snapshot", sa.String(length=100), nullable=False),

        sa.Column("numero_documento", sa.String(length=50), server_default=""),
        sa.Column("data_entrega", sa.Date(), nullable=True),
        sa.Column("data_emissao", sa.Date(), nullable=True),

        sa.Column("fornecedor_codigo", sa.String(length=50), server_default=""),
        sa.Column("fornecedor_nome", sa.String(length=200), server_default=""),

        sa.Column("tipo", sa.String(length=20), server_default=""),
        sa.Column("item", sa.String(length=20), server_default=""),
        sa.Column("descricao_totvs", sa.Text(), server_default=""),
        sa.Column("unidade", sa.String(length=20), server_default=""),
        sa.Column("segunda_unidade", sa.String(length=20), server_default=""),

        sa.Column("quantidade", sa.Numeric(15, 4), nullable=True),
        sa.Column("preco_kg", sa.Numeric(15, 6), nullable=True),
        sa.Column("preco_unitario", sa.Numeric(15, 6), nullable=False),
        sa.Column("ultimo_preco", sa.Numeric(15, 6), nullable=True),
        sa.Column("aliquota_ipi", sa.Numeric(8, 4), nullable=True),

        sa.Column("observacoes", sa.Text(), server_default=""),
        sa.Column("numero_sc", sa.String(length=50), server_default=""),
        sa.Column("qtd_entregue", sa.Numeric(15, 4), nullable=True),

        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latest_unit_price", sa.Numeric(15, 6), nullable=True),

        sa.Column("source", sa.String(length=50), server_default="TOTVS"),
        sa.Column("source_file_name", sa.String(length=500), server_default=""),
        sa.Column("imported_at", sa.DateTime(), nullable=True),

        sa.UniqueConstraint("row_hash", name="uq_tool_price_history_row_hash"),
    )
    op.create_index("ix_tool_price_history_id", "tool_price_history", ["id"])
    op.create_index("ix_tool_price_history_tool_id", "tool_price_history", ["tool_id"])
    op.create_index("ix_tool_price_history_data_entrega", "tool_price_history", ["data_entrega"])
    op.create_index("ix_tool_price_history_is_latest", "tool_price_history", ["is_latest"])


def downgrade() -> None:
    op.drop_index("ix_tool_price_history_is_latest", table_name="tool_price_history")
    op.drop_index("ix_tool_price_history_data_entrega", table_name="tool_price_history")
    op.drop_index("ix_tool_price_history_tool_id", table_name="tool_price_history")
    op.drop_index("ix_tool_price_history_id", table_name="tool_price_history")
    op.drop_table("tool_price_history")
