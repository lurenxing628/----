import io
import os
import re
import sys
import tempfile
from html import unescape


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None

    ws.title = "Sheet1"
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
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
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:400]}")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_preview_confirm_baseline_")
    test_db = os.path.join(tmpdir, "aps_test.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(test_db)
    try:
        # 批次导入前置：图号必须存在
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw) VALUES (?, ?, ?)",
            ("A1234", "测试零件", "5数车"),
        )
        # 人员日历导入前置：工号必须存在
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)",
            ("OP001", "测试员工", "active"),
        )
        conn.commit()
    finally:
        conn.close()

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    # ---------------------------------------------------------
    # 1) 批次：preview 后并发写同主键，confirm 应拒绝并提示重新预览
    # ---------------------------------------------------------
    batch_rows = [
        {
            "批次号": "B_CONC",
            "图号": "A1234",
            "数量": 1,
            "交期": "2026-03-01",
            "优先级": "normal",
            "齐套": "yes",
            "齐套日期": None,
            "备注": "baseline-guard",
        }
    ]
    batch_buf = _make_xlsx_bytes(["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"], batch_rows)
    resp = client.post(
        "/scheduler/excel/batches/preview",
        data={"mode": "append", "file": (batch_buf, "batches.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("batches preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    raw_rows_json = _extract_raw_rows_json(html)
    preview_baseline = _extract_hidden_input(html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError("批次预览未生成 preview_baseline")

    from core.services.scheduler import BatchService

    conn = get_connection(test_db)
    try:
        BatchService(conn).create(
            batch_id="B_CONC",
            part_no="A1234",
            quantity=1,
            due_date="2026-03-01",
            priority="normal",
            ready_status="yes",
            remark="concurrent-write",
        )
    finally:
        conn.close()

    resp2 = client.post(
        "/scheduler/excel/batches/confirm",
        data={
            "mode": "append",
            "filename": "batches.xlsx",
            "raw_rows_json": raw_rows_json,
            "preview_baseline": preview_baseline,
        },
        follow_redirects=True,
    )
    _assert_status("batches confirm", resp2, 200)
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if "需重新预览" not in html2:
        raise RuntimeError("批次确认未提示“需重新预览”")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM Batches WHERE batch_id=?", ("B_CONC",)).fetchone()[0]
        if int(cnt) != 1:
            raise RuntimeError(f"批次并发保护后数量异常：{cnt}")
    finally:
        conn.close()

    # ---------------------------------------------------------
    # 2) 人员日历：preview 后并发写同主键，confirm 应拒绝并提示重新预览
    # ---------------------------------------------------------
    cal_rows = [
        {
            "工号": "OP001",
            "日期": "2026-03-02",
            "类型": "workday",
            "班次开始": "08:00",
            "班次结束": "16:00",
            "可用工时": 8,
            "效率": 1.0,
            "允许普通件": "yes",
            "允许急件": "yes",
            "说明": "baseline-guard",
        }
    ]
    cal_buf = _make_xlsx_bytes(
        ["工号", "日期", "类型", "班次开始", "班次结束", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
        cal_rows,
    )
    resp3 = client.post(
        "/personnel/excel/operator_calendar/preview",
        data={"mode": "append", "file": (cal_buf, "calendar.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("operator_calendar preview", resp3, 200)
    html3 = resp3.data.decode("utf-8", errors="ignore")
    raw_rows_json3 = _extract_raw_rows_json(html3)
    preview_baseline3 = _extract_hidden_input(html3, "preview_baseline")
    if not preview_baseline3:
        raise RuntimeError("人员日历预览未生成 preview_baseline")

    from core.services.scheduler import CalendarService

    conn = get_connection(test_db)
    try:
        CalendarService(conn).upsert_operator_calendar(
            operator_id="OP001",
            date_value="2026-03-02",
            day_type="workday",
            shift_hours=8,
            shift_start="08:00",
            shift_end="16:00",
            efficiency=1.0,
            allow_normal="yes",
            allow_urgent="yes",
            remark="concurrent-write",
        )
    finally:
        conn.close()

    resp4 = client.post(
        "/personnel/excel/operator_calendar/confirm",
        data={
            "mode": "append",
            "filename": "calendar.xlsx",
            "raw_rows_json": raw_rows_json3,
            "preview_baseline": preview_baseline3,
        },
        follow_redirects=True,
    )
    _assert_status("operator_calendar confirm", resp4, 200)
    html4 = resp4.data.decode("utf-8", errors="ignore")
    if "需重新预览" not in html4:
        raise RuntimeError("人员日历确认未提示“需重新预览”")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute(
            "SELECT COUNT(1) FROM OperatorCalendar WHERE operator_id=? AND date=?",
            ("OP001", "2026-03-02"),
        ).fetchone()[0]
        if int(cnt) != 1:
            raise RuntimeError(f"人员日历并发保护后数量异常：{cnt}")
    finally:
        conn.close()

    # ---------------------------------------------------------
    # 3) 工作日历：preview 后并发写同主键，confirm 应拒绝并提示重新预览
    # ---------------------------------------------------------
    global_cal_rows = [
        {
            "日期": "2026-03-03",
            "类型": "workday",
            "可用工时": 8,
            "效率": 1.0,
            "允许普通件": "yes",
            "允许急件": "yes",
            "说明": "baseline-guard",
        }
    ]
    global_cal_buf = _make_xlsx_bytes(
        ["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
        global_cal_rows,
    )
    resp5 = client.post(
        "/scheduler/excel/calendar/preview",
        data={"mode": "append", "file": (global_cal_buf, "global_calendar.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("calendar preview", resp5, 200)
    html5 = resp5.data.decode("utf-8", errors="ignore")
    raw_rows_json5 = _extract_raw_rows_json(html5)
    preview_baseline5 = _extract_hidden_input(html5, "preview_baseline")
    if not preview_baseline5:
        raise RuntimeError("工作日历预览未生成 preview_baseline")

    conn = get_connection(test_db)
    try:
        from core.services.scheduler import CalendarService

        CalendarService(conn).upsert_no_tx(
            {
                "date": "2026-03-03",
                "day_type": "workday",
                "shift_hours": 8,
                "efficiency": 1.0,
                "allow_normal": "yes",
                "allow_urgent": "yes",
                "remark": "concurrent-write",
            }
        )
        conn.commit()
    finally:
        conn.close()

    resp6 = client.post(
        "/scheduler/excel/calendar/confirm",
        data={
            "mode": "append",
            "filename": "global_calendar.xlsx",
            "raw_rows_json": raw_rows_json5,
            "preview_baseline": preview_baseline5,
        },
        follow_redirects=True,
    )
    _assert_status("calendar confirm", resp6, 200)
    html6 = resp6.data.decode("utf-8", errors="ignore")
    if "需重新预览" not in html6:
        raise RuntimeError("工作日历确认未提示“需重新预览”")

    # ---------------------------------------------------------
    # 4) 设备信息：preview 后并发写同主键，confirm 应拒绝并提示重新预览
    # ---------------------------------------------------------
    machine_rows = [
        {
            "设备编号": "MC_CONC",
            "设备名称": "测试设备",
            "工种": None,
            "班组": None,
            "状态": "active",
        }
    ]
    machine_buf = _make_xlsx_bytes(["设备编号", "设备名称", "工种", "班组", "状态"], machine_rows)
    resp7 = client.post(
        "/equipment/excel/machines/preview",
        data={"mode": "append", "file": (machine_buf, "machines.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("machines preview", resp7, 200)
    html7 = resp7.data.decode("utf-8", errors="ignore")
    raw_rows_json7 = _extract_raw_rows_json(html7)
    preview_baseline7 = _extract_hidden_input(html7, "preview_baseline")
    if not preview_baseline7:
        raise RuntimeError("设备预览未生成 preview_baseline")

    conn = get_connection(test_db)
    try:
        from core.services.equipment.machine_service import MachineService

        MachineService(conn).create(machine_id="MC_CONC", name="并发设备", status="active")
    finally:
        conn.close()

    resp8 = client.post(
        "/equipment/excel/machines/confirm",
        data={
            "mode": "append",
            "filename": "machines.xlsx",
            "raw_rows_json": raw_rows_json7,
            "preview_baseline": preview_baseline7,
        },
        follow_redirects=True,
    )
    _assert_status("machines confirm", resp8, 200)
    html8 = resp8.data.decode("utf-8", errors="ignore")
    if "需重新预览" not in html8:
        raise RuntimeError("设备确认未提示“需重新预览”")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM Machines WHERE machine_id=?", ("MC_CONC",)).fetchone()[0]
        if int(cnt) != 1:
            raise RuntimeError(f"设备并发保护后数量异常：{cnt}")
    finally:
        conn.close()

    # ---------------------------------------------------------
    # 5) 设备人员关联：preview 后并发写同主键，confirm 应拒绝并提示重新预览
    # ---------------------------------------------------------
    conn = get_connection(test_db)
    try:
        from core.services.equipment.machine_service import MachineService

        if conn.execute("SELECT COUNT(1) FROM Machines WHERE machine_id=?", ("MC_LINK",)).fetchone()[0] == 0:
            MachineService(conn).create(machine_id="MC_LINK", name="关联设备", status="active")
    finally:
        conn.close()

    link_rows = [
        {
            "设备编号": "MC_LINK",
            "工号": "OP001",
            "技能等级": "normal",
            "主操设备": "yes",
        }
    ]
    link_buf = _make_xlsx_bytes(["设备编号", "工号", "技能等级", "主操设备"], link_rows)
    resp9 = client.post(
        "/equipment/excel/links/preview",
        data={"mode": "append", "file": (link_buf, "links.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("equipment links preview", resp9, 200)
    html9 = resp9.data.decode("utf-8", errors="ignore")
    raw_rows_json9 = _extract_raw_rows_json(html9)
    preview_baseline9 = _extract_hidden_input(html9, "preview_baseline")
    if not preview_baseline9:
        raise RuntimeError("设备人员关联预览未生成 preview_baseline")

    conn = get_connection(test_db)
    try:
        from core.services.personnel import OperatorMachineService

        OperatorMachineService(conn).add_link("OP001", "MC_LINK", skill_level="normal", is_primary="yes")
    finally:
        conn.close()

    resp10 = client.post(
        "/equipment/excel/links/confirm",
        data={
            "mode": "append",
            "filename": "links.xlsx",
            "raw_rows_json": raw_rows_json9,
            "preview_baseline": preview_baseline9,
        },
        follow_redirects=True,
    )
    _assert_status("equipment links confirm", resp10, 200)
    html10 = resp10.data.decode("utf-8", errors="ignore")
    if "需重新预览" not in html10:
        raise RuntimeError("设备人员关联确认未提示“需重新预览”")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute(
            "SELECT COUNT(1) FROM OperatorMachine WHERE operator_id=? AND machine_id=?",
            ("OP001", "MC_LINK"),
        ).fetchone()[0]
        if int(cnt) != 1:
            raise RuntimeError(f"设备人员关联并发保护后数量异常：{cnt}")
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
