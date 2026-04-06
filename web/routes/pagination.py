from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple, TypeVar

from flask import Request

T = TypeVar("T")


def parse_page_args(
    req: Request,
    *,
    default_per_page: int = 100,
    max_per_page: int = 300,
) -> Tuple[int, int]:
    page_raw = (req.args.get("page") or "").strip()
    per_page_raw = (req.args.get("per_page") or "").strip()

    page = 1
    per_page = default_per_page
    try:
        if page_raw:
            page = int(page_raw)
    except Exception:
        page = 1
    try:
        if per_page_raw:
            per_page = int(per_page_raw)
    except Exception:
        per_page = default_per_page

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = default_per_page
    if per_page > max_per_page:
        per_page = max_per_page
    return page, per_page


def paginate_rows(rows: Sequence[T], page: int, per_page: int) -> Tuple[List[T], Dict[str, Any]]:
    total = len(rows or [])
    if per_page <= 0:
        per_page = 100
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    if page < 1:
        page = 1
    start = (page - 1) * per_page
    end = start + per_page
    page_rows = list(rows[start:end])
    pager = {
        "page": int(page),
        "per_page": int(per_page),
        "total": int(total),
        "total_pages": int(total_pages),
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else 1,
        "next_page": page + 1 if page < total_pages else total_pages,
    }
    return page_rows, pager
