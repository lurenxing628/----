from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.services.common.enum_normalizers import skill_level_label, yes_no_label
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_service import ImportMode
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.equipment import MachineService
from core.services.personnel import OperatorMachineService, OperatorService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from web.ui_mode import render_ui_template as render_template

from .equipment_bp import _parse_mode, _read_uploaded_xlsx, bp
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

# ============================================================
# Excel：设备人员关联（OperatorMachine）
# ============================================================


def _build_existing_machine_link_page_data() -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    q = OperatorMachineQueryService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = q.list_with_names_by_machine()
    existing_list = [
        {
            "设备编号": r["machine_id"],
            "设备名称": r["machine_name"],
            "工号": r["operator_id"],
            "姓名": r["operator_name"],
            "技能等级": skill_level_label(r["skill_level"]),
            "主操设备": yes_no_label(r["is_primary"]),
        }
        for r in rows
    ]
    existing_snapshot: Dict[str, Dict[str, Any]] = {}
    for r in q.list_simple_rows():
        op_id = str(r.get("operator_id") or "").strip()
        machine_id = str(r.get("machine_id") or "").strip()
        if not op_id or not machine_id:
            continue
        existing_snapshot[f"{op_id}|{machine_id}"] = {
            "skill_level": r.get("skill_level"),
            "is_primary": r.get("is_primary"),
        }
    return existing_list, existing_snapshot


def _operator_machine_reference_snapshot() -> Dict[str, Any]:
    operator_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    machine_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    return {
        "operator_ids": sorted([str(op.operator_id) for op in operator_svc.list(status=None) if getattr(op, "operator_id", None)]),
        "machine_ids": sorted([str(machine.machine_id) for machine in machine_svc.list(status=None) if getattr(machine, "machine_id", None)]),
    }


def _render_excel_link_page(
    *,
    existing_list: List[Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
):
    return render_template(
        "equipment/excel_import_machine_operator.html",
        title="批量维护设备人员关联",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("equipment.excel_link_preview"),
        confirm_url=url_for("equipment.excel_link_confirm"),
        template_download_url=url_for("equipment.excel_link_template"),
        export_url=url_for("equipment.excel_link_export"),
        back_url=url_for("equipment.list_page"),
        back_label="返回设备管理",
    )


@bp.get("/excel/links")
def excel_link_page():
    existing_list, _existing_snapshot = _build_existing_machine_link_page_data()
    return _render_excel_link_page(
        existing_list=existing_list,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
    )


@bp.post("/excel/links/preview")
def excel_link_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)

    # 设备侧导入字段：设备编号、工号（底层服务使用：工号、设备编号）
    # 这里做一次兼容：若用户写成“工号/设备编号”，也能识别
    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        if "工号" not in item and "操作工号" in item:
            item["工号"] = item.get("操作工号")
        if "设备编号" not in item and "机器编号" in item:
            item["设备编号"] = item.get("机器编号")
        # 若表头为“设备编号/工号”，这里已经满足
        if "工号" not in item and "工号" in r:
            item["工号"] = r.get("工号")
        normalized_rows.append(item)

    link_svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    preview_rows = link_svc.preview_import_links(rows=normalized_rows, mode=mode)
    existing_list, existing_snapshot = _build_existing_machine_link_page_data()
    preview_baseline = build_preview_baseline_token(
        existing_data=existing_snapshot,
        mode=mode,
        id_column="工号|设备编号",
        extra_state=_operator_machine_reference_snapshot(),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="equipment",
        target_type="operator_machine",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    return _render_excel_link_page(
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
    )


@bp.post("/excel/links/confirm")
def excel_link_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    existing_list, existing_snapshot = _build_existing_machine_link_page_data()
    if preview_baseline_is_stale(
        payload.preview_baseline,
        existing_data=existing_snapshot,
        mode=mode,
        id_column="工号|设备编号",
        extra_state=_operator_machine_reference_snapshot(),
    ):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_excel_link_page(
            existing_list=existing_list,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
        )

    link_svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")

        return _render_excel_link_page(
            existing_list=existing_list,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
        )

    stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)
    new_count, update_count, skip_count, error_count = extract_import_stats(stats)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="equipment",
        target_type="operator_machine",
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
    return redirect(url_for("equipment.excel_link_page"))


@bp.get("/excel/links/template")
def excel_link_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "设备人员关联.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="equipment",
            target_type="operator_machine",
            template_or_export_type="设备人员关联模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_excel_template_file(template_path, download_name="设备人员关联.xlsx")

    template_def = get_template_definition("设备人员关联.xlsx")
    sample_rows = template_def.get("sample_rows") or []
    output = build_xlsx_bytes(
        template_def["headers"],
        sample_rows,
        format_spec=template_def.get("format_spec"),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="equipment",
        target_type="operator_machine",
        template_or_export_type="设备人员关联模板.xlsx",
        filters={},
        row_count=len(sample_rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="设备人员关联.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/links/export")
def excel_link_export():
    start = time.time()
    q = OperatorMachineQueryService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = q.list_simple_rows()
    rows.sort(key=lambda r: (str(r.get("machine_id") or ""), str(r.get("operator_id") or "")))
    template_def = get_template_definition("设备人员关联.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [[r["machine_id"], r["operator_id"], skill_level_label(r["skill_level"]), yes_no_label(r["is_primary"])] for r in rows],
        format_spec=template_def.get("format_spec"),
        sanitize_formula=True,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="equipment",
        target_type="operator_machine",
        template_or_export_type="设备人员关联导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="设备人员关联.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
