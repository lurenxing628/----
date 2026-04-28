from __future__ import annotations

from typing import Optional, Sequence, cast

from flask import current_app, flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError
from web.error_boundary import user_visible_app_error_message
from web.viewmodels.scheduler_run_view_result import RunScheduleViewResult, build_run_schedule_view_result

from ...excel_utils import strict_mode_enabled as _strict_mode_enabled
from .scheduler_bp import (
    _surface_schedule_errors,
    _surface_schedule_warnings,
    _surface_secondary_degradation_messages,
    bp,
)


def _parse_optional_checkbox_flag(name: str):
    """
    解析 checkbox 三态：
    - key 不存在：None（由服务层回退默认配置）
    - key 存在且为真值：True
    - key 存在但非真值：False
    """
    if name not in request.form:
        return None
    raw = request.form.get(name)
    return str(raw or "").strip().lower() in ("yes", "y", "true", "1", "on")


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
    _surface_schedule_warnings(view_result.warning_messages)
    _surface_schedule_errors(view_result.error_preview, total=view_result.error_total)


@bp.post("/run")
def run_schedule():
    """
    执行排产（Phase 7）。
    """
    batch_ids = request.form.getlist("batch_ids")
    start_dt = request.form.get("start_dt") or None
    end_date = request.form.get("end_date") or None
    enforce_ready = _parse_optional_checkbox_flag("enforce_ready")
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    sch_svc = g.services.schedule_service
    try:
        result = sch_svc.run_schedule(
            batch_ids=batch_ids,
            start_dt=start_dt,
            end_date=end_date,
            created_by="web",
            enforce_ready=enforce_ready,
            strict_mode=strict_mode,
        )
        _flash_run_schedule_view_result(build_run_schedule_view_result(result))
    except AppError as e:
        flash(user_visible_app_error_message(e), "error")
    except Exception:
        current_app.logger.exception("排产执行失败")
        flash("排产失败，请稍后重试或联系管理员。", "error")

    return redirect(url_for("scheduler.batches_page"))
