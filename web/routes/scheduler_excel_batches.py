from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.excel_validators import get_batch_row_validate_and_normalize
from core.services.process import PartService
from core.services.process.part_operation_query_service import PartOperationQueryService
from core.services.scheduler import BatchService
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
from .excel_utils import (
    strict_mode_enabled as _strict_mode_enabled,
)
from .scheduler_bp import _surface_schedule_warnings, bp
from .scheduler_utils import (
    _ensure_unique_ids,
    _normalize_batch_priority,
    _normalize_due_date,
    _normalize_ready_status,
    _parse_mode,
    _read_uploaded_xlsx,
)

# ============================================================
# Excel：批次信息（Batches）
# ============================================================


def _sorted_existing_list(existing_preview_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    existing_list = list(existing_preview_data.values())
    existing_list.sort(key=lambda x: str(x.get("批次号") or ""))
    return existing_list


def _parse_auto_generate_ops(value: Any) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "on", "yes")


def _build_existing_preview_data(batch_svc: BatchService) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    existing = {b.batch_id: b for b in batch_svc.list()}
    existing_preview_data = {
        k: {
            "批次号": v.batch_id,
            "图号": v.part_no,
            "数量": v.quantity,
            "交期": v.due_date,
            "优先级": v.priority,
            "齐套": v.ready_status,
            "齐套日期": getattr(v, "ready_date", None),
            "备注": v.remark,
        }
        for k, v in existing.items()
    }
    return existing, existing_preview_data


def _build_parts_cache(conn) -> Dict[str, Any]:
    svc = PartService(conn, op_logger=getattr(g, "op_logger", None))
    return {p.part_no: p for p in svc.list()}


