from __future__ import annotations

import time
from typing import Any, Dict, Optional

from flask import current_app, flash, g, redirect, render_template, request, url_for

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, ValidationError
from core.models.schedule_plan_role import VALID_PLAN_ROLES
from core.services.common.excel_audit import log_excel_export
from core.services.scheduler.schedule_plan_option_display import public_plan_role_options
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED
from core.services.scheduler.schedule_result_view_context import default_plan_resolution_dict, selected_plan_role
from core.services.scheduler.summary.schedule_summary_types import ScheduleResultStatus
from core.services.scheduler.week_plan_excel import build_week_plan_export_workbook
from core.shared.strict_parse import parse_required_int
from web.error_boundary import user_visible_app_error_message
from web.routes.form_values import form_optional_toggle_bool, form_toggle_bool
from web.routes.history_summary_logging import (
    log_history_summary_parse_warning,
    log_history_version_option_parse_warnings,
)
from web.viewmodels.scheduler_history_summary import (
    decorate_history_version_options,
    format_public_datetime,
    parse_history_summary_state,
    strategy_display_label,
)
from web.viewmodels.scheduler_summary_display import build_summary_display_state

from .scheduler_bp import (
    _surface_public_summary_warnings,
    _surface_schedule_errors,
    _surface_secondary_degradation_messages,
    bp,
)
from .scheduler_gantt_redirect import build_success_gantt_redirect_kwargs
from .scheduler_history_resolution import build_requested_history_resolution
from .scheduler_navigation_publish import (
    publish_week_plan_navigation_context,
    requested_plan_role,
    resolved_scenario_id,
)
from .scheduler_user_messages import scheduler_user_visible_app_error_message
from .scheduler_utils import _current_scheduler_operator, get_plan_role_arg
from .scheduler_week_plan_query import (
    request_week_plan_batch_id,
    request_week_plan_resource_context,
    week_plan_data_kwargs,
    week_plan_export_url,
)
from .scheduler_week_plan_response import send_week_plan_export_file


def _get_int_arg(name: str, default: int = 0) -> int:
    raw = request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return int(default)
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError) as e:
        raise ValidationError(f"{name} 填写不对，请填写整数。", field=name) from e


def _safe_redirect_plan_role(plan_role: Optional[str]) -> Optional[str]:
    text = str(plan_role or "").strip()
    return text if text in VALID_PLAN_ROLES else None


def _get_scenario_id_arg() -> Optional[str]:
    text = str(request.args.get("scenario_id") or "").strip()
    return text or None


def _fallback_plan_context(plan_role: Optional[str], version: Any = None) -> Dict[str, Any]:
    resolution = default_plan_resolution_dict(plan_role)
    resolution["version"] = version
    return resolution


def _plan_context_from_data(data: Dict[str, Any], plan_role: Optional[str]) -> Dict[str, Any]:
    plan_resolution = data.get("plan_role_resolution") if isinstance(data, dict) else None
    if isinstance(plan_resolution, dict):
        return plan_resolution
    version = data.get("version") if isinstance(data, dict) else None
    return _fallback_plan_context(plan_role, version=version)


def _load_selected_week_plan_summary(services, version: int):
    selected_history_item = services.schedule_history_query_service.get_by_version(version)
    selected_history = selected_history_item.to_dict() if hasattr(selected_history_item, "to_dict") else None
    if selected_history is not None:
        selected_history["schedule_time_display"] = format_public_datetime(selected_history.get("schedule_time"))
        selected_history["strategy_label"] = strategy_display_label(selected_history.get("strategy"))
    parse_state = parse_history_summary_state((selected_history or {}).get("result_summary"))
    log_history_summary_parse_warning(
        parse_state,
        version=(selected_history or {}).get("version"),
        log_label="周计划页",
        source="selected",
    )
    payload = parse_state.get("payload")
    selected_summary = payload if isinstance(payload, dict) else None
    summary_display = build_summary_display_state(
        selected_summary if isinstance(selected_summary, dict) else None,
        result_status=(selected_history or {}).get("result_status"),
        parse_state=parse_state,
    )
    return selected_history, selected_summary, summary_display


