from __future__ import annotations

import json
import os
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.services.common.enum_normalizers import calendar_day_type_label, yes_no_label
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.excel_validators import get_operator_calendar_row_validate_and_normalize
from core.services.common.normalize import to_str_or_blank
from core.services.personnel import OperatorService
from core.services.scheduler import CalendarService, ConfigService
from web.ui_mode import render_ui_template as render_template

from .excel_utils import (
    build_error_rows_message,
    build_preview_baseline_token,
    collect_error_rows,
    extract_import_stats,
    flash_import_result,
    load_confirm_payload,
    preview_baseline_is_stale,
    send_excel_template_file,
)
from .personnel_bp import (
    _ensure_unique_ids,
    _normalize_operator_calendar_day_type,
    _normalize_yesno,
    _parse_mode,
    _read_uploaded_xlsx,
    bp,
)

# ============================================================
# Excel：人员专属工作日历（OperatorCalendar）
# ============================================================


def _list_operator_ids() -> List[str]:
    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    return sorted([str(op.operator_id) for op in op_svc.list(status=None) if getattr(op, "operator_id", None)])


def _operator_calendar_baseline_extra_state(*, holiday_default_efficiency: float, operator_ids: List[str]) -> Dict[str, Any]:
    return {
        "holiday_default_efficiency": float(holiday_default_efficiency),
        "operator_ids": list(operator_ids or []),
    }


def _fallback_calendar_date_text(raw_date: Any) -> str:
    if isinstance(raw_date, datetime):
        return raw_date.date().isoformat()

    if isinstance(raw_date, date):
        return raw_date.isoformat()

    return to_str_or_blank(raw_date).replace("/", "-")[:10]


def _require_holiday_default_efficiency(value: Optional[float]) -> float:
    if value is None:
        raise ValidationError("“假期工作效率”配置缺失，无法继续人员专属工作日历 Excel 导入。")
    return float(value)


def _build_existing_operator_calendar_preview_data() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    existing: Dict[str, Dict[str, Any]] = {}
    existing_list: List[Dict[str, Any]] = []
    for c in cal_svc.list_operator_calendar_all():
        item = {
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
        existing[item["__id"]] = item
        existing_list.append(item)
    return existing, existing_list


def _render_excel_operator_calendar_page(
    *,
    existing_list: List[Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
):
    return render_template(
        "personnel/excel_import_operator_calendar.html",
        title="人员专属工作日历 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("personnel.excel_operator_calendar_preview"),
        confirm_url=url_for("personnel.excel_operator_calendar_confirm"),
        template_download_url=url_for("personnel.excel_operator_calendar_template"),
        export_url=url_for("personnel.excel_operator_calendar_export"),
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
            "人员专属工作日历 Excel 导入读取假期工作效率配置失败，已拒绝操作：%s",
            exc.message,
        )
        flash(
            "“假期工作效率”配置无效，无法继续人员专属工作日历 Excel 导入，请先在排产参数中修复。",
            "error",
        )
        return None, _render_excel_operator_calendar_page(
            existing_list=existing_list,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode_value,
            filename=filename,
        )


@bp.get("/excel/operator_calendar")
def excel_operator_calendar_page():
    _existing, existing_list = _build_existing_operator_calendar_preview_data()
    return _render_excel_operator_calendar_page(
        existing_list=existing_list,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
    )


@bp.post("/excel/operator_calendar/preview")
def excel_operator_calendar_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    existing, existing_list = _build_existing_operator_calendar_preview_data()

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

    # 预标准化（用于生成复合键与提升预览可读性）
    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        op_id = to_str_or_blank(item.get("工号"))
        item["工号"] = op_id
        # 日期尽量标准化（失败留原值，让 validator 报错）
        raw_date = item.get("日期")
        try:
            item["日期"] = CalendarService._normalize_date(raw_date)
        except ValidationError:
            item["日期"] = _fallback_calendar_date_text(raw_date)
        item["类型"] = _normalize_operator_calendar_day_type(item.get("类型"))
        item["允许普通件"] = _normalize_yesno(item.get("允许普通件"))
        item["允许急件"] = _normalize_yesno(item.get("允许急件"))
        item["__id"] = f"{op_id}|{to_str_or_blank(item.get('日期'))}"
        normalized_rows.append(item)

    _ensure_unique_ids(normalized_rows, id_column="__id")

    validate_row = get_operator_calendar_row_validate_and_normalize(
        g.db,
        holiday_default_efficiency=hde_value,
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
    operator_ids = _list_operator_ids()
    preview_baseline = build_preview_baseline_token(
        existing_data=existing,
        mode=mode,
        id_column="__id",
        extra_state=_operator_calendar_baseline_extra_state(
            holiday_default_efficiency=hde_value,
            operator_ids=operator_ids,
        ),
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

    return _render_excel_operator_calendar_page(
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
    )


@bp.post("/excel/operator_calendar/confirm")
def excel_operator_calendar_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    existing, existing_list = _build_existing_operator_calendar_preview_data()
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

    _ensure_unique_ids(rows, id_column="__id")

    cal_svc = CalendarService(g.db, op_logger=getattr(g, "op_logger", None))
    operator_ids = _list_operator_ids()
    if preview_baseline_is_stale(
        payload.preview_baseline,
        existing_data=existing,
        mode=mode,
        id_column="__id",
        extra_state=_operator_calendar_baseline_extra_state(
            holiday_default_efficiency=hde_value,
            operator_ids=operator_ids,
        ),
    ):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_excel_operator_calendar_page(
            existing_list=existing_list,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
        )

    validate_row = get_operator_calendar_row_validate_and_normalize(
        g.db,
        holiday_default_efficiency=hde_value,
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

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_excel_operator_calendar_page(
            existing_list=existing_list,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
        )

    import_stats = cal_svc.import_operator_calendar_from_preview_rows(
        preview_rows=preview_rows,
        mode=mode,
        existing_ids=set(existing.keys()),
    )
    new_count, update_count, skip_count, error_count = extract_import_stats(import_stats)

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

    flash_import_result(
        new_count=new_count,
        update_count=update_count,
        skip_count=skip_count,
        error_count=error_count,
        errors_sample=list(import_stats.get("errors_sample") or []),
    )
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
        return send_excel_template_file(template_path, download_name="人员专属工作日历.xlsx")

    template_def = get_template_definition("人员专属工作日历.xlsx")
    sample_rows = template_def.get("sample_rows") or []
    output = build_xlsx_bytes(
        template_def["headers"],
        sample_rows,
        format_spec=template_def.get("format_spec"),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_calendar",
        template_or_export_type="人员专属工作日历模板.xlsx",
        filters={},
        row_count=len(sample_rows),
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
    template_def = get_template_definition("人员专属工作日历.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [
            [
                c.operator_id,
                c.date,
                calendar_day_type_label(c.day_type),
                c.shift_start,
                c.shift_end,
                c.shift_hours,
                c.efficiency,
                yes_no_label(c.allow_normal, default="yes"),
                yes_no_label(c.allow_urgent, default="yes"),
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
