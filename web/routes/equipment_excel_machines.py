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
from core.services.equipment import MachineService
from data.repositories import MachineRepository, OpTypeRepository

from .equipment_bp import bp, _ensure_unique_ids, _parse_mode, _read_uploaded_xlsx


# ============================================================
# Excel：设备信息（Machines）
# （Phase4-03 会在此基础上完善；先占位，避免后续拆文件）
# ============================================================


def _validate_machine_excel_row(row: Dict[str, Any]) -> Optional[str]:
    if not row.get("设备编号") or str(row.get("设备编号")).strip() == "":
        return "“设备编号”不能为空"
    if not row.get("设备名称") or str(row.get("设备名称")).strip() == "":
        return "“设备名称”不能为空"

    status = row.get("状态")
    if status is None or str(status).strip() == "":
        return "“状态”不能为空（允许：active / inactive / maintain）"
    status = str(status).strip()
    if status not in ("active", "inactive", "maintain", "可用", "停用", "维修", "维护", "维护中", "维修中"):
        return "“状态”不合法（允许：active / inactive / maintain；或中文：可用/停用/维修）"

    # 工种可为空；不为空时在 confirm/preview 中做存在性校验并给出中文提示
    return None


def _normalize_machine_status_for_excel(value: Any) -> str:
    """
    Excel 中的状态允许：
    - 英文：active / inactive / maintain
    - 中文：可用 / 停用 / 维修/维护
    返回统一的英文枚举值。
    """
    if value is None:
        return ""
    v = str(value).strip()
    if v in ("可用", "启用", "正常"):
        return "active"
    if v in ("维修", "维护", "维护中", "维修中", "保养"):
        return "maintain"
    if v in ("停用", "禁用", "不可用"):
        return "inactive"
    return v


def _resolve_op_type(value: Any, op_type_repo: OpTypeRepository) -> Dict[str, Optional[str]]:
    """
    解析 Excel 的“工种”字段：
    - 支持填写 op_type_id 或 工种名称
    - 返回 dict：{op_type_id, op_type_name}
    """
    v = None if value is None else str(value).strip()
    if not v:
        return {"op_type_id": None, "op_type_name": None}
    ot = op_type_repo.get(v)
    if not ot:
        ot = op_type_repo.get_by_name(v)
    if not ot:
        raise ValidationError(f"工种“{v}”不存在，请先在工艺管理-工种配置中维护。", field="工种")
    return {"op_type_id": ot.op_type_id, "op_type_name": ot.name}


@bp.get("/excel/machines")
def excel_machine_page():
    svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = svc.build_existing_for_excel()
    return render_template(
        "equipment/excel_import_machine.html",
        title="设备信息 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=None,
        raw_rows_json=None,
        mode=ImportMode.OVERWRITE.value,
        filename=None,
        preview_url=url_for("equipment.excel_machine_preview"),
        confirm_url=url_for("equipment.excel_machine_confirm"),
        template_download_url=url_for("equipment.excel_machine_template"),
        export_url=url_for("equipment.excel_machine_export"),
    )


