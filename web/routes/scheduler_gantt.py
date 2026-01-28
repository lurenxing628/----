from __future__ import annotations

from typing import Any, Dict, Optional

from flask import g, jsonify, request, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import AppError, ValidationError
from core.services.scheduler import GanttService
from data.repositories import ScheduleHistoryRepository

from .scheduler_bp import bp


def _get_int_arg(name: str, default: int = 0) -> int:
    raw = request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception:
        raise ValidationError(f"{name} 不合法（期望整数）", field=name)


@bp.get("/gantt")
def gantt_page():
    """
    甘特图页面（Phase 8）。
    """
    view = (request.args.get("view") or "machine").strip()
    week_start = (request.args.get("week_start") or "").strip() or None
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    offset = _get_int_arg("offset", 0)
    version_raw = (request.args.get("version") or "").strip()
    version: Optional[int] = None
    if version_raw:
        try:
            version = int(version_raw)
        except Exception:
            raise ValidationError("version 不合法（期望整数）", field="version")

    svc = GanttService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    wr = svc.resolve_week_range(week_start=week_start, offset_weeks=offset, start_date=start_date, end_date=end_date)
    ver = version if version is not None else svc.get_latest_version_or_1()

    versions = ScheduleHistoryRepository(g.db).list_versions(limit=30)

    return render_template(
        "scheduler/gantt.html",
        title="甘特图（排程可视化）",
        view=view,
        week_start=wr.week_start_date.isoformat(),
        week_end=wr.week_end_date.isoformat(),
        start_date=wr.week_start_date.isoformat(),
        end_date=wr.week_end_date.isoformat(),
        offset=offset,
        version=ver,
        versions=versions,
        data_url=url_for("scheduler.gantt_data"),
    )


@bp.get("/gantt/data")
def gantt_data():
    """
    甘特图数据接口：返回 tasks（Frappe Gantt 0.6.1）。
    """
    view = (request.args.get("view") or "machine").strip()
    week_start = (request.args.get("week_start") or "").strip() or None
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    svc = GanttService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    try:
        offset = _get_int_arg("offset", 0)
        version_raw = (request.args.get("version") or "").strip()
        version: Optional[int] = None
        if version_raw:
            try:
                version = int(version_raw)
            except Exception:
                raise ValidationError("version 不合法（期望整数）", field="version")

        data: Dict[str, Any] = svc.get_gantt_tasks(
            view=view, week_start=week_start, offset_weeks=offset, start_date=start_date, end_date=end_date, version=version
        )
        return jsonify({"success": True, "data": data})
    except AppError as e:
        return jsonify({"success": False, "error": {"code": e.code.value, "message": e.message}}), 400
    except Exception as e:
        return jsonify({"success": False, "error": {"code": "UNKNOWN", "message": f"甘特图数据生成失败：{e}"}}), 500

