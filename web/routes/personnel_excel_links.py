from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, List

from flask import current_app, flash, g, redirect, request, send_file, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import ValidationError
from core.services.common.excel_audit import log_excel_export, log_excel_import
from core.services.common.excel_service import ImportMode, RowStatus
from core.services.personnel import OperatorMachineService

from .personnel_bp import bp, _parse_mode, _read_uploaded_xlsx


# ============================================================
# Excel：人员设备关联（OperatorMachine）
# ============================================================


@bp.get("/excel/links")
def excel_link_page():
    # 当前关联展示（用于用户核对）
    rows = g.db.execute(
        """
        SELECT om.operator_id, o.name AS operator_name, om.machine_id, m.name AS machine_name,
               om.skill_level, om.is_primary
        FROM OperatorMachine om
        LEFT JOIN Operators o ON o.operator_id = om.operator_id
        LEFT JOIN Machines m ON m.machine_id = om.machine_id
        ORDER BY om.operator_id, om.machine_id
        """
    ).fetchall()
    existing_list = [
        {
            "工号": r["operator_id"],
            "姓名": r["operator_name"],
            "设备编号": r["machine_id"],
            "设备名称": r["machine_name"],
            "技能等级": r["skill_level"],
            "主操设备": r["is_primary"],
        }
        for r in rows
    ]

    return render_template(
        "personnel/excel_import_operator_machine.html",
        title="人员设备关联 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("personnel.excel_link_preview"),
        confirm_url=url_for("personnel.excel_link_confirm"),
        template_download_url=url_for("personnel.excel_link_template"),
        export_url=url_for("personnel.excel_link_export"),
    )


@bp.post("/excel/links/preview")
def excel_link_preview():
    start = time.time()

    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    link_svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_machine",
        filename=file.filename,
        mode=mode,
        preview_or_result=preview_rows,
        time_cost_ms=time_cost_ms,
    )

    # 刷新 existing list
    existing_rows = g.db.execute(
        """
        SELECT om.operator_id, o.name AS operator_name, om.machine_id, m.name AS machine_name,
               om.skill_level, om.is_primary
        FROM OperatorMachine om
        LEFT JOIN Operators o ON o.operator_id = om.operator_id
        LEFT JOIN Machines m ON m.machine_id = om.machine_id
        ORDER BY om.operator_id, om.machine_id
        """
    ).fetchall()
    existing_list = [
        {
            "工号": r["operator_id"],
            "姓名": r["operator_name"],
            "设备编号": r["machine_id"],
            "设备名称": r["machine_name"],
            "技能等级": r["skill_level"],
            "主操设备": r["is_primary"],
        }
        for r in existing_rows
    ]

    return render_template(
        "personnel/excel_import_operator_machine.html",
        title="人员设备关联 - Excel 导入/导出",
        existing_list=existing_list,
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("personnel.excel_link_preview"),
        confirm_url=url_for("personnel.excel_link_confirm"),
        template_download_url=url_for("personnel.excel_link_template"),
        export_url=url_for("personnel.excel_link_export"),
    )


@bp.post("/excel/links/confirm")
def excel_link_confirm():
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

    link_svc = OperatorMachineService(g.db, op_logger=getattr(g, "op_logger", None))
    preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)

    # 严格模式：只要存在错误行，就拒绝导入（规范用户行为）
    error_rows = [pr for pr in preview_rows if pr.status == RowStatus.ERROR]
    if error_rows:
        sample = "；".join([f"第{pr.row_num}行：{pr.message}" for pr in error_rows[:5] if pr and pr.message])
        flash(
            f"导入被拒绝：Excel 存在 {len(error_rows)} 行错误。请修正后重新预览并确认。{('错误示例：' + sample) if sample else ''}",
            "error",
        )

        # 刷新 existing list（与 preview 保持一致）
        existing_rows = g.db.execute(
            """
            SELECT om.operator_id, o.name AS operator_name, om.machine_id, m.name AS machine_name,
                   om.skill_level, om.is_primary
            FROM OperatorMachine om
            LEFT JOIN Operators o ON o.operator_id = om.operator_id
            LEFT JOIN Machines m ON m.machine_id = om.machine_id
            ORDER BY om.operator_id, om.machine_id
            """
        ).fetchall()
        existing_list = [
            {
                "工号": r["operator_id"],
                "姓名": r["operator_name"],
                "设备编号": r["machine_id"],
                "设备名称": r["machine_name"],
                "技能等级": r["skill_level"],
                "主操设备": r["is_primary"],
            }
            for r in existing_rows
        ]

        return render_template(
            "personnel/excel_import_operator_machine.html",
            title="人员设备关联 - Excel 导入/导出",
            existing_list=existing_list,
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("personnel.excel_link_preview"),
            confirm_url=url_for("personnel.excel_link_confirm"),
            template_download_url=url_for("personnel.excel_link_template"),
            export_url=url_for("personnel.excel_link_export"),
        )

    stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_machine",
        filename=filename,
        mode=mode,
        preview_or_result=stats,
        time_cost_ms=time_cost_ms,
    )

    flash(
        f"导入完成：新增 {stats.get('new_count', 0)}，更新 {stats.get('update_count', 0)}，跳过 {stats.get('skip_count', 0)}，错误 {stats.get('error_count', 0)}。",
        "success",
    )
    return redirect(url_for("personnel.excel_link_page"))


@bp.get("/excel/links/template")
def excel_link_template():
    start = time.time()
    template_path = os.path.join(current_app.config["EXCEL_TEMPLATE_DIR"], "人员设备关联.xlsx")
    if os.path.exists(template_path):
        time_cost_ms = int((time.time() - start) * 1000)
        log_excel_export(
            op_logger=getattr(g, "op_logger", None),
            module="personnel",
            target_type="operator_machine",
            template_or_export_type="人员设备关联模板.xlsx",
            filters={},
            row_count=1,
            time_range={},
            time_cost_ms=time_cost_ms,
        )
        return send_file(
            template_path,
            as_attachment=True,
            download_name="人员设备关联.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工号", "设备编号", "技能等级", "主操设备"])
    ws.append(["OP001", "CNC-01", "normal", "yes"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_machine",
        template_or_export_type="人员设备关联模板.xlsx",
        filters={},
        row_count=1,
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="人员设备关联.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/links/export")
def excel_link_export():
    start = time.time()
    rows = g.db.execute(
        "SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine ORDER BY operator_id, machine_id"
    ).fetchall()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["工号", "设备编号", "技能等级", "主操设备"])
    for r in rows:
        ws.append([r["operator_id"], r["machine_id"], r["skill_level"], r["is_primary"]])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="personnel",
        target_type="operator_machine",
        template_or_export_type="人员设备关联导出.xlsx",
        filters={},
        row_count=len(rows),
        time_range={},
        time_cost_ms=time_cost_ms,
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="人员设备关联.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

