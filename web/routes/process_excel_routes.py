from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.normalize import is_blank_value
from core.services.process import PartService
from core.services.scheduler.batch_query_service import BatchQueryService
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
from .process_bp import _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx, bp

# ============================================================
# Excel：零件工艺路线（Parts.route_raw + 解析生成模板）
# ============================================================


def _validate_route_row(part_svc: PartService, row: Dict[str, Any], *, strict_mode: bool) -> Optional[str]:
    if is_blank_value(row.get("图号")):
        return "“图号”不能为空"
    if is_blank_value(row.get("名称")):
        return "“名称”不能为空"
    route_raw = row.get("工艺路线字符串")
    if route_raw is None or str(route_raw).strip() == "":
        return "“工艺路线字符串”不能为空"
    ok, msg = part_svc.validate_route_format(route_raw)
    if not ok:
        return f"工艺路线格式不合法：{msg}"
    if strict_mode:
        part_no = str(row.get("图号") or "").strip() or "<unknown>"
        result = part_svc.parse(route_raw, part_no=part_no, strict_mode=True)
        status_value = getattr(getattr(result, "status", None), "value", getattr(result, "status", None))
        if str(status_value or "").strip().lower() == "failed":
            sample = [str(msg) for msg in (getattr(result, "errors", None) or []) if str(msg).strip()]
            if sample:
                return "；".join(sample[:3])
            return "工艺路线严格解析失败"
    return None


def _route_parse_extra_state(part_svc: PartService, *, strict_mode: bool) -> Dict[str, Any]:
    # 这里必须只镜像 RouteParser 真正读取的解析输入，
    # 不能把供应商状态等展示/管理字段并入基线，
    # 否则确认阶段会被与解析结果无关的变更误伤。
    op_types = sorted(
        part_svc.op_type_repo.list() or [],
        key=lambda item: (str(getattr(item, "op_type_id", "") or ""), str(getattr(item, "name", "") or "")),
    )
    suppliers = sorted(
        part_svc.supplier_repo.list() or [],
        key=lambda item: (str(getattr(item, "supplier_id", "") or ""), str(getattr(item, "op_type_id", "") or "")),
    )
    return {
        "strict_mode": bool(strict_mode),
        "op_types": [
            {
                "op_type_id": ot.op_type_id,
                "name": ot.name,
                "category": ot.category,
            }
            for ot in op_types
        ],
        "suppliers": [
            {
                "supplier_id": supplier.supplier_id,
                "op_type_id": supplier.op_type_id,
                "default_days": supplier.default_days,
            }
            for supplier in suppliers
        ],
    }


