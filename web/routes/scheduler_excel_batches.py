from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, render_template, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.common.openpyxl_backend import OpenpyxlBackend
from core.services.scheduler import BatchService
from data.repositories import PartRepository

from .scheduler_bp import bp
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


@bp.get("/excel/batches")
def excel_batches_page():
    svc = BatchService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = {
        b.batch_id: {"批次号": b.batch_id, "图号": b.part_no, "数量": b.quantity, "交期": b.due_date, "优先级": b.priority, "齐套": b.ready_status, "备注": b.remark}
        for b in svc.list()
    }  # type: ignore[misc]
    return render_template(
        "scheduler/excel_import_batches.html",
        title="批次信息 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("scheduler.excel_batches_preview"),
        confirm_url=url_for("scheduler.excel_batches_confirm"),
        template_download_url=url_for("scheduler.excel_batches_template"),
        export_url=url_for("scheduler.excel_batches_export"),
    )


@bp.post("/excel/batches/preview")
def excel_batches_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
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
        if "交期" in item:
            item["交期"] = _normalize_due_date(item.get("交期"))
        normalized_rows.append(item)

    svc = BatchService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = {
        b.batch_id: {"批次号": b.batch_id, "图号": b.part_no, "数量": b.quantity, "交期": b.due_date, "优先级": b.priority, "齐套": b.ready_status, "备注": b.remark}
        for b in svc.list()
    }

    part_repo = PartRepository(g.db)
    parts = {p.part_no: p for p in part_repo.list()}

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        if not row.get("批次号") or str(row.get("批次号")).strip() == "":
            return "“批次号”不能为空"
        if not row.get("图号") or str(row.get("图号")).strip() == "":
            return "“图号”不能为空"
        pn = str(row.get("图号")).strip()
        if pn not in parts:
            return f"图号“{pn}”不存在，请先在工艺管理中维护零件。"

        qty = row.get("数量")
        if qty is None or str(qty).strip() == "":
            return "“数量”不能为空"
        try:
            q = int(qty)
            if q <= 0:
                return "“数量”必须大于 0"
            row["数量"] = q
        except Exception:
            return "“数量”必须是整数"

        row["优先级"] = _normalize_batch_priority(row.get("优先级"))
        if row["优先级"] not in ("normal", "urgent", "critical"):
            return "“优先级”不合法（允许：normal/urgent/critical；或中文：普通/急件/特急）"

        row["齐套"] = _normalize_ready_status(row.get("齐套"))
        if row["齐套"] not in ("yes", "no", "partial"):
            return "“齐套”不合法（允许：yes/no/partial；或中文：齐套/未齐套/部分齐套）"

        row["交期"] = _normalize_due_date(row.get("交期"))
        return None

    excel_svc = ExcelService(backend=OpenpyxlBackend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=normalized_rows,
        id_column="批次号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
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

    return render_template(
        "scheduler/excel_import_batches.html",
        title="批次信息 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("scheduler.excel_batches_preview"),
        confirm_url=url_for("scheduler.excel_batches_confirm"),
        template_download_url=url_for("scheduler.excel_batches_template"),
        export_url=url_for("scheduler.excel_batches_export"),
    )


@bp.post("/excel/batches/confirm")
def excel_batches_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    raw_rows_json = request.form.get("raw_rows_json")
    auto_generate_ops = (request.form.get("auto_generate_ops") or "").strip().lower() in ("1", "true", "on", "yes")
    if not raw_rows_json:
        raise ValidationError("缺少预览数据，请重新上传并预览后再确认导入。")

    try:
        rows = json.loads(raw_rows_json)
        if not isinstance(rows, list):
            raise ValueError("rows not list")
    except Exception:
        raise ValidationError("预览数据解析失败，请重新上传并预览。")

    _ensure_unique_ids(rows, id_column="批次号")

    svc = BatchService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = {b.batch_id: b for b in svc.list()}
    parts = {p.part_no: p for p in PartRepository(g.db).list()}

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        # 与 preview 保持一致（防止被篡改）
        if not row.get("批次号") or str(row.get("批次号")).strip() == "":
            return "“批次号”不能为空"
        if not row.get("图号") or str(row.get("图号")).strip() == "":
            return "“图号”不能为空"
        pn = str(row.get("图号")).strip()
        if pn not in parts:
            return f"图号“{pn}”不存在，请先在工艺管理中维护零件。"
        qty = row.get("数量")
        if qty is None or str(qty).strip() == "":
            return "“数量”不能为空"
        try:
            q = int(qty)
            if q <= 0:
                return "“数量”必须大于 0"
            row["数量"] = q
        except Exception:
            return "“数量”必须是整数"
        row["优先级"] = _normalize_batch_priority(row.get("优先级"))
        if row["优先级"] not in ("normal", "urgent", "critical"):
            return "“优先级”不合法（允许：normal/urgent/critical；或中文：普通/急件/特急）"
        row["齐套"] = _normalize_ready_status(row.get("齐套"))
        if row["齐套"] not in ("yes", "no", "partial"):
            return "“齐套”不合法（允许：yes/no/partial；或中文：齐套/未齐套/部分齐套）"
        row["交期"] = _normalize_due_date(row.get("交期"))
        return None

    excel_svc = ExcelService(backend=OpenpyxlBackend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="批次号",
        existing_data={
            k: {"批次号": v.batch_id, "图号": v.part_no, "数量": v.quantity, "交期": v.due_date, "优先级": v.priority, "齐套": v.ready_status, "备注": v.remark}
            for k, v in existing.items()
        },
        validators=[validate_row],
        mode=mode,
    )

    tx = TransactionManager(g.db)
    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []

    with tx.transaction():
        if mode == ImportMode.REPLACE:
            # 直接清空批次（级联会清空批次工序/排程等）
            g.db.execute("DELETE FROM Batches")
            existing = {}  # 重要：REPLACE 后按“全新导入”处理，避免走 update 分支

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message and len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": pr.message})
                continue

            bid = str(pr.data.get("批次号")).strip()
            pn = str(pr.data.get("图号")).strip()
            qty = int(pr.data.get("数量"))
            dd = pr.data.get("交期")
            prio = str(pr.data.get("优先级") or "normal").strip()
            ready = str(pr.data.get("齐套") or "no").strip()
            remark = pr.data.get("备注")

            if mode == ImportMode.APPEND and bid in existing:
                skip_count += 1
                continue

            part_name = parts.get(pn).part_name if parts.get(pn) else None

            if bid in existing:
                # 注意：此处必须使用 no_tx，保证整批导入可整体回滚
                svc.update_no_tx(
                    bid,
                    {
                        "part_no": pn,
                        "part_name": part_name,
                        "quantity": qty,
                        "due_date": dd,
                        "priority": prio,
                        "ready_status": ready,
                        "remark": remark,
                    },
                )
                update_count += 1
            else:
                svc.create_no_tx(
                    {
                        "batch_id": bid,
                        "part_no": pn,
                        "part_name": part_name,
                        "quantity": qty,
                        "due_date": dd,
                        "priority": prio,
                        "ready_status": ready,
                        "status": "pending",
                        "remark": remark,
                    }
                )
                new_count += 1

            if auto_generate_ops:
                # 统一按“重建工序”执行（会覆盖已补充信息）
                svc.create_batch_from_template_no_tx(
                    batch_id=bid,
                    part_no=pn,
                    quantity=qty,
                    due_date=_normalize_due_date(dd),
                    priority=prio,
                    ready_status=ready,
                    remark=(str(remark).strip() if remark is not None and str(remark).strip() else None),
                    rebuild_ops=True,
                )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="scheduler",
        target_type="batch",
        filename=filename,
        mode=mode,
        preview_or_result={
            "total_rows": len(preview_rows),
            "new_count": new_count,
            "update_count": update_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "errors_sample": errors_sample,
            "auto_generate_ops": bool(auto_generate_ops),
        },
        time_cost_ms=time_cost_ms,
    )

    auto_text = "（已自动从模板生成/重建工序）" if auto_generate_ops else ""
    flash(f"导入完成：新增 {new_count}，更新 {update_count}，跳过 {skip_count}，错误 {error_count}。{auto_text}", "success")
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
        return send_file(
            template_path,
            as_attachment=True,
            download_name="批次信息.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # 动态兜底（理论上不会走到，因为启动会 ensure）
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["批次号", "图号", "数量", "交期", "优先级", "齐套", "备注"])
    ws.append(["B001", "A1234", 50, "2026-01-25", "urgent", "yes", "示例"])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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
    return send_file(
        output,
        as_attachment=True,
        download_name="批次信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/batches/export")
def excel_batches_export():
    start = time.time()
    svc = BatchService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = svc.list()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["批次号", "图号", "数量", "交期", "优先级", "齐套", "备注"])
    for b in rows:
        ws.append([b.batch_id, b.part_no, b.quantity, b.due_date, b.priority, b.ready_status, b.remark])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

