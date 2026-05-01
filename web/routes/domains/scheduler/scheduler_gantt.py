from __future__ import annotations

from typing import Any, Dict, Optional

from flask import current_app, g, jsonify, request, url_for

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, ValidationError, error_response
from web.error_boundary import json_error_response
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import build_history_summary_display, decorate_history_version_options

from .scheduler_bp import bp


def _get_int_arg(name: str, default: int = 0) -> int:
    raw = request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception as e:
        raise ValidationError(f"{name} 不合法（期望整数）", field=name) from e


def _get_bool_arg(name: str, default: bool = False) -> bool:
    raw = request.args.get(name)
    if raw is None:
        return bool(default)
    v = str(raw).strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off", ""):
        return False
    raise ValidationError(f"{name} 不合法（期望布尔值）", field=name)


def _selected_version_result_status_label(services, version: Optional[int]) -> str:
    if version is None:
        return ""
    item = services.schedule_history_query_service.get_by_version(int(version))
    selected = item.to_dict() if item and hasattr(item, "to_dict") else None
    if not selected:
        return ""
    display = build_history_summary_display(
        raw_summary=selected.get("result_summary"),
        result_status=selected.get("result_status"),
    )
    return str(display.get("result_status_label") or "")


@bp.get("/gantt")
def gantt_page():
    """
    甘特图页面（Phase 8）。
    """
    view = (request.args.get("view") or "machine").strip()
    week_start = (request.args.get("week_start") or "").strip() or None
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    services = g.services
    offset = _get_int_arg("offset", 0)
    svc = services.gantt_service
    version_resolution = svc.resolve_version(request.args.get("version"))
    if version_resolution.status == "missing_history":
        raise BusinessError(
            ErrorCode.NOT_FOUND,
            "排产版本不存在，请先选择已有版本。",
            details={
                "field": "version",
                "requested_version": version_resolution.requested_version,
                "status": version_resolution.status,
            },
        )
    wr = svc.resolve_week_range(week_start=week_start, offset_weeks=offset, start_date=start_date, end_date=end_date)
    ver = version_resolution.selected_version

    versions = decorate_history_version_options(services.schedule_history_query_service.list_versions(limit=30))
    selected_result_status_label = _selected_version_result_status_label(services, ver)
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
        version_resolution=version_resolution.to_dict(),
        versions=versions,
        selected_result_status_label=selected_result_status_label,
        has_history=bool(versions),
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
    svc = g.services.gantt_service
    try:
        offset = _get_int_arg("offset", 0)
        # 当显式给出区间时，以 start/end 为准，避免客户端重复叠加 offset 造成“跳两周”。
        effective_offset = 0 if (start_date or end_date) else offset
        include_history = _get_bool_arg("include_history", False)
        data: Dict[str, Any] = svc.get_gantt_tasks(
            view=view,
            week_start=week_start,
            offset_weeks=effective_offset,
            start_date=start_date,
            end_date=end_date,
            version=request.args.get("version"),
            include_history=include_history,
        )
        return jsonify({"success": True, "data": data})
    except AppError as exc:
        return json_error_response(exc)
    except Exception:
        current_app.logger.exception("甘特图数据生成失败")
        return jsonify(error_response(ErrorCode.UNKNOWN_ERROR, "甘特图数据生成失败，请稍后重试。")), 500
