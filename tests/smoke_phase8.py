import io
import json
import os
import tempfile
import time
import traceback
from datetime import datetime


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
    lines.append("# Phase8（甘特图与周计划 / M4）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{os.sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录（自动识别）：`{repo_root}`")

    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase8_")
    test_db = os.path.join(tmpdir, "aps_phase8_test.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    lines.append("")
    lines.append("## 0. 测试环境")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")

    # 隔离：让 app.create_app() 读取测试 DB/目录
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    os.sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.scheduler import BatchService, CalendarService, ConfigService, ScheduleService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    op_logger = OperationLogger(conn, logger=None)

    try:
        # 1) 基础数据：工种/供应商/人员/设备/人机关联
        lines.append("")
        lines.append("## 1. 基础数据准备（资源 + 工艺模板）")
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN", "数铣", "internal"))
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX", "标印", "external"))
        conn.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
            ("S001", "外协-标印厂", "OT_EX", 1.0, "active"),
        )
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "CNC-01", "active"))
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC001"))

        # 2) 零件与模板：P_CAL 用于跨天；P_SIM 用于模拟不改状态
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_CAL", "周计划跨天件", "yes"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_SIM", "模拟件", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_CAL", 5, "OT_IN", "数铣", "internal", None, None, None, 0.0, 1.0, "active"),
        )
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_SIM", 5, "OT_IN", "数铣", "internal", None, None, None, 0.0, 4.0, "active"),
        )
        conn.commit()

        # 3) 创建批次并生成工序
        lines.append("")
        lines.append("## 2. 批次创建与工序补全")
        batch_svc = BatchService(conn, logger=None, op_logger=op_logger)
        sch_svc = ScheduleService(conn, logger=None, op_logger=op_logger)

        b_cal = batch_svc.create_batch_from_template(
            batch_id="B_CAL",
            part_no="P_CAL",
            quantity=3,  # 3h
            due_date="2026-01-22",  # 故意设置为会超期（排产结束在 01-23）
            priority="urgent",
            ready_status="yes",
        )
        b_sim = batch_svc.create_batch_from_template(
            batch_id="B_SIM",
            part_no="P_SIM",
            quantity=1,  # 4h
            due_date="2026-02-10",
            priority="normal",
            ready_status="yes",
        )
        lines.append(f"- 已创建批次：{b_cal.batch_id} / {b_sim.batch_id}")

        # 内部工序补全（人机匹配）
        def _set_internal(batch_id: str):
            ops = batch_svc.list_operations(batch_id)
            op_in = next(o for o in ops if o.source == "internal")
            sch_svc.update_internal_operation(
                op_in.id,
                machine_id="MC001",
                operator_id="OP001",
                setup_hours=op_in.setup_hours,
                unit_hours=op_in.unit_hours,
            )
            return op_in.op_code

        oc_cal = _set_internal("B_CAL")
        oc_sim = _set_internal("B_SIM")
        lines.append(f"- 内部工序已补全：{oc_cal} / {oc_sim}")

        # 4) 日历：短班次+停工，触发跨天（同 Phase7 口径）
        lines.append("")
        lines.append("## 3. 工作日历约束（用于跨天）")
        cal_svc = CalendarService(conn, logger=None, op_logger=op_logger)
        cal_svc.upsert("2026-01-21", day_type="workday", shift_hours=2, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="短班次")
        cal_svc.upsert("2026-01-22", day_type="holiday", shift_hours=0, efficiency=1.0, allow_normal="no", allow_urgent="no", remark="停工")
        lines.append("- 已配置：2026-01-21 2h；2026-01-22 停工")

        # 5) 执行一次正式排产（生成 version1）
        lines.append("")
        lines.append("## 4. 正式排产（生成版本，用于甘特图/周计划）")
        cfg_svc = ConfigService(conn, logger=None, op_logger=op_logger)
        cfg_svc.set_strategy("priority_first")
        r1 = sch_svc.run_schedule(batch_ids=["B_CAL"], start_dt="2026-01-21 08:00:00", created_by="smoke", simulate=False)
        v1 = int(r1["version"])
        lines.append(f"- 排产完成：version={v1} result_status={r1['result_status']} overdue_count={len(r1.get('overdue_batches') or [])}")
        if not any(x.get("batch_id") == "B_CAL" for x in (r1.get("overdue_batches") or [])):
            raise RuntimeError("超期预警未包含 B_CAL（期望超期）")

        # 6) Flask test_client（验证页面与接口）
        lines.append("")
        lines.append("## 5. Web 页面与接口（甘特图/周计划）")
        import importlib

        app_mod = importlib.import_module("app")
        test_app = app_mod.create_app()
        client = test_app.test_client()

        week_start = "2026-01-21"  # 任意日期（服务端会归到周一）

        _assert_status(lines, "GET /scheduler/gantt", client.get(f"/scheduler/gantt?view=machine&week_start={week_start}&version={v1}"), 200)
        gantt_t0 = time.perf_counter()
        resp = client.get(f"/scheduler/gantt/data?view=machine&week_start={week_start}&version={v1}")
        gantt_ms = int((time.perf_counter() - gantt_t0) * 1000)
        _assert_status(lines, "GET /scheduler/gantt/data", resp, 200)
        payload = json.loads(resp.data.decode("utf-8", errors="ignore") or "{}")
        if not payload.get("success"):
            raise RuntimeError(f"甘特图数据接口返回失败：{payload}")
        data = payload.get("data") or {}
        top_required = [
            "contract_version",
            "view",
            "version",
            "week_start",
            "week_end",
            "task_count",
            "tasks",
            "calendar_days",
            "critical_chain",
        ]
        for f in top_required:
            if f not in data:
                raise RuntimeError(f"甘特图返回缺少字段：{f}")
        if int(data.get("contract_version") or 0) < 2:
            raise RuntimeError(f"甘特图 contract_version 异常：{data.get('contract_version')}")

        tasks = data.get("tasks") or []
        if not isinstance(tasks, list) or not tasks:
            raise RuntimeError("甘特图 tasks 为空（期望至少 1 条）")
        req_fields = [
            "id",
            "name",
            "start",
            "end",
            "progress",
            "dependencies",
            "custom_class",
            "schedule_id",
            "lock_status",
            "duration_minutes",
            "edge_type",
        ]
        for f in req_fields:
            if f not in tasks[0]:
                raise RuntimeError(f"甘特图任务缺少字段：{f} task0={tasks[0]}")
        meta = tasks[0].get("meta") or {}
        for f in ("schedule_id", "lock_status", "duration_minutes"):
            if f not in meta:
                raise RuntimeError(f"甘特图任务 meta 缺少字段：{f} meta={meta}")

        cc = data.get("critical_chain") or {}
        for f in ("ids", "edges", "makespan_end", "edge_type_stats", "edge_count", "cache_hit"):
            if f not in cc:
                raise RuntimeError(f"critical_chain 缺少字段：{f}")
        edges = cc.get("edges") or []
        if edges:
            for f in ("from", "to", "edge_type", "reason", "gap_minutes"):
                if f not in edges[0]:
                    raise RuntimeError(f"critical_chain edge 缺少字段：{f}")

        # 二次请求应命中关键链缓存（同 version）
        gantt_t1 = time.perf_counter()
        resp2 = client.get(f"/scheduler/gantt/data?view=machine&week_start={week_start}&version={v1}")
        gantt_ms_2 = int((time.perf_counter() - gantt_t1) * 1000)
        _assert_status(lines, "GET /scheduler/gantt/data (2nd)", resp2, 200)
        payload2 = json.loads(resp2.data.decode("utf-8", errors="ignore") or "{}")
        if not payload2.get("success"):
            raise RuntimeError(f"甘特图二次请求失败：{payload2}")
        cc2 = ((payload2.get("data") or {}).get("critical_chain") or {})
        if cc2.get("cache_hit") is not True:
            raise RuntimeError(f"关键链缓存未命中：critical_chain={cc2}")

        if not any(("overdue" in (t.get("custom_class") or "")) for t in tasks):
            raise RuntimeError("甘特图任务未标记 overdue（期望至少 1 条含 overdue class）")
        lines.append(
            f"- 甘特图 tasks 校验：{len(tasks)} 条（契约字段齐全，含 overdue 标记，关键链缓存命中）"
        )
        lines.append(f"- 甘特图数据耗时：首次 {gantt_ms} ms，二次 {gantt_ms_2} ms")
        if gantt_ms > 8000:
            raise RuntimeError(f"甘特图接口耗时超门禁：{gantt_ms} ms（阈值 8000 ms）")

        _assert_status(lines, "GET /scheduler/week-plan", client.get(f"/scheduler/week-plan?week_start={week_start}&version={v1}"), 200)
        exp = client.get(f"/scheduler/week-plan/export?week_start={week_start}&version={v1}")
        _assert_xlsx(lines, "GET /scheduler/week-plan/export", exp)

        # 校验 xlsx 表头
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(exp.data), data_only=True)
        ws = wb.active
        headers = [ws.cell(row=1, column=i + 1).value for i in range(7)]
        expect_headers = ["日期", "批次号", "图号", "工序", "设备", "人员", "时段"]
        if headers != expect_headers:
            raise RuntimeError(f"周计划表表头不符合预期：got={headers} expect={expect_headers}")
        lines.append("- 周计划表.xlsx 表头校验：通过")

        # 导出留痕：OperationLogs action=export target_type=week_plan
        log_row = conn.execute(
            """
            SELECT id, detail
            FROM OperationLogs
            WHERE module='scheduler' AND action='export' AND target_type='week_plan'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if not log_row:
            raise RuntimeError("未找到周计划导出留痕（OperationLogs export/week_plan）")
        detail = _parse_detail_json(log_row["detail"])
        export_keys = ["template_or_export_type", "filters", "row_count", "time_range", "time_cost_ms"]
        _require_keys(detail, export_keys, "周计划导出留痕")
        tr = detail.get("time_range") or {}
        if "start" not in tr or "end" not in tr:
            raise RuntimeError(f"周计划导出留痕 time_range 缺少 start/end：{tr}")
        lines.append(f"- 周计划导出留痕：通过（log_id={log_row['id']}）")

        # 7) 模拟排产：不更新批次/工序状态
        lines.append("")
        lines.append("## 6. 插单模拟：新版本 + 不更新状态")
        before_batch = conn.execute("SELECT status FROM Batches WHERE batch_id='B_SIM'").fetchone()["status"]
        before_op = conn.execute(
            "SELECT status FROM BatchOperations WHERE op_code=?",
            (oc_sim,),
        ).fetchone()["status"]
        r2 = sch_svc.run_schedule(batch_ids=["B_SIM"], start_dt="2026-02-02 08:00:00", created_by="smoke", simulate=True)
        v2 = int(r2["version"])
        if r2.get("result_status") != "simulated":
            raise RuntimeError(f"模拟排产 result_status 异常：{r2.get('result_status')}")
        after_batch = conn.execute("SELECT status FROM Batches WHERE batch_id='B_SIM'").fetchone()["status"]
        after_op = conn.execute("SELECT status FROM BatchOperations WHERE op_code=?", (oc_sim,)).fetchone()["status"]
        if before_batch != after_batch or before_op != after_op:
            raise RuntimeError(f"模拟排产不应更新状态：before=({before_batch},{before_op}) after=({after_batch},{after_op})")

        hist_row = conn.execute("SELECT result_status FROM ScheduleHistory WHERE version=?", (v2,)).fetchone()
        if not hist_row or hist_row["result_status"] != "simulated":
            raise RuntimeError("ScheduleHistory 未记录 simulated 状态")

        sim_log = conn.execute(
            """
            SELECT id, action, detail
            FROM OperationLogs
            WHERE module='scheduler' AND action='simulate'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if not sim_log:
            raise RuntimeError("OperationLogs 未写入 simulate 留痕")
        sim_detail = _parse_detail_json(sim_log["detail"])
        _require_keys(sim_detail, ["version", "strategy", "batch_ids", "time_cost_ms", "result_status"], "模拟排产留痕")
        lines.append(f"- 模拟排产校验：通过（version={v2}；状态未变化；simulate 留痕存在）")

        # 成功结论
        lines.append("")
        lines.append("## 结论")
        lines.append("- 通过：Phase8（甘特图与周计划 / M4）冒烟测试通过（甘特图数据/周计划导出与留痕/插单模拟可追溯）。")
        lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    report_path = os.path.join(repo_root, "evidence", "Phase8", "smoke_phase8_report.md")
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
        lines.append("# Phase8（甘特图与周计划 / M4）冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase8", "smoke_phase8_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