def _build_week_plan_preview_state(data):
    rows = data.get("rows") or []
    degradation_counters = data.get("degradation_counters") or {}
    bad_time_skipped = int(degradation_counters.get("bad_time_row_skipped") or 0)
    degradation_message = ""
    if bad_time_skipped > 0:
        degradation_message = f"已过滤 {bad_time_skipped} 条开始或结束时间写法不对的排程记录。"
    empty_message = "暂无数据（该周/该版本没有排程记录）。"
    if not rows and str(data.get("empty_reason") or "") == "all_rows_filtered_by_invalid_time":
        if bad_time_skipped > 0:
            empty_message = (
                f"已过滤 {bad_time_skipped} 条开始或结束时间写法不对的排程记录。"
                "当前区间没有可显示排程，请到系统管理里的排产历史查看这次排产的详细提醒。"
            )
        else:
            empty_message = "当前区间的排程开始或结束时间写法不对，已全部过滤，请到系统管理里的排产历史查看这次排产的详细提醒。"
    return {
        "rows": rows,
        "preview_rows": rows[:50],
        "degradation_message": degradation_message,
        "empty_message": empty_message,
    }


def _flash_summary_primary_degradation(summary_display):
    primary_degradation = summary_display.get("primary_degradation")
    if not isinstance(primary_degradation, dict):
        return
    details = "、".join(list(primary_degradation.get("details") or []))
    detail = f" 原因：{details}" if details else ""
    flash(f"{primary_degradation.get('message')}{detail}", "warning")


def _flash_simulate_completion(*, version: int, completion_status: str) -> None:
    if completion_status == ScheduleResultStatus.FAILED.value:
        flash(f"模拟排产失败：生成版本 {version}（不影响批次状态）。", "error")
        return
    if completion_status == ScheduleResultStatus.PARTIAL.value:
        flash(f"模拟排产部分完成：生成版本 {version}（不影响批次状态）。", "warning")
        return
    if completion_status == "unknown":
        flash(f"模拟排产结果有问题，需要检查：生成版本 {version}（不影响批次状态）。", "error")
        return
    flash(f"模拟排产完成：生成版本 {version}（不影响批次状态）。", "success")


def _simulate_result_version(result: Any) -> int:
    try:
        raw_version = result["version"]
    except (KeyError, TypeError) as exc:
        raise ValidationError("排产结果缺少可查看的版本号，本次不会跳到甘特图。请重试或联系管理员。", field="排产版本") from exc
    return parse_required_int(raw_version, field="排产版本", min_value=1)


def _simulate_result_without_viewable_version(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    return bool(result.get("is_simulation")) and result.get("can_open_result_version") is False


def _flash_simulate_validated_only(result: Dict[str, Any]) -> None:
    message = str(result.get("user_message") or "").strip()
    if not message:
        message = "现场已经有开工或完工记录，这次模拟只做安全检查，没有生成新的排程版本，也没有改动正式排程。"
    flash(message, "warning")


def _result_summary_dict(result: Any) -> dict:
    if not isinstance(result, dict):
        return {}
    summary = result.get("summary")
    return summary if isinstance(summary, dict) else {}


def _flash_simulate_summary(summary, summary_display, *, completion_status: str) -> None:
    _flash_summary_primary_degradation(summary_display)
    _surface_secondary_degradation_messages(
        summary_display.get("display_secondary_degradation_messages"),
        suppress_messages=summary.get("warnings"),
    )
    _surface_public_summary_warnings(summary.get("warnings"))
    error_category = "error" if completion_status in {ScheduleResultStatus.FAILED.value, "unknown"} else "warning"
    _surface_schedule_errors(
        summary_display.get("errors_preview"),
        total=int(summary_display.get("error_total") or 0),
        category=error_category,
    )


def _ensure_week_plan_exportable(data: Dict[str, Any]) -> None:
    if data.get("status") == "no_history":
        raise BusinessError(ErrorCode.NOT_FOUND, "暂无排产历史，无法导出周计划。", details={"field": "version", "status": "no_history"})


def _log_week_plan_export(
    *,
    data: Dict[str, Any],
    plan_resolution: Dict[str, Any],
    row_count: int,
    time_cost_ms: int,
) -> None:
    ver = int(data.get("version") or 0)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="week_plan",
        template_or_export_type="周计划表.xlsx",
        filters={
            "version": ver,
            "requested_plan_role": plan_resolution.get("requested_role") or ROLE_ADOPTED,
            "effective_plan_role": plan_resolution.get("selected_role") or ROLE_ADOPTED,
            "plan_role_status": plan_resolution.get("status"),
            "candidate_id": plan_resolution.get("candidate_id"),
            "candidate_key": plan_resolution.get("candidate_key"),
            "scenario_id": plan_resolution.get("scenario_id"),
            "scenario_name": plan_resolution.get("scenario_name"),
            "is_scenario_preview": bool(plan_resolution.get("is_scenario_preview")),
        },
        row_count=row_count,
        time_range={"start": data.get("week_start"), "end": data.get("week_end")},
        time_cost_ms=time_cost_ms,
        target_id=str(ver),
    )


