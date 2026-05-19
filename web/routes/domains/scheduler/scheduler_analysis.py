from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from flask import g, request, url_for

from core.services.scheduler.version_resolution import resolve_version_or_latest
from web.routes.history_summary_logging import (
    log_history_summary_parse_warning,
    log_history_version_option_parse_warnings,
)
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, build_candidate_comparison_display, safe_int
from web.viewmodels.scheduler_history_summary import decorate_history_version_options, parse_history_summary_state
from web.viewmodels.scheduler_summary_display import build_summary_display_state

from .scheduler_bp import bp
from .scheduler_history_resolution import build_requested_history_resolution


def _history_item_to_dict(item: Any) -> Dict[str, Any]:
    return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})


def _parse_analysis_summary(row: Dict[str, Any], *, source: str) -> Dict[str, Any]:
    parsed = dict(row or {})
    parse_state = parse_history_summary_state(parsed.get("result_summary"))
    log_history_summary_parse_warning(
        parse_state,
        version=parsed.get("version"),
        source=source,
        log_label="排产分析页",
    )
    payload = parse_state.get("payload")
    parsed["result_summary_parse_state"] = parse_state
    parsed["result_summary"] = payload if isinstance(payload, dict) else None
    return parsed


def _load_recent_analysis_history(history_query_service) -> List[Dict[str, Any]]:
    return [_parse_analysis_summary(_history_item_to_dict(item), source="trend") for item in history_query_service.list_recent(limit=400)]


def _load_selected_analysis_item(history_query_service, selected_ver: Optional[int]) -> Optional[Dict[str, Any]]:
    if selected_ver is None:
        return None
    item = history_query_service.get_by_version(int(selected_ver))
    return None if item is None else _parse_analysis_summary(_history_item_to_dict(item), source="selected")


@dataclass(frozen=True)
class _AnalysisVersionSelection:
    versions: List[Dict[str, Any]]
    version_resolution: Any
    selected_version: Optional[int]
    selected_item: Optional[Dict[str, Any]]


def _selected_analysis_version(version_resolution) -> Optional[int]:
    return version_resolution.selected_version


def _version_option_from_selected_item(item: Optional[Dict[str, Any]], selected_ver: int) -> Dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    option: Dict[str, Any] = {"version": int(selected_ver)}
    for key in ("schedule_time", "strategy", "result_status", "result_summary", "created_by"):
        if key in raw:
            option[key] = raw.get(key)
    return option


