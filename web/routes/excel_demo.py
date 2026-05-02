from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.models.enums import OperatorStatus
from core.services.common.enum_normalizers import normalize_operator_status
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.normalize import is_blank_value
from core.services.personnel import OperatorService
from core.services.personnel.operator_excel_import_service import OperatorExcelImportService
from web.ui_mode import render_ui_template as render_template

from .excel_utils import (
    build_error_rows_message,
    build_preview_baseline_token,
    collect_error_rows,
    extract_import_stats,
    flash_import_result,
    load_confirm_payload,
    parse_import_mode,
    preview_baseline_is_stale,
    read_uploaded_xlsx,
    send_excel_template_file,
)

bp = Blueprint("excel_demo", __name__)


def _fetch_existing_operators(conn) -> Dict[str, Dict[str, Any]]:
    """以 Excel 列名（中文）构建 existing_data，便于 preview_import 做 diff。"""
    return OperatorService(conn, op_logger=None).build_existing_for_excel()


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _render_demo_page(
    *,
    existing: Dict[str, Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Any,
    preview_baseline: str,
    mode_value: str,
    filename: Any,
):
    return render_template(
        "excel/demo.html",
        title="Excel 导入演示",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("excel_demo.preview"),
        confirm_url=url_for("excel_demo.confirm"),
        template_download_url=url_for("excel_demo.download_template"),
    )


def _validate_operator_row(row: Dict[str, Any]) -> Optional[str]:
    # 返回中文错误提示；返回 None 表示通过
    if is_blank_value(row.get("工号")):
        return "“工号”不能为空"
    if is_blank_value(row.get("姓名")):
        return "“姓名”不能为空"

    st = normalize_operator_status(row.get("状态"))
    if not st:
        return "“状态”不能为空，请填写：在岗 或 停用。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。"
    if st not in (OperatorStatus.ACTIVE.value, OperatorStatus.INACTIVE.value):
        return "“状态”不合法，可填写：在岗 / 停用。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。"
    row["状态"] = st
    return None


@bp.get("/")
def index():
    existing = _fetch_existing_operators(g.db)
    return _render_demo_page(
        existing=existing,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline="",
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
    )


@bp.post("/preview")
def preview():
    start = time.time()

    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    parsed_rows = read_uploaded_xlsx(file)

    existing = _fetch_existing_operators(g.db)
    svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=g.op_logger)
    preview_rows = svc.preview_import(
        rows=parsed_rows,
        id_column="工号",
        existing_data=existing,
        validators=[_validate_operator_row],
        mode=mode,
    )
    preview_baseline = build_preview_baseline_token(existing_data=existing, mode=mode, id_column="工号")

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=g.op_logger,
        module="excel_demo",
        target_type="operator",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return _render_demo_page(
        existing=existing,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(parsed_rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
    )


@bp.post("/confirm")
def confirm():
    start = time.time()

    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    existing = _fetch_existing_operators(g.db)
    if preview_baseline_is_stale(payload.preview_baseline, existing_data=existing, mode=mode, id_column="工号"):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_demo_page(
            existing=existing,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline="",
            mode_value=mode.value,
            filename=filename,
        )
    backend = get_excel_backend()
    svc = ExcelService(backend=backend, logger=None, op_logger=g.op_logger)
    preview_rows = svc.preview_import(
        rows=rows,
        id_column="工号",
        existing_data=existing,
        validators=[_validate_operator_row],
        mode=mode,
    )

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_demo_page(
            existing=existing,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
        )

    import_svc = OperatorExcelImportService(
        g.db,
        logger=getattr(g, "app_logger", None),
        op_logger=getattr(g, "op_logger", None),
    )
    import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_ids=set(existing.keys()))
    new_count, update_count, skip_count, error_count = extract_import_stats(import_stats)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=g.op_logger,
        module="excel_demo",
        target_type="operator",
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
    return redirect(url_for("excel_demo.index"))


@bp.get("/template")
def download_template():
    """
    下载“人员基本信息.xlsx”模板（演示用）：列名与文档一致（工号/姓名/状态/班组/备注）。
    """
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "人员基本信息.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=g.op_logger,
            module="excel_demo",
            target_type="operator",
            template_or_export_type="人员基本信息模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_excel_template_file(template_path, download_name="人员基本信息.xlsx")

    template_def = get_template_definition("人员基本信息.xlsx")
    sample_rows = template_def.get("sample_rows") or []
    output = build_xlsx_bytes(
        template_def["headers"],
        sample_rows,
        format_spec=template_def.get("format_spec"),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=g.op_logger,
        module="excel_demo",
        target_type="operator",
        template_or_export_type="人员基本信息模板.xlsx",
        filters={},
        row_count=len(sample_rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="人员基本信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
