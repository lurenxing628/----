from __future__ import annotations

from typing import Optional, Sequence, cast

from flask import flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError
from web.routes.form_values import form_optional_toggle_bool, form_toggle_bool
from web.viewmodels.scheduler_run_view_result import RunScheduleViewResult, build_run_schedule_view_result

from .scheduler_bp import (
    _surface_public_summary_warnings,
    _surface_schedule_errors,
    _surface_secondary_degradation_messages,
    bp,
)
from .scheduler_gantt_redirect import build_success_gantt_redirect_kwargs
from .scheduler_user_messages import scheduler_user_visible_app_error_message


def _flash_run_schedule_view_result(view_result: RunScheduleViewResult) -> None:
    flash(view_result.headline_message, view_result.headline_category)
    if view_result.primary_degradation_message:
        flash(view_result.primary_degradation_message, "warning")
    if view_result.overdue_sample_message:
        flash(view_result.overdue_sample_message, "warning")
    warning_messages = cast(Optional[Sequence[str]], view_result.warning_messages)
    _surface_secondary_degradation_messages(
        view_result.secondary_degradation_messages,
        suppress_messages=warning_messages,
    )
    _surface_public_summary_warnings(view_result.raw_warning_messages)
    error_category = "error" if view_result.result_status in {"failed", "unknown"} else "warning"
    _surface_schedule_errors(view_result.error_preview, total=view_result.error_total, category=error_category)


@bp.post("/run")
def run_schedule():
    """
    执行排产（Phase 7）。
    """
    try:
        batch_ids = request.form.getlist("batch_ids")
        start_dt = request.form.get("start_dt") or None
        end_date = request.form.get("end_date") or None
        run_time_budget_seconds = request.form.get("run_time_budget_seconds") or None
        enforce_ready = form_optional_toggle_bool(request.form, "enforce_ready")
        strict_mode = form_toggle_bool(request.form, "strict_mode")
        sch_svc = g.services.schedule_service
        result = sch_svc.run_schedule(
            batch_ids=batch_ids,
            start_dt=start_dt,
            end_date=end_date,
            created_by="web",
            enforce_ready=enforce_ready,
            strict_mode=strict_mode,
            run_time_budget_seconds=run_time_budget_seconds,
        )
        view_result = build_run_schedule_view_result(result)
        if view_result.result_status in {"success", "partial"}:
            redirect_kwargs = build_success_gantt_redirect_kwargs(result, requested_start_dt=start_dt)
            _flash_run_schedule_view_result(view_result)
            return redirect(url_for("scheduler.gantt_page", **redirect_kwargs))
        _flash_run_schedule_view_result(view_result)
    except AppError as e:
        flash(scheduler_user_visible_app_error_message(e), "error")

    return redirect(url_for("scheduler.batches_page"))
