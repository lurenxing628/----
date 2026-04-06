from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from datetime import datetime


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _FailingOperationLogsConn:
    def __init__(self, inner: sqlite3.Connection):
        self._inner = inner

    @property
    def in_transaction(self):
        return getattr(self._inner, "in_transaction", False)

    def execute(self, sql, params=()):
        stmt = " ".join(str(sql).split()).upper()
        if stmt.startswith("INSERT INTO OPERATIONLOGS"):
            raise sqlite3.OperationalError("blocked OperationLogs insert")
        return self._inner.execute(sql, params)

    def commit(self):
        return self._inner.commit()

    def rollback(self):
        return self._inner.rollback()

    def close(self):
        return self._inner.close()

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []
        self.errors = []
        self.infos = []

    def warning(self, msg: str) -> None:
        self.warnings.append(str(msg))

    def error(self, msg: str) -> None:
        self.errors.append(str(msg))

    def info(self, msg: str) -> None:
        self.infos.append(str(msg))


def _due(*_args, **_kwargs):
    return True, None


def _fmt_db_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.system.maintenance.cleanup_task import maybe_run_auto_log_cleanup
    from data.repositories.system_job_state_repo import SystemJobStateRepository

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_real_oplog_")
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    ensure_schema(
        db_path,
        logger=None,
        schema_path=os.path.join(repo_root, "schema.sql"),
        backup_dir=backup_dir,
    )

    base_conn = get_connection(db_path)
    try:
        for i in range(20):
            base_conn.execute(
                "INSERT INTO OperationLogs (log_time, log_level, module, action, detail) VALUES (?, ?, ?, ?, ?)",
                (
                    f"2000-01-01 00:00:{i:02d}",
                    "INFO",
                    "system",
                    "backup",
                    '{"note":"old"}',
                ),
            )
        for i in range(60):
            base_conn.execute(
                "INSERT INTO OperationLogs (log_level, module, action, detail) VALUES (?, ?, ?, ?)",
                ("INFO", "system", "backup", '{"note":"new"}'),
            )
        base_conn.commit()

        proxy_conn = _FailingOperationLogsConn(base_conn)
        job_repo = SystemJobStateRepository(proxy_conn, logger=None)
        maint_logger = _CollectingLogger()
        op_logger = OperationLogger(proxy_conn, logger=_CollectingLogger())

        ran, detail = maybe_run_auto_log_cleanup(
            proxy_conn,
            job_repo=job_repo,
            now=datetime.now(),
            interval_minutes=1,
            keep_days=1,
            min_keep_logs=50,
            max_log_delete_per_run=200,
            job_key="reg_real_oplog_fail",
            logger=maint_logger,
            op_logger=op_logger,
            is_due_fn=_due,
            fmt_db_dt_fn=_fmt_db_dt,
        )
        assert ran is True, f"主流程不应因真实 OperationLogger 落库失败而返回 False：{detail}"
        assert detail.get("oplog_persisted") is False, f"应暴露 oplog_persisted=False，实际 {detail}"
        assert detail.get("job_state_persisted") is True, f"应暴露 job_state_persisted=True，实际 {detail}"
        assert maint_logger.warnings, "真实 OperationLogger 落库失败时应留下 telemetry warning"
    finally:
        base_conn.close()

    check_conn = get_connection(db_path)
    try:
        row = check_conn.execute(
            "SELECT last_run_time FROM SystemJobState WHERE job_key = ?",
            ("reg_real_oplog_fail",),
        ).fetchone()
        assert row is not None and str(row[0]).strip() != "", "job state 应已持久化"
        log_count = int(
            check_conn.execute(
                "SELECT COUNT(1) FROM OperationLogs WHERE module='system' AND action='logs_cleanup'"
            ).fetchone()[0]
        )
        assert log_count == 0, f"OperationLogs 落库被阻断时不应出现成功留痕，实际 {log_count}"
    finally:
        check_conn.close()

    print("OK")


if __name__ == "__main__":
    main()
