from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from core.infrastructure.errors import AppError
from core.services.scheduler import ScheduleService

from .scheduler_bp import bp


@bp.post("/run")
def run_schedule():
    """
    执行排产（Phase 7）。
    """
    batch_ids = request.form.getlist("batch_ids")
    start_dt = request.form.get("start_dt") or None
    end_date = request.form.get("end_date") or None
    enforce_ready = str(request.form.get("enforce_ready") or "").strip().lower() in ("yes", "y", "true", "1", "on")
    sch_svc = ScheduleService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    try:
        result = sch_svc.run_schedule(
            batch_ids=batch_ids,
            start_dt=start_dt,
            end_date=end_date,
            created_by="web",
            enforce_ready=enforce_ready,
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

        # 有错误则补充提示（最多 5 条）
        errs = summary.get("errors") or []
        if errs:
            for e in errs[:5]:
                flash(str(e), "warning")
    except AppError as e:
        flash(e.message, "error")
    except Exception as e:
        flash(f"排产失败：{e}", "error")

    return redirect(url_for("scheduler.batches_page"))

