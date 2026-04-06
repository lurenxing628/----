import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from unittest import mock


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
    from core.services.system.maintenance.cleanup_task import maybe_run_auto_log_cleanup
    from data.repositories.system_job_state_repo import SystemJobStateRepository

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

        # 该回归关注的是 telemetry 持久化，不应被前序测试的节流状态污染。
        SystemMaintenanceService.reset_throttle_for_tests()
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
    finally:
        try:
            conn2.close()
        except Exception:
            pass

    class _BrokenErrorOpLogger:
        def error(self, **_kwargs):
            raise RuntimeError("oplog error exploded")

        def info(self, **_kwargs):
            raise RuntimeError("unexpected info call")

    class _CollectingLogger:
        def __init__(self) -> None:
            self.warnings = []

        def warning(self, msg: str) -> None:
            self.warnings.append(str(msg))

        def error(self, _msg: str) -> None:
            pass

    def _due(*_args, **_kwargs):
        return True, None

    def _fmt_db_dt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    conn3 = get_connection(db_path)
    try:
        job_repo = SystemJobStateRepository(conn3, logger=None)
        logger = _CollectingLogger()
        failure_job_key = "regression_auto_log_cleanup_failure"
        with mock.patch(
            "core.services.system.maintenance.cleanup_task.cleanup_operation_logs_with_limit",
            side_effect=RuntimeError("cleanup boom"),
        ):
            ran, detail = maybe_run_auto_log_cleanup(
                conn3,
                job_repo=job_repo,
                now=datetime.now(),
                interval_minutes=1,
                keep_days=1,
                min_keep_logs=50,
                max_log_delete_per_run=200,
                job_key=failure_job_key,
                logger=logger,
                op_logger=_BrokenErrorOpLogger(),
                is_due_fn=_due,
                fmt_db_dt_fn=_fmt_db_dt,
            )
        assert ran is False, f"failure path 预期 ran=False，实际 {ran} / {detail}"
        assert "error" in detail and "cleanup boom" in str(detail["error"]), detail
        assert detail.get("oplog_persisted") is False, f"预期 failure telemetry 暴露 oplog_persisted=False，实际 {detail}"
        assert detail.get("job_state_persisted") is True, f"预期 failure telemetry 暴露 job_state_persisted=True，实际 {detail}"
        assert logger.warnings, "failure telemetry 隔离后仍应留下 warning 日志"
    finally:
        try:
            conn3.close()
        except Exception:
            pass

    conn4 = get_connection(db_path)
    try:
        row2 = conn4.execute(
            "SELECT job_key, last_run_time, last_run_detail FROM SystemJobState WHERE job_key = ?",
            ("regression_auto_log_cleanup_failure",),
        ).fetchone()
        assert row2 is not None, "failure telemetry 场景下 SystemJobState 未持久化"
        assert row2[1] is not None and str(row2[1]).strip() != "", f"failure last_run_time 为空：{row2[1]!r}"
        assert "cleanup boom" in str(row2[2] or ""), f"failure last_run_detail 未记录错误：{row2[2]!r}"
        print("OK")
    finally:
        try:
            conn4.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

