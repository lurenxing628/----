from __future__ import annotations

import os
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


def _fmt_db_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.system import SystemMaintenanceService
    from core.services.system.maintenance.cleanup_task import maybe_run_auto_log_cleanup
    from data.repositories.system_job_state_repo import SystemJobStateRepository

    tmpdir = tempfile.mkdtemp(prefix="aps_reg_jobstate_retry_")
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
        for i in range(30):
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

        job_repo = SystemJobStateRepository(conn, logger=None)
        job_key = "reg_jobstate_retry_signal"

        with mock.patch.object(job_repo, "set_last_run", side_effect=RuntimeError("jobstate boom")):
            ran1, detail1 = maybe_run_auto_log_cleanup(
                conn,
                job_repo=job_repo,
                now=datetime.now(),
                interval_minutes=1,
                keep_days=1,
                min_keep_logs=50,
                max_log_delete_per_run=5,
                job_key=job_key,
                logger=None,
                op_logger=None,
                is_due_fn=SystemMaintenanceService._is_due,
                fmt_db_dt_fn=_fmt_db_dt,
            )
        assert ran1 is True, f"首次主动作不应因 job state 持久化失败而返回 False：{detail1}"
        assert detail1.get("job_state_persisted") is False, f"应暴露 job_state_persisted=False，实际 {detail1}"
        row1 = conn.execute("SELECT COUNT(1) FROM SystemJobState WHERE job_key = ?", (job_key,)).fetchone()
        assert int(row1[0]) == 0, "首次 job state 失败后不应已有持久化记录"

        conn.execute(
            "INSERT INTO OperationLogs (log_time, log_level, module, action, detail) VALUES (?, ?, ?, ?, ?)",
            ("2000-01-02 00:00:00", "INFO", "system", "backup", '{"note":"old-second"}'),
        )
        conn.commit()

        ran2, detail2 = maybe_run_auto_log_cleanup(
            conn,
            job_repo=job_repo,
            now=datetime.now(),
            interval_minutes=1,
            keep_days=1,
            min_keep_logs=50,
            max_log_delete_per_run=5,
            job_key=job_key,
            logger=None,
            op_logger=None,
            is_due_fn=SystemMaintenanceService._is_due,
            fmt_db_dt_fn=_fmt_db_dt,
        )
        assert ran2 is True, f"由于首次未持久化 last_run，第二次仍应判定 due：{detail2}"
        assert detail2.get("job_state_persisted") is True, f"第二次应成功持久化 job state，实际 {detail2}"

        row2 = conn.execute(
            "SELECT last_run_time, last_run_detail FROM SystemJobState WHERE job_key = ?",
            (job_key,),
        ).fetchone()
        assert row2 is not None and str(row2[0]).strip() != "", "第二次后应持久化 last_run_time"
        assert "deleted_count" in str(row2[1] or ""), f"last_run_detail 应记录删除结果，实际 {row2[1]!r}"
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
