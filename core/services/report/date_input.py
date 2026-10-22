"""Explicit report date input validation shared by old and new web adapters."""

from __future__ import annotations

from datetime import datetime

from core.errors import ValidationError
from core.services.report.date_range_limits import ensure_report_date_range_within_limit


def validate_ymd_date(raw: str, field: str):
    text = (raw or "").strip()
    if not text:
        raise ValidationError("缺少开始日期或结束日期。", field="日期范围")

    text = text.replace("/", "-")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("日期格式不正确，请按 2026-03-13 或 2026/03/13 这样的格式填写。", field=field) from exc
    return text, parsed


def validate_explicit_report_date_range(start_raw: str, end_raw: str):
    start_text, start_date = validate_ymd_date(start_raw, field="开始日期")
    end_text, end_date = validate_ymd_date(end_raw, field="结束日期")
    if end_date < start_date:
        raise ValidationError("结束日期不能早于开始日期", field="结束日期")
    ensure_report_date_range_within_limit(start_date, end_date, field="日期范围")
    return start_text, end_text
