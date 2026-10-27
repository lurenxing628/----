from __future__ import annotations

import os
import time
import traceback
from datetime import datetime
from typing import Callable, Tuple

from core.infrastructure.backup import BackupManager
from core.infrastructure.logging import safe_log
from core.shared.strict_json import canonical_json

from .telemetry import write_job_state, write_oplog


def maybe_run_auto_backup(
    conn,
    *,
    job_repo,
    now: datetime,
    interval_minutes: int,
    db_path: str,
    backup_dir: str,
    keep_days: int,
    job_key: str,
    logger,
    op_logger,
    is_due_fn: Callable[..., bool],
    fmt_db_dt_fn: Callable[[datetime], str],
) -> Tuple[bool, bool]:
    if not is_due_fn(job_repo, job_key, now, interval_minutes):
        return False, False

    mgr = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=int(keep_days), logger=logger)
    t0 = time.time()
    try:
        path = mgr.backup(suffix="auto")
        filename = os.path.basename(path)
        time_cost_ms = int((time.time() - t0) * 1000)
        size_mb = None
        size_mb_status = "ok"
        size_mb_error = None
        try:
            size_mb = round(os.stat(path).st_size / 1024 / 1024, 2)
        except OSError as exc:
            size_mb_status = "stat_failed"
            size_mb_error = str(exc)

        detail = {
            "filename": filename,
            "suffix": "auto",
            "size_mb": size_mb,
            "size_mb_status": size_mb_status,
            "mode": "auto",
            "time_cost_ms": time_cost_ms,
        }
        if size_mb_error:
            detail["size_mb_error"] = size_mb_error
        job_detail = canonical_json(
            {
                "filename": filename,
                "size_mb": size_mb,
                "size_mb_status": size_mb_status,
                "size_mb_error": size_mb_error,
                "time_cost_ms": time_cost_ms,
            }
        )

        write_oplog(
            conn,
            op_logger=op_logger,
            logger=logger,
            level="info",
            module="system",
            action="backup",
            target_type="backup",
            target_id=filename,
            detail=detail,
        )
        write_job_state(
            conn,
            job_repo=job_repo,
            job_key=job_key,
            last_run_time=fmt_db_dt_fn(now),
            last_run_detail=job_detail,
            logger=logger,
        )
        return True, True
    except Exception as e:
        # B01(3)：失败留全量上下文与堆栈（不再只留一行 message），错误仍进 oplog/job_state 审计链，
        # 返回 False 供调度方（system_maintenance_service）据此跳过本轮自动清理。
        safe_log(
            logger,
            "error",
            f"自动备份失败（job_key={job_key} db_path={db_path} backup_dir={backup_dir} "
            f"keep_days={int(keep_days)}）：{e}\n{traceback.format_exc()}",
        )
        time_cost_ms = int((time.time() - t0) * 1000)
        write_oplog(
            conn,
            op_logger=op_logger,
            logger=logger,
            level="error",
            module="system",
            action="backup",
            target_type="backup",
            target_id=None,
            detail={"mode": "auto", "time_cost_ms": time_cost_ms},
            error_code="auto_backup_failed",
            error_message=str(e),
        )
        write_job_state(
            conn,
            job_repo=job_repo,
            job_key=job_key,
            last_run_time=fmt_db_dt_fn(now),
            last_run_detail=canonical_json({"error": str(e), "time_cost_ms": time_cost_ms}),
            logger=logger,
        )
        return True, False
