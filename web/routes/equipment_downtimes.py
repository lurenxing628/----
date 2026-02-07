from __future__ import annotations

from flask import current_app, flash, g, redirect, request, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import AppError
from core.services.equipment import MachineDowntimeService
from data.repositories import MachineRepository

from .equipment_bp import bp


# ============================================================
# 设备停机（MachineDowntimes）
# ============================================================


@bp.get("/downtimes/batch")
def downtime_batch_page():
    """
    批量停机计划：按设备/类别/全部创建停机区间。
    """
    repo = MachineRepository(g.db)
    machines = repo.list()
    categories = sorted({(m.category or "").strip() for m in machines if (m.category or "").strip()})
    machine_options = [(m.machine_id, f"{m.machine_id} {m.name}".strip()) for m in machines]
    machine_options.sort(key=lambda x: x[0])

    return render_template(
        "equipment/downtime_batch.html",
        title="批量停机计划",
        machine_options=machine_options,
        categories=categories,
        reason_options=list(MachineDowntimeService.REASON_OPTIONS),
    )


@bp.post("/downtimes/batch/create")
def downtime_batch_create():
    scope_type = request.form.get("scope_type")
    scope_value = request.form.get("scope_value") or None
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    reason_code = request.form.get("reason_code")
    reason_detail = request.form.get("reason_detail")

    svc = MachineDowntimeService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        res = svc.create_by_scope(
            scope_type=scope_type,
            scope_value=scope_value,
            start_time=start_time,
            end_time=end_time,
            reason_code=reason_code,
            reason_detail=reason_detail,
        )
        flash(f"已创建停机计划：影响设备 {res.get('created_count')} 台。", "success")
        skipped = res.get("skipped_overlap") or []
        if skipped:
            sample = "，".join(list(skipped)[:10])
            flash(f"以下设备因时间段重叠已跳过（最多 10 台）：{sample}", "warning")
    except AppError as e:
        flash(e.message, "error")
    except Exception:
        current_app.logger.exception("批量停机创建失败")
        flash("批量停机创建失败，请稍后重试。", "error")
    return redirect(url_for("equipment.downtime_batch_page"))


@bp.post("/<machine_id>/downtimes/create")
def create_downtime(machine_id: str):
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    reason_code = request.form.get("reason_code")
    reason_detail = request.form.get("reason_detail")

    svc = MachineDowntimeService(g.db, op_logger=getattr(g, "op_logger", None))
    d = svc.create(
        machine_id=machine_id,
        start_time=start_time,
        end_time=end_time,
        reason_code=reason_code,
        reason_detail=reason_detail,
    )
    flash(f"已新增停机计划（ID={d.id}）。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))


@bp.post("/<machine_id>/downtimes/<int:downtime_id>/cancel")
def cancel_downtime(machine_id: str, downtime_id: int):
    svc = MachineDowntimeService(g.db, op_logger=getattr(g, "op_logger", None))
    svc.cancel(downtime_id=downtime_id, machine_id=machine_id)
    flash("已取消停机计划。", "success")
    return redirect(url_for("equipment.detail_page", machine_id=machine_id))