def _build_template_ops_snapshot(conn, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    part_nos = sorted({str((row or {}).get("图号") or "").strip() for row in (rows or []) if str((row or {}).get("图号") or "").strip()})
    if not part_nos:
        return []
    query_svc = PartOperationQueryService(conn, op_logger=getattr(g, "op_logger", None))
    return query_svc.list_template_snapshot_for_parts(part_nos)


def _batch_baseline_extra_state(
    *,
    conn,
    parts_cache: Dict[str, Any],
    auto_generate_ops: bool,
    strict_mode: bool,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    parts_snapshot = []
    for part_no in sorted(parts_cache.keys()):
        part = parts_cache.get(part_no)
        parts_snapshot.append(
            {
                "part_no": str(part_no),
                "part_name": getattr(part, "part_name", None),
                "route_raw": getattr(part, "route_raw", None),
            }
        )
    return {
        "auto_generate_ops": bool(auto_generate_ops),
        "strict_mode": bool(strict_mode),
        "parts_snapshot": parts_snapshot,
        "template_ops_snapshot": _build_template_ops_snapshot(conn, rows) if auto_generate_ops else [],
    }


def _render_excel_batches_page(
    *,
    existing_list: List[Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
    auto_generate_ops: bool,
    strict_mode: bool,
):
    return render_template(
        "scheduler/excel_import_batches.html",
        title="批次信息 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        auto_generate_ops=auto_generate_ops,
        preview_url=url_for("scheduler.excel_batches_preview"),
        strict_mode_supported=True,
        strict_mode=bool(strict_mode),
        strict_mode_label="严格模式",
        strict_mode_help="开启后，自动补建工序时不允许兼容性回退。",
        confirm_url=url_for("scheduler.excel_batches_confirm"),
        template_download_url=url_for("scheduler.excel_batches_template"),
        export_url=url_for("scheduler.excel_batches_export"),
    )


@bp.get("/excel/batches")
def excel_batches_page():
    svc = BatchService(g.db, logger=current_app.logger, op_logger=getattr(g, "op_logger", None))
    existing = {
        b.batch_id: {
            "批次号": b.batch_id,
            "图号": b.part_no,
            "数量": b.quantity,
            "交期": b.due_date,
            "优先级": b.priority,
            "齐套": b.ready_status,
            "齐套日期": getattr(b, "ready_date", None),
            "备注": b.remark,
        }
        for b in svc.list()
    }  # type: ignore[misc]
    return _render_excel_batches_page(
        existing_list=list(existing.values()),
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
        auto_generate_ops=True,
        strict_mode=False,
    )


@bp.post("/excel/batches/preview")
def excel_batches_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    auto_generate_ops = _parse_auto_generate_ops(request.form.get("auto_generate_ops"))
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    _ensure_unique_ids(rows, id_column="批次号")

    # 标准化字段，方便差异对比
    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        if "优先级" in item:
            item["优先级"] = _normalize_batch_priority(item.get("优先级"))
        if "齐套" in item:
            item["齐套"] = _normalize_ready_status(item.get("齐套"))
        if "齐套日期" in item:
            item["齐套日期"] = _normalize_due_date(item.get("齐套日期"))
        if "交期" in item:
            item["交期"] = _normalize_due_date(item.get("交期"))
        normalized_rows.append(item)

    svc = BatchService(g.db, logger=current_app.logger, op_logger=getattr(g, "op_logger", None))
    existing = {
        b.batch_id: {
            "批次号": b.batch_id,
            "图号": b.part_no,
            "数量": b.quantity,
            "交期": b.due_date,
            "优先级": b.priority,
            "齐套": b.ready_status,
            "齐套日期": getattr(b, "ready_date", None),
            "备注": b.remark,
        }
        for b in svc.list()
    }

    parts = _build_parts_cache(g.db)

    validate_row = get_batch_row_validate_and_normalize(g.db, parts_cache=parts, inplace=True)

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=normalized_rows,
        id_column="批次号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )
    preview_baseline = build_preview_baseline_token(
        existing_data=existing,
        mode=mode,
        id_column="批次号",
        extra_state=_batch_baseline_extra_state(
            conn=g.db,
            parts_cache=parts,
            auto_generate_ops=auto_generate_ops,
            strict_mode=strict_mode,
            rows=normalized_rows,
        ),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="batch",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return _render_excel_batches_page(
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
        auto_generate_ops=auto_generate_ops,
        strict_mode=strict_mode,
    )


@bp.post("/excel/batches/confirm")
def excel_batches_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    auto_generate_ops = _parse_auto_generate_ops(request.form.get("auto_generate_ops"))
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    _ensure_unique_ids(rows, id_column="批次号")

    svc = BatchService(g.db, logger=current_app.logger, op_logger=getattr(g, "op_logger", None))
    existing, existing_preview_data = _build_existing_preview_data(svc)
    parts = _build_parts_cache(g.db)
    if preview_baseline_is_stale(
        payload.preview_baseline,
        existing_data=existing_preview_data,
        mode=mode,
        id_column="批次号",
        extra_state=_batch_baseline_extra_state(
            conn=g.db,
            parts_cache=parts,
            auto_generate_ops=auto_generate_ops,
            strict_mode=strict_mode,
            rows=rows,
        ),
    ):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_excel_batches_page(
            existing_list=_sorted_existing_list(existing_preview_data),
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
            auto_generate_ops=auto_generate_ops,
            strict_mode=strict_mode,
        )
    validate_row = get_batch_row_validate_and_normalize(g.db, parts_cache=parts, inplace=True)

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="批次号",
        existing_data=existing_preview_data,
        validators=[validate_row],
        mode=mode,
    )

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_excel_batches_page(
            existing_list=_sorted_existing_list(existing_preview_data),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
            auto_generate_ops=auto_generate_ops,
            strict_mode=strict_mode,
        )

    import_stats = svc.import_from_preview_rows(
        preview_rows=preview_rows,
        mode=mode,
        parts_cache=parts,
        auto_generate_ops=auto_generate_ops,
        strict_mode=strict_mode,
        existing_ids=set(existing.keys()),
    )
    new_count, update_count, skip_count, error_count = extract_import_stats(import_stats)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="batch",
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
        suffix="（已自动从模板生成/重建工序）" if auto_generate_ops else "",
    )
    if auto_generate_ops:
        _surface_schedule_warnings(svc.consume_user_visible_warnings(), limit=3)

    return redirect(url_for("scheduler.excel_batches_page"))


@bp.get("/excel/batches/template")
def excel_batches_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "批次信息.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="scheduler",
            target_type="batch",
            template_or_export_type="批次信息模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_excel_template_file(template_path, download_name="批次信息.xlsx")

    template_def = get_template_definition("批次信息.xlsx")
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
        target_type="batch",
        template_or_export_type="批次信息模板.xlsx",
        filters={},
        row_count=len(sample_rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )
    return send_file(
        output,
        as_attachment=True,
        download_name="批次信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/batches/export")
def excel_batches_export():
    start = time.time()
    svc = BatchService(g.db, logger=current_app.logger, op_logger=getattr(g, "op_logger", None))
    rows = svc.list()
    template_def = get_template_definition("批次信息.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [
            [b.batch_id, b.part_no, b.quantity, b.due_date, b.priority, b.ready_status, getattr(b, "ready_date", None), b.remark]
            for b in rows
        ],
        format_spec=template_def.get("format_spec"),
        sanitize_formula=True,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="batch",
        template_or_export_type="批次信息导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="批次信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

