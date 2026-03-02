import os
import sqlite3
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _upsert_system_config(conn: sqlite3.Connection, key: str, value: str, desc: str = "") -> None:
    conn.execute(
        """
        INSERT INTO SystemConfig (config_key, config_value, description, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(config_key) DO UPDATE SET
          config_value = excluded.config_value,
          description = excluded.description,
          updated_at = CURRENT_TIMESTAMP
        """,
        (str(key), str(value), str(desc or "")),
    )


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.system import SystemMaintenanceService

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_system_maintenance_")
    db_path = os.path.join(tmpdir, "aps_maintenance.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    conn = get_connection(db_path)
    try:
        schema_path = os.path.join(repo_root, "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        # 启用“自动清理操作日志”，确保会写 SystemJobState（关键：需要跨连接持久化）
        _upsert_system_config(conn, "auto_log_cleanup_enabled", "yes", desc="regression")
        conn.commit()

        op_logger = OperationLogger(conn, logger=None)
        _ = SystemMaintenanceService.run_if_due(
            conn,
            db_path=db_path,
            backup_dir=backup_dir,
            backup_keep_days_default=7,
            logger=None,
            op_logger=op_logger,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 重新连接后应能读到 last_run_time（修复前该值会因为未 commit 而丢失）
    conn2 = get_connection(db_path)
    try:
        row = conn2.execute(
            "SELECT job_key, last_run_time FROM SystemJobState WHERE job_key = ?",
            (SystemMaintenanceService.JOB_AUTO_LOG_CLEANUP,),
        ).fetchone()
        assert row is not None, "SystemJobState 未持久化（row is None）"
        last_run_time = row[1]
        assert last_run_time is not None and str(last_run_time).strip() != "", f"last_run_time 为空：{last_run_time!r}"
        print("OK")
    finally:
        try:
            conn2.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

