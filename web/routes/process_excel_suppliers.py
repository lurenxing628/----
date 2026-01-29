from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import AppError, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.process import SupplierService
from data.repositories import OpTypeRepository, SupplierRepository

from .process_bp import bp, _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx


# ============================================================
# Excel：供应商配置（Suppliers）
# ============================================================


def _normalize_supplier_status(value: Any) -> str:
    v = "" if value is None else str(value).strip()
    if v in ("启用", "在用", "正常", "active"):
        return "active"
    if v in ("停用", "禁用", "inactive"):
        return "inactive"
    return v or "active"


def _resolve_op_type_name(value: Any, op_type_repo: OpTypeRepository) -> Optional[str]:
    v = None if value is None else str(value).strip()
    if not v:
        return None
    ot = op_type_repo.get(v)
    if not ot:
        ot = op_type_repo.get_by_name(v)
    if not ot:
        raise ValidationError(f"工种“{v}”不存在，请先维护工种配置。", field="对应工种")
    return ot.name


def _resolve_op_type_id(value: Any, op_type_repo: OpTypeRepository) -> Optional[str]:
    v = None if value is None else str(value).strip()
    if not v:
        return None
    ot = op_type_repo.get(v)
    if not ot:
        ot = op_type_repo.get_by_name(v)
    if not ot:
        raise ValidationError(f"工种“{v}”不存在，请先维护工种配置。", field="对应工种")
    return ot.op_type_id


@bp.get("/excel/suppliers")
def excel_supplier_page():
    svc = SupplierService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel()
    return render_template(
        "process/excel_import_suppliers.html",
        title="供应商配置 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("process.excel_supplier_preview"),
        confirm_url=url_for("process.excel_supplier_confirm"),
        template_download_url=url_for("process.excel_supplier_template"),
        export_url=url_for("process.excel_supplier_export"),
    )


@bp.post("/excel/suppliers/preview")
def excel_supplier_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    _ensure_unique_ids(rows, id_column="供应商ID")

    svc = SupplierService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel()
    op_type_repo = OpTypeRepository(g.db)

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("供应商ID") or str(row.get("供应商ID")).strip() == "":
            return "“供应商ID”不能为空"
        if not row.get("名称") or str(row.get("名称")).strip() == "":
            return "“名称”不能为空"

        # 默认周期
        if row.get("默认周期") is None or str(row.get("默认周期")).strip() == "":
            row["默认周期"] = 1.0
        try:
            d = float(row.get("默认周期"))
            if d <= 0:
                return "“默认周期”必须大于 0"
            row["默认周期"] = d
        except Exception:
            return "“默认周期”必须是数字"

        # 状态可选
        if "状态" in row:
            row["状态"] = _normalize_supplier_status(row.get("状态"))
            if row["状态"] not in ("active", "inactive"):
                return "“状态”不合法（允许：active / inactive；或中文：启用/停用）"
        else:
            row["状态"] = "active"

        # 工种可选（允许 id 或 名称），预览阶段标准化为“名称”
        try:
            name = _resolve_op_type_name(row.get("对应工种"), op_type_repo=op_type_repo)
            row["对应工种"] = name
        except ValidationError as e:
            return e.message

        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="供应商ID",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="supplier",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return render_template(
        "process/excel_import_suppliers.html",
        title="供应商配置 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("process.excel_supplier_preview"),
        confirm_url=url_for("process.excel_supplier_confirm"),
        template_download_url=url_for("process.excel_supplier_template"),
        export_url=url_for("process.excel_supplier_export"),
    )


