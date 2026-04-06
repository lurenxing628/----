from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, send_file, url_for

from core.infrastructure.errors import ValidationError
from core.models.enums import OperatorStatus
from core.services.common.enum_normalizers import normalize_operator_status
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_backend_factory import get_excel_backend
from core.services.common.excel_service import ExcelService, ImportMode
from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
from core.services.common.normalize import is_blank_value
from core.services.personnel import OperatorService, ResourceTeamService
from core.services.personnel.operator_excel_import_service import OperatorExcelImportService
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
from .personnel_bp import _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx, bp


def _validate_operator_excel_row(row: Dict[str, Any]) -> Optional[str]:
    if is_blank_value(row.get("工号")):
        return "工号不能为空"
    if is_blank_value(row.get("姓名")):
        return "姓名不能为空"

    st = normalize_operator_status(row.get("状态"))
    if not st:
        return "状态不能为空，请填写：在岗 或 停用（也兼容 active / inactive）。"
    if st not in (OperatorStatus.ACTIVE.value, OperatorStatus.INACTIVE.value):
        return "状态不合法，可填写：在岗 / 停用（也兼容 active / inactive）。"
    row["状态"] = st
    return None


# ============================================================
# Excel：人员基本信息（Operators）
# ============================================================


def _render_excel_operator_page(
    *,
    existing: Dict[str, Dict[str, Any]],
    preview_rows: Any,
    raw_rows_json: Optional[str],
    preview_baseline: Optional[str],
    mode_value: str,
    filename: Optional[str],
):
    return render_template(
        "personnel/excel_import_operator.html",
        title="人员基本信息 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=raw_rows_json,
        preview_baseline=preview_baseline,
        mode=mode_value,
        filename=filename,
        preview_url=url_for("personnel.excel_operator_preview"),
        confirm_url=url_for("personnel.excel_operator_confirm"),
        template_download_url=url_for("personnel.excel_operator_template"),
        export_url=url_for("personnel.excel_operator_export"),
    )


def _operator_team_snapshot(team_svc: ResourceTeamService) -> Dict[str, Any]:
    return {
        "teams": [
            {
                "team_id": team.team_id,
                "name": team.name,
                "status": team.status,
            }
            for team in sorted(team_svc.list(status=None), key=lambda item: str(item.team_id))
        ]
    }


@bp.get("/excel/operators")
def excel_operator_page():
    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = op_svc.build_existing_for_excel()

    return _render_excel_operator_page(
        existing=existing,
        preview_rows=None,
        raw_rows_json=None,
        preview_baseline=None,
        mode_value=ImportMode.OVERWRITE.value,
        filename=None,
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
    team_svc = ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = op_svc.build_existing_for_excel()

    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        if "状态" in item:
            item["状态"] = normalize_operator_status(item.get("状态"))
        if "班组" in item:
            try:
                item["班组"] = team_svc.resolve_team_name_optional(item.get("班组"))
            except ValidationError:
                pass
        normalized_rows.append(item)

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        err = _validate_operator_excel_row(row)
        if err:
            return err
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
        id_column="工号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )
    preview_baseline = build_preview_baseline_token(
        existing_data=existing,
        mode=mode,
        id_column="工号",
        extra_state=_operator_team_snapshot(team_svc),
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

    return _render_excel_operator_page(
        existing=existing,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        preview_baseline=preview_baseline,
        mode_value=mode.value,
        filename=file.filename,
    )


@bp.post("/excel/operators/confirm")
def excel_operator_confirm():
    start = time.time()

    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    filename = request.form.get("filename") or "unknown.xlsx"
    payload = load_confirm_payload(request.form.get("raw_rows_json"), request.form.get("preview_baseline"))
    rows = payload.rows

    _ensure_unique_ids(rows, id_column="工号")

    op_svc = OperatorService(g.db, op_logger=getattr(g, "op_logger", None))
    team_svc = ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = op_svc.build_existing_for_excel()
    if preview_baseline_is_stale(
        payload.preview_baseline,
        existing_data=existing,
        mode=mode,
        id_column="工号",
        extra_state=_operator_team_snapshot(team_svc),
    ):
        flash("导入被拒绝：数据已变化，需重新预览后再确认导入。", "error")
        return _render_excel_operator_page(
            existing=existing,
            preview_rows=None,
            raw_rows_json=None,
            preview_baseline=None,
            mode_value=mode.value,
            filename=filename,
        )

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        err = _validate_operator_excel_row(row)
        if err:
            return err
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
        id_column="工号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
    )

    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        flash(build_error_rows_message(error_rows), "error")
        return _render_excel_operator_page(
            existing=existing,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            preview_baseline=payload.preview_baseline,
            mode_value=mode.value,
            filename=filename,
        )

    import_svc = OperatorExcelImportService(
        g.db,
        logger=getattr(g, "app_logger", None),
        op_logger=getattr(g, "op_logger", None),
    )
    import_stats = import_svc.apply_preview_rows(preview_rows, mode=mode, existing_ids=set(existing.keys()))
    new_count, update_count, skip_count, error_count = extract_import_stats(import_stats)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator",
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
        return send_excel_template_file(template_path, download_name="人员基本信息.xlsx")

    template_def = get_template_definition("人员基本信息.xlsx")
    sample_rows = template_def.get("sample_rows") or []
    output = build_xlsx_bytes(
        template_def["headers"],
        sample_rows,
        format_spec=template_def.get("format_spec"),
    )

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator",
        template_or_export_type="人员基本信息模板.xlsx",
        filters={},
        row_count=len(sample_rows),
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

    existing = OperatorService(g.db, op_logger=getattr(g, "op_logger", None)).build_existing_for_excel()
    export_rows = list(existing.values())
    template_def = get_template_definition("人员基本信息.xlsx")
    output = build_xlsx_bytes(
        template_def["headers"],
        [[r.get("工号"), r.get("姓名"), r.get("状态"), r.get("班组"), r.get("备注")] for r in export_rows],
        format_spec=template_def.get("format_spec"),
        sanitize_formula=True,
    )

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