def _ensure_selected_version_option(
    versions: List[Dict[str, Any]],
    *,
    selected_ver: Optional[int],
    selected_item: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out = [dict(item or {}) for item in list(versions or [])]
    if selected_ver is None:
        return out
    if selected_item is None:
        return out
    selected = int(selected_ver)
    if any(safe_int((item or {}).get("version"), default=0) == selected for item in out):
        return out
    out.append(_version_option_from_selected_item(selected_item, selected))
    return out


def _select_analysis_version(
    history_query_service,
    *,
    versions: List[Dict[str, Any]],
    raw_version: Any,
) -> _AnalysisVersionSelection:
    selected_cache: Dict[int, Optional[Dict[str, Any]]] = {}

    def load_selected(version: int) -> Optional[Dict[str, Any]]:
        normalized = int(version)
        if normalized not in selected_cache:
            selected_cache[normalized] = _load_selected_analysis_item(history_query_service, normalized)
        return selected_cache[normalized]

    raw_missing = raw_version is None or str(raw_version).strip() == ""
    raw_text = "" if raw_missing else str(raw_version).strip()
    is_latest = raw_text.lower() == "latest"
    if raw_missing or is_latest:
        latest_version = safe_int(history_query_service.get_latest_version(), default=0)
        version_resolution = resolve_version_or_latest(raw_version, latest_version=latest_version)
    else:
        latest_version = safe_int((versions[0] or {}).get("version"), default=0) if versions else 0
        version_resolution = resolve_version_or_latest(
            raw_version,
            latest_version=latest_version,
            version_exists=lambda version: load_selected(int(version)) is not None,
        )

    selected_ver = _selected_analysis_version(version_resolution)
    selected_item = load_selected(int(selected_ver)) if selected_ver is not None else None
    return _AnalysisVersionSelection(
        versions=_ensure_selected_version_option(versions, selected_ver=selected_ver, selected_item=selected_item),
        version_resolution=version_resolution,
        selected_version=selected_ver,
        selected_item=selected_item,
    )


def _missing_history_message(selected_ver: Optional[int]) -> Optional[str]:
    if selected_ver is None:
        return None
    return f"v{selected_ver} 无对应排产历史，无法展示该版本摘要；趋势和其他可用分析仍按现有数据展示。"


def _selected_history_placeholder(selected_ver: int) -> Dict[str, Any]:
    return {
        "version": int(selected_ver),
        "schedule_time": None,
        "strategy": None,
        "result_status": None,
        "created_by": None,
        "result_summary_parse_state": {
            "payload": None,
            "parse_failed": False,
            "user_message": None,
            "reason": "missing_history",
        },
    }


def _ensure_selected_analysis_context(
    ctx: Dict[str, Any],
    *,
    selected_ver: Optional[int],
    selected_history_resolution: Dict[str, Any],
) -> None:
    if not selected_history_resolution.get("history_missing"):
        return
    if ctx.get("selected") is not None or selected_ver is None:
        return
    ctx["selected"] = _selected_history_placeholder(selected_ver)


def _trend_summary_state(raw_hist: List[Dict[str, Any]]) -> Dict[str, Any]:
    parse_failed_count = sum(
        1 for item in raw_hist if bool(((item or {}).get("result_summary_parse_state") or {}).get("parse_failed"))
    )
    return {
        "incomplete": bool(parse_failed_count),
        "parse_failed_count": int(parse_failed_count),
    }


def _plan_role_option_to_dict(item: Any) -> Optional[Dict[str, Any]]:
    if hasattr(item, "to_dict"):
        data = item.to_dict()
        return dict(data) if isinstance(data, dict) else None
    if isinstance(item, dict):
        return dict(item)
    return None


def _load_selected_plan_role_options(services: Any, selected_ver: Optional[int]) -> List[Dict[str, Any]]:
    if selected_ver is None:
        return []
    plan_query_service = getattr(services, "schedule_plan_query_service", None)
    if plan_query_service is None:
        return []
    options: List[Dict[str, Any]] = []
    for item in plan_query_service.list_plan_roles(int(selected_ver)):
        option = _plan_role_option_to_dict(item)
        if option:
            options.append(option)
    return options


def _plan_role_links(version: int, role: str) -> List[Dict[str, str]]:
    return [
        {
            "label": "设备甘特图",
            "url": url_for("scheduler.gantt_page", view="machine", version=version, plan_role=role),
        },
        {
            "label": "人员甘特图",
            "url": url_for("scheduler.gantt_page", view="operator", version=version, plan_role=role),
        },
        {
            "label": "周计划",
            "url": url_for("scheduler.week_plan_page", version=version, plan_role=role),
        },
        {
            "label": "资源排班",
            "url": url_for("scheduler.resource_dispatch_page", version=version, plan_role=role),
        },
    ]


def _attach_candidate_plan_links(ctx: Dict[str, Any], selected_ver: Optional[int]) -> None:
    display = ctx.get("candidate_comparison_display")
    if selected_ver is None or not isinstance(display, dict):
        return
    for row in list(display.get("rows") or []):
        if not isinstance(row, dict) or not row.get("plan_role_available"):
            continue
        role = str(row.get("role") or "").strip()
        if not role:
            continue
        row["links"] = _plan_role_links(int(selected_ver), role)


@bp.get("/analysis")
def analysis_page():
    q = g.services.schedule_history_query_service
    versions = q.list_versions(limit=50)
    selection = _select_analysis_version(q, versions=versions, raw_version=request.args.get("version"))
    version_resolution = selection.version_resolution
    selected_ver = selection.selected_version
    selected_item = selection.selected_item
    versions = decorate_history_version_options(selection.versions)
    log_history_version_option_parse_warnings(versions, log_label="排产分析页")

    raw_hist = _load_recent_analysis_history(q)
    ctx = build_analysis_context(selected_ver=selected_ver, raw_hist=raw_hist, selected_item=selected_item)
    initial_candidate_display = ctx.get("candidate_comparison_display")
    if isinstance(initial_candidate_display, dict) and initial_candidate_display.get("has_comparison"):
        plan_role_options = _load_selected_plan_role_options(g.services, selected_ver)
        ctx["candidate_comparison_display"] = build_candidate_comparison_display(
            ctx.get("selected_summary"),
            selected_ver=selected_ver,
            plan_role_options=plan_role_options,
        )
        _attach_candidate_plan_links(ctx, selected_ver)
    requested_ver = version_resolution.requested_version if version_resolution.requested_version is not None else selected_ver
    selected_history_resolution = build_requested_history_resolution(
        requested_version=requested_ver,
        selected_history=selected_item,
        missing_message=_missing_history_message(requested_ver),
    )

    selected_summary_display = build_summary_display_state(
        ctx.get("selected_summary"),
        result_status=(ctx.get("selected") or {}).get("result_status"),
        parse_state=(ctx.get("selected") or {}).get("result_summary_parse_state"),
    )

    return render_template(
        "scheduler/analysis.html",
        title="排产优化分析",
        versions=versions,
        selected_history_resolution=selected_history_resolution,
        selected_summary_display=selected_summary_display,
        trend_summary_state=_trend_summary_state(raw_hist),
        version_resolution=version_resolution.to_dict(),
        **ctx,
    )
