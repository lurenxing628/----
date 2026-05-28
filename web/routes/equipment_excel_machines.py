from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.models.enums import MACHINE_STATUS_VALUES
from core.services.common.enum_normalizers import machine_status_label, normalize_machine_status
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.normalize import is_blank_value
from core.services.equipment import MachineService
from core.services.equipment.machine_excel_import_service import MachineExcelImportService
from core.services.personnel import ResourceTeamService
from core.services.process import OpTypeService
from web.ui_mode import render_ui_template as render_template

from .equipment_bp import _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx, bp
from .excel_utils import (
    build_error_rows_message,
    build_preview_baseline_token,
    collect_error_rows,
    encode_preview_rows_payload,
    extract_import_stats,
    flash_import_result,
    load_confirm_payload,
    normalize_renamed_column,
    preview_baseline_is_stale,
    project_preview_rows_for_display,
    renamed_column_conflict_message,
    send_excel_template_file,
)

# ============================================================
# Excel：设备信息（Machines）
# （Phase4-03 会在此基础上完善；先占位，避免后续拆文件）
# ============================================================

MACHINE_ID_COLUMN = "设备编号"
LEGACY_MACHINE_ID_COLUMN = "机器编号"
MACHINE_NAME_COLUMN = "设备名称"
LEGACY_MACHINE_NAME_COLUMN = "机器名称"


def _normalize_machine_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for row in rows:
        normalize_renamed_column(row, current_column=MACHINE_ID_COLUMN, legacy_column=LEGACY_MACHINE_ID_COLUMN)
        normalize_renamed_column(row, current_column=MACHINE_NAME_COLUMN, legacy_column=LEGACY_MACHINE_NAME_COLUMN)
    return rows


def _machine_name_conflict_message(row: Dict[str, Any]) -> Optional[str]:
    current_text = "" if is_blank_value(row.get(MACHINE_NAME_COLUMN)) else str(row.get(MACHINE_NAME_COLUMN)).strip()
    legacy_text = "" if is_blank_value(row.get(LEGACY_MACHINE_NAME_COLUMN)) else str(row.get(LEGACY_MACHINE_NAME_COLUMN)).strip()
    if not current_text or not legacy_text or current_text == legacy_text:
        return None
    return (
        f"“{MACHINE_NAME_COLUMN}”和旧列“{LEGACY_MACHINE_NAME_COLUMN}”不能同时填写不同值："
        f"当前“{MACHINE_NAME_COLUMN}”为“{current_text}”，“{LEGACY_MACHINE_NAME_COLUMN}”为“{legacy_text}”。"
        "请保留一个名称列，或把两个值改成一致后重新导入。"
    )


def _validate_machine_excel_row(row: Dict[str, Any]) -> Optional[str]:
    id_conflict = renamed_column_conflict_message(
        row,
        current_column=MACHINE_ID_COLUMN,
        legacy_column=LEGACY_MACHINE_ID_COLUMN,
    )
    if id_conflict:
        return id_conflict

    name_conflict = _machine_name_conflict_message(row)
    if name_conflict:
        return name_conflict

    if is_blank_value(row.get(MACHINE_ID_COLUMN)):
        return "设备编号不能为空"
    if is_blank_value(row.get(MACHINE_NAME_COLUMN)):
        return "设备名称不能为空"

    status = row.get("状态")
    if status is None or str(status).strip() == "":
        return "状态不能为空，请填写：可用 / 停用 / 维修。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。"
    st = _normalize_machine_status_for_excel(status)
    if st not in MACHINE_STATUS_VALUES:
        return "状态不合法，可填写：可用 / 停用 / 维修。以前的 Excel 如果写过英文状态，系统会尽量按中文意思读取；新文件请直接填中文。"
    row["状态"] = st

    return None


def _normalize_machine_status_for_excel(value: Any) -> str:
    """
    Excel 中的状态允许：
    - 英文：active / inactive / maintain
    - 中文：可用 / 停用 / 维修/维护
    返回统一的英文枚举值。
    """
    return normalize_machine_status(value)


def _resolve_op_type(value: Any, op_type_svc: OpTypeService) -> Dict[str, Optional[str]]:
    """
    解析 Excel 的工种字段：
    - 支持填写 op_type_id 或 工种名称
    - 返回 dict：{op_type_id, op_type_name}
    """
    v = None if value is None else str(value).strip()
    if not v:
        return {"op_type_id": None, "op_type_name": None}
    ot = op_type_svc.get_optional(v)
    if not ot:
        ot = op_type_svc.get_by_name_optional(v)
    if not ot:
        raise ValidationError(f"工种{v}不存在，请先在工艺管理-工种配置中维护。", field="工种")
    return {"op_type_id": ot.op_type_id, "op_type_name": ot.name}


def _machine_reference_snapshot(*, op_type_svc: OpTypeService, team_svc: ResourceTeamService) -> Dict[str, Any]:
    return {
        "op_types": [
            {
                "op_type_id": ot.op_type_id,
                "name": ot.name,
                "category": ot.category,
            }
            for ot in sorted(op_type_svc.list(), key=lambda item: str(item.op_type_id))
        ],
        "teams": [
            {
                "team_id": team.team_id,
                "name": team.name,
                "status": team.status,
            }
            for team in sorted(team_svc.list(status=None), key=lambda item: str(item.team_id))
        ],
    }


