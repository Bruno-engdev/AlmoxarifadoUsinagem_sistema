"""
Serviço de importação de histórico de preços.

Recebe a lista de :class:`ImportedPriceRow` (já normalizada pelo adapter
:mod:`app.services.price_history_xlsx`) e aplica as regras de negócio:

1. Casa cada linha com uma ferramenta cadastrada via ``Tool.origin_id``.
   Linhas sem match são contadas em ``skipped_no_match`` e ignoradas.
2. Calcula ``row_hash`` (SHA-256) e descarta duplicatas já presentes.
3. Faz insert em lote dentro de uma transação.
4. Para cada ferramenta afetada, reposiciona ``is_latest`` (apenas a linha
   com a data mais recente fica True) e replica ``latest_unit_price`` em
   todas as linhas da mesma ferramenta.
5. Atualiza ``Tool.unit_cost`` para manter o dashboard coerente.

O parâmetro ``dry_run=True`` executa toda a lógica sem fazer commit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tool, ToolPriceHistory
from app.services.price_history_xlsx import ImportedPriceRow


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    total_rows: int = 0
    inserted: int = 0
    skipped_duplicate: int = 0
    skipped_no_match: int = 0
    skipped_invalid: int = 0
    tools_affected: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def summary(self) -> str:
        prefix = "[DRY-RUN] " if self.dry_run else ""
        return (
            f"{prefix}Total: {self.total_rows} | Inseridas: {self.inserted} | "
            f"Duplicadas: {self.skipped_duplicate} | "
            f"Sem ferramenta: {self.skipped_no_match} | "
            f"Inválidas: {self.skipped_invalid} | "
            f"Ferramentas atualizadas: {self.tools_affected}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_hash(origin_id: str,
              numero_documento: str,
              data_entrega: date | None,
              preco_unitario: Decimal) -> str:
    payload = "|".join([
        origin_id.strip(),
        (numero_documento or "").strip(),
        data_entrega.isoformat() if data_entrega else "",
        f"{preco_unitario:.6f}",
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_tools_by_origin(db: Session, origin_ids: Iterable[str]) -> dict[str, Tool]:
    ids = sorted({o for o in origin_ids if o})
    if not ids:
        return {}
    tools = db.execute(
        select(Tool).where(Tool.origin_id.in_(ids))
    ).scalars().all()
    return {t.origin_id: t for t in tools if t.origin_id}


def _recompute_latest(db: Session, tool_id: int) -> Decimal | None:
    """
    Reposiciona is_latest e replica latest_unit_price para uma ferramenta.
    Retorna o preço mais recente, ou None se a ferramenta não tiver histórico.
    """
    records = db.execute(
        select(ToolPriceHistory).where(ToolPriceHistory.tool_id == tool_id)
    ).scalars().all()
    if not records:
        return None

    def _sort_key(r: ToolPriceHistory):
        # Mais recente primeiro: por data_entrega desc, depois imported_at desc, depois id desc.
        return (
            r.data_entrega or date.min,
            r.imported_at or datetime.min,
            r.id or 0,
        )

    records.sort(key=_sort_key, reverse=True)
    latest = records[0]
    latest_price = latest.preco_unitario

    for r in records:
        r.is_latest = (r.id == latest.id)
        r.latest_unit_price = latest_price

    return latest_price


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def import_price_history(
    db: Session,
    rows: list[ImportedPriceRow],
    *,
    source: str = "TOTVS",
    file_name: str = "",
    dry_run: bool = False,
) -> ImportResult:
    result = ImportResult(total_rows=len(rows), dry_run=dry_run)

    # 1) Filtra inválidas
    valid_rows: list[ImportedPriceRow] = []
    for row in rows:
        if not row.is_valid:
            result.skipped_invalid += 1
            if row.parse_errors:
                result.errors.append(
                    f"Linha {row.row_number}: {'; '.join(row.parse_errors)}"
                )
            continue
        valid_rows.append(row)

    # 2) Carrega ferramentas existentes em uma única query
    tools_by_origin = _load_tools_by_origin(
        db, (r.origin_id for r in valid_rows)
    )

    # 3) Carrega hashes já gravados (entre os candidatos) para dedup
    candidate_hashes: dict[str, ImportedPriceRow] = {}
    for row in valid_rows:
        tool = tools_by_origin.get(row.origin_id)
        if tool is None:
            result.skipped_no_match += 1
            continue
        # row.preco_unitario aqui nunca é None (filtrado em is_valid)
        assert row.preco_unitario is not None
        h = _row_hash(row.origin_id, row.numero_documento,
                      row.data_entrega, row.preco_unitario)
        # Dedup intra-arquivo: se o mesmo hash aparece duas vezes, mantém só a
        # primeira ocorrência e conta as outras como duplicadas.
        if h in candidate_hashes:
            result.skipped_duplicate += 1
            continue
        candidate_hashes[h] = row

    if candidate_hashes:
        existing = db.execute(
            select(ToolPriceHistory.row_hash).where(
                ToolPriceHistory.row_hash.in_(list(candidate_hashes.keys()))
            )
        ).scalars().all()
        existing_set = set(existing)
    else:
        existing_set = set()

    # 4) Insert em lote (em memória; commit no final)
    affected_tool_ids: set[int] = set()
    imported_at = datetime.utcnow()

    for h, row in candidate_hashes.items():
        if h in existing_set:
            result.skipped_duplicate += 1
            continue

        tool = tools_by_origin[row.origin_id]
        assert row.preco_unitario is not None
        record = ToolPriceHistory(
            tool_id=tool.id,
            origin_id_snapshot=row.origin_id,
            numero_documento=row.numero_documento,
            data_entrega=row.data_entrega,
            data_emissao=row.data_emissao,
            fornecedor_codigo=row.fornecedor_codigo,
            fornecedor_nome=row.fornecedor_nome,
            tipo=row.tipo,
            item=row.item,
            descricao_totvs=row.descricao_totvs,
            unidade=row.unidade,
            segunda_unidade=row.segunda_unidade,
            quantidade=row.quantidade,
            preco_kg=row.preco_kg,
            preco_unitario=row.preco_unitario,
            ultimo_preco=row.ultimo_preco,
            aliquota_ipi=row.aliquota_ipi,
            observacoes=row.observacoes,
            numero_sc=row.numero_sc,
            qtd_entregue=row.qtd_entregue,
            row_hash=h,
            is_latest=False,
            latest_unit_price=None,
            source=source,
            source_file_name=file_name,
            imported_at=imported_at,
        )
        db.add(record)
        result.inserted += 1
        affected_tool_ids.add(tool.id)

    # Precisamos dos IDs gerados para o recompute; flush sem commit.
    db.flush()

    # 5) Recalcula is_latest + latest_unit_price por ferramenta afetada,
    # e propaga em Tool.unit_cost.
    for tool_id in affected_tool_ids:
        latest_price = _recompute_latest(db, tool_id)
        if latest_price is not None:
            tool = db.get(Tool, tool_id)
            if tool is not None:
                tool.unit_cost = float(latest_price)

    result.tools_affected = len(affected_tool_ids)

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return result
