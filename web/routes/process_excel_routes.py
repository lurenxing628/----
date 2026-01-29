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
from core.services.process import PartService

from .process_bp import bp, _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx


# ============================================================
# Excel：零件工艺路线（Parts.route_raw + 解析生成模板）
# ============================================================


@bp.get("/excel/routes")
def excel_routes_page():
    svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel_routes()
    return render_template(
        "process/excel_import_routes.html",
        title="零件工艺路线 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("process.excel_routes_preview"),
        confirm_url=url_for("process.excel_routes_confirm"),
        template_download_url=url_for("process.excel_routes_template"),
        export_url=url_for("process.excel_routes_export"),
    )


@bp.post("/excel/routes/preview")
def excel_routes_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    _ensure_unique_ids(rows, id_column="图号")

    part_svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = part_svc.build_existing_for_excel_routes()

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("图号") or str(row.get("图号")).strip() == "":
            return "“图号”不能为空"
        if not row.get("名称") or str(row.get("名称")).strip() == "":
            return "“名称”不能为空"
        route_raw = row.get("工艺路线字符串")
        if route_raw is None or str(route_raw).strip() == "":
            return "“工艺路线字符串”不能为空"
        ok, msg = part_svc.validate_route_format(route_raw)
        if not ok:
            return f"工艺路线格式不合法：{msg}"
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="图号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
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

    return render_template(
        "process/excel_import_routes.html",
        title="零件工艺路线 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("process.excel_routes_preview"),
        confirm_url=url_for("process.excel_routes_confirm"),
        template_download_url=url_for("process.excel_routes_template"),
        export_url=url_for("process.excel_routes_export"),
    )


@bp.post("/excel/routes/confirm")
def excel_routes_confirm():
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

    _ensure_unique_ids(rows, id_column="图号")

    part_svc = PartService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = part_svc.build_existing_for_excel_routes()

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("图号") or str(row.get("图号")).strip() == "":
            return "“图号”不能为空"
        if not row.get("名称") or str(row.get("名称")).strip() == "":
            return "“名称”不能为空"
        route_raw = row.get("工艺路线字符串")
        if route_raw is None or str(route_raw).strip() == "":
            return "“工艺路线字符串”不能为空"
        ok, msg = part_svc.validate_route_format(route_raw)
        if not ok:
            return f"工艺路线格式不合法：{msg}"
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="图号",
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
            "process/excel_import_routes.html",
            title="零件工艺路线 - Excel 导入/导出",
            existing_list=list(existing.values()),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("process.excel_routes_preview"),
            confirm_url=url_for("process.excel_routes_confirm"),
            template_download_url=url_for("process.excel_routes_template"),
            export_url=url_for("process.excel_routes_export"),
        )

    tx = TransactionManager(g.db)
    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []

    with tx.transaction():
        if mode == ImportMode.REPLACE:
            # 若存在批次引用，删除 Parts 会触发外键错误，因此这里做保护
            row = g.db.execute("SELECT 1 FROM Batches LIMIT 1").fetchone()
            if row is not None:
                raise ValidationError("已存在批次数据，不能执行“替换（清空后导入）”。请改用“覆盖/追加”。")
            g.db.execute("DELETE FROM Parts")

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message and len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": pr.message})
                continue

            pn = str(pr.data.get("图号")).strip()
            name = str(pr.data.get("名称")).strip()
            route_raw = str(pr.data.get("工艺路线字符串")).strip()

            if mode == ImportMode.APPEND and pn in existing:
                skip_count += 1
                continue

            try:
                existed = pn in existing
                part_svc.upsert_and_parse_no_tx(part_no=pn, part_name=name, route_raw=route_raw)
                if existed:
                    update_count += 1
                else:
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
        target_type="part_route",
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
        return send_file(
            template_path,
            as_attachment=True,
            download_name="零件工艺路线.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["图号", "名称", "工艺路线字符串"])
    ws.append(["A1234", "壳体-大", "5数铣10钳20数车35标印40总检45表处理"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

    return send_file(
        output,
        as_attachment=True,
        download_name="零件工艺路线.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/routes/export")
def excel_routes_export():
    start = time.time()
    rows = g.db.execute("SELECT part_no, part_name, route_raw FROM Parts ORDER BY part_no").fetchall()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["图号", "名称", "工艺路线字符串"])
    for r in rows:
        ws.append([r["part_no"], r["part_name"], r["route_raw"]])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

