from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from web.ui_mode import render_ui_template as render_template

from core.services.scheduler import CalendarService

from .scheduler_bp import bp, _day_type_zh


@bp.get("/calendar")
def calendar_page():
    cal_svc = CalendarService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    rows = [c.to_dict() for c in cal_svc.list_all()]
    for r in rows:
        r["day_type_zh"] = _day_type_zh(r.get("day_type") or "")
    return render_template("scheduler/calendar.html", title="工作日历配置", rows=rows)


@bp.post("/calendar/upsert")
def calendar_upsert():
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
    cal_svc.upsert(
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
    flash("日历配置已保存。", "success")
    return redirect(url_for("scheduler.calendar_page"))

