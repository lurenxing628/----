import io
import json
import os
import re
import sys
import tempfile
import time
import traceback

from excel_preview_confirm_helpers import build_confirm_payload


def find_repo_root():
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    兼容不同目录结构：优先 tests/ 上一级，其次扫描 D:\\Github 下子目录。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root

    base = r"D:\Github"
    try:
        if os.path.isdir(base):
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if not os.path.isdir(p):
                    continue
                if os.path.exists(os.path.join(p, "app.py")) and os.path.exists(os.path.join(p, "schema.sql")):
                    return p
    except Exception:
        pass

    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def write_report(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


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
        raise RuntimeError("未能从预览页面提取 raw_rows_json（确认导入需要该字段）")
    raw = m.group(1)
    raw = raw.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    return raw.strip()


def _assert_status(lines, name: str, resp, expect_code: int = 200):
    lines.append(f"- {name}：{resp.status_code}")
    if resp.status_code != expect_code:
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}")


def _assert_xlsx(lines, name: str, resp):
    ct = resp.headers.get("Content-Type", "")
    lines.append(f"- {name}：{resp.status_code} content-type={ct}")
    if resp.status_code != 200:
        raise RuntimeError(f"{name} 返回非 200")
    if "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in ct:
        raise RuntimeError(f"{name} content-type 异常：{ct}")


