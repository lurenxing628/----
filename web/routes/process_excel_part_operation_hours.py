from __future__ import annotations

import io
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode, RowStatus
from core.services.scheduler.number_utils import parse_finite_float
from data.repositories import PartOperationRepository

from .process_bp import bp, _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx


# ============================================================
# Excel：零件工序工时（PartOperations.setup_hours / unit_hours）
# ============================================================


def _parse_seq(value: Any) -> Optional[int]:
    if value is None:
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
    rows = g.db.execute(
        """
        SELECT part_no, seq, op_type_name, source, setup_hours, unit_hours
        FROM PartOperations
        WHERE status='active'
        ORDER BY part_no, seq
        """
    ).fetchall()

    existing_internal: Dict[str, Dict[str, Any]] = {}
    meta_all: Dict[str, Dict[str, Any]] = {}
    existing_list: List[Dict[str, Any]] = []

    for r in rows:
        part_no = str(r["part_no"] or "").strip()
        seq = int(r["seq"] or 0)
        row_id = f"{part_no}|{seq}"
        source = str(r["source"] or "").strip().lower() or "internal"
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
        if source == "internal":
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
        part_no = str(r.get("图号") or "").strip()
        seq = _parse_seq(r.get("工序"))
        normalized.append(
            {
                "图号": part_no or None,
                "工序": seq if seq is not None else r.get("工序"),
                "换型时间(h)": r.get("换型时间(h)"),
                "单件工时(h)": r.get("单件工时(h)"),
                "__row_id__": (f"{part_no}|{seq}" if part_no and seq is not None else None),
            }
        )
    return normalized


def _build_validator(meta_all: Dict[str, Dict[str, Any]]):
    def _validate_row(row: Dict[str, Any]) -> Optional[str]:
        part_no = str(row.get("图号") or "").strip()
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
        if str(meta.get("归属") or "").strip().lower() != "internal":
            return f"仅支持内部工序导入工时：图号={part_no} 工序={seq}"
        return None

    return _validate_row


@bp.get("/excel/part-operation-hours")
def excel_part_op_hours_page():
    _existing_internal, _meta_all, existing_list = _build_existing_internal()
    return render_template(
        "process/excel_import_part_operation_hours.html",
        title="零件工序工时 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("process.excel_part_op_hours_preview"),
        confirm_url=url_for("process.excel_part_op_hours_confirm"),
        template_download_url=url_for("process.excel_part_op_hours_template"),
        export_url=url_for("process.excel_part_op_hours_export"),
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
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="__row_id__",
        existing_data=existing_internal,
        validators=[validator],
        mode=mode,
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

    return render_template(
        "process/excel_import_part_operation_hours.html",
        title="零件工序工时 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("process.excel_part_op_hours_preview"),
        confirm_url=url_for("process.excel_part_op_hours_confirm"),
        template_download_url=url_for("process.excel_part_op_hours_template"),
        export_url=url_for("process.excel_part_op_hours_export"),
    )


@bp.post("/excel/part-operation-hours/confirm")
def excel_part_op_hours_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    if mode == ImportMode.REPLACE:
        raise ValidationError("该页面不支持“替换（清空后导入）”，请使用“覆盖”或“追加”。", field="mode")

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

    _ensure_unique_ids(rows, id_column="__row_id__")

    existing_internal, meta_all, existing_list = _build_existing_internal()
    validator = _build_validator(meta_all=meta_all)
    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="__row_id__",
        existing_data=existing_internal,
        validators=[validator],
        mode=mode,
    )

    error_rows = [pr for pr in preview_rows if pr.status == RowStatus.ERROR]
    if error_rows:
        sample = "；".join([f"第{pr.row_num}行：{pr.message}" for pr in error_rows[:5] if pr and pr.message])
        flash(
            f"导入被拒绝：Excel 存在 {len(error_rows)} 行错误。请修正后重新预览并确认。{('错误示例：' + sample) if sample else ''}",
            "error",
        )
        return render_template(
            "process/excel_import_part_operation_hours.html",
            title="零件工序工时 - Excel 导入/导出",
            existing_list=existing_list,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("process.excel_part_op_hours_preview"),
            confirm_url=url_for("process.excel_part_op_hours_confirm"),
            template_download_url=url_for("process.excel_part_op_hours_template"),
            export_url=url_for("process.excel_part_op_hours_export"),
        )

    tx = TransactionManager(g.db)
    op_repo = PartOperationRepository(g.db)
    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []

    with tx.transaction():
        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message and len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": pr.message})
                continue
            if pr.status == RowStatus.SKIP:
                skip_count += 1
                continue
            if pr.status == RowStatus.UNCHANGED:
                continue

            part_no = str(pr.data.get("图号") or "").strip()
            seq = _parse_seq(pr.data.get("工序"))
            if not part_no or seq is None:
                error_count += 1
                if len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": "缺少图号/工序，无法写入。"})
                continue

            try:
                sh_raw = parse_finite_float(pr.data.get("换型时间(h)"), field="换型时间(h)", allow_none=True)
                uh_raw = parse_finite_float(pr.data.get("单件工时(h)"), field="单件工时(h)", allow_none=True)
            except ValidationError as e:
                error_count += 1
                if len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": e.message})
                continue
            sh = 0.0 if sh_raw is None else float(sh_raw)
            uh = 0.0 if uh_raw is None else float(uh_raw)

            op = op_repo.get(part_no, int(seq))
            if not op:
                error_count += 1
                if len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": f"工序不存在：图号={part_no} 工序={seq}"})
                continue
            if (op.source or "").strip().lower() != "internal":
                error_count += 1
                if len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": f"仅内部工序可导入工时：图号={part_no} 工序={seq}"})
                continue

            op_repo.update(part_no, int(seq), {"setup_hours": sh, "unit_hours": uh})
            if pr.status == RowStatus.NEW:
                new_count += 1
            else:
                update_count += 1

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="process",
        target_type="part_operation_hours",
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
        return send_file(
            template_path,
            as_attachment=True,
            download_name="零件工序工时.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["图号", "工序", "换型时间(h)", "单件工时(h)"])
    ws.append(["A1234", 5, 1.0, 0.25])
    ws.append(["A1234", 10, 0.5, 0.1])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

    return send_file(
        output,
        as_attachment=True,
        download_name="零件工序工时.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/part-operation-hours/export")
def excel_part_op_hours_export():
    start = time.time()
    rows = g.db.execute(
        """
        SELECT part_no, seq, setup_hours, unit_hours
        FROM PartOperations
        WHERE status='active' AND source='internal'
        ORDER BY part_no, seq
        """
    ).fetchall()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["图号", "工序", "换型时间(h)", "单件工时(h)"])
    for r in rows:
        ws.append([r["part_no"], int(r["seq"] or 0), float(r["setup_hours"] or 0.0), float(r["unit_hours"] or 0.0)])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

