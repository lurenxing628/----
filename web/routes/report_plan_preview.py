from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from core.infrastructure.errors import ValidationError
from core.services.report import ReportEngine
from core.services.report.date_range_limits import ensure_report_date_range_within_limit
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED
from core.services.scheduler.schedule_result_view_context import default_plan_resolution_dict
from web.routes.domains.scheduler.scheduler_plan_context_token import request_scenario_id_from_args


def default_date_range(days: int = 7):
    end_d = date.today()
    start_d = end_d - timedelta(days=max(0, int(days) - 1))
    return start_d.isoformat(), end_d.isoformat()


def validate_ymd_date(raw: str, field: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValidationError("缺少开始日期或结束日期。", field="日期范围")

    text = text.replace("/", "-")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValidationError("日期格式不正确，请按 2026-03-13 或 2026/03/13 这样的格式填写。", field=field) from exc
    return text


def validate_explicit_report_date_range(start_raw: str, end_raw: str):
    start_text = validate_ymd_date(start_raw, field="开始日期")
    end_text = validate_ymd_date(end_raw, field="结束日期")
    start_date = datetime.strptime(start_text, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_text, "%Y-%m-%d").date()
    if end_date < start_date:
        raise ValidationError("结束日期不能早于开始日期", field="结束日期")
    ensure_report_date_range_within_limit(start_date, end_date, field="日期范围")
    return start_text, end_text


def request_scenario_id(args: Any) -> Optional[str]:
    return request_scenario_id_from_args(args)


def default_plan_resolution(version=None, raw_role=None) -> Dict[str, Any]:
    resolution = default_plan_resolution_dict(raw_role)
    resolution["version"] = version
    return resolution


def page_plan_resolution(plan_query_service, version, raw_role, scenario_id=None) -> Dict[str, Any]:
    if version is None:
        return default_plan_resolution(version=version, raw_role=raw_role)
    try:
        return plan_query_service.resolve_plan_view(int(version), raw_role, scenario_id).to_dict()
    except ValueError as exc:
        raise ValidationError(str(exc), field="scenario_id" if scenario_id else "plan_role") from exc


def page_date_range_or_version_span(
    engine: ReportEngine,
    version: int,
    plan_role,
    scenario_id,
    start_raw: str,
    end_raw: str,
):
    start_text = (start_raw or "").strip()
    end_text = (end_raw or "").strip()
    if start_text or end_text:
        start, end = validate_explicit_report_date_range(start_text, end_text)
        return start, end, "query", {"has_data": False}

    span = engine.version_date_range(int(version or 0), plan_role=plan_role, scenario_id=scenario_id)
    if span.get("has_data") and span.get("start_date") and span.get("end_date"):
        return str(span["start_date"]), str(span["end_date"]), "version_span", span

    start_7d, end_7d = default_date_range(days=7)
    return start_7d, end_7d, "default_7d", span


def export_date_range_or_version_span(
    engine: ReportEngine,
    version: int,
    plan_role,
    scenario_id,
    start_raw: str,
    end_raw: str,
):
    start_text = (start_raw or "").strip()
    end_text = (end_raw or "").strip()
    if start_text or end_text:
        return validate_explicit_report_date_range(start_text, end_text)
    span = engine.version_date_range(int(version or 0), plan_role=plan_role, scenario_id=scenario_id)
    if span.get("has_data") and span.get("start_date") and span.get("end_date"):
        return str(span["start_date"]), str(span["end_date"])
    raise ValidationError("暂无数据，不能导出。请调整版本或日期范围后再试。", field="导出")


def report_export_filters(engine: ReportEngine, version: int, raw_plan_role, scenario_id=None) -> dict:
    plan_resolution = engine.resolve_plan_context(int(version), raw_plan_role, scenario_id)
    return {
        "version": int(version),
        "requested_plan_role": plan_resolution.get("requested_role") or ROLE_ADOPTED,
        "effective_plan_role": plan_resolution.get("selected_role") or ROLE_ADOPTED,
        "plan_role_status": plan_resolution.get("status"),
        "candidate_id": plan_resolution.get("candidate_id"),
        "candidate_key": plan_resolution.get("candidate_key"),
        "scenario_id": plan_resolution.get("scenario_id"),
        "scenario_display_name": plan_resolution.get("scenario_display_name"),
    }
