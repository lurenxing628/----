from __future__ import annotations

from flask import flash, g, redirect, request, url_for

from core.services.scheduler import CalendarService, ConfigService
from web.ui_mode import render_ui_template as render_template

from .scheduler_bp import _day_type_zh, bp
from .scheduler_utils import _normalize_day_type, _normalize_yesno


@bp.get("/calendar")
def calendar_page():
    cal_svc = CalendarService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    cfg_svc = ConfigService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    # 工作日历：假期默认效率（用于页面默认填充）
    hde = 0.8
    try:
        raw = cfg_svc.get("holiday_default_efficiency", default=0.8)
        hde = float(raw) if raw is not None else 0.8
        if hde <= 0:
            hde = 0.8
    except Exception:
        hde = 0.8
    rows = [c.to_dict() for c in cal_svc.list_all()]
    for r in rows:
        day_type = _normalize_day_type(r.get("day_type"))
        allow_normal = _normalize_yesno(r.get("allow_normal"))
        allow_urgent = _normalize_yesno(r.get("allow_urgent"))
        r["day_type"] = day_type
        r["allow_normal"] = allow_normal
        r["allow_urgent"] = allow_urgent
        r["day_type_zh"] = _day_type_zh(day_type)
        r["allow_normal_zh"] = "是" if allow_normal == "yes" else "否"
        r["allow_urgent_zh"] = "是" if allow_urgent == "yes" else "否"
    return render_template("scheduler/calendar.html", title="工作日历配置", rows=rows, holiday_default_efficiency=hde)


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

