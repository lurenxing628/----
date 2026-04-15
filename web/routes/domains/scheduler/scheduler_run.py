from __future__ import annotations

from flask import current_app, flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError

from ...excel_utils import strict_mode_enabled as _strict_mode_enabled
from .scheduler_bp import _surface_schedule_warnings, bp


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
        ver = result.get("version")
        summary = result.get("summary") or {}
        overdue = result.get("overdue_batches") or []
        overdue_text = f"超期 {len(overdue)} 个" if overdue else "无超期"

        msg = (
            f"排产完成（版本 {ver}）：成功 {summary.get('scheduled_ops')}/{summary.get('total_ops')}，"
            f"失败 {summary.get('failed_ops')}。{overdue_text}。"
        )
        flash(msg, "success")

        if overdue:
            sample = "，".join([x.get("batch_id") for x in overdue[:10] if x.get("batch_id")])
            if sample:
                flash(f"超期批次（最多展示10个）：{sample}", "warning")

        _surface_schedule_warnings(summary.get("warnings"))

        # 有错误则补充提示（最多 5 条）
        errs = summary.get("errors") or []
        if errs:
            for e in errs[:5]:
                flash(str(e), "warning")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("排产执行失败")
        flash("排产失败，请稍后重试或联系管理员。", "error")

    return redirect(url_for("scheduler.batches_page"))
