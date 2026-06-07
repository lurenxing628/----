"""回归测试：七类 Excel「预览→确认」入口（工作日历/人员日历/批次/工序工时/设备/供应商/人员设备关联）在预览与确认之间相关主数据漂移时，confirm 一律拒绝并提示「请重新上传 Excel 并检查」，不按陈旧 preview_baseline 落库。"""

import io
import re
from html import unescape


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None

    ws.title = "Sheet1"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _extract_raw_rows_json(html: str) -> str:
    m = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("未能从页面提取 raw_rows_json")
    return unescape(m.group(1)).strip()


def _extract_hidden_input(html: str, name: str) -> str:
    for m in re.finditer(r"<input[^>]+>", html, re.I):
        tag = m.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag):
            vm = re.search(r'value="([^"]*)"', tag)
            return unescape(vm.group(1)).strip() if vm else ""
    raise RuntimeError(f"未能从页面提取隐藏字段：{name}")


def _assert_status(name: str, resp, expect_code: int = 200):
    if resp.status_code != expect_code:
        body = ""
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500]}")


def _preview_excel(client, url: str, mode: str, headers, rows, filename: str, extra=None):
    payload = {"mode": mode}
    if extra:
        payload.update(extra)
    resp = client.post(
        url,
        data={**payload, "file": (_make_xlsx_bytes(headers, rows), filename)},
        content_type="multipart/form-data",
    )
    _assert_status(f"{url} preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    return {
        "raw_rows_json": _extract_raw_rows_json(html),
        "preview_baseline": _extract_hidden_input(html, "preview_baseline"),
    }


def _confirm_excel(client, url: str, mode: str, filename: str, raw_rows_json: str, preview_baseline: str, extra=None) -> str:
    payload = {
        "mode": mode,
        "filename": filename,
        "raw_rows_json": raw_rows_json,
        "preview_baseline": preview_baseline,
    }
    if extra:
        payload.update(extra)
    resp = client.post(url, data=payload, follow_redirects=True)
    _assert_status(f"{url} confirm", resp, 200)
    return resp.data.decode("utf-8", errors="ignore")


def _assert_need_repreview(case_name: str, html: str) -> None:
    if "请重新上传 Excel 并检查" not in html:
        raise RuntimeError(f"{case_name} 未提示“请重新上传 Excel 并检查”")


