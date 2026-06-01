from types import SimpleNamespace
from datetime import date

from app.main import app
from app.database import SessionLocal
from app.models import ToolType
from app.pagination import paginate_items
from app.routers.financials import (
    _build_financial_payload,
    _build_variation_rows,
    _filter_variation_rows,
    _sort_variation_rows,
    _financial_nav_query,
    _variation_sort_urls,
    _resolve_financial_window,
    _previous_window,
)


def main() -> None:
    db = SessionLocal()
    try:
        templates = app.state.templates
        user = SimpleNamespace(full_name="Teste", username="teste", role="ADMIN")
        request = SimpleNamespace(state=SimpleNamespace(current_user=user))
        d_from = date(2026, 4, 1)
        d_to = date(2026, 5, 31)
        resolved_start, resolved_end = _resolve_financial_window(d_from, d_to)
        prev_start, prev_end = _previous_window(resolved_start, resolved_end)
        tool_types = db.query(ToolType).order_by(ToolType.name).all()
        payload = _build_financial_payload(db, d_from=d_from, d_to=d_to, tt_id=None, t_name=None)
        financial_nav_query = _financial_nav_query(
            date_from="2026-04-01",
            date_to="2026-05-31",
            tool_type_id=0,
            tool_name="",
        )

        templates.env.get_template("financials.html").render(
            request=request,
            active_page="financials",
            active_financial_view="dashboard",
            financial_nav_query=financial_nav_query,
            payload=payload,
            tool_types=tool_types,
            f_date_from="2026-04-01",
            f_date_to="2026-05-31",
            f_tool_type_id=0,
            f_tool_name="",
            window_start=resolved_start.isoformat(),
            window_end=resolved_end.isoformat(),
            prev_window_start=prev_start.isoformat(),
            prev_window_end=prev_end.isoformat(),
        )

        rows = _sort_variation_rows(
            _filter_variation_rows(
                _build_variation_rows(db, d_from=d_from, d_to=d_to, tt_id=None, t_name=None),
                search="",
                min_consumed=None,
                min_share=None,
            ),
            sort_by="var_pct_abs",
            sort_dir="desc",
        )
        page_rows, pagination = paginate_items(
            rows,
            base_path="/financials/table",
            params={
                "date_from": "2026-04-01",
                "date_to": "2026-05-31",
                "tool_type_id": 0,
                "tool_name": "",
                "search": "",
                "min_consumed": "",
                "min_share": "",
                "sort_by": "var_pct_abs",
                "sort_dir": "desc",
            },
            page=1,
            per_page=25,
            id_prefix="financialTable",
        )
        sort_urls = _variation_sort_urls(
            "/financials/table",
            date_from="2026-04-01",
            date_to="2026-05-31",
            tool_type_id=0,
            tool_name="",
            search="",
            min_consumed="",
            min_share="",
            per_page=pagination["per_page"],
            current_sort_by="var_pct_abs",
            current_sort_dir="desc",
        )

        templates.env.get_template("financials_table.html").render(
            request=request,
            active_page="financials",
            active_financial_view="table",
            financial_nav_query=financial_nav_query,
            tool_types=tool_types,
            variations=page_rows,
            pagination=pagination,
            sort_by="var_pct_abs",
            sort_dir="desc",
            sort_urls=sort_urls,
            search="",
            min_consumed="",
            min_share="",
            f_date_from="2026-04-01",
            f_date_to="2026-05-31",
            f_tool_type_id=0,
            f_tool_name="",
            window_start=resolved_start.isoformat(),
            window_end=resolved_end.isoformat(),
            prev_window_start=prev_start.isoformat(),
            prev_window_end=prev_end.isoformat(),
        )
    finally:
        db.close()

    print(f"render-ok {len(page_rows)}")


if __name__ == "__main__":
    main()
