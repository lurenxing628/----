from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from core.models.enums import SourceType

from .scheduler_bp import bp


@bp.post("/ops/<int:op_id>/update")
def update_op(op_id: int):
    sch_svc = g.services.schedule_service
    op = sch_svc.get_operation(op_id)

    src = (getattr(op, "source", "") or "").strip().lower()
    if src == SourceType.INTERNAL.value:
        machine_id = request.form.get("machine_id") or None
        operator_id = request.form.get("operator_id") or None
        setup_hours = request.form.get("setup_hours")
        unit_hours = request.form.get("unit_hours")
        sch_svc.update_internal_operation(
            op_id=op_id,
            machine_id=machine_id,
            operator_id=operator_id,
            setup_hours=setup_hours,
            unit_hours=unit_hours,
        )
        flash("自制工序已保存。", "success")
    else:
        supplier_id = request.form.get("supplier_id") or None
        ext_days = request.form.get("ext_days")
        # merged 外协组时 ext_days 可能为空；服务层会区分 merged 限制与普通外协周期必填校验
        sch_svc.update_external_operation(op_id=op_id, supplier_id=supplier_id, ext_days=ext_days)
        flash("外协工序已保存。", "success")

    return redirect(url_for("scheduler.batch_detail", batch_id=op.batch_id))