def test_excel_preview_confirm_extra_state_guard(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    client = app_client

    from core.services.equipment.machine_service import MachineService
    from core.services.personnel.operator_service import OperatorService
    from core.services.personnel.resource_team_service import ResourceTeamService
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.part_service import PartService
    from core.services.scheduler.config_service import ConfigService

    conn = get_connection(db_path)
    try:
        op_type_svc = OpTypeService(conn)
        team_svc = ResourceTeamService(conn)
        operator_svc = OperatorService(conn)
        machine_svc = MachineService(conn)
        part_svc = PartService(conn)

        op_type_svc.create("OT_IN", "数车", "internal")
        op_type_svc.create("OT_MACH", "机加工", "internal")
        op_type_svc.create("OT_SUP", "外协工种", "external")
        team_svc.create("TM001", "一班")
        operator_svc.create("OP_CAL", "日历人员", "active")
        operator_svc.create("OP_LINK", "关联人员", "active")
        machine_svc.create("MC_LINK", "关联设备", status="active")
        part_svc.upsert_and_parse_no_tx("P_BATCH", "批次件", "5数车")
        part_svc.upsert_and_parse_no_tx("P_HOURS", "工时件", "5数车")
        conn.commit()
    finally:
        conn.close()

    # 1) 工作日历：holiday_default_efficiency 漂移
    preview = _preview_excel(
        client,
        "/scheduler/excel/calendar/preview",
        "overwrite",
        ["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
        [{"日期": "2026-04-01", "类型": "holiday", "可用工时": 0, "效率": None, "允许普通件": "no", "允许急件": "no", "说明": "cfg-drift"}],
        "calendar.xlsx",
    )
    conn = get_connection(db_path)
    try:
        ConfigService(conn).set_holiday_default_efficiency(0.6)
    finally:
        conn.close()
    html = _confirm_excel(
        client,
        "/scheduler/excel/calendar/confirm",
        "overwrite",
        "calendar.xlsx",
        preview["raw_rows_json"],
        preview["preview_baseline"],
    )
    _assert_need_repreview("工作日历基线漂移", html)

    # 2) 人员专属日历：operator_ids 漂移
    preview = _preview_excel(
        client,
        "/personnel/excel/operator_calendar/preview",
        "overwrite",
        ["工号", "日期", "类型", "班次开始", "班次结束", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
        [
            {
                "工号": "OP_CAL",
                "日期": "2026-04-02",
                "类型": "workday",
                "班次开始": "08:00",
                "班次结束": "16:00",
                "可用工时": 8,
                "效率": 1.0,
                "允许普通件": "yes",
                "允许急件": "yes",
                "说明": "operator-drift",
            }
        ],
        "operator_calendar.xlsx",
    )
    conn = get_connection(db_path)
    try:
        OperatorService(conn).delete("OP_CAL")
    finally:
        conn.close()
    html = _confirm_excel(
        client,
        "/personnel/excel/operator_calendar/confirm",
        "overwrite",
        "operator_calendar.xlsx",
        preview["raw_rows_json"],
        preview["preview_baseline"],
    )
    _assert_need_repreview("人员专属日历基线漂移", html)

    # 3) 批次：template_ops_snapshot 漂移
    preview = _preview_excel(
        client,
        "/scheduler/excel/batches/preview",
        "overwrite",
        ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
        [{"批次号": "B_ADV", "图号": "P_BATCH", "数量": 2, "交期": "2026-04-10", "优先级": "normal", "齐套": "yes", "齐套日期": None, "备注": "batch-drift"}],
        "batches.xlsx",
        extra={"auto_generate_ops": "1"},
    )
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE PartOperations SET setup_hours = ? WHERE part_no = ? AND seq = ?", (2.5, "P_BATCH", 5))
        conn.commit()
    finally:
        conn.close()
    html = _confirm_excel(
        client,
        "/scheduler/excel/batches/confirm",
        "overwrite",
        "batches.xlsx",
        preview["raw_rows_json"],
        preview["preview_baseline"],
        extra={"auto_generate_ops": "1"},
    )
    _assert_need_repreview("批次模板工序快照漂移", html)

    # 4) 工序工时：meta_rows.source 漂移
    preview = _preview_excel(
        client,
        "/process/excel/part-operation-hours/preview",
        "overwrite",
        ["图号", "工序", "换型时间(h)", "单件工时(h)"],
        [{"图号": "P_HOURS", "工序": 5, "换型时间(h)": 1.0, "单件工时(h)": 0.5}],
        "part_operation_hours.xlsx",
    )
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE PartOperations SET source = ? WHERE part_no = ? AND seq = ?", ("external", "P_HOURS", 5))
        conn.commit()
    finally:
        conn.close()
    html = _confirm_excel(
        client,
        "/process/excel/part-operation-hours/confirm",
        "overwrite",
        "part_operation_hours.xlsx",
        preview["raw_rows_json"],
        preview["preview_baseline"],
    )
    _assert_need_repreview("工序工时归属漂移", html)

    # 5) 设备：班组快照漂移
    preview = _preview_excel(
        client,
        "/equipment/excel/machines/preview",
        "overwrite",
        ["设备编号", "设备名称", "工种", "班组", "状态"],
        [{"设备编号": "MC_ADV", "设备名称": "测试设备", "工种": "机加工", "班组": "一班", "状态": "active"}],
        "machines.xlsx",
    )
    conn = get_connection(db_path)
    try:
        ResourceTeamService(conn).update("TM001", name="二班")
    finally:
        conn.close()
    html = _confirm_excel(
        client,
        "/equipment/excel/machines/confirm",
        "overwrite",
        "machines.xlsx",
        preview["raw_rows_json"],
        preview["preview_baseline"],
    )
    _assert_need_repreview("设备班组快照漂移", html)

    # 6) 供应商：工种快照漂移
    preview = _preview_excel(
        client,
        "/process/excel/suppliers/preview",
        "overwrite",
        ["供应商ID", "名称", "对应工种", "默认周期", "状态", "备注"],
        [{"供应商ID": "SUP_ADV", "名称": "供应商A", "对应工种": "外协工种", "默认周期": 3.0, "状态": "active", "备注": "supplier-drift"}],
        "suppliers.xlsx",
    )
    conn = get_connection(db_path)
    try:
        OpTypeService(conn).update("OT_SUP", name="改名工种")
    finally:
        conn.close()
    html = _confirm_excel(
        client,
        "/process/excel/suppliers/confirm",
        "overwrite",
        "suppliers.xlsx",
        preview["raw_rows_json"],
        preview["preview_baseline"],
    )
    _assert_need_repreview("供应商工种快照漂移", html)

    # 7) 人员设备关联：operator_ids/machine_ids 漂移
    preview = _preview_excel(
        client,
        "/personnel/excel/links/preview",
        "overwrite",
        ["工号", "设备编号", "技能等级", "主操设备"],
        [{"工号": "OP_LINK", "设备编号": "MC_LINK", "技能等级": "normal", "主操设备": "yes"}],
        "personnel_links.xlsx",
    )
    conn = get_connection(db_path)
    try:
        MachineService(conn).delete("MC_LINK")
    finally:
        conn.close()
    html = _confirm_excel(
        client,
        "/personnel/excel/links/confirm",
        "overwrite",
        "personnel_links.xlsx",
        preview["raw_rows_json"],
        preview["preview_baseline"],
    )
    _assert_need_repreview("人员设备关联主数据漂移", html)
