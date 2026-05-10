from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from flask import current_app, g

from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import parse_required_int


def _parse_schedule_anchor_date(value: Any) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("/", "-").replace("T", " ")
    date_part = normalized.split(" ", 1)[0].strip()
    try:
        return datetime.strptime(date_part, "%Y-%m-%d").date()
    except ValueError:
        return None


def _result_start_week_span(result: Dict[str, Any], requested_start_dt: Any = None, *, version: Any = None) -> Dict[str, str]:
    raw_summary = result.get("summary")
    summary: Dict[str, Any] = raw_summary if isinstance(raw_summary, dict) else {}
    summary_start = summary.get("start_time")
    anchor = _parse_schedule_anchor_date(summary_start) or _parse_schedule_anchor_date(requested_start_dt)
    if anchor is None:
        current_app.logger.warning(
            "排产成功跳转甘特图缺少可解析日期范围：version=%s summary_start=%r requested_start_dt=%r",
            version,
            summary_start,
            requested_start_dt,
        )
        return {}
    return {
        "start_date": anchor.isoformat(),
        "end_date": (anchor + timedelta(days=6)).isoformat(),
    }


def build_success_gantt_redirect_kwargs(result: Dict[str, Any], *, requested_start_dt: Any = None) -> Dict[str, Any]:
    if "version" not in result:
        raise ValidationError("排产结果缺少可查看的版本号，本次不会跳到甘特图。请重试或联系管理员。", field="排产版本")
    version = parse_required_int(result["version"], field="排产版本", min_value=1)
    kwargs: Dict[str, Any] = {"view": "machine", "version": version}

    span = g.services.gantt_service.get_version_time_span_dates(version) or _result_start_week_span(
        result,
        requested_start_dt=requested_start_dt,
        version=version,
    )
    if span:
        kwargs["start_date"] = span["start_date"]
        kwargs["end_date"] = span["end_date"]
    return kwargs
