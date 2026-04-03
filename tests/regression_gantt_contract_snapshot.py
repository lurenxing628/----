from __future__ import annotations

import json
import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_reg_gantt_contract_")
    test_db = os.path.join(root, "aps_test.db")
    test_logs = os.path.join(root, "logs")
    test_backups = os.path.join(root, "backups")
    test_templates = os.path.join(root, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.scheduler import BatchService, ConfigService, ScheduleService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    op_logger = OperationLogger(conn, logger=None)
    try:
        conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN", "数铣", "internal"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "CNC-01", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC001"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_GANTT", "甘特契约件", "yes"))
        conn.execute(
            """
            INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("P_GANTT", 5, "OT_IN", "数铣", "internal", 0.0, 1.0, "active"),
        )
        conn.commit()

        batch_svc = BatchService(conn, logger=None, op_logger=op_logger)
        sch_svc = ScheduleService(conn, logger=None, op_logger=op_logger)
        cfg_svc = ConfigService(conn, logger=None, op_logger=op_logger)
        cfg_svc.set_strategy("priority_first")
        batch_svc.create_batch_from_template(
            batch_id="B_GANTT",
            part_no="P_GANTT",
            quantity=1,
            due_date="2099-12-31",
            priority="normal",
            ready_status="yes",
        )
        op = batch_svc.list_operations("B_GANTT")[0]
        sch_svc.update_internal_operation(op.id, machine_id="MC001", operator_id="OP001", setup_hours=0.0, unit_hours=1.0)
        run_ret = sch_svc.run_schedule(batch_ids=["B_GANTT"], start_dt="2026-03-02 08:00:00", created_by="reg")
        version = int(run_ret["version"])
    finally:
        conn.close()

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    # 1) 默认契约（history 不下发）
    resp = client.get(f"/scheduler/gantt/data?view=machine&week_start=2026-03-02&version={version}")
    _assert_status(resp, "GET /scheduler/gantt/data")
    payload = json.loads(resp.data.decode("utf-8", errors="ignore") or "{}")
    if payload.get("success") is not True:
        raise RuntimeError(f"甘特图接口失败：{payload}")
    data = payload.get("data") or {}

    required_top_keys = {
        "contract_version",
        "view",
        "version",
        "week_start",
        "week_end",
        "task_count",
        "tasks",
        "calendar_days",
        "critical_chain",
        "overdue_markers_degraded",
        "overdue_markers_partial",
        "overdue_markers_message",
    }
    missing_top = sorted(required_top_keys - set(data.keys()))
    if missing_top:
        raise RuntimeError(f"甘特契约缺少顶层字段：{missing_top}")
    if "history" in data:
        raise RuntimeError("默认契约不应包含 history（应按需下发）")

    tasks = data.get("tasks") or []
    if not tasks:
        raise RuntimeError("tasks 为空，无法验证契约")
    if int(data.get("task_count") or 0) != len(tasks):
        raise RuntimeError(f"task_count 与 tasks 数量不一致：{data.get('task_count')} vs {len(tasks)}")

    t0 = tasks[0]
    for k in ("schedule_id", "lock_status", "duration_minutes", "edge_type", "meta"):
        if k not in t0:
            raise RuntimeError(f"task 缺少字段：{k}")
    meta = t0.get("meta") or {}
    for k in ("schedule_id", "lock_status", "duration_minutes"):
        if k not in meta:
            raise RuntimeError(f"task.meta 缺少字段：{k}")

    cc = data.get("critical_chain") or {}
    for k in ("ids", "edges", "makespan_end", "edge_type_stats", "edge_count", "cache_hit"):
        if k not in cc:
            raise RuntimeError(f"critical_chain 缺少字段：{k}")
    edges = cc.get("edges") or []
    if edges:
        for k in ("from", "to", "edge_type", "reason", "gap_minutes"):
            if k not in edges[0]:
                raise RuntimeError(f"critical_chain.edges[0] 缺少字段：{k}")

    # 2) include_history=1 时应包含 history
    resp_hist = client.get(f"/scheduler/gantt/data?view=machine&week_start=2026-03-02&version={version}&include_history=1")
    _assert_status(resp_hist, "GET /scheduler/gantt/data?include_history=1")
    payload_hist = json.loads(resp_hist.data.decode("utf-8", errors="ignore") or "{}")
    data_hist = (payload_hist.get("data") or {}) if payload_hist.get("success") else {}
    if "history" not in data_hist:
        raise RuntimeError("include_history=1 时未返回 history")

    # 3) 空数据版本也应返回完整 critical_chain；include_history=1 且无历史时应返回 history=null
    empty_version = int(version) + 99999
    resp_empty = client.get(f"/scheduler/gantt/data?view=machine&week_start=2026-03-02&version={empty_version}")
    _assert_status(resp_empty, "GET /scheduler/gantt/data?empty_version")
    payload_empty = json.loads(resp_empty.data.decode("utf-8", errors="ignore") or "{}")
    if payload_empty.get("success") is not True:
        raise RuntimeError(f"空数据版本甘特图接口失败：{payload_empty}")
    data_empty = payload_empty.get("data") or {}
    if int(data_empty.get("task_count") or 0) != 0 or (data_empty.get("tasks") or []):
        raise RuntimeError(f"空数据版本 tasks 应为空：task_count={data_empty.get('task_count')} tasks={data_empty.get('tasks')}")
    cc_empty = data_empty.get("critical_chain") or {}
    for k in ("ids", "edges", "makespan_end", "edge_type_stats", "edge_count", "cache_hit"):
        if k not in cc_empty:
            raise RuntimeError(f"空数据版本 critical_chain 缺少字段：{k}")
    raw_edge_count = cc_empty.get("edge_count")
    if raw_edge_count is None:
        raise RuntimeError("空数据版本 edge_count 缺失")
    if not isinstance(raw_edge_count, (int, str, bytes, bytearray)):
        raise RuntimeError(f"空数据版本 edge_count 类型不正确：{type(raw_edge_count)!r}")
    try:
        edge_count = int(raw_edge_count)
    except Exception:
        raise RuntimeError(f"空数据版本 edge_count 不是整数：{cc_empty.get('edge_count')!r}")
    if edge_count != 0:
        raise RuntimeError(f"空数据版本 edge_count 非 0：{cc_empty.get('edge_count')}")

    resp_empty_hist = client.get(
        f"/scheduler/gantt/data?view=machine&week_start=2026-03-02&version={empty_version}&include_history=1"
    )
    _assert_status(resp_empty_hist, "GET /scheduler/gantt/data?empty_version&include_history=1")
    payload_empty_hist = json.loads(resp_empty_hist.data.decode("utf-8", errors="ignore") or "{}")
    if payload_empty_hist.get("success") is not True:
        raise RuntimeError(f"空数据版本 include_history=1 接口失败：{payload_empty_hist}")
    data_empty_hist = payload_empty_hist.get("data") or {}
    if "history" not in data_empty_hist:
        raise RuntimeError("空数据版本 include_history=1 时未返回 history")
    if data_empty_hist.get("history", "__MISSING__") is not None:
        raise RuntimeError(f"空数据版本无历史时 history 应为 null：{data_empty_hist.get('history')!r}")

    print("OK")


if __name__ == "__main__":
    main()

