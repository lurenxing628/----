from __future__ import annotations

import io
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import ValidationError
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.common.excel_validators import get_operator_calendar_row_validate_and_normalize
from core.services.scheduler import CalendarService, ConfigService
from data.repositories import OperatorRepository

from .personnel_bp import (
    bp,
    _ensure_unique_ids,
    _normalize_operator_calendar_day_type,
    _normalize_yesno,
    _parse_mode,
    _read_uploaded_xlsx,
)


# ============================================================
# Excel：人员专属工作日历（OperatorCalendar）
# ============================================================


@bp.get("/excel/operator_calendar")
def excel_operator_calendar_page():
    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing_list: List[Dict[str, Any]] = []
    for c in cal_svc.list_operator_calendar_all():
        existing_list.append(
            {
                "工号": c.operator_id,
                "日期": c.date,
                "类型": _normalize_operator_calendar_day_type(c.day_type),
                "班次开始": c.shift_start,
                "班次结束": c.shift_end,
                "可用工时": c.shift_hours,
                "效率": c.efficiency,
                "允许普通件": c.allow_normal,
                "允许急件": c.allow_urgent,
                "说明": c.remark,
            }
        )
    return render_template(
        "personnel/excel_import_operator_calendar.html",
        title="人员专属工作日历 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("personnel.excel_operator_calendar_preview"),
        confirm_url=url_for("personnel.excel_operator_calendar_confirm"),
        template_download_url=url_for("personnel.excel_operator_calendar_template"),
        export_url=url_for("personnel.excel_operator_calendar_export"),
    )


@bp.post("/excel/operator_calendar/preview")
def excel_operator_calendar_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    # 读取假期默认效率（用于效率空值兜底）
    cfg_svc = ConfigService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        hde = float(cfg_svc.get("holiday_default_efficiency", default=0.8) or 0.8)
        if hde <= 0:
            hde = 0.8
    except Exception:
        hde = 0.8

    rows = _read_uploaded_xlsx(file)

    # 预标准化（用于生成复合键与提升预览可读性）
    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        op_id = str(item.get("工号") or "").strip()
        item["工号"] = op_id
        # 日期尽量标准化（失败留原值，让 validator 报错）
        try:
            item["日期"] = CalendarService._normalize_date(item.get("日期"))
        except Exception:
            item["日期"] = ("" if item.get("日期") is None else str(item.get("日期")).strip().replace("/", "-"))
        item["类型"] = _normalize_operator_calendar_day_type(item.get("类型"))
        item["允许普通件"] = _normalize_yesno(item.get("允许普通件"))
        item["允许急件"] = _normalize_yesno(item.get("允许急件"))
        item["__id"] = f"{op_id}|{str(item.get('日期') or '').strip()}"
        normalized_rows.append(item)

    _ensure_unique_ids(normalized_rows, id_column="__id")

    # existing（复合键：工号|日期）
    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing: Dict[str, Dict[str, Any]] = {}
    existing_list: List[Dict[str, Any]] = []
    for c in cal_svc.list_operator_calendar_all():
        d = {
            "工号": c.operator_id,
            "日期": c.date,
            "类型": _normalize_operator_calendar_day_type(c.day_type),
            "班次开始": c.shift_start,
            "班次结束": c.shift_end,
            "可用工时": c.shift_hours,
            "效率": c.efficiency,
            "允许普通件": c.allow_normal,
            "允许急件": c.allow_urgent,
            "说明": c.remark,
            "__id": f"{c.operator_id}|{c.date}",
        }
        existing[d["__id"]] = d
        existing_list.append(d)

    op_repo = OperatorRepository(g.db)

    validate_row = get_operator_calendar_row_validate_and_normalize(
        g.db,
        holiday_default_efficiency=hde,
        op_repo=op_repo,
        inplace=True,
    )

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=normalized_rows,
        id_column="__id",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_calendar",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return render_template(
        "personnel/excel_import_operator_calendar.html",
        title="人员专属工作日历 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("personnel.excel_operator_calendar_preview"),
        confirm_url=url_for("personnel.excel_operator_calendar_confirm"),
        template_download_url=url_for("personnel.excel_operator_calendar_template"),
        export_url=url_for("personnel.excel_operator_calendar_export"),
    )


