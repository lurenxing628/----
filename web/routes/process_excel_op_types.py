from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.process import OpTypeService
from core.services.process.op_type_excel_import_service import OpTypeExcelImportService
from web.ui_mode import render_ui_template as render_template

from .process_bp import _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx, bp

# ============================================================
# Excel：工种配置（OpTypes）
# ============================================================


def _normalize_op_type_category(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("内部", "内", "internal"):
        return "internal"
    if v in ("外部", "外", "external"):
        return "external"
    return v


@bp.get("/excel/op-types")
def excel_op_type_page():
    svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel()
    return render_template(
        "process/excel_import_op_types.html",
        title="工种配置 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("process.excel_op_type_preview"),
        confirm_url=url_for("process.excel_op_type_confirm"),
        template_download_url=url_for("process.excel_op_type_template"),
        export_url=url_for("process.excel_op_type_export"),
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

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("工种ID") or str(row.get("工种ID")).strip() == "":
            return "“工种ID”不能为空"
        if not row.get("工种名称") or str(row.get("工种名称")).strip() == "":
            return "“工种名称”不能为空"
        cat = _normalize_op_type_category(row.get("归属") or "internal")
        if not cat:
            cat = "internal"
        if cat not in ("internal", "external"):
            return "“归属”不合法（允许：internal / external；或中文：内部/外部）"
        row["归属"] = cat
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="工种ID",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

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

    return render_template(
        "process/excel_import_op_types.html",
        title="工种配置 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("process.excel_op_type_preview"),
        confirm_url=url_for("process.excel_op_type_confirm"),
        template_download_url=url_for("process.excel_op_type_template"),
        export_url=url_for("process.excel_op_type_export"),
    )


@bp.post("/excel/op-types/confirm")
def excel_op_type_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    raw_rows_json = request.form.get("raw_rows_json")
    if not raw_rows_json:
        raise ValidationError("缺少预览数据，请重新上传并预览后再确认导入。")

    try:
        rows = json.loads(raw_rows_json)
        if not isinstance(rows, list):
            raise ValueError("rows not list")
    except Exception as e:
        raise ValidationError("预览数据解析失败，请重新上传并预览。") from e

    _ensure_unique_ids(rows, id_column="工种ID")

    op_type_svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = op_type_svc.build_existing_for_excel()

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("工种ID") or str(row.get("工种ID")).strip() == "":
            return "“工种ID”不能为空"
        if not row.get("工种名称") or str(row.get("工种名称")).strip() == "":
            return "“工种名称”不能为空"
        cat = _normalize_op_type_category(row.get("归属") or "internal")
        if not cat:
            cat = "internal"
        if cat not in ("internal", "external"):
            return "“归属”不合法（允许：internal / external；或中文：内部/外部）"
        row["归属"] = cat
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="工种ID",
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
            "process/excel_import_op_types.html",
            title="工种配置 - Excel 导入/导出",
            existing_list=list(existing.values()),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("process.excel_op_type_preview"),
            confirm_url=url_for("process.excel_op_type_confirm"),
            template_download_url=url_for("process.excel_op_type_template"),
            export_url=url_for("process.excel_op_type_export"),
        )

    import_svc = OpTypeExcelImportService(
        g.db,
        logger=getattr(g, "app_logger", None),
        op_logger=getattr(g, "op_logger", None),
    )
    import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_ids=set(existing.keys()))
    new_count = int(import_stats.get("new_count", 0))
    update_count = int(import_stats.get("update_count", 0))
    skip_count = int(import_stats.get("skip_count", 0))
    error_count = int(import_stats.get("error_count", 0))

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

    flash(f"导入完成：新增 {new_count}，更新 {update_count}，跳过 {skip_count}，错误 {error_count}。", "success")
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
        return send_file(
            template_path,
            as_attachment=True,
            download_name="工种配置.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工种ID", "工种名称", "归属"])
    ws.append(["OT001", "数车", "internal"])
    ws.append(["OT002", "标印", "external"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工种ID", "工种名称", "归属"])
    for r in rows:
        ws.append([r.op_type_id, r.name, r.category])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

