from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import datetime


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _BrokenInfoOpLogger:
    def __init__(self) -> None:
        self.calls = []

    def info(self, **kwargs):
        self.calls.append(("info", dict(kwargs)))
        raise RuntimeError("oplog info exploded")

    def error(self, **kwargs):
        self.calls.append(("error", dict(kwargs)))
        raise RuntimeError("oplog error exploded")


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []
        self.errors = []

    def warning(self, msg: str) -> None:
        self.warnings.append(str(msg))

    def error(self, msg: str) -> None:
        self.errors.append(str(msg))


def _due(*_args, **_kwargs):
    return True, None


def _fmt_db_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _job_row(conn, job_key: str):
    return conn.execute(
        "SELECT last_run_time, last_run_detail FROM SystemJobState WHERE job_key = ?",
        (str(job_key),),
    ).fetchone()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.system.maintenance.backup_task import maybe_run_auto_backup
    from core.services.system.maintenance.cleanup_task import (
        maybe_run_auto_backup_cleanup,
        maybe_run_auto_log_cleanup,
    )
    from data.repositories.system_job_state_repo import SystemJobStateRepository

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_telemetry_isolation_")
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    ensure_schema(
        db_path,
        logger=None,
        schema_path=os.path.join(repo_root, "schema.sql"),
        backup_dir=backup_dir,
    )

    conn = get_connection(db_path)
    try:
        job_repo = SystemJobStateRepository(conn, logger=None)
        logger = _CollectingLogger()
        op_logger = _BrokenInfoOpLogger()
        now = datetime.now()

        ran_backup, detail_backup = maybe_run_auto_backup(
            conn,
            job_repo=job_repo,
            now=now,
            interval_minutes=1,
            db_path=db_path,
            backup_dir=backup_dir,
            keep_days=7,
            job_key="reg_auto_backup_success",
            logger=logger,
            op_logger=op_logger,
            is_due_fn=_due,
            fmt_db_dt_fn=_fmt_db_dt,
        )
        if not ran_backup:
            raise RuntimeError(f"自动备份成功路径不应因 telemetry 失败而返回 False：{detail_backup}")
        if detail_backup.get("oplog_persisted") is not False:
            raise RuntimeError(f"自动备份成功路径预期暴露 oplog_persisted=False，实际 {detail_backup}")
        if detail_backup.get("job_state_persisted") is not True:
            raise RuntimeError(f"自动备份成功路径预期 job_state_persisted=True，实际 {detail_backup}")
        if not [f for f in os.listdir(backup_dir) if f.startswith("aps_backup_") and "_auto.db" in f]:
            raise RuntimeError("自动备份成功路径未生成 *_auto.db")
        if _job_row(conn, "reg_auto_backup_success") is None:
            raise RuntimeError("自动备份成功路径下 SystemJobState 未持久化")

        old_backup = os.path.join(backup_dir, "aps_backup_20000101_000000_auto.db")
        with open(old_backup, "wb") as f:
            f.write(b"old")
        old_mtime = time.time() - 30 * 24 * 3600
        os.utime(old_backup, (old_mtime, old_mtime))

        ran_cleanup, detail_cleanup = maybe_run_auto_backup_cleanup(
            conn,
            job_repo=job_repo,
            now=datetime.now(),
            interval_minutes=1,
            backup_dir=backup_dir,
            keep_days=7,
            max_backup_delete_per_run=20,
            job_key="reg_auto_backup_cleanup_success",
            logger=logger,
            op_logger=op_logger,
            is_due_fn=_due,
            fmt_db_dt_fn=_fmt_db_dt,
        )
        if not ran_cleanup:
            raise RuntimeError(f"自动清理备份成功路径不应因 telemetry 失败而返回 False：{detail_cleanup}")
        if detail_cleanup.get("oplog_persisted") is not False:
            raise RuntimeError(f"自动清理备份成功路径预期暴露 oplog_persisted=False，实际 {detail_cleanup}")
        if detail_cleanup.get("job_state_persisted") is not True:
            raise RuntimeError(f"自动清理备份成功路径预期 job_state_persisted=True，实际 {detail_cleanup}")
        if os.path.exists(old_backup):
            raise RuntimeError("自动清理备份成功路径未删除过期备份")
        if _job_row(conn, "reg_auto_backup_cleanup_success") is None:
            raise RuntimeError("自动清理备份成功路径下 SystemJobState 未持久化")

        for i in range(20):
            conn.execute(
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
            conn.execute(
                "INSERT INTO OperationLogs (log_level, module, action, detail) VALUES (?, ?, ?, ?)",
                ("INFO", "system", "backup", '{"note":"new"}'),
            )
        conn.commit()

        before_old = int(conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE log_time < ?", ("2001-01-01 00:00:00",)).fetchone()[0])
        ran_logs, detail_logs = maybe_run_auto_log_cleanup(
            conn,
            job_repo=job_repo,
            now=datetime.now(),
            interval_minutes=1,
            keep_days=1,
            min_keep_logs=50,
            max_log_delete_per_run=200,
            job_key="reg_auto_log_cleanup_success",
            logger=logger,
            op_logger=op_logger,
            is_due_fn=_due,
            fmt_db_dt_fn=_fmt_db_dt,
        )
        after_old = int(conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE log_time < ?", ("2001-01-01 00:00:00",)).fetchone()[0])
        if not ran_logs:
            raise RuntimeError(f"自动清理日志成功路径不应因 telemetry 失败而返回 False：{detail_logs}")
        if detail_logs.get("oplog_persisted") is not False:
            raise RuntimeError(f"自动清理日志成功路径预期暴露 oplog_persisted=False，实际 {detail_logs}")
        if detail_logs.get("job_state_persisted") is not True:
            raise RuntimeError(f"自动清理日志成功路径预期 job_state_persisted=True，实际 {detail_logs}")
        if after_old >= before_old:
            raise RuntimeError("自动清理日志成功路径未删除旧日志")
        if _job_row(conn, "reg_auto_log_cleanup_success") is None:
            raise RuntimeError("自动清理日志成功路径下 SystemJobState 未持久化")

        if len(logger.warnings) < 3:
            raise RuntimeError(f"预期至少记录 3 条 telemetry warning，实际 {logger.warnings!r}")

        print("OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
