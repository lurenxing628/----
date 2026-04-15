from __future__ import annotations

import time
from datetime import date

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.services.common.excel_audit import log_excel_export
from core.services.common.excel_templates import build_xlsx_bytes
from web.ui_mode import render_ui_template as render_template

from ...excel_utils import strict_mode_enabled as _strict_mode_enabled
from ...normalizers import normalize_version_or_latest
from .scheduler_bp import _surface_schedule_warnings, bp


def _get_int_arg(name: str, default: int = 0) -> int:
    raw = request.args.get(name)
    if raw is None or str(raw).strip() == "":
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception as e:
        raise ValidationError(f"{name} 不合法（期望整数）", field=name) from e


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


@bp.get("/week-plan")
def week_plan_page():
    week_start = (request.args.get("week_start") or "").strip() or None
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    services = g.services
    offset = _get_int_arg("offset", 0)
    svc = services.gantt_service
    latest_version = svc.get_latest_version_or_1()
    wr = svc.resolve_week_range(week_start=week_start, offset_weeks=offset, start_date=start_date, end_date=end_date)
    ver = normalize_version_or_latest(request.args.get("version"), latest_version=latest_version)

    versions = services.schedule_history_query_service.list_versions(limit=30)
    data = svc.get_week_plan_rows(start_date=wr.week_start_date.isoformat(), end_date=wr.week_end_date.isoformat(), version=ver)

    rows = data.get("rows") or []
    degradation_counters = data.get("degradation_counters") or {}
    bad_time_skipped = int(degradation_counters.get("bad_time_row_skipped") or 0)
    preview_rows = rows[:50]
    degradation_message = ""
    if bad_time_skipped > 0:
        degradation_message = f"已过滤 {bad_time_skipped} 条时间不合法的排程记录。"
    empty_message = "暂无数据（该周/该版本没有排程记录）。"
    if not rows and str(data.get("empty_reason") or "") == "all_rows_filtered_by_invalid_time":
        empty_message = "当前区间存在时间非法的排程数据，已全部过滤，请检查排产结果。"

    return render_template(
        "scheduler/week_plan.html",
        title="周计划（导出）",
        degraded=bool(data.get("degraded")),
        degradation_message=degradation_message,
        empty_message=empty_message,
        week_start=wr.week_start_date.isoformat(),
        week_end=wr.week_end_date.isoformat(),
        start_date=wr.week_start_date.isoformat(),
        end_date=wr.week_end_date.isoformat(),
        offset=offset,
        version=ver,
        versions=versions,
        preview_rows=preview_rows,
        total_rows=len(rows),
        export_url=url_for(
            "scheduler.week_plan_export", start_date=wr.week_start_date.isoformat(), end_date=wr.week_end_date.isoformat(), version=ver
        ),
    )


@bp.get("/week-plan/export")
def week_plan_export():
    start = time.time()
    week_start = (request.args.get("week_start") or "").strip() or None
    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    offset = _get_int_arg("offset", 0)

    svc = g.services.gantt_service
    try:
        version = normalize_version_or_latest(request.args.get("version"), latest_version=svc.get_latest_version_or_1())

        data = svc.get_week_plan_rows(
            week_start=week_start, offset_weeks=offset, start_date=start_date, end_date=end_date, version=version
        )
        rows = data.get("rows") or []
        ver = int(data.get("version") or 1)
        ws = data.get("week_start")
        we = data.get("week_end")

        headers = ["日期", "批次号", "图号", "工序", "设备", "人员", "时段"]
        output = build_xlsx_bytes(
            headers,
            [[r.get(h, "") for h in headers] for r in rows],
            format_spec={
                "date_cols": [0],
                "text_cols": [1, 2, 4, 5, 6],
                "int_cols": [3],
                "column_widths": {0: 12, 1: 14, 2: 14, 3: 10, 4: 14, 5: 14, 6: 18},
            },
            sheet_title="周计划",
            sanitize_formula=True,
        )

        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="scheduler",
            target_type="week_plan",
            template_or_export_type="周计划表.xlsx",
            filters={"version": ver},
            row_count=len(rows),
            time_range={"start": ws, "end": we},
            time_cost_ms=time_cost_ms,
            target_id=str(ver),
        )

        filename = f"周计划表_v{ver}_{ws}_to_{we}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except AppError as e:
        flash(e.message, "error")
        return redirect(url_for("scheduler.week_plan_page"))
    except Exception:
        current_app.logger.exception("导出周计划失败")
        flash("导出周计划失败，请稍后重试。", "error")
        return redirect(url_for("scheduler.week_plan_page"))


@bp.post("/simulate")
def simulate_schedule():
    """
    插单模拟（Phase 8）：
    - 选择批次执行一次“模拟排产”，落库到新版本（可追溯）
    - 不更新批次/工序状态（避免污染正式状态）
    """
    batch_ids = request.form.getlist("batch_ids")
    start_dt = request.form.get("start_dt") or None
    end_date = request.form.get("end_date") or None
    enforce_ready = _parse_optional_checkbox_flag("enforce_ready")
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    if not batch_ids:
        flash("请至少选择 1 个批次进行模拟排产。", "error")
        return redirect(url_for("scheduler.batches_page"))

    sch_svc = g.services.schedule_service
    try:
        result = sch_svc.run_schedule(
            batch_ids=batch_ids,
            start_dt=start_dt,
            end_date=end_date,
            created_by="web",
            simulate=True,
            enforce_ready=enforce_ready,
            strict_mode=strict_mode,
        )
        ver = int(result.get("version") or 1)
        flash(f"模拟排产完成：生成版本 {ver}（不影响批次状态）。", "success")

        summary = result.get("summary") or {}
        _surface_schedule_warnings(summary.get("warnings"))

        # 默认跳到“本周”甘特图（设备视图）
        today = date.today().isoformat()
        return redirect(url_for("scheduler.gantt_page", view="machine", week_start=today, offset=0, version=ver))
    except AppError as e:
        flash(e.message, "error")
        return redirect(url_for("scheduler.batches_page"))
    except Exception:
        current_app.logger.exception("模拟排产失败")
        flash("模拟排产失败，请稍后重试。", "error")
        return redirect(url_for("scheduler.batches_page"))
