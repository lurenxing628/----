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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # 隔离目录，避免污染真实 db/logs/backups/templates_excel
    root = tempfile.mkdtemp(prefix="aps_regression_logs_delete_")
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

    # 插入 2 条操作日志，确保存在 id=1
    conn = get_connection(test_db)
    try:
        cur1 = conn.execute(
            """
            INSERT INTO OperationLogs (log_level, module, action, target_type, target_id, operator, detail, error_code, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("INFO", "system", "seed", "operation_log", "1", "regression", None, None, None),
        )
        cur2 = conn.execute(
            """
            INSERT INTO OperationLogs (log_level, module, action, target_type, target_id, operator, detail, error_code, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("INFO", "system", "seed", "operation_log", "2", "regression", None, None, None),
        )
        conn.commit()
        id1 = int(cur1.lastrowid or 0)
        id2 = int(cur2.lastrowid or 0)
        if id1 != 1:
            raise RuntimeError(f"前置条件失败：期望第一条 OperationLogs.id=1，实际 id={id1}")
        if id2 != 2:
            raise RuntimeError(f"前置条件失败：期望第二条 OperationLogs.id=2，实际 id={id2}")
    finally:
        conn.close()

    # Flask test_client（不启动 server）
    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    # log_id=0/负数 不应夹逼为 1（不应误删 id=1）
    r0 = client.post("/system/logs/delete", data={"log_id": "0"}, follow_redirects=True)
    if r0.status_code != 200:
        raise RuntimeError(f"POST /system/logs/delete log_id=0 返回 {r0.status_code}，期望 200")
    rn = client.post("/system/logs/delete", data={"log_id": "-1"}, follow_redirects=True)
    if rn.status_code != 200:
        raise RuntimeError(f"POST /system/logs/delete log_id=-1 返回 {rn.status_code}，期望 200")

    conn = get_connection(test_db)
    try:
        c1 = int(conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE id=1").fetchone()[0])
        if c1 != 1:
            raise RuntimeError("log_id=0/-1 不应删除 OperationLogs.id=1（但查询不到 id=1）")
    finally:
        conn.close()

    # log_id=1 应能正常删除
    r1 = client.post("/system/logs/delete", data={"log_id": "1"}, follow_redirects=True)
    if r1.status_code != 200:
        raise RuntimeError(f"POST /system/logs/delete log_id=1 返回 {r1.status_code}，期望 200")

    conn = get_connection(test_db)
    try:
        c1 = int(conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE id=1").fetchone()[0])
        if c1 != 0:
            raise RuntimeError("log_id=1 删除后仍能查询到 OperationLogs.id=1")
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()

