from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from flask import g, request

from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, safe_int
from web.viewmodels.scheduler_summary_display import build_summary_display_state

from ...normalizers import (
    _parse_result_summary_payload_with_meta,
    decorate_history_version_options,
    resolve_route_version_or_latest,
)
from .scheduler_bp import bp
from .scheduler_history_resolution import build_requested_history_resolution


def _history_item_to_dict(item: Any) -> Dict[str, Any]:
    return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})


def _parse_analysis_summary(row: Dict[str, Any], *, source: str) -> Dict[str, Any]:
    parsed = dict(row or {})
    parsed["result_summary_parse_state"] = {
        "payload": None,
        "parse_failed": False,
        "user_message": None,
        "reason": None,
    }
    if parsed.get("result_summary"):
        parsed["result_summary_parse_state"] = _parse_result_summary_payload_with_meta(
            parsed.get("result_summary"),
            version=parsed.get("version"),
            source=source,
            log_label="排产分析页",
        )
        parsed["result_summary"] = parsed["result_summary_parse_state"].get("payload")
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
        version_resolution = resolve_route_version_or_latest(raw_version, latest_version=latest_version)
    else:
        latest_version = safe_int((versions[0] or {}).get("version"), default=0) if versions else 0
        version_resolution = resolve_route_version_or_latest(
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


@bp.get("/analysis")
def analysis_page():
    q = g.services.schedule_history_query_service
    versions = q.list_versions(limit=50)
    selection = _select_analysis_version(q, versions=versions, raw_version=request.args.get("version"))
    version_resolution = selection.version_resolution
    selected_ver = selection.selected_version
    selected_item = selection.selected_item
    versions = decorate_history_version_options(selection.versions, log_label="排产分析页")

    raw_hist = _load_recent_analysis_history(q)
    ctx = build_analysis_context(selected_ver=selected_ver, raw_hist=raw_hist, selected_item=selected_item)
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
