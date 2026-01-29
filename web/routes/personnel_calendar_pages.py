from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from web.ui_mode import render_ui_template as render_template

from core.services.personnel import OperatorService
from core.services.scheduler import CalendarService, ConfigService

from .personnel_bp import bp, _day_type_zh


@bp.get("/<operator_id>/calendar")
def operator_calendar_page(operator_id: str):
    """
    人员专属工作日历页面（OperatorCalendar）。
    语义：若某日期存在个人配置，则覆盖全局 WorkCalendar。
    """
    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op = op_svc.get(operator_id)

    cal_svc = CalendarService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]
    for r in rows:
        r["day_type_zh"] = _day_type_zh(r.get("day_type") or "")

    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    hde = 0.8
    try:
        raw = cfg_svc.get("holiday_default_efficiency", default=0.8)
        hde = float(raw) if raw is not None else 0.8
        if hde <= 0:
            hde = 0.8
    except Exception:
        hde = 0.8

    return render_template(
        "personnel/calendar.html",
        title=f"个人工作日历 - {op.operator_id} {op.name}",
        operator=op.to_dict(),
        rows=rows,
        holiday_default_efficiency=hde,
    )


@bp.post("/<operator_id>/calendar/upsert")
def operator_calendar_upsert(operator_id: str):
    # 校验人员存在（避免 FK 失败给出英文错误）
    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    op_svc.get(operator_id)

    date_value = request.form.get("date")
    day_type = request.form.get("day_type")
    shift_hours = request.form.get("shift_hours")
    shift_start = request.form.get("shift_start")
    shift_end = request.form.get("shift_end")
    efficiency = request.form.get("efficiency")
    allow_normal = request.form.get("allow_normal")
    allow_urgent = request.form.get("allow_urgent")
    remark = request.form.get("remark")

    cal_svc = CalendarService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cal_svc.upsert_operator_calendar(
        operator_id=operator_id,
        date_value=date_value,
        day_type=day_type,
        shift_hours=shift_hours,
        shift_start=shift_start,
        shift_end=shift_end,
        efficiency=efficiency,
        allow_normal=allow_normal,
        allow_urgent=allow_urgent,
        remark=remark,
    )
    flash("个人日历配置已保存。", "success")
    return redirect(url_for("personnel.operator_calendar_page", operator_id=operator_id))

