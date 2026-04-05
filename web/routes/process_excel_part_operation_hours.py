from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.models.enums import SourceType
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.normalize import to_str_or_blank
from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService
from core.services.process.part_operation_query_service import PartOperationQueryService
from core.services.scheduler.number_utils import parse_finite_float
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
from .process_bp import _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx, bp

# ============================================================
# Excel：零件工序工时（PartOperations.setup_hours / unit_hours）
# ============================================================


_PART_OP_HOURS_MODE_OPTIONS: List[Dict[str, str]] = [
    {"value": ImportMode.OVERWRITE.value, "label": "覆盖（相同ID更新）"},
    {"value": ImportMode.APPEND.value, "label": "追加（仅补齐空工时）"},
]


def _part_op_hours_mode_options() -> List[Dict[str, str]]:
    return [dict(x) for x in _PART_OP_HOURS_MODE_OPTIONS]


def _parse_seq(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    s = str(value).strip()
    if not s:
        return None
    if "e" in s.lower():
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    try:
        f = float(s)
        if float(f).is_integer():
            return int(f)
    except Exception:
        return None
    return None


def _build_existing_internal() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    q = PartOperationQueryService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = q.list_active_hours()

    existing_internal: Dict[str, Dict[str, Any]] = {}
    meta_all: Dict[str, Dict[str, Any]] = {}
    existing_list: List[Dict[str, Any]] = []

    for r in rows:
        part_no = to_str_or_blank(r["part_no"])
        seq = int(r["seq"] or 0)
        row_id = f"{part_no}|{seq}"
        source = to_str_or_blank(r["source"]).lower() or SourceType.INTERNAL.value
        item = {
            "图号": part_no,
            "工序": seq,
            "工种": r["op_type_name"],
            "归属": source,
            "换型时间(h)": float(r["setup_hours"] or 0.0),
            "单件工时(h)": float(r["unit_hours"] or 0.0),
        }
        meta_all[row_id] = item
        existing_list.append(item)
        if source == SourceType.INTERNAL.value:
            existing_internal[row_id] = {
                "__row_id__": row_id,
                "图号": part_no,
                "工序": seq,
                "换型时间(h)": float(r["setup_hours"] or 0.0),
                "单件工时(h)": float(r["unit_hours"] or 0.0),
            }

    return existing_internal, meta_all, existing_list


def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r or {})
        part_no = to_str_or_blank(item.get("图号"))
        seq = _parse_seq(item.get("工序"))
        item["图号"] = part_no or None
        item["工序"] = seq if seq is not None else item.get("工序")
        item["换型时间(h)"] = item.get("换型时间(h)")
        item["单件工时(h)"] = item.get("单件工时(h)")
        item["__row_id__"] = f"{part_no}|{seq}" if part_no and seq is not None else None
        normalized.append(item)
    return normalized


def _build_validator(meta_all: Dict[str, Dict[str, Any]]):
    def _validate_row(row: Dict[str, Any]) -> Optional[str]:
        part_no = to_str_or_blank(row.get("图号"))
        if not part_no:
            return "“图号”不能为空"

        seq = _parse_seq(row.get("工序"))
        if seq is None or seq <= 0:
            return "“工序”必须是正整数"
        row["工序"] = int(seq)
        row["__row_id__"] = f"{part_no}|{seq}"

        try:
            sh = parse_finite_float(row.get("换型时间(h)"), field="换型时间(h)", allow_none=True)
            uh = parse_finite_float(row.get("单件工时(h)"), field="单件工时(h)", allow_none=True)
        except ValidationError as e:
            return e.message
        sh = 0.0 if sh is None else float(sh)
        uh = 0.0 if uh is None else float(uh)
        if sh < 0 or uh < 0:
            return "“换型时间(h)”和“单件工时(h)”不能为负数"
        row["换型时间(h)"] = sh
        row["单件工时(h)"] = uh

        rid = row["__row_id__"]
        meta = meta_all.get(rid)
        if not meta:
            return f"工序不存在：图号={part_no} 工序={seq}"
        if to_str_or_blank(meta.get("归属")).lower() != SourceType.INTERNAL.value:
            return f"仅支持内部工序导入工时：图号={part_no} 工序={seq}"
        return None

    return _validate_row


def _build_part_op_hours_extra_state(meta_all: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "meta_rows": [
            {
                "row_id": str(row_id),
                "source": to_str_or_blank((meta or {}).get("归属")).lower(),
            }
            for row_id, meta in sorted((meta_all or {}).items(), key=lambda item: str(item[0]))
        ]
    }