def _render_excel_machine_page(
    *,
    existing: Dict[str, Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
):
    existing_list = []
    for row in list((existing or {}).values()):
        existing_list.append(
            {
                **dict(row or {}),
                "状态显示": machine_status_label((row or {}).get("状态")),
            }
        )
    return render_template(
        "equipment/excel_import_machine.html",
        title="批量维护设备",
        existing_list=existing_list,
        preview_rows=project_preview_rows_for_display(preview_rows, {"状态": machine_status_label}),
        raw_rows_json=encode_preview_rows_payload(raw_rows_json),
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("equipment.excel_machine_preview"),
        confirm_url=url_for("equipment.excel_machine_confirm"),
        template_download_url=url_for("equipment.excel_machine_template"),
        export_url=url_for("equipment.excel_machine_export"),
        back_url=url_for("equipment.list_page"),
        back_label="返回设备管理",
    )


@bp.get("/excel/machines")
def excel_machine_page():
    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel()
    return _render_excel_machine_page(
        existing=existing,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
    )


@bp.post("/excel/machines/preview")
def excel_machine_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    used_legacy_column = any(LEGACY_MACHINE_ID_COLUMN in row or LEGACY_MACHINE_NAME_COLUMN in row for row in rows)
    rows = _normalize_machine_rows(rows)
    _ensure_unique_ids(rows, id_column=MACHINE_ID_COLUMN)

    op_type_svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    team_svc = ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None))

    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        if "状态" in item:
            item["状态"] = _normalize_machine_status_for_excel(item.get("状态"))
        try:
            ot = _resolve_op_type(item.get("工种"), op_type_svc=op_type_svc)
            if ot.get("op_type_name") is not None:
                item["工种"] = ot.get("op_type_name")
        except ValidationError:
            pass
        if "班组" in item:
            try:
                item["班组"] = team_svc.resolve_team_name_optional(item.get("班组"))
            except ValidationError:
                pass
        normalized_rows.append(item)

    m_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = m_svc.build_existing_for_excel()

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        err = _validate_machine_excel_row(row)
        if err:
            return err

        v = row.get("工种")
        if v is not None and str(v).strip() != "":
            try:
                ot = _resolve_op_type(v, op_type_svc=op_type_svc)
                row["工种"] = ot.get("op_type_name")
            except ValidationError as e:
                return e.message
        if "班组" not in row:
            return None
        try:
            row["班组"] = team_svc.resolve_team_name_optional(row.get("班组"))
        except ValidationError as e:
            return e.message
        return None

    svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = svc.preview_import(
        rows=normalized_rows,
        id_column=MACHINE_ID_COLUMN,
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )
    preview_baseline = build_preview_baseline_token(
        existing_data=existing,
        mode=mode,
        id_column=MACHINE_ID_COLUMN,
        extra_state=_machine_reference_snapshot(op_type_svc=op_type_svc, team_svc=team_svc),
        rows=normalized_rows,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="equipment",
        target_type="machine",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )
    if used_legacy_column:
        flash("已识别旧列“机器编号/机器名称”，本次按“设备编号/设备名称”处理。建议下载新模板后再维护。", "warning")

    return _render_excel_machine_page(
        existing=existing,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
    )


@bp.post("/excel/machines/confirm")
def excel_machine_confirm():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = _normalize_machine_rows(payload.rows)

    _ensure_unique_ids(rows, id_column=MACHINE_ID_COLUMN)

    op_type_svc = OpTypeService(g.db, op_logger=getattr(g, "op_logger", None))
    team_svc = ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None))
    m_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = m_svc.build_existing_for_excel()
    if preview_baseline_is_stale(
        payload.preview_baseline,
        existing_data=existing,
        mode=mode,
        id_column=MACHINE_ID_COLUMN,
        extra_state=_machine_reference_snapshot(op_type_svc=op_type_svc, team_svc=team_svc),
        rows=rows,
    ):
        flash("导入被拒绝：数据已变化，请重新上传 Excel 并检查后再确认写入。", "error")
        return _render_excel_machine_page(
            existing=existing,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
        )

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        err = _validate_machine_excel_row(row)
        if err:
            return err
        v = row.get("工种")
        if v is not None and str(v).strip() != "":
            try:
                ot = _resolve_op_type(v, op_type_svc=op_type_svc)
                row["工种"] = ot.get("op_type_name")
            except ValidationError as e:
                return e.message
        if "班组" not in row:
            return None
        try:
            row["班组"] = team_svc.resolve_team_name_optional(row.get("班组"))
        except ValidationError as e:
            return e.message
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column=MACHINE_ID_COLUMN,
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_excel_machine_page(
            existing=existing,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
        )

    import_svc = MachineExcelImportService(
        g.db,
        logger=getattr(g, "app_logger", None),
        op_logger=getattr(g, "op_logger", None),
    )
    import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_ids=set(existing.keys()))
    new_count, update_count, skip_count, error_count = extract_import_stats(import_stats)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="equipment",
        target_type="machine",
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
    )
    return redirect(url_for("equipment.excel_machine_page"))


@bp.get("/excel/machines/template")
def excel_machine_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "设备信息.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="equipment",
            target_type="machine",
            template_or_export_type="设备信息模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_excel_template_file(template_path, download_name="设备信息.xlsx")

    template_def = get_template_definition("设备信息.xlsx")
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
        target_type="machine",
        template_or_export_type="设备信息模板.xlsx",
        filters={},
        row_count=len(sample_rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )
    return send_file(
        output,
        as_attachment=True,
        download_name="设备信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/machines/export")
def excel_machine_export():
    start = time.time()
    m_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    rows = m_svc.list_for_export()
    template_def = get_template_definition("设备信息.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [[r["machine_id"], r["name"], r.get("op_type_name"), r.get("team_name"), machine_status_label(r["status"])] for r in rows],
        format_spec=template_def.get("format_spec"),
        sanitize_formula=True,
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="equipment",
        target_type="machine",
        template_or_export_type="设备信息导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="设备信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
