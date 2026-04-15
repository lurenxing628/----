from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.models.enums import CALENDAR_DAY_TYPE_STORED_VALUES, YESNO_VALUES, CalendarDayType
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_import_executor import execute_preview_rows_transactional
from core.services.common.excel_service import ExcelService, ImportMode
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.normalize import is_blank_value
from core.services.common.number_utils import parse_finite_float
from core.services.scheduler import CalendarService, ConfigService
from web.ui_mode import render_ui_template as render_template

from ...excel_utils import (
    build_error_rows_message,
    build_preview_baseline_token,
    collect_error_rows,
    extract_import_stats,
    flash_import_result,
    load_confirm_payload,
    preview_baseline_is_stale,
    send_excel_template_file,
)
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


def _canonicalize_calendar_date(value: Any) -> str:
    try:
        return CalendarService._normalize_date(value)  # type: ignore[attr-defined]
    except ValidationError:
        return _normalize_calendar_date(value)


def _build_existing_preview_data() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing: Dict[str, Dict[str, Any]] = {}
    existing_list: List[Dict[str, Any]] = []
    for c in cal_svc.list_all():
        item = {
            "日期": c.date,
            "类型": _normalize_day_type(c.day_type),
            "可用工时": c.shift_hours,
            "效率": c.efficiency,
            "允许普通件": c.allow_normal,
            "允许急件": c.allow_urgent,
            "说明": c.remark,
        }
        existing[c.date] = item
        existing_list.append(item)
    return existing, existing_list


def _calendar_baseline_extra_state(*, holiday_default_efficiency: float) -> Dict[str, Any]:
    return {"holiday_default_efficiency": float(holiday_default_efficiency)}


def _require_holiday_default_efficiency(value: Optional[float]) -> float:
    if value is None:
        raise ValidationError("holiday_default_efficiency 缺失，无法继续工作日历 Excel 导入。")
    return float(value)


