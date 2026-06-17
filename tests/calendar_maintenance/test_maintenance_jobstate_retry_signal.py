"""回归测试：自动日志清理 maybe_run_auto_log_cleanup 在 SystemJobStateRepository.set_last_run 持久化失败时，首次仍执行清理但返回 job_state_persisted=False 且不写 last_run 记录，因 last_run 未落库下次仍判定 due 并成功持久化删除结果。"""

from __future__ import annotations

import os
from datetime import datetime
from unittest import mock


def _fmt_db_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_maintenance_jobstate_retry_signal(db_path, tmp_path) -> None:

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.system import SystemMaintenanceService
    from core.services.system.maintenance.cleanup_task import maybe_run_auto_log_cleanup
    from data.repositories.system_job_state_repo import SystemJobStateRepository

    backup_dir = os.path.join(str(tmp_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)


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