def _build_existing_for_append(existing_internal: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    append 仅用于“补齐空工时”：
    - 已维护（任一工时非 0）=> 视为 existing（preview 会 SKIP）
    - 空工时（setup=0 且 unit=0）=> 允许更新
    """
    filtered: Dict[str, Dict[str, Any]] = {}
    for rid, row in (existing_internal or {}).items():
        sh = float(row.get("换型时间(h)") or 0.0)
        uh = float(row.get("单件工时(h)") or 0.0)
        if abs(sh) > 1e-12 or abs(uh) > 1e-12:
            filtered[rid] = row
    return filtered


def _rewrite_append_preview_rows(preview_rows: List[Any], mode: ImportMode) -> None:
    """
    append 下可补录空工时的行在通用 preview 中会标为 NEW，
    这里改成 UPDATE，避免误导为“新增工序”。
    """
    if mode != ImportMode.APPEND:
        return
    for pr in preview_rows:
        if pr.status == RowStatus.NEW:
            pr.status = RowStatus.UPDATE
            pr.message = "工时为空，按“追加”模式将补齐"


def _render_excel_part_op_hours_page(
    *,
    existing_list: List[Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
):
    return render_template(
        "process/excel_import_part_operation_hours.html",
        title="零件工序工时 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("process.excel_part_op_hours_preview"),
        confirm_url=url_for("process.excel_part_op_hours_confirm"),
        template_download_url=url_for("process.excel_part_op_hours_template"),
        export_url=url_for("process.excel_part_op_hours_export"),
        mode_options=_part_op_hours_mode_options(),
    )


@bp.get("/excel/part-operation-hours")
def excel_part_op_hours_page():
    _existing_internal, _meta_all, existing_list = _build_existing_internal()
    return _render_excel_part_op_hours_page(
        existing_list=existing_list,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
    )


@bp.post("/excel/part-operation-hours/preview")
def excel_part_op_hours_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    if mode == ImportMode.REPLACE:
        raise ValidationError("该页面不支持“替换（清空后导入）”，请使用“覆盖”或“追加”。", field="mode")

    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    raw_rows = _read_uploaded_xlsx(file)
    rows = _normalize_rows(raw_rows)
    _ensure_unique_ids(rows, id_column="__row_id__")

    existing_internal, meta_all, existing_list = _build_existing_internal()
    validator = _build_validator(meta_all=meta_all)

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    existing_for_preview = existing_internal if mode != ImportMode.APPEND else _build_existing_for_append(existing_internal)
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="__row_id__",
        existing_data=existing_for_preview,
        validators=[validator],
        mode=mode,
    )
    _rewrite_append_preview_rows(preview_rows, mode)
    preview_baseline = build_preview_baseline_token(
        existing_data=existing_for_preview,
        mode=mode,
        id_column="__row_id__",
        extra_state=_build_part_op_hours_extra_state(meta_all),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="part_operation_hours",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return _render_excel_part_op_hours_page(
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
    )


@bp.post("/excel/part-operation-hours/confirm")
def excel_part_op_hours_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    if mode == ImportMode.REPLACE:
        raise ValidationError("该页面不支持“替换（清空后导入）”，请使用“覆盖”或“追加”。", field="mode")

    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    _ensure_unique_ids(rows, id_column="__row_id__")

    existing_internal, meta_all, existing_list = _build_existing_internal()
    validator = _build_validator(meta_all=meta_all)
    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    existing_for_preview = existing_internal if mode != ImportMode.APPEND else _build_existing_for_append(existing_internal)
    if preview_baseline_is_stale(
        payload.preview_baseline,
        existing_data=existing_for_preview,
        mode=mode,
        id_column="__row_id__",
        extra_state=_build_part_op_hours_extra_state(meta_all),
    ):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_excel_part_op_hours_page(
            existing_list=existing_list,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
        )
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="__row_id__",
        existing_data=existing_for_preview,
        validators=[validator],
        mode=mode,
    )
    _rewrite_append_preview_rows(preview_rows, mode)

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_excel_part_op_hours_page(
            existing_list=existing_list,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
        )

    import_svc = PartOperationHoursExcelImportService(
        g.db,
        logger=getattr(g, "app_logger", None),
        op_logger=getattr(g, "op_logger", None),
    )
    stats = import_svc.apply_preview_rows(preview_rows)
    new_count, update_count, skip_count, error_count = extract_import_stats(stats)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="part_operation_hours",
        filename=filename,
        mode=mode,
        preview_or_result=stats,
        time_cost_ms=time_cost_ms,
    )

    flash_import_result(
        new_count=new_count,
        update_count=update_count,
        skip_count=skip_count,
        error_count=error_count,
        errors_sample=list(stats.get("errors_sample") or []),
    )
    return redirect(url_for("process.excel_part_op_hours_page"))


@bp.get("/excel/part-operation-hours/template")
def excel_part_op_hours_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "零件工序工时.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="process",
            target_type="part_operation_hours",
            template_or_export_type="零件工序工时模板.xlsx",
            filters={},
            row_count=2,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_excel_template_file(template_path, download_name="零件工序工时.xlsx")

    template_def = get_template_definition("零件工序工时.xlsx")
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
        target_type="part_operation_hours",
        template_or_export_type="零件工序工时模板.xlsx",
        filters={},
        row_count=len(sample_rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="零件工序工时.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/part-operation-hours/export")
def excel_part_op_hours_export():
    start = time.time()
    q = PartOperationQueryService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = q.list_internal_active_hours()
    template_def = get_template_definition("零件工序工时.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [[r["part_no"], int(r["seq"] or 0), float(r["setup_hours"] or 0.0), float(r["unit_hours"] or 0.0)] for r in rows],
        format_spec=template_def.get("format_spec"),
        sanitize_formula=True,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="part_operation_hours",
        template_or_export_type="零件工序工时导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="零件工序工时.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

