from __future__ import annotations

from typing import Any, Dict, Optional

from flask import current_app, g, jsonify, request, url_for

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, ValidationError, error_response
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED
from core.services.scheduler.schedule_result_view_context import default_plan_resolution_dict
from core.services.scheduler.schedule_result_view_range import normalize_week_offset_for_explicit_range
from web.error_boundary import json_error_response
from web.routes.history_summary_logging import (
    log_history_summary_parse_warning,
    log_history_version_option_parse_warnings,
)
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import build_history_summary_display, decorate_history_version_options

from .scheduler_bp import bp


def _get_int_arg(name: str, default: int = 0) -> int:
    raw = request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception as e:
        raise ValidationError(f"{name} 填写不对，请填写整数。", field=name) from e


def _get_bool_arg(name: str, default: bool = False) -> bool:
    raw = request.args.get(name)
    if raw is None:
        return bool(default)
    v = str(raw).strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off", ""):
        return False
    raise ValidationError(f"{name} 填写不对，这里只能填写是或否。", field=name)


def _get_raw_arg(name: str, default: str = "0") -> str:
    raw = request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return str(default)
    return str(raw).strip()


def _get_effective_offset_for_display_range(*, start_date: Optional[str], end_date: Optional[str]) -> int:
    try:
        return normalize_week_offset_for_explicit_range(
            start_date=start_date,
            end_date=end_date,
            offset_weeks=_get_raw_arg("offset", "0"),
        )
    except ValidationError as exc:
        if (exc.details or {}).get("field") == "offset_weeks":
            raise ValidationError("offset 填写不对，请填写整数。", field="offset") from exc
        raise


def _get_plan_role_arg() -> Optional[str]:
    raw = request.args.get("plan_role")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _resolve_plan_context(services, version: Optional[int], plan_role: Optional[str]) -> Dict[str, Any]:
    plan_query_service = getattr(services, "schedule_plan_query_service", None)
    if plan_query_service is not None and version is not None:
        try:
            return plan_query_service.resolve_plan(int(version), plan_role).to_dict()
        except ValueError as exc:
            raise ValidationError(str(exc), field="plan_role") from exc
    gantt_service = getattr(services, "gantt_service", None)
    if gantt_service is not None and hasattr(gantt_service, "resolve_plan_context"):
        return gantt_service.resolve_plan_context(version, plan_role, plan_query_service=plan_query_service)
    return default_plan_resolution_dict(plan_role)


def _selected_version_result_status_label(services, version: Optional[int]) -> str:
    if version is None:
        return ""
    item = services.schedule_history_query_service.get_by_version(int(version))
    selected = item.to_dict() if item and hasattr(item, "to_dict") else None
    if not selected:
        return ""
    display = build_history_summary_display(
        raw_summary=selected.get("result_summary"),
        result_status=selected.get("result_status"),
    )
    log_history_summary_parse_warning(
        display.get("summary_parse_state") or {},
        version=selected.get("version"),
        source="selected",
        log_label="甘特图页",
    )
    return str(display.get("result_status_label") or "")


@bp.get("/gantt")
def gantt_page():
    """
    甘特图页面（Phase 8）。
    """
    view = (request.args.get("view") or "machine").strip()
    week_start = (request.args.get("week_start") or "").strip() or None
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    plan_role = _get_plan_role_arg()
    services = g.services
    effective_offset = _get_effective_offset_for_display_range(start_date=start_date, end_date=end_date)
    svc = services.gantt_service
    version_resolution = svc.resolve_version(request.args.get("version"))
    if version_resolution.status == "missing_history":
        raise BusinessError(
            ErrorCode.NOT_FOUND,
            "排产版本不存在，请先选择已有版本。",
            details={
                "field": "version",
                "requested_version": version_resolution.requested_version,
                "status": version_resolution.status,
            },
        )
    ver = version_resolution.selected_version
    plan_resolution = _resolve_plan_context(services, ver, plan_role)
    plan_query_service = getattr(services, "schedule_plan_query_service", None)
    wr, version_span, range_source = svc.resolve_gantt_range_for_version(
        version=ver,
        plan_role=plan_resolution.get("selected_role"),
        plan_query_service=plan_query_service,
        week_start=week_start,
        offset_weeks=effective_offset,
        start_date=start_date,
        end_date=end_date,
    )

    versions = decorate_history_version_options(services.schedule_history_query_service.list_versions(limit=30))
    log_history_version_option_parse_warnings(versions, log_label="甘特图页")
    selected_result_status_label = _selected_version_result_status_label(services, ver)
    return render_template(
        "scheduler/gantt.html",
        title="甘特图（排程可视化）",
        view=view,
        week_start=wr.week_start_date.isoformat(),
        week_end=wr.week_end_date.isoformat(),
        start_date=wr.week_start_date.isoformat(),
        end_date=wr.week_end_date.isoformat(),
        offset=effective_offset,
        version=ver,
        version_resolution=version_resolution.to_dict(),
        versions=versions,
        selected_result_status_label=selected_result_status_label,
        has_history=bool(versions),
        plan_role=plan_resolution.get("requested_role") or ROLE_ADOPTED,
        effective_plan_role=plan_resolution.get("selected_role") or ROLE_ADOPTED,
        plan_resolution=plan_resolution,
        plan_role_options=plan_resolution.get("available_roles") or [],
        version_span=version_span,
        range_source=range_source,
        data_url=url_for("scheduler.gantt_data"),
    )


@bp.get("/gantt/data")
def gantt_data():
    """
    甘特图数据接口：返回 tasks（Frappe Gantt 0.6.1）。
    """
    view = (request.args.get("view") or "machine").strip()
    week_start = (request.args.get("week_start") or "").strip() or None
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    plan_role = _get_plan_role_arg()
    svc = g.services.gantt_service
    try:
        effective_offset = _get_effective_offset_for_display_range(start_date=start_date, end_date=end_date)
        include_history = _get_bool_arg("include_history", False)
        data_kwargs: Dict[str, Any] = {
            "view": view,
            "week_start": week_start,
            "offset_weeks": effective_offset,
            "start_date": start_date,
            "end_date": end_date,
            "version": request.args.get("version"),
            "include_history": include_history,
        }
        if plan_role is not None:
            data_kwargs["plan_role"] = plan_role
        plan_query_service = getattr(g.services, "schedule_plan_query_service", None)
        if plan_query_service is not None:
            data_kwargs["plan_query_service"] = plan_query_service
        data: Dict[str, Any] = svc.get_gantt_tasks(**data_kwargs)
        return jsonify({"success": True, "data": data})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图数据生成失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图数据生成失败，请稍后重试。")), 500
