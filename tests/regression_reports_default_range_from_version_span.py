from __future__ import annotations

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


def _assert_contains(html: str, needle: str, name: str) -> None:
    if needle not in html:
        raise RuntimeError(f"{name} 未包含期望内容：{needle!r}")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_regression_reports_range_span_")
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

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(test_db)
    try:
        conn.execute("INSERT INTO Parts(part_no, part_name) VALUES (?, ?)", ("P_RANGE", "测试零件"))
        conn.execute("INSERT INTO Machines(machine_id, name, status) VALUES (?, ?, ?)", ("MC_R1", "测试设备", "active"))
        conn.execute("INSERT INTO Operators(operator_id, name, status) VALUES (?, ?, ?)", ("OP_R1", "测试人员", "active"))
        conn.execute(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_RANGE", "P_RANGE", "测试零件", 1, "2099-12-31", "normal", "yes", "pending", "range regression"),
        )
        conn.execute(
            """
            INSERT INTO BatchOperations(op_code, batch_id, seq, op_type_name, source, machine_id, operator_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_RANGE_10", "B_RANGE", 10, "数铣", "internal", "MC_R1", "OP_R1", 0.5, 1.0, "scheduled"),
        )
        row = conn.execute("SELECT id FROM BatchOperations WHERE op_code=?", ("B_RANGE_10",)).fetchone()
        if not row:
            raise RuntimeError("未插入 BatchOperations")
        op_id = int(row["id"])

        conn.execute(
            """
            INSERT INTO Schedule(op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (op_id, "MC_R1", "OP_R1", "2099-01-10 08:00:00", "2099-01-10 12:00:00", "unlocked", 9),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (9, "test", 1, 1, "success", "{}", "regression"),
        )
        conn.commit()
    finally:
        conn.close()

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    # utilization：无日期参数时，应自动落到 version=9 的排程范围
    r = client.get("/reports/utilization?version=9")
    _assert_status(r, "GET /reports/utilization?version=9")
    util_html = r.data.decode("utf-8", errors="ignore")
    _assert_contains(util_html, 'name="start_date" value="2099-01-10"', "utilization start_date")
    _assert_contains(util_html, 'name="end_date" value="2099-01-10"', "utilization end_date")
    _assert_contains(util_html, "已按所选版本的排程范围自动带入日期。", "utilization hint")
    _assert_contains(util_html, "MC_R1", "utilization machine row")

    # downtime：同样应自动使用 version=9 的日期范围（即使结果为空）
    r = client.get("/reports/downtime?version=9")
    _assert_status(r, "GET /reports/downtime?version=9")
    dt_html = r.data.decode("utf-8", errors="ignore")
    _assert_contains(dt_html, 'name="start_date" value="2099-01-10"', "downtime start_date")
    _assert_contains(dt_html, 'name="end_date" value="2099-01-10"', "downtime end_date")
    _assert_contains(dt_html, "已按所选版本的排程范围自动带入日期。", "downtime hint")

    print("OK")


if __name__ == "__main__":
    main()