@bp.post("/excel/machines/preview")
def excel_machine_preview():
    start = time.time()
    mode = _parse_mode(request.form.get("mode", ImportMode.OVERWRITE.value))
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValidationError("请先选择要上传的 Excel 文件", field="file")

    rows = _read_uploaded_xlsx(file)
    _ensure_unique_ids(rows, id_column="设备编号")

    op_type_repo = OpTypeRepository(g.db)

    # 预先做字段标准化，便于差异对比与落库
    normalized_rows: List[Dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        if "状态" in item:
            item["状态"] = _normalize_machine_status_for_excel(item.get("状态"))
        # 工种：预览时也尽量标准化为“工种名称”
        try:
            ot = _resolve_op_type(item.get("工种"), op_type_repo=op_type_repo)
            if ot.get("op_type_name") is not None:
                item["工种"] = ot.get("op_type_name")
        except ValidationError:
            # 让 validator 输出更友好的错误，不在这里中断
            pass
        normalized_rows.append(item)

    m_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = m_svc.build_existing_for_excel()

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        err = _validate_machine_excel_row(row)
        if err:
            return err

        # 状态标准化
        row["状态"] = _normalize_machine_status_for_excel(row.get("状态"))
        if row["状态"] not in ("active", "inactive", "maintain"):
            return "“状态”不合法（允许：active / inactive / maintain；或中文：可用/停用/维修）"

        # 工种存在性校验 + 标准化（允许为空）
        v = row.get("工种")
        if v is None or str(v).strip() == "":
            return None
        try:
            ot = _resolve_op_type(v, op_type_repo=op_type_repo)
            row["工种"] = ot.get("op_type_name")
        except ValidationError as e:
            return e.message
        return None

    svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = svc.preview_import(
        rows=normalized_rows,
        id_column="设备编号",
        existing_data=existing,
        validators=[validate_row],
        mode=mode,
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

    return render_template(
        "equipment/excel_import_machine.html",
        title="设备信息 - Excel 导入/导出",
        existing_list=list(existing.values()),
        preview_rows=preview_rows,
        raw_rows_json=json.dumps(normalized_rows, ensure_ascii=False),
        mode=mode.value,
        filename=file.filename,
        preview_url=url_for("equipment.excel_machine_preview"),
        confirm_url=url_for("equipment.excel_machine_confirm"),
        template_download_url=url_for("equipment.excel_machine_template"),
        export_url=url_for("equipment.excel_machine_export"),
    )


@bp.post("/excel/machines/confirm")
def excel_machine_confirm():
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

    _ensure_unique_ids(rows, id_column="设备编号")

    op_type_repo = OpTypeRepository(g.db)
    m_svc = MachineService(g.db, op_logger=getattr(g, "op_logger", None))
    existing = m_svc.build_existing_for_excel()

    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        err = _validate_machine_excel_row(row)
        if err:
            return err
        row["状态"] = _normalize_machine_status_for_excel(row.get("状态"))
        if row["状态"] not in ("active", "inactive", "maintain"):
            return "“状态”不合法（允许：active / inactive / maintain；或中文：可用/停用/维修）"
        v = row.get("工种")
        if v is None or str(v).strip() == "":
            return None
        try:
            ot = _resolve_op_type(v, op_type_repo=op_type_repo)
            row["工种"] = ot.get("op_type_name")
        except ValidationError as e:
            return e.message
        return None

    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    preview_rows = excel_svc.preview_import(
        rows=rows,
        id_column="设备编号",
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
            "equipment/excel_import_machine.html",
            title="设备信息 - Excel 导入/导出",
            existing_list=list(existing.values()),
            preview_rows=preview_rows,
            raw_rows_json=json.dumps(rows, ensure_ascii=False),
            mode=mode.value,
            filename=filename,
            preview_url=url_for("equipment.excel_machine_preview"),
            confirm_url=url_for("equipment.excel_machine_confirm"),
            template_download_url=url_for("equipment.excel_machine_template"),
            export_url=url_for("equipment.excel_machine_export"),
        )

    # 落库：忽略 ERROR 行
    tx = TransactionManager(g.db)
    m_repo = MachineRepository(g.db)

    new_count = update_count = skip_count = error_count = 0
    errors_sample: List[Dict[str, Any]] = []

    with tx.transaction():
        if mode == ImportMode.REPLACE:
            m_svc.ensure_replace_allowed()
            g.db.execute("DELETE FROM Machines")

        for pr in preview_rows:
            if pr.status == RowStatus.ERROR:
                error_count += 1
                if pr.message and len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": pr.message})
                continue

            machine_id = str(pr.data.get("设备编号")).strip()
            name = pr.data.get("设备名称")
            status = _normalize_machine_status_for_excel(pr.data.get("状态"))
            if status not in ("active", "inactive", "maintain"):
                # 防御：理论上不会发生
                error_count += 1
                if len(errors_sample) < 10:
                    errors_sample.append({"row": pr.row_num, "message": "状态不合法，无法写入。"})
                continue

            # 工种：预览阶段已标准化为名称（或空）；这里统一再解析一次拿到 op_type_id
            op_type_id = None
            try:
                ot = _resolve_op_type(pr.data.get("工种"), op_type_repo=op_type_repo)
                op_type_id = ot.get("op_type_id")
            except ValidationError:
                op_type_id = None

            if mode == ImportMode.APPEND and machine_id in existing:
                skip_count += 1
                continue

            if m_repo.exists(machine_id):
                m_repo.update(
                    machine_id,
                    {"name": name, "op_type_id": op_type_id, "status": status},
                )
                update_count += 1
            else:
                m_repo.create({"machine_id": machine_id, "name": name, "op_type_id": op_type_id, "status": status})
                new_count += 1

    time_cost_ms = int((time.time() - start) * 1000)
    log_excel_import(
        op_logger=getattr(g, "op_logger", None),
        module="equipment",
        target_type="machine",
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
        return send_file(
            template_path,
            as_attachment=True,
            download_name="设备信息.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["设备编号", "设备名称", "工种", "状态"])
    ws.append(["CNC-01", "数控车床1", "数车", "active"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

    return send_file(
        output,
        as_attachment=True,
        download_name="设备信息.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/excel/machines/export")
def excel_machine_export():
    start = time.time()
    rows = g.db.execute(
        """
        SELECT m.machine_id, m.name, m.status, ot.name AS op_type_name
        FROM Machines m
        LEFT JOIN OpTypes ot ON ot.op_type_id = m.op_type_id
        ORDER BY m.machine_id
        """
    ).fetchall()

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["设备编号", "设备名称", "工种", "状态"])
    for r in rows:
        ws.append([r["machine_id"], r["name"], r["op_type_name"], r["status"]])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

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

