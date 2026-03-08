from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.enums import CALENDAR_DAY_TYPE_STORED_VALUES, YESNO_VALUES, CalendarDayType
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.scheduler import CalendarService, ConfigService
from web.ui_mode import render_ui_template as render_template

from .scheduler_bp import bp
from .scheduler_utils import (
    _ensure_unique_ids,
    _normalize_calendar_date,
    _normalize_day_type,
    _normalize_yesno,
    _parse_mode,
    _read_uploaded_xlsx,
)

# ============================================================
# Excel：工作日历（WorkCalendar）
# ============================================================


@bp.get("/excel/calendar")
def excel_calendar_page():
    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing_list = []
    for c in cal_svc.list_all():
        existing_list.append(
            {
                "日期": c.date,
                "类型": _normalize_day_type(c.day_type),
                "可用工时": c.shift_hours,
                "效率": c.efficiency,
                "允许普通件": c.allow_normal,
                "允许急件": c.allow_urgent,
                "说明": c.remark,
            }
        )
    return render_template(
        "scheduler/excel_import_calendar.html",
        title="工作日历 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("scheduler.excel_calendar_preview"),
        confirm_url=url_for("scheduler.excel_calendar_confirm"),
        template_download_url=url_for("scheduler.excel_calendar_template"),
        export_url=url_for("scheduler.excel_calendar_export"),
    )


@bp.post("/excel/calendar/preview")
def excel_calendar_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    cfg_svc = ConfigService(g.db, op_logger=getattr(g, "op_logger", None))
    try:
        hde = float(cfg_svc.get("holiday_default_efficiency", default=0.8) or 0.8)
        if hde <= 0:
            hde = 0.8
    except Exception:
        hde = 0.8

    rows = _read_uploaded_xlsx(file)
    _ensure_unique_ids(rows, id_column="日期")

    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        item["日期"] = _normalize_calendar_date(item.get("日期"))
        item["类型"] = _normalize_day_type(item.get("类型"))
        item["允许普通件"] = _normalize_yesno(item.get("允许普通件"))
        item["允许急件"] = _normalize_yesno(item.get("允许急件"))
        # 说明字段：允许为空
        normalized_rows.append(item)

    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = {}
    existing_list = []
    for c in cal_svc.list_all():
        d = {
            "日期": c.date,
            "类型": _normalize_day_type(c.day_type),
            "可用工时": c.shift_hours,
            "效率": c.efficiency,
            "允许普通件": c.allow_normal,
            "允许急件": c.allow_urgent,
            "说明": c.remark,
        }
        existing[c.date] = d
        existing_list.append(d)

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("日期") or str(row.get("日期")).strip() == "":
            return "“日期”不能为空"
        # 严格日期校验（允许 YYYY/MM/DD；统一写回 YYYY-MM-DD）
        try:
            row["日期"] = CalendarService._normalize_date(row.get("日期"))  # type: ignore[attr-defined]
        except ValidationError as e:
            return e.message

        row["类型"] = _normalize_day_type(row.get("类型"))
        if row["类型"] not in CALENDAR_DAY_TYPE_STORED_VALUES:
            return "“类型”不合法（允许：workday/holiday；或中文：工作日/假期/节假日/周末）"

        sh = row.get("可用工时")
        if sh is None or str(sh).strip() == "":
            # 允许空：按类型给默认
            row["可用工时"] = 8 if row["类型"] == CalendarDayType.WORKDAY.value else 0
        else:
            try:
                v = float(sh)
                if v < 0:
                    return "“可用工时”不能为负数"
                row["可用工时"] = v
            except Exception:
                return "“可用工时”必须是数字"

        eff = row.get("效率")
        if eff is None or str(eff).strip() == "":
            row["效率"] = 1.0 if row["类型"] == CalendarDayType.WORKDAY.value else float(hde)
        else:
            try:
                v = float(eff)
                if v <= 0:
                    return "“效率”必须大于 0"
                row["效率"] = v
            except Exception:
                return "“效率”必须是数字"

        row["允许普通件"] = _normalize_yesno(row.get("允许普通件"))
        if row["允许普通件"] not in YESNO_VALUES:
            return "“允许普通件”不合法（允许：yes/no；或中文：是/否）"
        row["允许急件"] = _normalize_yesno(row.get("允许急件"))
        if row["允许急件"] not in YESNO_VALUES:
            return "“允许急件”不合法（允许：yes/no；或中文：是/否）"

        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=normalized_rows,
        id_column="日期",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="calendar",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return render_template(
        "scheduler/excel_import_calendar.html",
        title="工作日历 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("scheduler.excel_calendar_preview"),
        confirm_url=url_for("scheduler.excel_calendar_confirm"),
        template_download_url=url_for("scheduler.excel_calendar_template"),
        export_url=url_for("scheduler.excel_calendar_export"),
    )


