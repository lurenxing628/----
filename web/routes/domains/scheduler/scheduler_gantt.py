from __future__ import annotations

from typing import Any, Dict, Optional

from flask import current_app, g, jsonify, render_template, request, url_for

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, ValidationError, error_response
from core.services.scheduler.schedule_plan_option_display import public_plan_role_options
from core.services.scheduler.schedule_result_view_context import selected_plan_role
from core.services.scheduler.schedule_result_view_range import normalize_week_offset_for_explicit_range
from web.error_boundary import json_error_response
from web.routes.history_summary_logging import (
    log_history_summary_parse_warning,
    log_history_version_option_parse_warnings,
)
from web.viewmodels.scheduler_gantt_task_detail import decorate_gantt_task_detail_payload
from web.viewmodels.scheduler_history_summary import (
    build_history_summary_display,
    decorate_history_version_options,
    format_public_date,
)

from .scheduler_bp import bp
from .scheduler_navigation_publish import (
    is_plan_preview,
    publish_gantt_navigation_context,
    requested_plan_role,
    resolve_navigation_plan_context,
    resolved_scenario_id,
)
from .scheduler_utils import get_plan_role_arg


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


def _get_optional_arg(name: str) -> Optional[str]:
    text = str(request.args.get(name) or "").strip()
    return text or None


def _gantt_data_scope_query() -> Dict[str, str]:
    query: Dict[str, str] = {}
    batch_id = _get_optional_arg("gantt_batch")
    resource_id = _get_optional_arg("gantt_resource")
    if batch_id:
        query["gantt_batch"] = batch_id
    if resource_id:
        query["gantt_resource"] = resource_id
    return query


def _gantt_page_scope_query(*, current_view: str, target_view: str) -> Dict[str, str]:
    query: Dict[str, str] = {}
    batch_id = _get_optional_arg("gantt_batch")
    resource_id = _get_optional_arg("gantt_resource")
    if batch_id:
        query["gantt_batch"] = batch_id
    if resource_id and str(current_view or "").strip() == str(target_view or "").strip():
        query["gantt_resource"] = resource_id
    return query


def _gantt_data_url() -> str:
    query: Dict[str, Any] = dict(_gantt_data_scope_query())
    return url_for("scheduler.gantt_data", **query)


