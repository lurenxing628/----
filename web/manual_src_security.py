from __future__ import annotations

from typing import Any, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import has_request_context, request

from core.models.schedule_plan_role import VALID_PLAN_ROLES

_PLAN_CONTEXT_TOKEN_PATHS = {
    "/",
    "/reports",
    "/reports/",
    "/reports/overdue",
    "/reports/utilization",
    "/reports/execution-review",
    "/reports/downtime",
    "/scheduler/analysis",
    "/scheduler/gantt",
    "/scheduler/week-plan",
    "/scheduler/resource-dispatch",
}


def _has_forbidden_manual_chars(text: str) -> bool:
    # 控制字符/反斜杠守卫（开放重定向防护核心）：必须在 urlsplit 之前对原始 text 调用。
    return any(ch in text for ch in ("\r", "\n", "\x00", "\\"))


def _is_same_origin(parsed: Any, current: Any) -> bool:
    # 空 scheme/netloc 先判否（短路），再比 scheme/netloc 相等——退化输入（无 scheme）不放行。
    return (
        bool(parsed.scheme)
        and bool(parsed.netloc)
        and parsed.scheme == current.scheme
        and parsed.netloc == current.netloc
    )


def _compose_same_origin_candidate(parsed: Any, text: str) -> str:
    # 末尾空问号依赖原始 text（urlsplit 会丢空 query 的 '?'），故须传入 text 而非只传 parsed。
    candidate = parsed.path or "/"
    if parsed.query:
        candidate = f"{candidate}?{parsed.query}"
    elif text.endswith("?"):
        candidate = f"{candidate}?"
    if parsed.fragment:
        candidate = f"{candidate}#{parsed.fragment}"
    return candidate


def normalize_manual_src(text: str) -> Optional[str]:
    if not text or text.startswith("//") or _has_forbidden_manual_chars(text):
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.path.startswith("//"):
        return None
    if not parsed.scheme and not parsed.netloc:
        return text if parsed.path.startswith("/") else None
    if not has_request_context():
        return None
    current = urlsplit(request.host_url)
    if not _is_same_origin(parsed, current):
        return None
    return _compose_same_origin_candidate(parsed, text)


def _rewrite_manual_src_query_item(
    key: str,
    value: str,
    supports_plan_context_token: bool,
) -> Tuple[Optional[Tuple[str, str]], bool, str, bool]:
    value_text = value.strip()
    if key == "plan_role" and value_text not in VALID_PLAN_ROLES:
        return None, True, "", False
    if supports_plan_context_token and key == "plan_context_token" and value_text:
        return (key, value), False, "", True
    if supports_plan_context_token and key == "scenario_id" and value_text:
        return None, True, value_text, False
    return (key, value), False, "", False


def _rewrite_manual_src_query(parts: Any) -> Tuple[List[Tuple[str, str]], bool]:
    query: List[Tuple[str, str]] = []
    changed = False
    scenario_for_token = ""
    has_plan_context_token = False
    supports_plan_context_token = parts.path in _PLAN_CONTEXT_TOKEN_PATHS
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query_item, item_changed, item_scenario, item_has_token = _rewrite_manual_src_query_item(
            key,
            value,
            supports_plan_context_token,
        )
        changed = changed or item_changed
        has_plan_context_token = has_plan_context_token or item_has_token
        if item_scenario:
            scenario_for_token = item_scenario
        if query_item is None:
            continue
        query.append(query_item)
    if scenario_for_token and not has_plan_context_token:
        from web.plan_context_token import plan_context_token

        query.append(("plan_context_token", plan_context_token(scenario_for_token)))
    return query, changed


def _sanitize_manual_src_context(src: Optional[str]) -> Optional[str]:
    if not src:
        return src
    parts = urlsplit(src)
    query, changed = _rewrite_manual_src_query(parts)
    if not changed:
        return src
    return urlunsplit(("", "", parts.path or "/", urlencode(query), parts.fragment))


def normalize_manual_src_context(raw: str) -> Optional[str]:
    return _sanitize_manual_src_context(normalize_manual_src(raw))
