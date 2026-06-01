"""
Financial dashboard router – cost and price analytics page.

Two analytical layers:
- Consumed cost: based on Movement.unit_cost (snapshot at OUT time).
- Purchase price: based on ToolPriceHistory (TOTVS imports).
"""

from datetime import datetime, date, timedelta
from urllib.parse import urlencode
import unicodedata

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tool, ToolType
from app.auth import require_login
from app.pagination import paginate_items
from app.services.analytics import (
    get_total_consumed_value,
    get_monthly_consumed_value,
    get_cost_share_by_tool,
    get_average_purchase_price_series,
    get_average_purchase_price_overall,
    get_latest_price_variation,
    get_top_average_cost_impact_tools,
    get_top_cost_impact_tools,
    _resolve_financial_window,
    _previous_window,
)

router = APIRouter(dependencies=[Depends(require_login)])

VARIATION_SORT_FIELDS = {
    "name",
    "tool_type_name",
    "consumed_value",
    "spent_share_pct",
    "last_price",
    "prev_price",
    "var_abs",
    "var_pct",
    "var_pct_abs",
    "last_date",
}

MONTH_NAMES = [
    "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_variation_rows(db: Session, *, d_from, d_to, tt_id, t_name) -> list[dict]:
    rows = get_latest_price_variation(
        db,
        date_from=d_from,
        date_to=d_to,
        tool_type_id=tt_id,
        tool_name=t_name,
        limit=None,
    )
    return [
        {
            **item,
            "tool_type_name": item.get("tool_type_name") or "Sem tipo",
            "consumed_value": round(float(item.get("consumed_value", 0) or 0), 2),
            "spent_share_pct": round(float(item.get("spent_share_pct", 0) or 0), 2),
        }
        for item in rows
    ]


def _normalize_text(value: object | None) -> str:
    normalized = unicodedata.normalize("NFD", str(value or ""))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def _parse_decimal_filter(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = value.strip().replace(",", ".")
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _compact_query(params: dict[str, object]) -> str:
    compact = {
        key: value
        for key, value in params.items()
        if value not in (None, "", 0)
    }
    return urlencode(compact)


def _financial_nav_query(*, date_from: str, date_to: str, tool_type_id: int, tool_name: str) -> str:
    return _compact_query(
        {
            "date_from": date_from,
            "date_to": date_to,
            "tool_type_id": tool_type_id,
            "tool_name": tool_name,
        }
    )


def _filter_variation_rows(rows: list[dict], *, search: str,
                           min_consumed: float | None,
                           min_share: float | None) -> list[dict]:
    search_term = _normalize_text(search)
    filtered = []
    for row in rows:
        if min_consumed is not None and float(row.get("consumed_value", 0) or 0) < min_consumed:
            continue
        if min_share is not None and float(row.get("spent_share_pct", 0) or 0) < min_share:
            continue
        if search_term:
            searchable = _normalize_text(
                " ".join(
                    str(value or "")
                    for value in (
                        row.get("name"),
                        row.get("tool_type_name"),
                        row.get("last_date"),
                        row.get("last_price"),
                        row.get("prev_price"),
                        row.get("var_abs"),
                        row.get("var_pct"),
                        row.get("consumed_value"),
                        row.get("spent_share_pct"),
                    )
                )
            )
            if search_term not in searchable:
                continue
        filtered.append(row)
    return filtered


def _sort_variation_rows(rows: list[dict], *, sort_by: str, sort_dir: str) -> list[dict]:
    sort_by = sort_by if sort_by in VARIATION_SORT_FIELDS else "var_pct_abs"
    reverse = sort_dir != "asc"

    if sort_by == "name":
        return sorted(rows, key=lambda item: _normalize_text(item.get("name")), reverse=reverse)
    if sort_by == "tool_type_name":
        return sorted(rows, key=lambda item: _normalize_text(item.get("tool_type_name")), reverse=reverse)
    if sort_by == "last_date":
        return sorted(rows, key=lambda item: item.get("last_date") or "", reverse=reverse)
    if sort_by == "var_pct_abs":
        return sorted(
            rows,
            key=lambda item: abs(float(item.get("var_pct", 0) or 0)),
            reverse=reverse,
        )

    return sorted(
        rows,
        key=lambda item: float(item.get(sort_by, 0) or 0),
        reverse=reverse,
    )


def _variation_sort_urls(base_path: str, *,
                         date_from: str, date_to: str,
                         tool_type_id: int, tool_name: str,
                         search: str, min_consumed: str, min_share: str,
                         per_page: int, current_sort_by: str,
                         current_sort_dir: str) -> dict[str, str]:
    base_params = {
        "date_from": date_from,
        "date_to": date_to,
        "tool_type_id": tool_type_id,
        "tool_name": tool_name,
        "search": search,
        "min_consumed": min_consumed,
        "min_share": min_share,
        "per_page": per_page,
        "page": 1,
    }
    urls = {}
    for field in VARIATION_SORT_FIELDS:
        next_dir = "asc" if current_sort_by == field and current_sort_dir == "desc" else "desc"
        query = _compact_query({**base_params, "sort_by": field, "sort_dir": next_dir})
        urls[field] = f"{base_path}?{query}" if query else base_path
    return urls


def _build_financial_payload(db: Session, *, d_from, d_to, tt_id, t_name) -> dict:
    flt = dict(date_from=d_from, date_to=d_to,
               tool_type_id=tt_id, tool_name=t_name)

    # Consumed cost
    total_cost = get_total_consumed_value(db, **flt)
    monthly = get_monthly_consumed_value(db, **flt)
    share = get_cost_share_by_tool(db, limit=10, **flt)
    cost_impact = get_top_cost_impact_tools(db, limit=3, **flt)
    impact = get_top_average_cost_impact_tools(db, limit=3, **flt)

    cost_labels = [f"{MONTH_NAMES[m['month']]} {m['year']}" for m in monthly]
    cost_data = [m["cost"] for m in monthly]

    share_labels = [s["name"][:32] for s in share]
    share_costs = [s["cost"] for s in share]
    share_pcts = [s["share_pct"] for s in share]

    # Purchase price
    avg_series = get_average_purchase_price_series(db, **flt)
    avg_overall = get_average_purchase_price_overall(db, **flt)
    variations = _build_variation_rows(
        db,
        d_from=d_from,
        d_to=d_to,
        tt_id=tt_id,
        t_name=t_name,
    )

    avg_labels = [f"{MONTH_NAMES[m['month']]} {m['year']}" for m in avg_series]
    avg_data = [m["avg_price"] for m in avg_series]

    # Derived KPIs
    leader_share = share[0] if share else None
    delta_total = round(cost_impact["current_total"] - cost_impact["previous_total"], 2)
    delta_total_pct = (
        round((delta_total / cost_impact["previous_total"]) * 100, 2)
        if cost_impact["previous_total"] else (100.0 if cost_impact["current_total"] else 0.0)
    )
    rising_count = sum(1 for v in variations if v["var_pct"] > 0)
    falling_count = sum(1 for v in variations if v["var_pct"] < 0)
    avg_recent_variation = (
        round(sum(v["var_pct"] for v in variations) / len(variations), 2)
        if variations else 0.0
    )

    return {
        "kpis": {
            "total_cost": total_cost,
            "leader_name": leader_share["name"] if leader_share else None,
            "leader_share_pct": leader_share["share_pct"] if leader_share else 0.0,
            "avg_purchase_price": avg_overall,
            "avg_recent_variation_pct": avg_recent_variation,
            "delta_total": delta_total,
            "delta_total_pct": delta_total_pct,
            "rising_count": rising_count,
            "falling_count": falling_count,
        },
        "cost_series": {
            "labels": cost_labels,
            "data": cost_data,
        },
        "share": {
            "labels": share_labels,
            "costs": share_costs,
            "pcts": share_pcts,
            "rows": share,
        },
        "impact": impact,
        "price_series": {
            "labels": avg_labels,
            "data": avg_data,
        },
        "variations": variations,
    }


@router.get("/financials")
def financials(
    request: Request,
    date_from: str = Query("", alias="date_from"),
    date_to: str = Query("", alias="date_to"),
    tool_type_id: int = Query(0, alias="tool_type_id"),
    tool_name: str = Query("", alias="tool_name"),
    db: Session = Depends(get_db),
):
    d_from = _parse_date(date_from) if date_from else None
    d_to = _parse_date(date_to) if date_to else None
    tt_id = tool_type_id if tool_type_id else None
    t_name = tool_name.strip() if tool_name else None

    # Apply default 12-month window when no dates provided (only for display chips).
    resolved_start, resolved_end = _resolve_financial_window(d_from, d_to)
    prev_start, prev_end = _previous_window(resolved_start, resolved_end)

    payload = _build_financial_payload(
        db, d_from=d_from or resolved_start, d_to=d_to or resolved_end,
        tt_id=tt_id, t_name=t_name,
    )

    tool_types = db.query(ToolType).order_by(ToolType.name).all()

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="financials.html",
        context={
            "active_page": "financials",
            "active_financial_view": "dashboard",
            "financial_nav_query": _financial_nav_query(
                date_from=date_from,
                date_to=date_to,
                tool_type_id=tool_type_id,
                tool_name=tool_name,
            ),
            "payload": payload,
            "tool_types": tool_types,
            # Filter state
            "f_date_from": date_from,
            "f_date_to": date_to,
            "f_tool_type_id": tool_type_id,
            "f_tool_name": tool_name,
            # Window chips
            "window_start": resolved_start.isoformat(),
            "window_end": resolved_end.isoformat(),
            "prev_window_start": prev_start.isoformat(),
            "prev_window_end": prev_end.isoformat(),
        },
    )


@router.get("/financials/table")
def financials_table(
    request: Request,
    date_from: str = Query("", alias="date_from"),
    date_to: str = Query("", alias="date_to"),
    tool_type_id: int = Query(0, alias="tool_type_id"),
    tool_name: str = Query("", alias="tool_name"),
    search: str = Query("", alias="search"),
    min_consumed: str = Query("", alias="min_consumed"),
    min_share: str = Query("", alias="min_share"),
    sort_by: str = Query("var_pct_abs", alias="sort_by"),
    sort_dir: str = Query("desc", alias="sort_dir"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, alias="per_page"),
    db: Session = Depends(get_db),
):
    d_from = _parse_date(date_from) if date_from else None
    d_to = _parse_date(date_to) if date_to else None
    tt_id = tool_type_id if tool_type_id else None
    t_name = tool_name.strip() if tool_name else None

    resolved_start, resolved_end = _resolve_financial_window(d_from, d_to)
    prev_start, prev_end = _previous_window(resolved_start, resolved_end)

    min_consumed_value = _parse_decimal_filter(min_consumed)
    min_share_value = _parse_decimal_filter(min_share)
    sort_by = sort_by if sort_by in VARIATION_SORT_FIELDS else "var_pct_abs"
    sort_dir = sort_dir if sort_dir in ("asc", "desc") else "desc"

    rows = _build_variation_rows(
        db,
        d_from=d_from or resolved_start,
        d_to=d_to or resolved_end,
        tt_id=tt_id,
        t_name=t_name,
    )
    rows = _filter_variation_rows(
        rows,
        search=search,
        min_consumed=min_consumed_value,
        min_share=min_share_value,
    )
    rows = _sort_variation_rows(rows, sort_by=sort_by, sort_dir=sort_dir)

    page_rows, pagination = paginate_items(
        rows,
        base_path=request.url.path,
        params={
            "date_from": date_from,
            "date_to": date_to,
            "tool_type_id": tool_type_id,
            "tool_name": tool_name,
            "search": search,
            "min_consumed": min_consumed,
            "min_share": min_share,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        },
        page=page,
        per_page=per_page,
        id_prefix="financialTable",
    )

    tool_types = db.query(ToolType).order_by(ToolType.name).all()

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="financials/table.html",
        context={
            "active_page": "financials",
            "active_financial_view": "table",
            "financial_nav_query": _financial_nav_query(
                date_from=date_from,
                date_to=date_to,
                tool_type_id=tool_type_id,
                tool_name=tool_name,
            ),
            "tool_types": tool_types,
            "variations": page_rows,
            "pagination": pagination,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "sort_urls": _variation_sort_urls(
                request.url.path,
                date_from=date_from,
                date_to=date_to,
                tool_type_id=tool_type_id,
                tool_name=tool_name,
                search=search,
                min_consumed=min_consumed,
                min_share=min_share,
                per_page=pagination["per_page"],
                current_sort_by=sort_by,
                current_sort_dir=sort_dir,
            ),
            "search": search,
            "min_consumed": min_consumed,
            "min_share": min_share,
            "f_date_from": date_from,
            "f_date_to": date_to,
            "f_tool_type_id": tool_type_id,
            "f_tool_name": tool_name,
            "window_start": resolved_start.isoformat(),
            "window_end": resolved_end.isoformat(),
            "prev_window_start": prev_start.isoformat(),
            "prev_window_end": prev_end.isoformat(),
        },
    )


@router.get("/api/financials")
def api_financials(
    date_from: str = Query("", alias="date_from"),
    date_to: str = Query("", alias="date_to"),
    tool_type_id: int = Query(0, alias="tool_type_id"),
    tool_name: str = Query("", alias="tool_name"),
    db: Session = Depends(get_db),
):
    d_from = _parse_date(date_from) if date_from else None
    d_to = _parse_date(date_to) if date_to else None
    tt_id = tool_type_id if tool_type_id else None
    t_name = tool_name.strip() if tool_name else None

    resolved_start, resolved_end = _resolve_financial_window(d_from, d_to)
    payload = _build_financial_payload(
        db, d_from=d_from or resolved_start, d_to=d_to or resolved_end,
        tt_id=tt_id, t_name=t_name,
    )
    return JSONResponse(payload)
