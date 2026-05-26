from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional

from core.services.scheduler.version_resolution import resolve_version_or_latest
from web.routes.history_summary_logging import (
    log_history_summary_parse_warning,
    log_history_version_option_parse_warnings,
)
from web.viewmodels.scheduler_analysis_metrics import extract_metrics_from_summary
from web.viewmodels.scheduler_analysis_trends import _metric_float_state, _metric_has_parse_failure, safe_int
from web.viewmodels.scheduler_history_summary import (
    decorate_history_version_options,
    format_public_datetime,
    parse_history_summary_state,
)

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
    parsed["schedule_time_display"] = format_public_datetime(parsed.get("schedule_time"))
    return parsed


def _load_recent_analysis_history(history_query_service) -> List[Dict[str, Any]]:
    return [_parse_analysis_summary(_history_item_to_dict(item), source="trend") for item in history_query_service.list_recent(limit=400)]


def _load_selected_analysis_item(history_query_service, selected_ver: Optional[int]) -> Optional[Dict[str, Any]]:
    if selected_ver is None:
        return None
    item = history_query_service.get_by_version(int(selected_ver))
    return None if item is None else _parse_analysis_summary(_history_item_to_dict(item), source="selected")


def _public_analysis_version_options(versions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in versions or []:
        public_item = dict(item or {})
        public_item.pop("result_summary", None)
        out.append(public_item)
    return out


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


_TREND_METRIC_KEYS = (
    "overdue_count",
    "total_tardiness_hours",
    "weighted_tardiness_hours",
    "makespan_hours",
    "makespan_internal_hours",
    "changeover_count",
    "machine_util_avg",
    "operator_util_avg",
)


def _trend_metric_parse_failed(item: Dict[str, Any]) -> bool:
    summary = (item or {}).get("result_summary")
    if not isinstance(summary, dict):
        return False
    metrics = extract_metrics_from_summary(summary)
    if not isinstance(metrics, dict):
        return False
    for key in _TREND_METRIC_KEYS:
        if _metric_has_parse_failure(metrics, key):
            return True
    return False


def _trend_summary_state(raw_hist: List[Dict[str, Any]]) -> Dict[str, Any]:
    parse_failed_count = sum(
        1 for item in raw_hist if bool(((item or {}).get("result_summary_parse_state") or {}).get("parse_failed"))
    )
    metric_parse_failed_count = sum(1 for item in raw_hist if _trend_metric_parse_failed(item))
    return {
        "incomplete": bool(parse_failed_count or metric_parse_failed_count),
        "parse_failed_count": int(parse_failed_count),
        "metric_parse_failed_count": int(metric_parse_failed_count),
    }


def _plan_role_option_to_dict(item: Any) -> Optional[Dict[str, Any]]:
    if hasattr(item, "to_dict"):
        data = item.to_dict()
        return dict(data) if isinstance(data, dict) else None
    if isinstance(item, dict):
        return dict(item)
    return None


class PlanRoleOptionsLoadResult(NamedTuple):
    options: List[Dict[str, Any]]
    integrity_notice: str


def _load_selected_plan_role_options(services: Any, selected_ver: Optional[int]) -> PlanRoleOptionsLoadResult:
    if selected_ver is None:
        return PlanRoleOptionsLoadResult([], "")
    plan_query_service = getattr(services, "schedule_plan_query_service", None)
    if plan_query_service is None:
        return PlanRoleOptionsLoadResult([], "")
    options: List[Dict[str, Any]] = []

    def _public_plan_role_error_message(error: Exception) -> str:
        raw = str(error or "")
        if "明细" in raw:
            return "方案对比明细不完整"
        if "缺少最终采用方案" in raw or "缺少正式采用方案" in raw:
            return "方案对比记录缺少正式采用方案"
        if "不存在" in raw or "找不到" in raw or "缺少" in raw:
            return "方案对比记录里的跳转关系不完整"
        return "方案对比记录需要检查"

    def _plan_role_integrity_notice(error: Exception) -> str:
        reason = _public_plan_role_error_message(error)
        if reason == "方案对比记录缺少正式采用方案":
            return f"本次方案对比记录不完整，当前不展示方案对比。原因：{reason}。"
        return f"本次方案对比记录不完整，当前只展示正式采用方案。原因：{reason}。"

    def _validate_plan_role_link_target(item: Any, option: Dict[str, Any]) -> None:
        resolve_plan = getattr(plan_query_service, "resolve_plan", None)
        if not callable(resolve_plan):
            return
        role = str(option.get("role") or getattr(item, "role", "") or "").strip()
        if role:
            resolution = resolve_plan(int(selected_ver), role)
            selected_role = str(getattr(resolution, "selected_role", role) or "").strip()
            if selected_role and selected_role != role:
                raise ValueError("方案对比明细和页面展示不一致。")
            for field in ("source_table", "candidate_key", "candidate_id"):
                option_value = option.get(field)
                resolution_value = getattr(resolution, field, option_value)
                if option_value is not None and resolution_value is not None and str(option_value) != str(resolution_value):
                    raise ValueError("方案对比明细和页面展示不一致。")

    try:
        items = plan_query_service.list_plan_roles(int(selected_ver))
    except ValueError as exc:
        return PlanRoleOptionsLoadResult([], _plan_role_integrity_notice(exc))
    for item in items:
        option = _plan_role_option_to_dict(item)
        if option:
            try:
                _validate_plan_role_link_target(item, option)
            except ValueError as exc:
                return PlanRoleOptionsLoadResult([], _plan_role_integrity_notice(exc))
            options.append(option)
    return PlanRoleOptionsLoadResult(options, "")


def _selected_item_needs_plan_role_options(selected_item: Optional[Dict[str, Any]]) -> bool:
    selected_summary = (selected_item or {}).get("result_summary")
    algo = selected_summary.get("algo") if isinstance(selected_summary, dict) else None
    comparison = algo.get("candidate_comparison") if isinstance(algo, dict) else None
    if not isinstance(comparison, dict):
        return False
    if comparison.get("enabled") is False:
        return False
    return comparison.get("planned_candidate_count") is not None


@dataclass(frozen=True)
class AnalysisReadContext:
    versions: List[Dict[str, Any]]
    version_resolution: Any
    selected_version: Optional[int]
    selected_item: Optional[Dict[str, Any]]
    raw_hist: List[Dict[str, Any]]
    selected_history_resolution: Dict[str, Any]
    trend_summary_state: Dict[str, Any]
    plan_role_options: List[Dict[str, Any]]
    plan_role_integrity_notice: str


def build_analysis_read_context(services: Any, raw_version: Any) -> AnalysisReadContext:
    history_query_service = services.schedule_history_query_service
    versions = history_query_service.list_versions(limit=50)
    selection = _select_analysis_version(history_query_service, versions=versions, raw_version=raw_version)
    version_options = _public_analysis_version_options(decorate_history_version_options(selection.versions))
    log_history_version_option_parse_warnings(version_options, log_label="排产分析页")

    raw_hist = _load_recent_analysis_history(history_query_service)
    requested_ver = (
        selection.version_resolution.requested_version
        if selection.version_resolution.requested_version is not None
        else selection.selected_version
    )
    selected_history_resolution = build_requested_history_resolution(
        requested_version=requested_ver,
        selected_history=selection.selected_item,
        missing_message=_missing_history_message(requested_ver),
    )
    plan_role_load = (
        _load_selected_plan_role_options(services, selection.selected_version)
        if _selected_item_needs_plan_role_options(selection.selected_item)
        else PlanRoleOptionsLoadResult([], "")
    )
    return AnalysisReadContext(
        versions=version_options,
        version_resolution=selection.version_resolution,
        selected_version=selection.selected_version,
        selected_item=selection.selected_item,
        raw_hist=raw_hist,
        selected_history_resolution=selected_history_resolution,
        trend_summary_state=_trend_summary_state(raw_hist),
        plan_role_options=plan_role_load.options,
        plan_role_integrity_notice=plan_role_load.integrity_notice,
    )


__all__ = [
    "AnalysisReadContext",
    "PlanRoleOptionsLoadResult",
    "build_analysis_read_context",
]