def _week_plan_page_redirect(
    *,
    week_start: Optional[str],
    offset: int,
    version: Optional[str],
    plan_role: Optional[str],
    scenario_id: Optional[str],
    resource_context: Optional[Dict[str, Any]] = None,
    batch_id: Optional[str] = None,
):
    args: Dict[str, Any] = {
        "offset": str(int(offset)),
        "week_start": week_start,
        "version": version,
        "plan_role": plan_role,
        "scenario_id": scenario_id,
        "batch_id": batch_id,
        "resource_type": (resource_context or {}).get("resource_type"),
        "resource_id": (resource_context or {}).get("resource_id"),
    }
    return redirect(
        url_for(
            "scheduler.week_plan_page",
            **{k: v for k, v in args.items() if str(v or "").strip()},
        )
    )


def _handle_week_plan_export_app_error(error: AppError, *, redirect_context: Dict[str, Any]):
    if error.code == ErrorCode.NOT_FOUND:
        return user_visible_app_error_message(error), 404
    flash(user_visible_app_error_message(error), "error")
    context = dict(redirect_context)
    if isinstance(error, ValidationError) and error.field == "version":
        context["version"] = None
    return _week_plan_page_redirect(**context)


@bp.get("/week-plan")
def week_plan_page():
    week_start = (request.args.get("week_start") or "").strip() or None
    plan_role = get_plan_role_arg()
    scenario_id = _get_scenario_id_arg()
    services = g.services
    offset = _get_int_arg("offset", 0)
    svc = services.gantt_service
    wr = svc.resolve_week_range(week_start=week_start, offset_weeks=offset)
    resource_context = request_week_plan_resource_context()
    batch_id = request_week_plan_batch_id()

    versions = decorate_history_version_options(services.schedule_history_query_service.list_versions(limit=30))
    log_history_version_option_parse_warnings(versions, log_label="周计划页")
    data = svc.get_week_plan_rows(
        **week_plan_data_kwargs(
            week_start=wr.week_start_date.isoformat(),
            offset_weeks=0,
            version=request.args.get("version"),
            plan_role=plan_role,
            scenario_id=scenario_id,
            services=services,
            resource_context=resource_context,
            batch_id=batch_id,
        )
    )
    plan_resolution = _plan_context_from_data(data, plan_role)
    ver = data.get("version")
    selected_history, selected_summary, selected_summary_display = (
        _load_selected_week_plan_summary(services, int(ver))
        if ver is not None
        else (None, None, build_summary_display_state(None, result_status=None))
    )
    selected_history_resolution = build_requested_history_resolution(
        requested_version=data.get("requested_version") or ver,
        selected_history=selected_history,
        missing_message=f"v{ver} 无对应排产历史，当前仅展示排程明细，历史摘要不可用。",
    )
    preview_state = _build_week_plan_preview_state(data)
    publish_week_plan_navigation_context(
        version=ver,
        plan_resolution=plan_resolution,
        fallback_scenario_id=scenario_id,
        date_from=wr.week_start_date.isoformat(),
        date_to=wr.week_end_date.isoformat(),
        resource_context=resource_context,
        batch_id=batch_id,
        back_to=(request.args.get("back_to") or "").strip() or None,
    )

    return render_template(
        "scheduler/week_plan.html",
        title="周计划（导出）",
        degraded=bool(data.get("degraded")),
        degradation_message=preview_state["degradation_message"],
        empty_message=preview_state["empty_message"],
        week_start=wr.week_start_date.isoformat(),
        week_end=wr.week_end_date.isoformat(),
        offset=offset,
        version=ver,
        has_history=bool(data.get("has_history")),
        versions=versions,
        selected_history=selected_history,
        selected_history_resolution=selected_history_resolution,
        selected_summary=selected_summary,
        selected_summary_display=selected_summary_display,
        plan_role=requested_plan_role(plan_resolution),
        effective_plan_role=selected_plan_role(plan_resolution),
        plan_resolution=plan_resolution,
        scenario_id=resolved_scenario_id(plan_resolution, scenario_id),
        batch_id=batch_id,
        resource_type=(resource_context or {}).get("resource_type"),
        resource_id=(resource_context or {}).get("resource_id"),
        plan_role_options=public_plan_role_options(plan_resolution),
        preview_rows=preview_state["preview_rows"],
        total_rows=len(preview_state["rows"]),
        export_url=week_plan_export_url(
            version=ver,
            week_start=wr.week_start_date.isoformat(),
            plan_resolution=plan_resolution,
            resource_context=resource_context,
            batch_id=batch_id,
        ),
    )