@bp.post("/excel/calendar/confirm")
def excel_calendar_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    raw_rows_json = request.form.get("raw_rows_json")
    if not raw_rows_json:
        raise ValidationError("缺少预览数据，请重新上传并预览后再确认导入。")

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
    except Exception as e:
        raise ValidationError("预览数据解析失败，请重新上传并预览。") from e

    _ensure_unique_ids(rows, id_column="日期")

    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = {}
    for c in cal_svc.list_all():
        existing[c.date] = {
            "日期": c.date,
            "类型": _normalize_day_type(c.day_type),
            "可用工时": c.shift_hours,
            "效率": c.efficiency,
            "允许普通件": c.allow_normal,
            "允许急件": c.allow_urgent,
            "说明": c.remark,
        }

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("日期") or str(row.get("日期")).strip() == "":
            return "“日期”不能为空"
        try:
            row["日期"] = CalendarService._normalize_date(row.get("日期"))  # type: ignore[attr-defined]
        except ValidationError as e:
            return e.message
        row["类型"] = _normalize_day_type(row.get("类型"))
        if row["类型"] not in CALENDAR_DAY_TYPE_STORED_VALUES:
            return "“类型”不合法（允许：workday/holiday；或中文：工作日/假期/节假日/周末）"

        # 可用工时/效率/允许*
        sh = row.get("可用工时")
        if sh is None or str(sh).strip() == "":
            row["可用工时"] = 8 if row["类型"] == CalendarDayType.WORKDAY.value else 0
        else:
            try:
                v = float(sh)
                if v < 0:
                    return "“可用工时”不能为负数"
                row["可用工时"] = v
            except Exception:
                return "“可用工时”必须是数字"

        eff = row.get("效率")
        if eff is None or str(eff).strip() == "":
            row["效率"] = 1.0 if row["类型"] == CalendarDayType.WORKDAY.value else float(hde)
        else:
            try:
                v = float(eff)
                if v <= 0:
                    return "“效率”必须大于 0"
                row["效率"] = v
            except Exception:
                return "“效率”必须是数字"

        row["允许普通件"] = _normalize_yesno(row.get("允许普通件"))
        if row["允许普通件"] not in YESNO_VALUES:
            return "“允许普通件”不合法（允许：yes/no；或中文：是/否）"
        row["允许急件"] = _normalize_yesno(row.get("允许急件"))
        if row["允许急件"] not in YESNO_VALUES:
            return "“允许急件”不合法（允许：yes/no；或中文：是/否）"
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="日期",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    # 严格模式：只要存在错误行，就拒绝导入（规范用户行为）
    error_rows = [pr for pr in preview_rows if pr.status == RowStatus.ERROR]
    if error_rows:
        sample = "；".join([f"第{pr.row_num}行：{pr.message}" for pr in error_rows[:5] if pr and pr.message])
        flash(
            f"导入被拒绝：Excel 存在 {len(error_rows)} 行错误。请修正后重新预览并确认。{('错误示例：' + sample) if sample else ''}",
            "error",
        )
        return render_template(
            "scheduler/excel_import_calendar.html",
            title="工作日历 - Excel 导入/导出",
            existing_list=list(existing.values()),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("scheduler.excel_calendar_preview"),
            confirm_url=url_for("scheduler.excel_calendar_confirm"),
            template_download_url=url_for("scheduler.excel_calendar_template"),
            export_url=url_for("scheduler.excel_calendar_export"),
        )

    tx = TransactionManager(g.db)
    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []

    with tx.transaction():
        if mode == ImportMode.REPLACE:
            cal_svc.delete_all_no_tx()
            existing = {}  # 重要：REPLACE 后按“全新导入”处理，避免 APPEND/统计走错

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message and len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": pr.message})
                continue

            ds = str(pr.data.get("日期")).strip()
            if mode == ImportMode.APPEND and ds in existing:
                skip_count += 1
                continue

            existed = ds in existing
            # 注意：此处必须使用 no_tx，保证整批导入可整体回滚
            cal_svc.upsert_no_tx(
                {
                    "date": ds,
                    "day_type": pr.data.get("类型"),
                    "shift_hours": pr.data.get("可用工时"),
                    "efficiency": pr.data.get("效率"),
                    "allow_normal": pr.data.get("允许普通件"),
                    "allow_urgent": pr.data.get("允许急件"),
                    "remark": pr.data.get("说明"),
                }
            )
            if existed:
                update_count += 1
            else:
                new_count += 1

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="calendar",
        filename=filename,
        mode=mode,
        preview_or_result={
            "total_rows": len(preview_rows),
            "new_count": new_count,
            "update_count": update_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "errors_sample": errors_sample,
        },
        time_cost_ms=time_cost_ms,
    )

    flash(f"导入完成：新增 {new_count}，更新 {update_count}，跳过 {skip_count}，错误 {error_count}。", "success")
    return redirect(url_for("scheduler.excel_calendar_page"))


@bp.get("/excel/calendar/template")
def excel_calendar_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "工作日历.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="scheduler",
            target_type="calendar",
            template_or_export_type="工作日历模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_file(
            template_path,
            as_attachment=True,
            download_name="工作日历.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"])
    ws.append(["2026-01-21", "workday", 8, 1.0, "yes", "yes", "示例"])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="calendar",
        template_or_export_type="工作日历模板.xlsx",
        filters={},
        row_count=1,
        time_range={},
        time_cost_ms=time_cost_ms,
    )
    return send_file(
        output,
        as_attachment=True,
        download_name="工作日历.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/calendar/export")
def excel_calendar_export():
    start = time.time()
    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = cal_svc.list_all()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"])
    for c in rows:
        ws.append(
            [
                c.date,
                _normalize_day_type(c.day_type),
                c.shift_hours,
                c.efficiency,
                _normalize_yesno(c.allow_normal),
                _normalize_yesno(c.allow_urgent),
                c.remark,
            ]
        )

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="calendar",
        template_or_export_type="工作日历导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="工作日历.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