def _gantt_page_url(
    *,
    current_view: str,
    target_view: str,
    version: Any,
    plan_role: Optional[str],
    scenario_id: Optional[str],
    gantt_zoom: str,
    week_start: Optional[str] = None,
    offset: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    args: Dict[str, Any] = {
        "view": target_view,
        "week_start": week_start,
        "offset": offset,
        "start_date": start_date,
        "end_date": end_date,
        "version": version,
        "plan_role": plan_role,
        "scenario_id": scenario_id,
        "gantt_zoom": gantt_zoom,
    }
    args.update(_gantt_page_scope_query(current_view=current_view, target_view=target_view))
    return url_for("scheduler.gantt_page", **{key: value for key, value in args.items() if str(value or "").strip()})


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


def _get_scenario_id_arg() -> Optional[str]:
    raw = request.args.get("scenario_id")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


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
    view = _get_raw_arg("view", "machine")
    week_start = _get_optional_arg("week_start")
    start_date = _get_optional_arg("start_date")
    end_date = _get_optional_arg("end_date")
    plan_role = get_plan_role_arg()
    scenario_id = _get_scenario_id_arg()
    gantt_zoom = _get_raw_arg("gantt_zoom", "day")
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
    plan_resolution = resolve_navigation_plan_context(services, ver, plan_role, scenario_id)
    plan_query_service = getattr(services, "schedule_plan_query_service", None)
    wr, version_span, range_source = svc.resolve_gantt_range_for_version(
        version=ver,
        plan_role=plan_resolution.get("selected_role"),
        scenario_id=plan_resolution.get("scenario_id"),
        plan_query_service=plan_query_service,
        week_start=week_start,
        offset_weeks=effective_offset,
        start_date=start_date,
        end_date=end_date,
    )

    versions = decorate_history_version_options(services.schedule_history_query_service.list_versions(limit=30))
    log_history_version_option_parse_warnings(versions, log_label="甘特图页")
    selected_result_status_label = _selected_version_result_status_label(services, ver)
    gantt_resource = (request.args.get("gantt_resource") or "").strip()
    gantt_zoom_value = gantt_zoom or "day"
    publish_gantt_navigation_context(
        version=ver,
        plan_resolution=plan_resolution,
        date_from=wr.week_start_date.isoformat(),
        date_to=wr.week_end_date.isoformat(),
        view=view,
        gantt_resource=gantt_resource,
        batch_id=_get_optional_arg("gantt_batch"),
        back_to=_get_optional_arg("back_to"),
    )
    gantt_view_urls = {
        "machine": _gantt_page_url(
            current_view=view,
            target_view="machine",
            version=ver,
            start_date=wr.week_start_date.isoformat(),
            end_date=wr.week_end_date.isoformat(),
            plan_role=requested_plan_role(plan_resolution),
            scenario_id=resolved_scenario_id(plan_resolution),
            gantt_zoom=gantt_zoom_value,
        ),
        "operator": _gantt_page_url(
            current_view=view,
            target_view="operator",
            version=ver,
            start_date=wr.week_start_date.isoformat(),
            end_date=wr.week_end_date.isoformat(),
            plan_role=requested_plan_role(plan_resolution),
            scenario_id=resolved_scenario_id(plan_resolution),
            gantt_zoom=gantt_zoom_value,
        ),
    }
    gantt_week_urls = {
        "prev": _gantt_page_url(
            current_view=view,
            target_view=view,
            version=ver,
            week_start=wr.week_start_date.isoformat(),
            offset=effective_offset - 1,
            plan_role=requested_plan_role(plan_resolution),
            scenario_id=resolved_scenario_id(plan_resolution),
            gantt_zoom=gantt_zoom_value,
        ),
        "current": _gantt_page_url(
            current_view=view,
            target_view=view,
            version=ver,
            week_start=wr.week_start_date.isoformat(),
            offset=0,
            plan_role=requested_plan_role(plan_resolution),
            scenario_id=resolved_scenario_id(plan_resolution),
            gantt_zoom=gantt_zoom_value,
        ),
        "next": _gantt_page_url(
            current_view=view,
            target_view=view,
            version=ver,
            week_start=wr.week_start_date.isoformat(),
            offset=effective_offset + 1,
            plan_role=requested_plan_role(plan_resolution),
            scenario_id=resolved_scenario_id(plan_resolution),
            gantt_zoom=gantt_zoom_value,
        ),
    }
    gantt_form_scope = _gantt_page_scope_query(current_view=view, target_view=view)
    return render_template(
        "scheduler/gantt.html",
        title="甘特图（排程可视化）",
        view=view,
        week_start=wr.week_start_date.isoformat(),
        week_end=wr.week_end_date.isoformat(),
        week_start_display=format_public_date(wr.week_start_date),
        week_end_display=format_public_date(wr.week_end_date),
        start_date=wr.week_start_date.isoformat(),
        end_date=wr.week_end_date.isoformat(),
        offset=effective_offset,
        version=ver,
        version_resolution=version_resolution.to_dict(),
        versions=versions,
        selected_result_status_label=selected_result_status_label,
        has_history=bool(versions),
        plan_role=requested_plan_role(plan_resolution),
        effective_plan_role=selected_plan_role(plan_resolution),
        plan_resolution=plan_resolution,
        plan_role_options=public_plan_role_options(plan_resolution),
        version_span=version_span,
        range_source=range_source,
        data_url=_gantt_data_url(),
        gantt_view_urls=gantt_view_urls,
        gantt_week_urls=gantt_week_urls,
        gantt_form_scope=gantt_form_scope,
        gantt_zoom=gantt_zoom,
        scenario_id=resolved_scenario_id(plan_resolution),
        scenario_name=plan_resolution.get("scenario_name"),
        scenario_display_name=plan_resolution.get("scenario_display_name"),
        is_scenario_preview=is_plan_preview(plan_resolution),
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
    plan_role = get_plan_role_arg()
    scenario_id = _get_scenario_id_arg()
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
        if scenario_id is not None:
            data_kwargs["scenario_id"] = scenario_id
        gantt_batch = _get_optional_arg("gantt_batch")
        gantt_resource = _get_optional_arg("gantt_resource")
        if gantt_batch:
            data_kwargs["batch_id"] = gantt_batch
        if gantt_resource:
            data_kwargs["resource_type"] = view
            data_kwargs["resource_id"] = gantt_resource
        plan_query_service = getattr(g.services, "schedule_plan_query_service", None)
        if plan_query_service is not None:
            data_kwargs["plan_query_service"] = plan_query_service
        data: Dict[str, Any] = svc.get_gantt_tasks(**data_kwargs)
        decorate_gantt_task_detail_payload(data)
        return jsonify({"success": True, "data": data})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图数据生成失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图数据生成失败，请稍后重试。")), 500
