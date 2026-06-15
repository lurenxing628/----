from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import g, has_request_context, request

from core.models.schedule_plan_role import VALID_PLAN_ROLES
from web.request_resource_context import request_report_resource_context
from web.viewmodels.plan_context_capsule import build_plan_context_capsule
from web.viewmodels.scheduler_navigation_links import (
    build_report_navigation_links as build_report_navigation_links_for_context,
)
from web.viewmodels.scheduler_navigation_links import (
    build_scheduler_navigation_links as build_scheduler_navigation_links_for_context,
)
from web.viewmodels.scheduler_navigation_links import (
    build_workbench_navigation_links as build_workbench_navigation_links_for_context,
)
from web.viewmodels.scheduler_navigation_links import (
    preserved_report_context_fields as preserved_report_context_fields_for_values,
)
from web.viewmodels.scheduler_workbench_links import build_workbench_plan_context

ROLE_ADOPTED = "adopted"
_NAVIGATION_CONTEXT_ATTR = "_workbench_navigation_context"
_PUBLIC_RETURN_DROP_QUERY_KEYS = {
    "scenario_id",
    "op_id",
    "schedule_id",
    "candidate_id",
    "candidate_key",
    "selection_candidate_id",
    "resolved_candidate_id",
    "source_table",
    "source_row_id",
    "related_op_id",
    "base_plan_role",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _request_arg(name: str) -> str:
    if not has_request_context():
        return ""
    return _text(request.args.get(name))


def _request_values() -> Dict[str, str]:
    if not has_request_context():
        return {}
    return {str(key): _text(request.args.get(key)) for key in request.args.keys()}


def _request_plan_context_token(scenario_id: str) -> str:
    token = _request_arg("plan_context_token")
    if token:
        return token
    if not scenario_id:
        return ""
    from web.routes.domains.scheduler.scheduler_plan_context_token import plan_context_token

    return plan_context_token(scenario_id)


def _is_scheduler_request() -> bool:
    return has_request_context() and _text(getattr(request, "path", "")).startswith("/scheduler")


def _request_resource() -> Dict[str, str]:
    return request_report_resource_context()


def set_current_workbench_navigation_context(context: Dict[str, Any]) -> None:
    if has_request_context():
        setattr(g, _NAVIGATION_CONTEXT_ATTR, dict(context or {}))


def publish_workbench_navigation_context(**kwargs: Any) -> Dict[str, Any]:
    context = build_workbench_plan_context(**kwargs)
    set_current_workbench_navigation_context(context)
    return context


def _navigation_context_override() -> Optional[Dict[str, Any]]:
    if not has_request_context():
        return None
    context = getattr(g, _NAVIGATION_CONTEXT_ATTR, None)
    return dict(context) if isinstance(context, dict) else None


def current_workbench_navigation_context() -> Dict[str, Any]:
    override = _navigation_context_override()
    if override is not None:
        return override
    plan_role = _request_arg("plan_role")
    scenario_id = _request_arg("scenario_id")
    plan_context_token = _request_plan_context_token(scenario_id)
    resource = _request_resource()
    return build_workbench_plan_context(
        version=_request_arg("version"),
        # 故意: fallback 只接受已登记的公开 role,非法 role 回 adopted 是 fail-closed 展示兜底。
        # 复盘页的正式身份护栏在 reports_page_support 页级 blocked 里执行,这里不信裸 role 放写入口。
        plan_role=plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED,
        scenario_id=scenario_id,
        plan_context_token=plan_context_token,
        date_from=_request_arg("start_date") or _request_arg("date_from"),
        date_to=_request_arg("end_date") or _request_arg("date_to"),
        query_date=_request_arg("query_date"),
        period_preset=_request_arg("period_preset"),
        batch_id=_request_arg("batch_id"),
        resource_type=resource["resource_type"],
        resource_id=resource["resource_id"],
        resource_label=resource["resource_label"],
        back_to=_request_arg("back_to"),
    )


def _plain_scheduler_chrome(context: Dict[str, Any]) -> bool:
    return _is_scheduler_request() and not (context.get("date_from") and context.get("date_to"))


def build_workbench_navigation_links() -> List[Dict[str, Any]]:
    context = current_workbench_navigation_context()
    return build_workbench_navigation_links_for_context(
        context,
        plain_scheduler_chrome=_plain_scheduler_chrome(context),
    )


def build_scheduler_navigation_links(active: str = "") -> List[Dict[str, Any]]:
    context = current_workbench_navigation_context()
    return build_scheduler_navigation_links_for_context(
        context,
        active=active,
        plain_scheduler_chrome=_plain_scheduler_chrome(context),
    )


def build_report_navigation_links(active: str = "") -> List[Dict[str, Any]]:
    return build_report_navigation_links_for_context(current_workbench_navigation_context(), active=active)


def preserved_report_context_fields(exclude: Iterable[str] = ()) -> List[Dict[str, str]]:
    values = _request_values()
    scenario_id = _text(values.get("scenario_id"))
    if scenario_id and not _text(values.get("plan_context_token")):
        values["plan_context_token"] = _request_plan_context_token(scenario_id)
    if _text(values.get("plan_context_token")):
        values.pop("scenario_id", None)
    return preserved_report_context_fields_for_values(exclude, values=values)


def current_public_return_url() -> str:
    """当前请求的公开版回跳 URL。

    普通筛选、页码继续保留；模拟方案的内部 scenario_id 转成公开 token；
    其他内部定位字段不带进页面链接或隐藏字段。
    """
    if not has_request_context():
        return "/"
    raw = str(getattr(request, "full_path", "") or getattr(request, "path", "") or "/")
    try:
        parts = urlsplit(raw)
    except ValueError:
        return "/"
    query = []
    scenario_id = ""
    has_plan_context_token = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key_s = str(key or "").strip()
        if key_s == "plan_context_token" and _text(value):
            has_plan_context_token = True
        if key_s == "scenario_id" and _text(value):
            scenario_id = _text(value)
            continue
        if key_s in _PUBLIC_RETURN_DROP_QUERY_KEYS:
            continue
        query.append((key_s, value))
    if scenario_id and not has_plan_context_token:
        from web.routes.domains.scheduler.scheduler_plan_context_token import plan_context_token

        token = plan_context_token(scenario_id)
        if token:
            query.append(("plan_context_token", token))
    return urlunsplit(("", "", parts.path or "/", urlencode(query), parts.fragment))


def workbench_plan_capsule() -> Optional[Dict[str, str]]:
    """壳层胶囊模板全局：当前导航上下文 → 胶囊五字段；无 version 页面返回 None。"""
    return build_plan_context_capsule(current_workbench_navigation_context())


__all__ = [
    "build_report_navigation_links",
    "build_scheduler_navigation_links",
    "build_workbench_navigation_links",
    "current_public_return_url",
    "current_workbench_navigation_context",
    "preserved_report_context_fields",
    "publish_workbench_navigation_context",
    "set_current_workbench_navigation_context",
    "workbench_plan_capsule",
]