@bp.post("/excel/operator_calendar/confirm")
def excel_operator_calendar_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    raw_rows_json = request.form.get("raw_rows_json")
    if not raw_rows_json:
        raise ValidationError("缺少预览数据，请重新上传并预览后再确认导入。")

    # 读取假期默认效率（用于效率空值兜底）
    cfg_svc = ConfigService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        hde = float(cfg_svc.get("holiday_default_efficiency", default=0.8) or 0.8)
        if hde <= 0:
            hde = 0.8
    except Exception:
        hde = 0.8

    try:
        rows = json.loads(raw_rows_json)
        if not isinstance(rows, list):
            raise ValueError("rows not list")
    except Exception:
        raise ValidationError("预览数据解析失败，请重新上传并预览。")

    _ensure_unique_ids(rows, id_column="__id")

    op_repo = OperatorRepository(g.db)
    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing: Dict[str, Dict[str, Any]] = {}
    for c in cal_svc.list_operator_calendar_all():
        existing[f"{c.operator_id}|{c.date}"] = {
            "工号": c.operator_id,
            "日期": c.date,
            "类型": _normalize_operator_calendar_day_type(c.day_type),
            "班次开始": c.shift_start,
            "班次结束": c.shift_end,
            "可用工时": c.shift_hours,
            "效率": c.efficiency,
            "允许普通件": c.allow_normal,
            "允许急件": c.allow_urgent,
            "说明": c.remark,
            "__id": f"{c.operator_id}|{c.date}",
        }

    validate_row = get_operator_calendar_row_validate_and_normalize(
        g.db,
        holiday_default_efficiency=hde,
        op_repo=op_repo,
        inplace=True,
    )

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="__id",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    error_rows = [pr for pr in preview_rows if pr.status == RowStatus.ERROR]
    if error_rows:
        sample = "；".join([f"第{pr.row_num}行：{pr.message}" for pr in error_rows[:5] if pr and pr.message])
        flash(
            f"导入被拒绝：Excel 存在 {len(error_rows)} 行错误。请修正后重新预览并确认。{('错误示例：' + sample) if sample else ''}",
            "error",
        )
        return render_template(
            "personnel/excel_import_operator_calendar.html",
            title="人员专属工作日历 - Excel 导入/导出",
            existing_list=list(existing.values()),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("personnel.excel_operator_calendar_preview"),
            confirm_url=url_for("personnel.excel_operator_calendar_confirm"),
            template_download_url=url_for("personnel.excel_operator_calendar_template"),
            export_url=url_for("personnel.excel_operator_calendar_export"),
        )

    import_stats = cal_svc.import_operator_calendar_from_preview_rows(
        preview_rows=preview_rows,
        mode=mode,
    )
    new_count = int(import_stats.get("new_count", 0))
    update_count = int(import_stats.get("update_count", 0))
    skip_count = int(import_stats.get("skip_count", 0))
    error_count = int(import_stats.get("error_count", 0))

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_calendar",
        filename=filename,
        mode=mode,
        preview_or_result=import_stats,
        time_cost_ms=time_cost_ms,
    )

    flash(f"导入完成：新增 {new_count}，更新 {update_count}，跳过 {skip_count}，错误 {error_count}。", "success")
    return redirect(url_for("personnel.excel_operator_calendar_page"))


@bp.get("/excel/operator_calendar/template")
def excel_operator_calendar_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "人员专属工作日历.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="personnel",
            target_type="operator_calendar",
            template_or_export_type="人员专属工作日历模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_file(
            template_path,
            as_attachment=True,
            download_name="人员专属工作日历.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工号", "日期", "类型", "班次开始", "班次结束", "可用工时", "效率", "允许普通件", "允许急件", "说明"])
    ws.append(["OP001", "2026-01-25", "holiday", "08:00", "", 0, 0.8, "no", "no", "示例：休假"])
    ws.append(["OP001", "2026-01-26", "holiday", "08:00", "16:00", "", "", "yes", "yes", "示例：假期加班（用班次结束推导工时）"])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_calendar",
        template_or_export_type="人员专属工作日历模板.xlsx",
        filters={},
        row_count=2,
        time_range={},
        time_cost_ms=time_cost_ms,
    )
    return send_file(
        output,
        as_attachment=True,
        download_name="人员专属工作日历.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/operator_calendar/export")
def excel_operator_calendar_export():
    start = time.time()
    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = cal_svc.list_operator_calendar_all()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工号", "日期", "类型", "班次开始", "班次结束", "可用工时", "效率", "允许普通件", "允许急件", "说明"])
    for c in rows:
        ws.append(
            [
                c.operator_id,
                c.date,
                _normalize_operator_calendar_day_type(c.day_type),
                c.shift_start,
                c.shift_end,
                c.shift_hours,
                c.efficiency,
                c.allow_normal,
                c.allow_urgent,
                c.remark,
            ]
        )

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_calendar",
        template_or_export_type="人员专属工作日历导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="人员专属工作日历.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