def _query_recent_logs(conn, module: str, action: str, target_type: str, limit: int = 10):
    rows = conn.execute(
        """
        SELECT id, log_time, log_level, module, action, target_type, target_id, detail
        FROM OperationLogs
        WHERE module=? AND action=? AND target_type=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (module, action, target_type, limit),
    ).fetchall()
    return rows


def _parse_detail_json(detail: str) -> dict:
    try:
        return json.loads(detail) if detail else {}
    except Exception as e:
        raise RuntimeError(f"OperationLogs.detail 不是有效 JSON：{e} detail={detail!r}")


def _require_keys(d: dict, keys, context: str):
    missing = [k for k in keys if k not in d]
    if missing:
        raise RuntimeError(f"{context} 缺少键：{missing}（detail={d}）")


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase0~Phase6 Web + Excel 端到端冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    # 临时目录（避免污染真实 db/logs/backups/templates_excel）
    tmpdir = tempfile.mkdtemp(prefix="aps_web_smoke_p6_")
    test_db = os.path.join(tmpdir, "aps_web_smoke_p6.db")
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

    sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    # 预置 Phase6 所需数据：零件+模板工序+供应商
    conn = get_connection(test_db)
    try:
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_1", "数铣", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_1", "标印", "external"))
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            ("S001", "外协-标印厂", "OT_EX_1", 1.0, "active"),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("A1234", "壳体-大", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("A1234", 5, "OT_IN_1", "数铣", "internal", None, None, None, 0.5, 0.2, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("A1234", 35, "OT_EX_1", "标印", "external", "S001", 1.0, None, 0, 0, "active"),
        )
        conn.commit()
    finally:
        conn.close()

    # Flask test_client（不启动 server）
    import importlib

    app_mod = importlib.import_module("app")
    test_app = app_mod.create_app()
    client = test_app.test_client()

    lines.append("")
    lines.append("## 1. 基础页面可用性（含 Scheduler）")
    _assert_status(lines, "GET /", client.get("/"), 200)
    _assert_status(lines, "GET /personnel/", client.get("/personnel/"), 200)
    _assert_status(lines, "GET /equipment/", client.get("/equipment/"), 200)
    _assert_status(lines, "GET /process/", client.get("/process/"), 200)
    _assert_status(lines, "GET /scheduler/", client.get("/scheduler/"), 200)
    _assert_status(lines, "GET /scheduler/calendar", client.get("/scheduler/calendar"), 200)

    # =====================
    lines.append("")
    lines.append("## 1.X 设备管理：停机计划（设备详情页展示 + 提交新增）")
    # 准备一个设备（直接写库，避免依赖 Excel 链路）
    conn = get_connection(test_db)
    try:
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC_D1", "测试设备-停机", "active"))
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/equipment/MC_D1")
    _assert_status(lines, "GET /equipment/MC_D1", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    if "停机计划" not in html:
        raise RuntimeError("设备详情页未展示“停机计划”区块")

    resp2 = client.post(
        "/equipment/MC_D1/downtimes/create",
        data={"start_time": "2026-01-22 08:00", "end_time": "2026-01-22 12:00", "reason_code": "maintenance", "reason_detail": "测试"},
        follow_redirects=True,
    )
    _assert_status(lines, "POST /equipment/MC_D1/downtimes/create", resp2, 200)
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if "已新增停机计划" not in html2:
        raise RuntimeError("提交新增停机计划后未看到成功提示")
    if "2026-01-22" not in html2:
        raise RuntimeError("新增停机计划后页面未回显时间段")

    import_keys = [
        "filename",
        "mode",
        "time_cost_ms",
        "total_rows",
        "new_count",
        "update_count",
        "skip_count",
        "error_count",
        "errors_sample",
    ]
    export_keys = ["template_or_export_type", "filters", "row_count", "time_range", "time_cost_ms"]

    # =====================
    # 2) Scheduler: Batches Excel
    # =====================
    lines.append("")
    lines.append("## 2. 排产调度：批次信息 Excel（上传→预览→确认→导出）")
    _assert_xlsx(lines, "GET /scheduler/excel/batches/template", client.get("/scheduler/excel/batches/template"))

    batch_rows = [
        {"批次号": "B001", "图号": "A1234", "数量": 50, "交期": "2026-01-25", "优先级": "urgent", "齐套": "yes", "备注": "web_smoke"},
        {"批次号": "B_BAD", "图号": "", "数量": 1, "交期": None, "优先级": "normal", "齐套": "no", "备注": None},  # ERROR：图号为空
    ]
    buf = _make_xlsx_bytes(["批次号", "图号", "数量", "交期", "优先级", "齐套", "备注"], batch_rows)
    resp = client.post(
        "/scheduler/excel/batches/preview",
        data={"mode": "overwrite", "file": (buf, "batches.xlsx"), "auto_generate_ops": "1"},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /scheduler/excel/batches/preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    if "导入预览" not in html and "预览" not in html:
        raise RuntimeError("批次 Excel 预览页面未包含预览内容")
    resp2 = client.post(
        "/scheduler/excel/batches/confirm",
        data=build_confirm_payload(
            html,
            mode="overwrite",
            filename="batches.xlsx",
            context="/scheduler/excel/batches/preview",
            confirm_hidden_fields=["auto_generate_ops"],
        ),
        follow_redirects=True,
    )
    _assert_status(lines, "POST /scheduler/excel/batches/confirm", resp2, 200)

    # 严格模式：存在错误行时，确认导入应被拒绝（不写入任何批次）
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in html2:
        raise RuntimeError("批次 Excel 确认导入未按严格模式拒绝（期望出现“导入被拒绝”提示）")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM Batches WHERE batch_id='B001'").fetchone()[0]
        op_cnt = conn.execute("SELECT COUNT(1) FROM BatchOperations WHERE batch_id='B001'").fetchone()[0]
        lines.append(f"- 严格拒绝校验：B001 batch_cnt={cnt} ops_cnt={op_cnt}（期望 batch_cnt=0 ops_cnt=0）")
        if cnt != 0 or op_cnt != 0:
            raise RuntimeError("严格拒绝失败：存在错误行时仍写入了 Batches/BatchOperations")
    finally:
        conn.close()

    # 再用“全合法”数据导入一次，应成功写入并自动生成工序
    batch_rows_ok = [
        {"批次号": "B001", "图号": "A1234", "数量": 50, "交期": "2026-01-25", "优先级": "urgent", "齐套": "yes", "备注": "web_smoke"},
    ]
    buf_ok = _make_xlsx_bytes(["批次号", "图号", "数量", "交期", "优先级", "齐套", "备注"], batch_rows_ok)
    resp_ok = client.post(
        "/scheduler/excel/batches/preview",
        data={"mode": "overwrite", "file": (buf_ok, "batches_ok.xlsx"), "auto_generate_ops": "1"},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /scheduler/excel/batches/preview（valid）", resp_ok, 200)
    html_ok = resp_ok.data.decode("utf-8", errors="ignore")
    resp_ok2 = client.post(
        "/scheduler/excel/batches/confirm",
        data=build_confirm_payload(
            html_ok,
            mode="overwrite",
            filename="batches_ok.xlsx",
            context="/scheduler/excel/batches/preview（valid）",
            confirm_hidden_fields=["auto_generate_ops"],
        ),
        follow_redirects=True,
    )
    _assert_status(lines, "POST /scheduler/excel/batches/confirm（valid）", resp_ok2, 200)

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM Batches WHERE batch_id='B001'").fetchone()[0]
        op_cnt = conn.execute("SELECT COUNT(1) FROM BatchOperations WHERE batch_id='B001'").fetchone()[0]
        lines.append(f"- Batches/BatchOperations 写入校验：B001 batch_cnt={cnt} ops_cnt={op_cnt}（期望 batch_cnt=1 ops_cnt>=1）")
        if cnt != 1 or op_cnt < 1:
            raise RuntimeError("批次导入或自动生成工序失败（未写入 Batches/BatchOperations）")

        logs = _query_recent_logs(conn, module="scheduler", action="import", target_type="batch", limit=10)
        lines.append(f"- OperationLogs 校验（scheduler/import/batch）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("批次导入留痕缺失（OperationLogs scheduler/import/batch）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, import_keys, "批次导入留痕(detail)")
    finally:
        conn.close()

    _assert_xlsx(lines, "GET /scheduler/excel/batches/export", client.get("/scheduler/excel/batches/export"))
    conn = get_connection(test_db)
    try:
        logs = _query_recent_logs(conn, module="scheduler", action="export", target_type="batch", limit=5)
        lines.append(f"- OperationLogs 校验（scheduler/export/batch）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("批次导出留痕缺失（OperationLogs scheduler/export/batch）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, export_keys, "批次导出留痕(detail)")
    finally:
        conn.close()

    # =====================
    # 2.X) Scheduler: 批次工序补充（人机匹配约束）
    # =====================
    lines.append("")
    lines.append("## 2.X 排产调度：批次工序补充（人机匹配约束）")
    conn = get_connection(test_db)
    try:
        # 准备资源与关联：OP001 只能操作 MC001
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "CNC-01", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC003", "CNC-03", "active"))
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC001"))
        conn.commit()

        row = conn.execute(
            "SELECT id, op_code FROM BatchOperations WHERE batch_id=? AND source='internal' ORDER BY id LIMIT 1",
            ("B001",),
        ).fetchone()
        if not row:
            raise RuntimeError("未找到 B001 的内部工序（BatchOperations.source='internal'）")
        op_id = int(row["id"])
        op_code = row["op_code"]
        lines.append(f"- 目标内部工序：id={op_id} op_code={op_code}")
    finally:
        conn.close()

    # 页面可访问
    _assert_status(lines, "GET /scheduler/batches/B001", client.get("/scheduler/batches/B001"), 200)

    # 不匹配组合：应报中文错误且包含工号/设备编号
    resp_bad = client.post(
        f"/scheduler/ops/{op_id}/update",
        data={"machine_id": "MC003", "operator_id": "OP001", "setup_hours": "0.5", "unit_hours": "0.2"},
        follow_redirects=False,
    )
    _assert_status(lines, f"POST /scheduler/ops/{op_id}/update（不匹配应拒绝）", resp_bad, 400)
    html_bad = resp_bad.data.decode("utf-8", errors="ignore")
    if "未被配置为可操作设备" not in html_bad or "MC003" not in html_bad or "OP001" not in html_bad:
        raise RuntimeError("人机不匹配错误提示不够明确（期望包含中文提示 + 设备编号/工号）")

    # 匹配组合：应可保存（返回批次详情页）
    resp_ok = client.post(
        f"/scheduler/ops/{op_id}/update",
        data={"machine_id": "MC001", "operator_id": "OP001", "setup_hours": "0.5", "unit_hours": "0.2"},
        follow_redirects=True,
    )
    _assert_status(lines, f"POST /scheduler/ops/{op_id}/update（匹配应成功）", resp_ok, 200)

    # =====================
    # 3) Scheduler: WorkCalendar Excel
    # =====================
    lines.append("")
    lines.append("## 3. 排产调度：工作日历 Excel（上传→预览→确认→导出）")
    _assert_xlsx(lines, "GET /scheduler/excel/calendar/template", client.get("/scheduler/excel/calendar/template"))

    cal_rows = [
        {"日期": "2026-01-21", "类型": "workday", "可用工时": 8, "效率": 1.0, "允许普通件": "yes", "允许急件": "yes", "说明": "web_smoke"},
        {"日期": "", "类型": "workday", "可用工时": 8, "效率": 1.0, "允许普通件": "yes", "允许急件": "yes", "说明": None},  # ERROR：日期为空
    ]
    buf = _make_xlsx_bytes(["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"], cal_rows)
    resp = client.post(
        "/scheduler/excel/calendar/preview",
        data={"mode": "overwrite", "file": (buf, "calendar.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /scheduler/excel/calendar/preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    resp2 = client.post(
        "/scheduler/excel/calendar/confirm",
        data=build_confirm_payload(
            html,
            mode="overwrite",
            filename="calendar.xlsx",
            context="/scheduler/excel/calendar/preview",
        ),
        follow_redirects=True,
    )
    _assert_status(lines, "POST /scheduler/excel/calendar/confirm", resp2, 200)

    # 严格模式：存在错误行时，确认导入应被拒绝（不写入任何日历）
    html2 = resp2.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in html2:
        raise RuntimeError("工作日历 Excel 确认导入未按严格模式拒绝（期望出现“导入被拒绝”提示）")

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM WorkCalendar WHERE date='2026-01-21'").fetchone()[0]
        lines.append(f"- 严格拒绝校验：2026-01-21 行数={cnt}（期望 0）")
        if cnt != 0:
            raise RuntimeError("严格拒绝失败：存在错误行时仍写入了 WorkCalendar 表")
    finally:
        conn.close()

    # 再用“全合法”数据导入一次，应成功写入
    cal_rows_ok = [
        {"日期": "2026-01-21", "类型": "workday", "可用工时": 8, "效率": 1.0, "允许普通件": "yes", "允许急件": "yes", "说明": "web_smoke"},
    ]
    buf_ok = _make_xlsx_bytes(["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"], cal_rows_ok)
    resp_ok = client.post(
        "/scheduler/excel/calendar/preview",
        data={"mode": "overwrite", "file": (buf_ok, "calendar_ok.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status(lines, "POST /scheduler/excel/calendar/preview（valid）", resp_ok, 200)
    html_ok = resp_ok.data.decode("utf-8", errors="ignore")
    resp_ok2 = client.post(
        "/scheduler/excel/calendar/confirm",
        data=build_confirm_payload(
            html_ok,
            mode="overwrite",
            filename="calendar_ok.xlsx",
            context="/scheduler/excel/calendar/preview（valid）",
        ),
        follow_redirects=True,
    )
    _assert_status(lines, "POST /scheduler/excel/calendar/confirm（valid）", resp_ok2, 200)

    conn = get_connection(test_db)
    try:
        cnt = conn.execute("SELECT COUNT(1) FROM WorkCalendar WHERE date='2026-01-21'").fetchone()[0]
        lines.append(f"- WorkCalendar 写入校验：2026-01-21 行数={cnt}（期望 1）")
        if cnt != 1:
            raise RuntimeError("日历确认导入未写入 WorkCalendar 表")

        logs = _query_recent_logs(conn, module="scheduler", action="import", target_type="calendar", limit=10)
        lines.append(f"- OperationLogs 校验（scheduler/import/calendar）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("日历导入留痕缺失（OperationLogs scheduler/import/calendar）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, import_keys, "日历导入留痕(detail)")
    finally:
        conn.close()

    _assert_xlsx(lines, "GET /scheduler/excel/calendar/export", client.get("/scheduler/excel/calendar/export"))
    conn = get_connection(test_db)
    try:
        logs = _query_recent_logs(conn, module="scheduler", action="export", target_type="calendar", limit=5)
        lines.append(f"- OperationLogs 校验（scheduler/export/calendar）：{len(logs)} 条（期望 >= 1）")
        if len(logs) < 1:
            raise RuntimeError("日历导出留痕缺失（OperationLogs scheduler/export/calendar）")
        d = _parse_detail_json(logs[0]["detail"])
        _require_keys(d, export_keys, "日历导出留痕(detail)")
    finally:
        conn.close()

    lines.append("")
    lines.append("## 结论")
    lines.append("- 通过：Phase0~Phase6 Web+Excel 关键链路端到端冒烟测试通过（含 Scheduler）。")
    lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    report_path = os.path.join(repo_root, "evidence", "Phase0_to_Phase6", "web_smoke_report.md")
    write_report(report_path, lines)
    print("OK")
    print(report_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        repo_root = None
        try:
            repo_root = find_repo_root()
        except Exception:
            pass

        lines = []
        lines.append("# Phase0~Phase6 Web + Excel 端到端冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase0_to_Phase6", "web_smoke_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

