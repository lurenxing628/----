from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, Tuple, Union

from core.infrastructure.backup import BackupManager
from core.infrastructure.logging import safe_log
from core.infrastructure.transaction import TransactionManager

IsDueResult = Union[Tuple[bool, Any], Tuple[bool, Any, str, Any]]


def _safe_logger_emit(logger, level: str, message: str) -> None:
    safe_log(logger, level, message)


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
        safe_log(logger, "warning", f"自动备份 telemetry 写入 OperationLogs 失败：{e}")
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
        safe_log(logger, "warning", f"自动备份 telemetry 写入 SystemJobState 失败：{e}")
        return False


def _unpack_due_info(result) -> Tuple[bool, Any, str, Any]:
    if not isinstance(result, tuple):
        return bool(result), None, "missing", None
    due = bool(result[0]) if len(result) >= 1 else False
    last_run = result[1] if len(result) >= 2 else None
    last_run_state = str(result[2]).strip() if len(result) >= 3 else ""
    last_run_raw = result[3] if len(result) >= 4 else None
    if last_run_state not in {"valid", "missing", "invalid"}:
        if last_run is None:
            last_run_state = "missing"
        else:
            last_run_state = "valid"
    return due, last_run, last_run_state, last_run_raw


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
    is_due_fn: Callable[..., IsDueResult],
    fmt_db_dt_fn: Callable[[datetime], str],
) -> Tuple[bool, Dict[str, Any]]:
    due, last_run, last_run_state, last_run_raw = _unpack_due_info(is_due_fn(job_repo, job_key, now, interval_minutes))
    if not due:
        return False, {"due": False, "last_run_time": last_run, "last_run_state": last_run_state, "last_run_raw": last_run_raw}

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
        job_detail = json.dumps(
            {
                "filename": filename,
                "size_mb": size_mb,
                "size_mb_status": size_mb_status,
                "size_mb_error": size_mb_error,
                "time_cost_ms": time_cost_ms,
            },
            ensure_ascii=False,
        )

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
            "size_mb": size_mb,
            "size_mb_status": size_mb_status,
            "size_mb_error": size_mb_error,
            "oplog_persisted": bool(oplog_written),
            "job_state_persisted": bool(job_state_written),
        }
    except Exception as e:
        safe_log(logger, "error", f"自动备份失败：{e}")
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
