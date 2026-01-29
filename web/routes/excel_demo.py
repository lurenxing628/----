import io
import json
import os
import time
from typing import Dict, Any, List

from flask import Blueprint, current_app, request, flash, redirect, url_for, send_file, g

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.openpyxl_backend import OpenpyxlBackend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.common.excel_audit import log_excel_import, log_excel_export

from .excel_utils import parse_import_mode

bp = Blueprint("excel_demo", __name__)


def _fetch_existing_operators(conn) -> Dict[str, Dict[str, Any]]:
    """以 Excel 列名（中文）构建 existing_data，便于 preview_import 做 diff。"""
    rows = conn.execute("SELECT operator_id, name, status, remark FROM Operators").fetchall()
    existing: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        operator_id = r["operator_id"]
        existing[operator_id] = {
            "工号": operator_id,
            "姓名": r["name"],
            "状态": r["status"],
            "备注": r["remark"],
        }
    return existing


def _parse_mode(value: str) -> ImportMode:
    return parse_import_mode(value)


def _validate_operator_row(row: Dict[str, Any]) -> str:
    # 返回中文错误提示；返回 None 表示通过
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


@bp.get("/")
def index():
    existing = _fetch_existing_operators(g.db)
    return render_template(
        "excel/demo.html",
        title="Excel 导入演示",
        existing_list=list(existing.values()),
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("excel_demo.preview"),
        confirm_url=url_for("excel_demo.confirm"),
        template_download_url=url_for("excel_demo.download_template"),
    )


@bp.post("/preview")
def preview():
    start = time.time()

    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    # 为了演示简单：直接读取上传流到内存（openpyxl 需要文件样式，因此保存到 BytesIO）
    data = file.read()
    if not data:
        raise AppError(ErrorCode.EXCEL_FORMAT_ERROR, "上传文件为空，请重新选择。")

    tmp = io.BytesIO(data)
    tmp.seek(0)

    backend = OpenpyxlBackend()
    # openpyxl.load_workbook 需要类文件对象时要用 filename=...；这里用临时文件流不稳定
    # 因此：写入一个临时内存文件并交给 openpyxl（openpyxl 支持 BytesIO）
    try:
        wb = None  # 仅用于异常时提示
        import openpyxl

        wb = openpyxl.load_workbook(tmp, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise AppError(ErrorCode.EXCEL_FORMAT_ERROR, "Excel 内容为空，未读取到任何行。")

        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        parsed_rows: List[Dict[str, Any]] = []
        for raw in rows[1:]:
            if raw is None or all(v is None or str(v).strip() == "" for v in raw):
                continue
            item: Dict[str, Any] = {}
            for idx, key in enumerate(headers):
                if not key:
                    continue
                val = raw[idx] if idx < len(raw) else None
                if isinstance(val, str):
                    val = val.strip()
                    if val == "":
                        val = None
                item[key] = val
            parsed_rows.append(item)
    except AppError:
        raise
    except Exception as e:
        raise AppError(ErrorCode.EXCEL_READ_ERROR, "读取 Excel 失败，请确认文件未损坏且未被占用。", cause=e)

    existing = _fetch_existing_operators(g.db)
    svc = ExcelService(backend=backend, logger=None, op_logger=g.op_logger)
    preview_rows = svc.preview_import(
        rows=parsed_rows,
        id_column="工号",
        existing_data=existing,
        validators=[_validate_operator_row],
        mode=mode,
    )

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

    return render_template(
        "excel/demo.html",
        title="Excel 导入演示",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(parsed_rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("excel_demo.preview"),
        confirm_url=url_for("excel_demo.confirm"),
        template_download_url=url_for("excel_demo.download_template"),
    )


@bp.post("/confirm")
def confirm():
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

    existing = _fetch_existing_operators(g.db)
    backend = OpenpyxlBackend()
    svc = ExcelService(backend=backend, logger=None, op_logger=g.op_logger)
    preview_rows = svc.preview_import(
        rows=rows,
        id_column="工号",
        existing_data=existing,
        validators=[_validate_operator_row],
        mode=mode,
    )

    # 严格模式：只要存在错误行，就拒绝导入（演示页也保持一致）
    error_rows = [pr for pr in preview_rows if pr.status == RowStatus.ERROR]
    if error_rows:
        sample = "；".join([f"第{pr.row_num}行：{pr.message}" for pr in error_rows[:5] if pr and pr.message])
        flash(
            f"导入被拒绝：Excel 存在 {len(error_rows)} 行错误。请修正后重新预览并确认。{('错误示例：' + sample) if sample else ''}",
            "error",
        )
        return render_template(
            "excel/demo.html",
            title="Excel 导入演示",
            existing_list=list(existing.values()),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("excel_demo.preview"),
            confirm_url=url_for("excel_demo.confirm"),
            template_download_url=url_for("excel_demo.download_template"),
        )

    # 过滤掉 ERROR 行，其他按模式落库
    tx_manager = TransactionManager(g.db)
    new_count = update_count = skip_count = error_count = 0
    errors_sample = []

    with tx_manager.transaction():
        if mode == ImportMode.REPLACE:
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

            # 是否存在
            cur = g.db.execute("SELECT 1 FROM Operators WHERE operator_id = ?", (op_id,))
            exists = cur.fetchone() is not None

            if exists:
                g.db.execute(
                    "UPDATE Operators SET name=?, status=?, remark=?, updated_at=CURRENT_TIMESTAMP WHERE operator_id=?",
                    (name, status, remark, op_id),
                )
                update_count += 1
            else:
                g.db.execute(
                    "INSERT INTO Operators (operator_id, name, status, remark) VALUES (?, ?, ?, ?)",
                    (op_id, name, status, remark),
                )
                new_count += 1

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=g.op_logger,
        module="excel_demo",
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
    return redirect(url_for("excel_demo.index"))


@bp.get("/template")
def download_template():
    """
    下载“人员基本信息.xlsx”模板（演示用）：列名与文档一致（工号/姓名/状态/备注）。
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
        op_logger=g.op_logger,
        module="excel_demo",
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