def _render_excel_calendar_page(
    *,
    existing_list: List[Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
):
    return render_template(
        "scheduler/excel_import_calendar.html",
        title="工作日历 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("scheduler.excel_calendar_preview"),
        confirm_url=url_for("scheduler.excel_calendar_confirm"),
        template_download_url=url_for("scheduler.excel_calendar_template"),
        export_url=url_for("scheduler.excel_calendar_export"),
    )


def _load_holiday_default_efficiency_for_excel(
    *,
    cfg_svc: ConfigService,
    existing_list: List[Dict[str, Any]],
    mode_value: str,
    filename: Optional[str],
) -> Tuple[Optional[float], Optional[Any]]:
    try:
        return float(cfg_svc.get_holiday_default_efficiency()), None
    except ValidationError as exc:
        current_app.logger.warning(
            "工作日历 Excel 导入读取 holiday_default_efficiency 非法，已拒绝操作：%s",
            exc.message,
        )
        flash("系统配置项 holiday_default_efficiency 非法，无法继续工作日历 Excel 导入，请先在排产参数中修复。", "error")
        return None, _render_excel_calendar_page(
            existing_list=existing_list,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode_value,
            filename=filename,
        )


@bp.get("/excel/calendar")
def excel_calendar_page():
    _existing, existing_list = _build_existing_preview_data()
    return _render_excel_calendar_page(
        existing_list=existing_list,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
    )


@bp.post("/excel/calendar/preview")
def excel_calendar_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    existing, existing_list = _build_existing_preview_data()
    cfg_svc = ConfigService(g.db, op_logger=getattr(g, "op_logger", None))
    hde, error_response = _load_holiday_default_efficiency_for_excel(
        cfg_svc=cfg_svc,
        existing_list=existing_list,
        mode_value=mode.value,
        filename=file.filename,
    )
    if error_response is not None:
        return error_response
    hde_value = _require_holiday_default_efficiency(hde)

    rows = _read_uploaded_xlsx(file)

    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        item["日期"] = _canonicalize_calendar_date(item.get("日期"))
        item["类型"] = _normalize_day_type(item.get("类型"))
        item["允许普通件"] = _normalize_yesno(item.get("允许普通件"))
        item["允许急件"] = _normalize_yesno(item.get("允许急件"))
        # 说明字段：允许为空
        normalized_rows.append(item)
    _ensure_unique_ids(normalized_rows, id_column="日期")

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if is_blank_value(row.get("日期")):
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
                v = parse_finite_float(sh, field="可用工时")
                if v < 0:
                    return "“可用工时”不能为负数"
                row["可用工时"] = v
            except ValidationError as e:
                return e.message

        eff = row.get("效率")
        if eff is None or str(eff).strip() == "":
            row["效率"] = 1.0 if row["类型"] == CalendarDayType.WORKDAY.value else hde_value
        else:
            try:
                v = parse_finite_float(eff, field="效率")
                if v <= 0:
                    return "“效率”必须大于 0"
                row["效率"] = v
            except ValidationError as e:
                return e.message

        row["允许普通件"] = _normalize_yesno(row.get("允许普通件"))
        if row["允许普通件"] not in YESNO_VALUES:
            return "“允许普通件”不合法（允许：yes/no/true/false/1/0；或中文：是/否）"
        row["允许急件"] = _normalize_yesno(row.get("允许急件"))
        if row["允许急件"] not in YESNO_VALUES:
            return "“允许急件”不合法（允许：yes/no/true/false/1/0；或中文：是/否）"

        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=normalized_rows,
        id_column="日期",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )
    preview_baseline = build_preview_baseline_token(
        existing_data=existing,
        mode=mode,
        id_column="日期",
        extra_state=_calendar_baseline_extra_state(holiday_default_efficiency=hde_value),
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

    return _render_excel_calendar_page(
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
    )


@bp.post("/excel/calendar/confirm")
def excel_calendar_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    existing, existing_list = _build_existing_preview_data()
    cfg_svc = ConfigService(g.db, op_logger=getattr(g, "op_logger", None))
    hde, error_response = _load_holiday_default_efficiency_for_excel(
        cfg_svc=cfg_svc,
        existing_list=existing_list,
        mode_value=mode.value,
        filename=filename,
    )
    if error_response is not None:
        return error_response
    hde_value = _require_holiday_default_efficiency(hde)

    if preview_baseline_is_stale(
        payload.preview_baseline,
        existing_data=existing,
        mode=mode,
        id_column="日期",
        extra_state=_calendar_baseline_extra_state(holiday_default_efficiency=hde_value),
    ):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_excel_calendar_page(
            existing_list=existing_list,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
        )

    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        item["日期"] = _canonicalize_calendar_date(item.get("日期"))
        item["类型"] = _normalize_day_type(item.get("类型"))
        item["允许普通件"] = _normalize_yesno(item.get("允许普通件"))
        item["允许急件"] = _normalize_yesno(item.get("允许急件"))
        normalized_rows.append(item)
    _ensure_unique_ids(normalized_rows, id_column="日期")

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if is_blank_value(row.get("日期")):
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
                v = parse_finite_float(sh, field="可用工时")
                if v < 0:
                    return "“可用工时”不能为负数"
                row["可用工时"] = v
            except ValidationError as e:
                return e.message

        eff = row.get("效率")
        if eff is None or str(eff).strip() == "":
            row["效率"] = 1.0 if row["类型"] == CalendarDayType.WORKDAY.value else hde_value
        else:
            try:
                v = parse_finite_float(eff, field="效率")
                if v <= 0:
                    return "“效率”必须大于 0"
                row["效率"] = v
            except ValidationError as e:
                return e.message

        row["允许普通件"] = _normalize_yesno(row.get("允许普通件"))
        if row["允许普通件"] not in YESNO_VALUES:
            return "“允许普通件”不合法（允许：yes/no/true/false/1/0；或中文：是/否）"
        row["允许急件"] = _normalize_yesno(row.get("允许急件"))
        if row["允许急件"] not in YESNO_VALUES:
            return "“允许急件”不合法（允许：yes/no/true/false/1/0；或中文：是/否）"
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=normalized_rows,
        id_column="日期",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_excel_calendar_page(
            existing_list=existing_list,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
        )

    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing_row_ids = set(existing.keys())

    def _replace_existing_no_tx() -> None:
        if mode == ImportMode.REPLACE:
            cal_svc.delete_all_no_tx()

    def _row_id_getter(pr: Any) -> str:
        return str((getattr(pr, "data", None) or {}).get("日期") or "").strip()

    def _apply_row_no_tx(pr: Any, _existed: bool) -> None:
        ds = _row_id_getter(pr)
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

    stats = execute_preview_rows_transactional(
        g.db,
        mode=mode,
        preview_rows=preview_rows,
        existing_row_ids=existing_row_ids,
        replace_existing_no_tx=_replace_existing_no_tx,
        row_id_getter=_row_id_getter,
        apply_row_no_tx=_apply_row_no_tx,
        max_error_sample=10,
        process_unchanged=False,
        continue_on_app_error=False,
    )
    result = stats.to_dict()
    new_count, update_count, skip_count, error_count = extract_import_stats(result)
    result["total_rows"] = len(preview_rows)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="calendar",
        filename=filename,
        mode=mode,
        preview_or_result=result,
        time_cost_ms=time_cost_ms,
    )

    flash_import_result(
        new_count=new_count,
        update_count=update_count,
        skip_count=skip_count,
        error_count=error_count,
        errors_sample=result["errors_sample"],
    )
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
        return send_excel_template_file(template_path, download_name="工作日历.xlsx")

    template_def = get_template_definition("工作日历.xlsx")
    sample_rows = template_def.get("sample_rows") or []
    output = build_xlsx_bytes(
        template_def["headers"],
        sample_rows,
        format_spec=template_def.get("format_spec"),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="calendar",
        template_or_export_type="工作日历模板.xlsx",
        filters={},
        row_count=len(sample_rows),
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
    template_def = get_template_definition("工作日历.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [
            [
                c.date,
                _normalize_day_type(c.day_type),
                c.shift_hours,
                c.efficiency,
                _normalize_yesno(c.allow_normal),
                _normalize_yesno(c.allow_urgent),
                c.remark,
            ]
            for c in rows
        ],
        format_spec=template_def.get("format_spec"),
        sanitize_formula=True,
    )

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
