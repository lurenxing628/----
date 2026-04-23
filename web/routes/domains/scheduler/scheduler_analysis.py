from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import g, request

from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, safe_int
from web.viewmodels.scheduler_summary_display import build_summary_display_state

from ...normalizers import _parse_result_summary_payload_with_meta, normalize_version_or_latest_fallback
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


def _selected_analysis_version(versions: List[Dict[str, Any]]) -> Optional[int]:
    latest_version = safe_int((versions[0] or {}).get("version"), default=0) if versions else 0
    if "version" in request.args:
        return normalize_version_or_latest_fallback(request.args.get("version"), latest_version=latest_version) or None
    if not versions:
        return None
    return safe_int((versions[0] or {}).get("version"), default=0) or None


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
    selected_ver = _selected_analysis_version(versions)

    raw_hist = _load_recent_analysis_history(q)
    selected_item = _load_selected_analysis_item(q, selected_ver)
    ctx = build_analysis_context(selected_ver=selected_ver, raw_hist=raw_hist, selected_item=selected_item)
    selected_history_resolution = build_requested_history_resolution(
        requested_version=selected_ver,
        selected_history=selected_item,
        missing_message=_missing_history_message(selected_ver),
    )
    _ensure_selected_analysis_context(
        ctx,
        selected_ver=selected_ver,
        selected_history_resolution=selected_history_resolution,
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
        **ctx,
    )
