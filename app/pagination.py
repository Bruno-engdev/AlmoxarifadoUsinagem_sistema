from math import ceil
from urllib.parse import urlencode


DEFAULT_PAGE_SIZE = 25
PAGE_SIZE_OPTIONS = (25, 50, 100)


def _page_window(page: int, total_pages: int) -> list[int | None]:
    if total_pages <= 7:
        return list(range(1, total_pages + 1))
    if page <= 3:
        return [1, 2, 3, 4, None, total_pages]
    if page >= total_pages - 2:
        return [1, None, total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
    return [1, None, page - 1, page, page + 1, None, total_pages]


def paginate_query(query, *, base_path: str, params: dict[str, object], page: int, per_page: int, id_prefix: str):
    per_page = per_page if per_page in PAGE_SIZE_OPTIONS else DEFAULT_PAGE_SIZE

    total_items = query.order_by(None).count()
    total_pages = max(1, ceil(total_items / per_page)) if total_items else 1
    page = min(max(page, 1), total_pages)

    items = query.limit(per_page).offset((page - 1) * per_page).all()
    start_item = 0 if total_items == 0 else (page - 1) * per_page + 1
    end_item = 0 if total_items == 0 else min(page * per_page, total_items)

    base_params = {key: value for key, value in params.items() if value not in (None, "")}
    base_params["per_page"] = per_page

    def page_url(page_number: int) -> str:
        query_params = dict(base_params)
        query_params["page"] = page_number
        return f"{base_path}?{urlencode(query_params)}"

    page_links = []
    for item in _page_window(page, total_pages):
        if item is None:
            page_links.append({"kind": "ellipsis", "label": "..."})
            continue
        page_links.append(
            {
                "kind": "page",
                "label": str(item),
                "number": item,
                "url": page_url(item),
                "current": item == page,
            }
        )

    form_params = {key: value for key, value in base_params.items() if key != "per_page"}

    return items, {
        "base_path": base_path,
        "id_prefix": id_prefix,
        "page": page,
        "per_page": per_page,
        "per_page_options": PAGE_SIZE_OPTIONS,
        "total_items": total_items,
        "total_pages": total_pages,
        "start_item": start_item,
        "end_item": end_item,
        "prev_url": page_url(page - 1) if page > 1 else None,
        "next_url": page_url(page + 1) if page < total_pages else None,
        "page_links": page_links,
        "form_params": form_params,
    }


def paginate_items(items: list, *, base_path: str, params: dict[str, object], page: int, per_page: int, id_prefix: str):
    per_page = per_page if per_page in PAGE_SIZE_OPTIONS else DEFAULT_PAGE_SIZE

    total_items = len(items)
    total_pages = max(1, ceil(total_items / per_page)) if total_items else 1
    page = min(max(page, 1), total_pages)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paged_items = items[start_idx:end_idx]
    start_item = 0 if total_items == 0 else start_idx + 1
    end_item = 0 if total_items == 0 else min(end_idx, total_items)

    base_params = {key: value for key, value in params.items() if value not in (None, "")}
    base_params["per_page"] = per_page

    def page_url(page_number: int) -> str:
        query_params = dict(base_params)
        query_params["page"] = page_number
        return f"{base_path}?{urlencode(query_params)}"

    page_links = []
    for item in _page_window(page, total_pages):
        if item is None:
            page_links.append({"kind": "ellipsis", "label": "..."})
            continue
        page_links.append(
            {
                "kind": "page",
                "label": str(item),
                "number": item,
                "url": page_url(item),
                "current": item == page,
            }
        )

    form_params = {key: value for key, value in base_params.items() if key != "per_page"}

    return paged_items, {
        "base_path": base_path,
        "id_prefix": id_prefix,
        "page": page,
        "per_page": per_page,
        "per_page_options": PAGE_SIZE_OPTIONS,
        "total_items": total_items,
        "total_pages": total_pages,
        "start_item": start_item,
        "end_item": end_item,
        "prev_url": page_url(page - 1) if page > 1 else None,
        "next_url": page_url(page + 1) if page < total_pages else None,
        "page_links": page_links,
        "form_params": form_params,
    }