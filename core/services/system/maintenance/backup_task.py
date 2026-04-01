from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, Tuple

from core.infrastructure.backup import BackupManager
from core.infrastructure.transaction import TransactionManager


def _safe_logger_emit(logger, level: str, message: str) -> None:
    if logger is None:
        return
    try:
        fn = getattr(logger, str(level or "").strip(), None)
        if callable(fn):
            fn(message)
    except Exception:
        pass


def _write_oplog(conn, *, op_logger, logger=None, level: str, **kwargs) -> bool:
    if op_logger is None:
        return True
    try:
        with TransactionManager(conn).transaction():
            if level == "error":
                result = op_logger.error(**kwargs)
            else:
                result = op_logger.info(**kwargs)
            if result is False:
                raise RuntimeError("OperationLogs 未成功落库。")
        return True
    except Exception as e:
        _safe_logger_emit(logger, "warning", f"自动备份 telemetry 写入 OperationLogs 失败：{e}")
        return False


def _write_job_state(conn, *, job_repo, job_key: str, last_run_time: str, last_run_detail: str, logger=None) -> bool:
    try:
        with TransactionManager(conn).transaction():
            job_repo.set_last_run(
                job_key,
                last_run_time=last_run_time,
                last_run_detail=last_run_detail,
            )
        return True
    except Exception as e:
        _safe_logger_emit(logger, "warning", f"自动备份 telemetry 写入 SystemJobState 失败：{e}")
        return False


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
    logger=None,
    op_logger=None,
    is_due_fn: Callable[..., Tuple[bool, str | None]],
    fmt_db_dt_fn: Callable[[datetime], str],
) -> Tuple[bool, Dict[str, Any]]:
    due, last_run = is_due_fn(job_repo, job_key, now, interval_minutes)
    if not due:
        return False, {"due": False, "last_run_time": last_run}

    mgr = BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=int(keep_days), logger=logger)
    t0 = time.time()
    try:
        path = mgr.backup(suffix="auto")
        filename = os.path.basename(path)
        time_cost_ms = int((time.time() - t0) * 1000)
        size_mb = None
        try:
            size_mb = round(os.stat(path).st_size / 1024 / 1024, 2)
        except Exception:
            size_mb = None

        detail = {
            "filename": filename,
            "suffix": "auto",
            "size_mb": size_mb,
            "mode": "auto",
            "time_cost_ms": time_cost_ms,
        }
        job_detail = json.dumps({"filename": filename, "size_mb": size_mb, "time_cost_ms": time_cost_ms}, ensure_ascii=False)

        oplog_written = _write_oplog(
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
        job_state_written = _write_job_state(
            conn,
            job_repo=job_repo,
            job_key=job_key,
            last_run_time=fmt_db_dt_fn(now),
            last_run_detail=job_detail,
            logger=logger,
        )
        return True, {
            "due": True,
            "created": filename,
            "oplog_persisted": bool(oplog_written),
            "job_state_persisted": bool(job_state_written),
        }
    except Exception as e:
        _safe_logger_emit(logger, "error", f"自动备份失败：{e}")
        time_cost_ms = int((time.time() - t0) * 1000)
        oplog_written = _write_oplog(
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
        job_state_written = _write_job_state(
            conn,
            job_repo=job_repo,
            job_key=job_key,
            last_run_time=fmt_db_dt_fn(now),
            last_run_detail=json.dumps({"error": str(e), "time_cost_ms": time_cost_ms}, ensure_ascii=False),
            logger=logger,
        )
        return False, {
            "due": True,
            "error": str(e),
            "oplog_persisted": bool(oplog_written),
            "job_state_persisted": bool(job_state_written),
        }

