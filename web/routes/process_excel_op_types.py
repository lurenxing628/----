from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.models.enums import SOURCE_TYPE_VALUES
from core.services.common.enum_normalizers import normalize_op_type_category, source_type_label
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.normalize import normalize_text
from core.services.process import OpTypeService
from core.services.process.op_type_excel_import_service import OpTypeExcelImportService
from web.ui_mode import render_ui_template as render_template

from .excel_utils import (
    build_error_rows_message,
    build_preview_baseline_token,
    collect_error_rows,
    extract_import_stats,
    flash_import_result,
    load_confirm_payload,
    preview_baseline_is_stale,
    project_preview_rows_for_display,
    send_excel_template_file,
)
from .process_bp import _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx, bp

# ============================================================
# Excel：工种配置（OpTypes）
# ============================================================


def _render_excel_op_type_page(
    *,
    existing: Dict[str, Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
):
    return render_template(
        "process/excel_import_op_types.html",
        title="批量维护工种配置",
        existing_list=list(existing.values()),
        preview_rows=project_preview_rows_for_display(preview_rows, {"归属": source_type_label}),
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("process.excel_op_type_preview"),
        confirm_url=url_for("process.excel_op_type_confirm"),
        template_download_url=url_for("process.excel_op_type_template"),
        export_url=url_for("process.excel_op_type_export"),
        back_url=url_for("process.op_types_page"),
        back_label="返回工种配置",
    )


def _normalize_op_type_category(value: Any) -> str:
    return normalize_op_type_category(value)


def _normalize_op_type_name(value: Any) -> str:
    return normalize_text(value) or ""


def _build_op_type_row_validator(
    *,
    rows: List[Dict[str, Any]],
    existing: Dict[str, Dict[str, Any]],
    mode: ImportMode,
):
    name_counts: Dict[str, int] = {}
    for row in rows:
        name = _normalize_op_type_name(row.get("工种名称"))
        if name:
            name_counts[name] = int(name_counts.get(name, 0) or 0) + 1

    existing_name_to_id: Dict[str, str] = {}
    if mode != ImportMode.REPLACE:
        for ot_id, existing_row in (existing or {}).items():
            name = _normalize_op_type_name((existing_row or {}).get("工种名称"))
            normalized_id = str(ot_id or "").strip()
            if name and normalized_id:
                existing_name_to_id[name] = normalized_id

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        ot_id = normalize_text(row.get("工种ID")) or ""
        if not ot_id:
            return "“工种编号（模板列名：工种ID）”不能为空"
        row["工种ID"] = ot_id

        name = _normalize_op_type_name(row.get("工种名称"))
        if not name:
            return "“工种名称”不能为空"
        row["工种名称"] = name

        cat = _normalize_op_type_category(row.get("归属"))
        if cat not in SOURCE_TYPE_VALUES:
            return "“归属”不合法，请填写中文：自制、外协。以前的 Excel 如果写过“内部、外部、内、外”，系统会尽量按自制或外协读取；新文件请直接写“自制”或“外协”。"
        row["归属"] = cat

        if int(name_counts.get(name, 0) or 0) > 1:
            return f"工种名称“{name}”在导入文件中重复，名称必须唯一。"

        existing_owner_id = existing_name_to_id.get(name)
        if existing_owner_id and existing_owner_id != ot_id:
            return f"工种名称“{name}”已被工种编号“{existing_owner_id}”使用，名称不能重复。"

        return None

    return validate_row


@bp.get("/excel/op-types")
def excel_op_type_page():
    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel()
    return _render_excel_op_type_page(
        existing=existing,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
    )


@bp.post("/excel/op-types/preview")
def excel_op_type_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    _ensure_unique_ids(rows, id_column="工种ID")

    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel()

    validate_row = _build_op_type_row_validator(rows=rows, existing=existing, mode=mode)

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="工种ID",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )
    preview_baseline = build_preview_baseline_token(existing_data=existing, mode=mode, id_column="工种ID")

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="op_type",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return _render_excel_op_type_page(
        existing=existing,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
    )


@bp.post("/excel/op-types/confirm")
def excel_op_type_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    _ensure_unique_ids(rows, id_column="工种ID")

    op_type_svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = op_type_svc.build_existing_for_excel()
    if preview_baseline_is_stale(payload.preview_baseline, existing_data=existing, mode=mode, id_column="工种ID"):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_excel_op_type_page(
            existing=existing,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
        )

    validate_row = _build_op_type_row_validator(rows=rows, existing=existing, mode=mode)

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="工种ID",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_excel_op_type_page(
            existing=existing,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
        )

    import_svc = OpTypeExcelImportService(
        g.db,
        logger=getattr(g, "app_logger", None),
        op_logger=getattr(g, "op_logger", None),
    )
    import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_ids=set(existing.keys()))
    new_count, update_count, skip_count, error_count = extract_import_stats(import_stats)
    errors_sample = list(import_stats.get("errors_sample") or [])

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="op_type",
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
        errors_sample=errors_sample,
    )
    return redirect(url_for("process.excel_op_type_page"))


@bp.get("/excel/op-types/template")
def excel_op_type_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "工种配置.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="process",
            target_type="op_type",
            template_or_export_type="工种配置模板.xlsx",
            filters={},
            row_count=2,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_excel_template_file(template_path, download_name="工种配置.xlsx")

    template_def = get_template_definition("工种配置.xlsx")
    sample_rows = template_def.get("sample_rows") or []
    output = build_xlsx_bytes(
        template_def["headers"],
        sample_rows,
        format_spec=template_def.get("format_spec"),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="op_type",
        template_or_export_type="工种配置模板.xlsx",
        filters={},
        row_count=len(sample_rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="工种配置.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/op-types/export")
def excel_op_type_export():
    start = time.time()
    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = svc.list()
    template_def = get_template_definition("工种配置.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [[r.op_type_id, r.name, source_type_label(r.category)] for r in rows],
        format_spec=template_def.get("format_spec"),
        sanitize_formula=True,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="op_type",
        template_or_export_type="工种配置导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="工种配置.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