@bp.get("/week-plan/export")
def week_plan_export():
    start = time.time()
    week_start = (request.args.get("week_start") or "").strip() or None
    plan_role = get_plan_role_arg()
    scenario_id = _get_scenario_id_arg()
    offset = _get_int_arg("offset", 0)
    resource_context = request_week_plan_resource_context()
    batch_id = request_week_plan_batch_id()
    redirect_context = {
        "week_start": week_start,
        "offset": offset,
        "version": request.args.get("version"),
        "plan_role": _safe_redirect_plan_role(plan_role),
        "scenario_id": scenario_id,
        "resource_context": resource_context,
        "batch_id": batch_id,
    }

    svc = g.services.gantt_service
    try:
        data = svc.get_week_plan_rows(
            **week_plan_data_kwargs(
                week_start=week_start,
                offset_weeks=offset,
                version=request.args.get("version"),
                plan_role=plan_role,
                scenario_id=scenario_id,
                services=g.services,
                resource_context=resource_context,
                batch_id=batch_id,
            )
        )
        plan_resolution = _plan_context_from_data(data, plan_role)
        _ensure_week_plan_exportable(data)
        rows = data.get("rows") or []
        ver = int(data.get("version") or 0)
        ws = data.get("week_start")
        we = data.get("week_end")

        output = build_week_plan_export_workbook(
            rows,
            plan_resolution=plan_resolution,
            export_context={"version": ver, "week_start": ws, "week_end": we},
        )

        time_cost_ms = int((time.time() - start) * 1000)
        _log_week_plan_export(
            data=data,
            plan_resolution=plan_resolution,
            row_count=len(rows),
            time_cost_ms=time_cost_ms,
        )

        return send_week_plan_export_file(output, version=ver, week_start=ws, week_end=we, plan_resolution=plan_resolution)
    except AppError as e:
        return _handle_week_plan_export_app_error(e, redirect_context=redirect_context)
    except Exception:
        current_app.logger.exception("导出周计划失败")
        flash("导出周计划失败，请稍后重试。", "error")
        return _week_plan_page_redirect(**redirect_context)


@bp.post("/simulate")
def simulate_schedule():
    """
    插单模拟（Phase 8）：
    - 选择批次执行一次“模拟排产”，落库到新版本（可追溯）
    - 不更新批次/工序状态（避免污染正式状态）
    """
    try:
        batch_ids = request.form.getlist("batch_ids")
        start_dt = request.form.get("start_dt") or None
        end_date = request.form.get("end_date") or None
        run_time_budget_seconds = request.form.get("run_time_budget_seconds") or None
        enforce_ready = form_optional_toggle_bool(request.form, "enforce_ready")
        strict_mode = form_toggle_bool(request.form, "strict_mode")
        if not batch_ids:
            flash("请至少选择 1 个批次进行模拟排产。", "error")
            return redirect(url_for("scheduler.batches_page"))

        sch_svc = g.services.schedule_service
        result = sch_svc.run_schedule(
            batch_ids=batch_ids,
            start_dt=start_dt,
            end_date=end_date,
            created_by=_current_scheduler_operator(),
            simulate=True,
            enforce_ready=enforce_ready,
            strict_mode=strict_mode,
            run_time_budget_seconds=run_time_budget_seconds,
        )
        result_dict = result if isinstance(result, dict) else {}
        summary = _result_summary_dict(result_dict)
        summary_display = build_summary_display_state(
            summary,
            result_status=result_dict.get("result_status") or ScheduleResultStatus.SIMULATED.value,
        )
        completion_status = str(summary_display.get("completion_status") or "success")
        if _simulate_result_without_viewable_version(result_dict):
            _flash_simulate_validated_only(result_dict)
            _flash_simulate_summary(summary, summary_display, completion_status=completion_status)
            return redirect(url_for("scheduler.batches_page"))

        ver = _simulate_result_version(result)
        _flash_simulate_completion(version=ver, completion_status=completion_status)
        _flash_simulate_summary(summary, summary_display, completion_status=completion_status)
        if completion_status not in {ScheduleResultStatus.SUCCESS.value, ScheduleResultStatus.PARTIAL.value}:
            return redirect(url_for("scheduler.batches_page"))

        return redirect(
            url_for(
                "scheduler.gantt_page",
                **build_success_gantt_redirect_kwargs(result, requested_start_dt=start_dt),
            )
        )
    except AppError as e:
        flash(scheduler_user_visible_app_error_message(e), "error")
        return redirect(url_for("scheduler.batches_page"))
