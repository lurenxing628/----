from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.personnel import OperatorService
from data.repositories import OperatorRepository

from .personnel_bp import bp, _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx


def _validate_operator_excel_row(row: Dict[str, Any]) -> Optional[str]:
    if not row.get("工号") or str(row.get("工号")).strip() == "":
        return "“工号”不能为空"
    if not row.get("姓名") or str(row.get("姓名")).strip() == "":
        return "“姓名”不能为空"

    status = row.get("状态")
    if status is None or str(status).strip() == "":
        return "“状态”不能为空（允许：active / inactive）"
    status = str(status).strip()
    if status not in ("active", "inactive"):
        return "“状态”不合法（允许：active / inactive）"
    return None


# ============================================================
# Excel：人员基本信息（Operators）
# ============================================================


@bp.get("/excel/operators")
def excel_operator_page():
    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = op_svc.build_existing_for_excel()

    return render_template(
        "personnel/excel_import_operator.html",
        title="人员基本信息 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("personnel.excel_operator_preview"),
        confirm_url=url_for("personnel.excel_operator_confirm"),
        template_download_url=url_for("personnel.excel_operator_template"),
        export_url=url_for("personnel.excel_operator_export"),
    )


@bp.post("/excel/operators/preview")
def excel_operator_preview():
    start = time.time()

    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    _ensure_unique_ids(rows, id_column="工号")

    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = op_svc.build_existing_for_excel()

    svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = svc.preview_import(
        rows=rows,
        id_column="工号",
        existing_data=existing,
        validators=[_validate_operator_excel_row],
        mode=mode,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return render_template(
        "personnel/excel_import_operator.html",
        title="人员基本信息 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("personnel.excel_operator_preview"),
        confirm_url=url_for("personnel.excel_operator_confirm"),
        template_download_url=url_for("personnel.excel_operator_template"),
        export_url=url_for("personnel.excel_operator_export"),
    )


@bp.post("/excel/operators/confirm")
def excel_operator_confirm():
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

    _ensure_unique_ids(rows, id_column="工号")

    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = op_svc.build_existing_for_excel()

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="工号",
        existing_data=existing,
        validators=[_validate_operator_excel_row],
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
            "personnel/excel_import_operator.html",
            title="人员基本信息 - Excel 导入/导出",
            existing_list=list(existing.values()),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("personnel.excel_operator_preview"),
            confirm_url=url_for("personnel.excel_operator_confirm"),
            template_download_url=url_for("personnel.excel_operator_template"),
            export_url=url_for("personnel.excel_operator_export"),
        )

    # 落库：忽略 ERROR 行
    tx = TransactionManager(g.db)
    op_repo = OperatorRepository(g.db)

    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []

    with tx.transaction():
        if mode == ImportMode.REPLACE:
            op_svc.ensure_replace_allowed()
            g.db.execute("DELETE FROM Operators")

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message and len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": pr.message})
                continue

            op_id = str(pr.data.get("工号")).strip()
            name = pr.data.get("姓名")
            status = str(pr.data.get("状态")).strip()
            remark = pr.data.get("备注")

            if mode == ImportMode.APPEND and op_id in existing:
                skip_count += 1
                continue

            exists = op_repo.exists(op_id)
            if exists:
                op_repo.update(op_id, {"name": name, "status": status, "remark": remark})
                update_count += 1
            else:
                op_repo.create({"operator_id": op_id, "name": name, "status": status, "remark": remark})
                new_count += 1

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator",
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

    flash(
        f"导入完成：新增 {new_count}，更新 {update_count}，跳过 {skip_count}，错误 {error_count}。",
        "success",
    )
    return redirect(url_for("personnel.excel_operator_page"))


@bp.get("/excel/operators/template")
def excel_operator_template():
    start = time.time()

    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "人员基本信息.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="personnel",
            target_type="operator",
            template_or_export_type="人员基本信息模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_file(
            template_path,
            as_attachment=True,
            download_name="人员基本信息.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工号", "姓名", "状态", "备注"])
    ws.append(["OP001", "张三", "active", "示例备注"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator",
        template_or_export_type="人员基本信息模板.xlsx",
        filters={},
        row_count=1,
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="人员基本信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/operators/export")
def excel_operator_export():
    start = time.time()

    # 导出全部人员
    rows = g.db.execute("SELECT operator_id, name, status, remark FROM Operators ORDER BY operator_id").fetchall()
    export_rows = [{"工号": r["operator_id"], "姓名": r["name"], "状态": r["status"], "备注": r["remark"]} for r in rows]

    # 导出到浏览器：这里直接用 openpyxl 写入内存（无需落地文件）
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工号", "姓名", "状态", "备注"])
    for r in export_rows:
        ws.append([r.get("工号"), r.get("姓名"), r.get("状态"), r.get("备注")])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator",
        template_or_export_type="人员基本信息导出.xlsx",
        filters={},
        row_count=len(export_rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="人员基本信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

