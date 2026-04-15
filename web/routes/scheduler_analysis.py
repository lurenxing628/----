from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import g, request

from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, safe_int

from .normalizers import _parse_result_summary_payload, normalize_version_or_latest
from .scheduler_bp import bp


def _history_item_to_dict(item: Any) -> Dict[str, Any]:
    return item.to_dict() if hasattr(item, "to_dict") else dict(item or {})


def _parse_analysis_summary(row: Dict[str, Any], *, source: str) -> Dict[str, Any]:
    parsed = dict(row or {})
    if parsed.get("result_summary"):
        parsed["result_summary"] = _parse_result_summary_payload(
            parsed.get("result_summary"),
            version=parsed.get("version"),
            source=source,
            log_label="排产分析页",
        )
    return parsed


def _load_recent_analysis_history(history_query_service) -> List[Dict[str, Any]]:
    return [_parse_analysis_summary(_history_item_to_dict(item), source="trend") for item in history_query_service.list_recent(limit=400)]


def _load_selected_analysis_item(history_query_service, selected_ver: Optional[int]) -> Optional[Dict[str, Any]]:
    if selected_ver is None:
        return None
    item = history_query_service.get_by_version(int(selected_ver))
    return None if item is None else _parse_analysis_summary(_history_item_to_dict(item), source="selected")


@bp.get("/analysis")
def analysis_page():
    """
    排产效果/优化分析：
    - 展示 result_summary.algo 中的指标、尝试列表（attempts），以及最近版本趋势。
    - 不依赖外网与第三方图表库（Win7 离线可用）。
    """
    q = g.services.schedule_history_query_service
    versions = q.list_versions(limit=50)

    latest_version = safe_int((versions[0] or {}).get("version"), default=0) if versions else 0
    selected_ver: Optional[int] = None
    if "version" in request.args:
        selected_ver = normalize_version_or_latest(request.args.get("version"), latest_version=latest_version) or None
    else:
        if versions:
            selected_ver = safe_int((versions[0] or {}).get("version"), default=0) or None

    raw_hist = _load_recent_analysis_history(q)
    selected_item = _load_selected_analysis_item(q, selected_ver)
    ctx = build_analysis_context(selected_ver=selected_ver, raw_hist=raw_hist, selected_item=selected_item)

    return render_template(
        "scheduler/analysis.html",
        title="排产优化分析",
        versions=versions,
        **ctx,
    )