def _render_excel_routes_page(
    *,
    existing: Dict[str, Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
    strict_mode: bool,
):
    return render_template(
        "process/excel_import_routes.html",
        title="零件工艺路线 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("process.excel_routes_preview"),
        confirm_url=url_for("process.excel_routes_confirm"),
        template_download_url=url_for("process.excel_routes_template"),
        export_url=url_for("process.excel_routes_export"),
        strict_mode_supported=True,
        strict_mode=bool(strict_mode),
        strict_mode_label="严格模式：拒绝隐式 1.0 天回退",
        strict_mode_help="开启后，缺供应商映射、供应商 default_days 无效/为空、未知工种等不再按兼容逻辑回退，而是直接标记该行为错误。",
    )


@bp.get("/excel/routes")
def excel_routes_page():
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel_routes()
    return _render_excel_routes_page(
        existing=existing,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
        strict_mode=False,
    )


@bp.post("/excel/routes/preview")
def excel_routes_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    _ensure_unique_ids(rows, id_column="图号")

    part_svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = part_svc.build_existing_for_excel_routes()

    def validate_row(row: Dict[str, Any]) -> Optional[str]: return _validate_route_row(part_svc, row, strict_mode=strict_mode)

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="图号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )
    preview_baseline = build_preview_baseline_token(
        existing_data=existing,
        mode=mode,
        id_column="图号",
        extra_state=_route_parse_extra_state(part_svc, strict_mode=strict_mode),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="part_route",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return _render_excel_routes_page(
        existing=existing,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
        strict_mode=strict_mode,
    )


@bp.post("/excel/routes/confirm")
def excel_routes_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    strict_mode = _strict_mode_enabled(request.form.get("strict_mode"))
    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    _ensure_unique_ids(rows, id_column="图号")

    part_svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = part_svc.build_existing_for_excel_routes()
    if preview_baseline_is_stale(
        payload.preview_baseline,
        existing_data=existing,
        mode=mode,
        id_column="图号",
        extra_state=_route_parse_extra_state(part_svc, strict_mode=strict_mode),
    ):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_excel_routes_page(
            existing=existing,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
            strict_mode=strict_mode,
        )

    def validate_row(row: Dict[str, Any]) -> Optional[str]: return _validate_route_row(part_svc, row, strict_mode=strict_mode)

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="图号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_excel_routes_page(
            existing=existing,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
            strict_mode=strict_mode,
        )

    tx = TransactionManager(g.db)
    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []

    with tx.transaction():
        if mode == ImportMode.REPLACE:
            # 若存在批次引用，删除 Parts 会触发外键错误，因此这里做保护
            batch_q = BatchQueryService(g.db, op_logger=getattr(g, "op_logger", None))
            if batch_q.has_any():
                raise ValidationError("已存在批次数据，不能执行“替换（清空后导入）”。请改用“覆盖/追加”。")
            part_svc.delete_all_no_tx()
            existing = {}

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message and len(errors_sample) < 10:
                    errors_sample.append(
                        {
                            "row": getattr(pr, "source_row_num", None) or pr.row_num,
                            "source_row_num": getattr(pr, "source_row_num", None),
                            "source_sheet_name": getattr(pr, "source_sheet_name", None),
                            "message": pr.message,
                        }
                    )
                continue
            if pr.status == RowStatus.SKIP:
                skip_count += 1
                continue
            if pr.status == RowStatus.UNCHANGED and mode != ImportMode.REPLACE:
                skip_count += 1
                continue

            pn = str(pr.data.get("图号")).strip()
            name = str(pr.data.get("名称")).strip()
            route_raw = str(pr.data.get("工艺路线字符串")).strip()

            if mode == ImportMode.APPEND and pn in existing:
                skip_count += 1
                continue

            try:
                existed = pn in existing
                part_svc.upsert_and_parse_no_tx(part_no=pn, part_name=name, route_raw=route_raw, strict_mode=strict_mode)
                if existed:
                    update_count += 1
                else:
                    new_count += 1
            except AppError as e:
                error_count += 1
                if len(errors_sample) < 10:
                    errors_sample.append(
                        {
                            "row": getattr(pr, "source_row_num", None) or pr.row_num,
                            "source_row_num": getattr(pr, "source_row_num", None),
                            "source_sheet_name": getattr(pr, "source_sheet_name", None),
                            "message": e.message,
                        }
                    )
                continue

    time_cost_ms = int((time.time() - start) * 1000)
    result = {
        "total_rows": len(preview_rows),
        "new_count": new_count,
        "update_count": update_count,
        "skip_count": skip_count,
        "error_count": error_count,
        "errors_sample": errors_sample,
    }
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="part_route",
        filename=filename,
        mode=mode,
        preview_or_result=result,
        time_cost_ms=time_cost_ms,
    )
    new_count, update_count, skip_count, error_count = extract_import_stats(result)

    flash_import_result(
        new_count=new_count,
        update_count=update_count,
        skip_count=skip_count,
        error_count=error_count,
        errors_sample=errors_sample,
    )
    return redirect(url_for("process.excel_routes_page"))


@bp.get("/excel/routes/template")
def excel_routes_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "零件工艺路线.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="process",
            target_type="part_route",
            template_or_export_type="零件工艺路线模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_excel_template_file(template_path, download_name="零件工艺路线.xlsx")

    template_def = get_template_definition("零件工艺路线.xlsx")
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
        target_type="part_route",
        template_or_export_type="零件工艺路线模板.xlsx",
        filters={},
        row_count=len(sample_rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="零件工艺路线.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/routes/export")
def excel_routes_export():
    start = time.time()
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    parts = svc.list()
    rows = [{"part_no": p.part_no, "part_name": p.part_name, "route_raw": p.route_raw} for p in parts]
    template_def = get_template_definition("零件工艺路线.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [[r["part_no"], r["part_name"], r["route_raw"]] for r in rows],
        format_spec=template_def.get("format_spec"),
        sanitize_formula=True,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="part_route",
        template_or_export_type="零件工艺路线导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="零件工艺路线.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