@bp.post("/excel/suppliers/confirm")
def excel_supplier_confirm():
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
    except Exception:
        raise ValidationError("预览数据解析失败，请重新上传并预览。")

    _ensure_unique_ids(rows, id_column="供应商ID")

    supplier_svc = SupplierService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = supplier_svc.build_existing_for_excel()
    op_type_repo = OpTypeRepository(g.db)

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("供应商ID") or str(row.get("供应商ID")).strip() == "":
            return "“供应商ID”不能为空"
        if not row.get("名称") or str(row.get("名称")).strip() == "":
            return "“名称”不能为空"
        if row.get("默认周期") is None or str(row.get("默认周期")).strip() == "":
            row["默认周期"] = 1.0
        try:
            d = float(row.get("默认周期"))
            if d <= 0:
                return "“默认周期”必须大于 0"
            row["默认周期"] = d
        except Exception:
            return "“默认周期”必须是数字"
        row["状态"] = _normalize_supplier_status(row.get("状态"))
        if row["状态"] not in ("active", "inactive"):
            return "“状态”不合法（允许：active / inactive；或中文：启用/停用）"
        try:
            name = _resolve_op_type_name(row.get("对应工种"), op_type_repo=op_type_repo)
            row["对应工种"] = name
        except ValidationError as e:
            return e.message
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="供应商ID",
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
            "process/excel_import_suppliers.html",
            title="供应商配置 - Excel 导入/导出",
            existing_list=list(existing.values()),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("process.excel_supplier_preview"),
            confirm_url=url_for("process.excel_supplier_confirm"),
            template_download_url=url_for("process.excel_supplier_template"),
            export_url=url_for("process.excel_supplier_export"),
        )

    tx = TransactionManager(g.db)
    s_repo = SupplierRepository(g.db)

    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []

    with tx.transaction():
        if mode == ImportMode.REPLACE:
            supplier_svc.ensure_replace_allowed()
            g.db.execute("DELETE FROM Suppliers")

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message and len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": pr.message})
                continue

            sid = str(pr.data.get("供应商ID")).strip()
            name = str(pr.data.get("名称")).strip()
            op_type_id = None
            try:
                op_type_id = _resolve_op_type_id(pr.data.get("对应工种"), op_type_repo=op_type_repo)
            except ValidationError:
                op_type_id = None
            default_days = float(pr.data.get("默认周期") or 1.0)
            status = _normalize_supplier_status(pr.data.get("状态"))
            remark = pr.data.get("备注")

            if mode == ImportMode.APPEND and sid in existing:
                skip_count += 1
                continue

            try:
                if s_repo.get(sid):
                    s_repo.update(
                        sid,
                        {
                            "name": name,
                            "op_type_id": op_type_id,
                            "default_days": default_days,
                            "status": status,
                            "remark": remark,
                        },
                    )
                    update_count += 1
                else:
                    s_repo.create(
                        {
                            "supplier_id": sid,
                            "name": name,
                            "op_type_id": op_type_id,
                            "default_days": default_days,
                            "status": status,
                            "remark": remark,
                        }
                    )
                    new_count += 1
            except AppError as e:
                error_count += 1
                if len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": e.message})
                continue

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="supplier",
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
    return redirect(url_for("process.excel_supplier_page"))


@bp.get("/excel/suppliers/template")
def excel_supplier_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "供应商配置.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="process",
            target_type="supplier",
            template_or_export_type="供应商配置模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_file(
            template_path,
            as_attachment=True,
            download_name="供应商配置.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["供应商ID", "名称", "对应工种", "默认周期"])
    ws.append(["S001", "外协-标印厂", "标印", 1])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="supplier",
        template_or_export_type="供应商配置模板.xlsx",
        filters={},
        row_count=1,
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="供应商配置.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/suppliers/export")
def excel_supplier_export():
    start = time.time()
    rows = g.db.execute(
        """
        SELECT s.supplier_id, s.name, s.default_days, s.status, s.remark, ot.name AS op_type_name
        FROM Suppliers s
        LEFT JOIN OpTypes ot ON ot.op_type_id = s.op_type_id
        ORDER BY s.supplier_id
        """
    ).fetchall()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["供应商ID", "名称", "对应工种", "默认周期", "状态", "备注"])
    for r in rows:
        ws.append([r["supplier_id"], r["name"], r["op_type_name"], r["default_days"], r["status"], r["remark"]])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="supplier",
        template_or_export_type="供应商配置导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="供应商配置.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

