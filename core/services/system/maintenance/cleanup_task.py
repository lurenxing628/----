from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Tuple, Union

from core.infrastructure.transaction import TransactionManager

IsDueResult = Union[Tuple[bool, Any], Tuple[bool, Any, str, Any]]


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
        _safe_logger_emit(logger, "warning", f"系统维护 telemetry 写入 OperationLogs 失败：{e}")
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
        _safe_logger_emit(logger, "warning", f"系统维护 telemetry 写入 SystemJobState 失败：{e}")
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


def cleanup_backups_with_limit(
    backup_dir: str,
    *,
    keep_days: int,
    max_delete: int,
    fmt_db_dt_fn: Callable[[datetime], str],
) -> Tuple[int, Dict[str, Any]]:
    cutoff = datetime.now() - timedelta(days=int(keep_days))
    if not os.path.exists(backup_dir):
        return 0, {"cutoff": fmt_db_dt_fn(cutoff), "reason": "backup_dir_not_exists"}

    candidates = []
    for fn in os.listdir(backup_dir):
        if not fn.startswith("aps_backup_") or not fn.endswith(".db"):
            continue
        fp = os.path.join(backup_dir, fn)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(fp))
        except Exception:
            continue
        if mtime < cutoff:
            candidates.append((mtime, fn, fp))

    candidates.sort(key=lambda x: x[0])
    removed = 0
    removed_sample = []
    for _, fn, fp in candidates[: int(max_delete)]:
        try:
            os.remove(fp)
            removed += 1
            if len(removed_sample) < 10:
                removed_sample.append(fn)
        except Exception:
            continue

    return removed, {"cutoff": fmt_db_dt_fn(cutoff), "candidates": len(candidates), "removed_sample": removed_sample}


def cleanup_operation_logs_with_limit(
    conn,
    *,
    keep_days: int,
    min_keep_logs: int,
    max_delete: int,
    fmt_db_dt_fn: Callable[[datetime], str],
) -> Tuple[int, Dict[str, Any]]:
    total = conn.execute("SELECT COUNT(1) FROM OperationLogs").fetchone()[0]
    if int(total) <= int(min_keep_logs):
        return 0, {"total": int(total), "skipped": True, "reason": "total_le_min_keep"}

    cutoff_dt = datetime.now() - timedelta(days=int(keep_days))
    cutoff = fmt_db_dt_fn(cutoff_dt)

    cand = conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE log_time < ?", (cutoff,)).fetchone()[0]
    cand = int(cand)
    if cand <= 0:
        return 0, {"total": int(total), "cutoff": cutoff, "candidates": 0, "skipped": True, "reason": "no_candidates"}

    allow = min(int(max_delete), int(total) - int(min_keep_logs))
    to_delete = min(cand, allow)
    if to_delete <= 0:
        return 0, {"total": int(total), "cutoff": cutoff, "candidates": cand, "skipped": True, "reason": "allow_le_0"}

    conn.execute(
        """
        DELETE FROM OperationLogs
        WHERE id IN (
            SELECT id FROM OperationLogs
            WHERE log_time < ?
            ORDER BY log_time ASC, id ASC
            LIMIT ?
        )
        """,
        (cutoff, int(to_delete)),
    )
    return int(to_delete), {"total": int(total), "cutoff": cutoff, "candidates": cand, "allow": int(allow)}


def maybe_run_auto_backup_cleanup(
    conn,
    *,
    job_repo,
    now: datetime,
    interval_minutes: int,
    backup_dir: str,
    keep_days: int,
    max_backup_delete_per_run: int,
    job_key: str,
    logger=None,
    op_logger=None,
    is_due_fn: Callable[..., IsDueResult],
    fmt_db_dt_fn: Callable[[datetime], str],
) -> Tuple[bool, Dict[str, Any]]:
    due, last_run, last_run_state, last_run_raw = _unpack_due_info(is_due_fn(job_repo, job_key, now, interval_minutes))
    if not due:
        return False, {
            "due": False,
            "last_run_time": last_run,
            "last_run_state": last_run_state,
            "last_run_raw": last_run_raw,
        }

    t0 = time.time()
    try:
        removed, meta = cleanup_backups_with_limit(
            backup_dir=str(backup_dir),
            keep_days=int(keep_days),
            max_delete=int(max_backup_delete_per_run),
            fmt_db_dt_fn=fmt_db_dt_fn,
        )
        time_cost_ms = int((time.time() - t0) * 1000)
        detail = {
            "mode": "auto",
            "keep_days": int(keep_days),
            "removed_count": int(removed),
            "max_delete_per_run": int(max_backup_delete_per_run),
            "time_cost_ms": time_cost_ms,
            **meta,
        }
        oplog_written = _write_oplog(
            conn,
            op_logger=op_logger,
            logger=logger,
            level="info",
            module="system",
            action="cleanup",
            target_type="backup",
            target_id=None,
            detail=detail,
        )
        job_state_written = _write_job_state(
            conn,
            job_repo=job_repo,
            job_key=job_key,
            last_run_time=fmt_db_dt_fn(now),
            last_run_detail=json.dumps({"removed_count": removed, "time_cost_ms": time_cost_ms, **meta}, ensure_ascii=False),
            logger=logger,
        )
        return True, {
            "due": True,
            "removed_count": int(removed),
            "oplog_persisted": bool(oplog_written),
            "job_state_persisted": bool(job_state_written),
            **meta,
        }
    except Exception as e:
        _safe_logger_emit(logger, "error", f"自动清理备份失败：{e}")
        time_cost_ms = int((time.time() - t0) * 1000)
        oplog_written = _write_oplog(
            conn,
            op_logger=op_logger,
            logger=logger,
            level="error",
            module="system",
            action="cleanup",
            target_type="backup",
            target_id=None,
            detail={"mode": "auto", "time_cost_ms": time_cost_ms},
            error_code="auto_backup_cleanup_failed",
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


def maybe_run_auto_log_cleanup(
    conn,
    *,
    job_repo,
    now: datetime,
    interval_minutes: int,
    keep_days: int,
    min_keep_logs: int,
    max_log_delete_per_run: int,
    job_key: str,
    logger=None,
    op_logger=None,
    is_due_fn: Callable[..., IsDueResult],
    fmt_db_dt_fn: Callable[[datetime], str],
) -> Tuple[bool, Dict[str, Any]]:
    due, last_run, last_run_state, last_run_raw = _unpack_due_info(is_due_fn(job_repo, job_key, now, interval_minutes))
    if not due:
        return False, {
            "due": False,
            "last_run_time": last_run,
            "last_run_state": last_run_state,
            "last_run_raw": last_run_raw,
        }

    t0 = time.time()
    try:
        deleted = 0
        meta: Dict[str, Any] = {}
        time_cost_ms = 0
        with TransactionManager(conn).transaction():
            deleted, meta = cleanup_operation_logs_with_limit(
                conn,
                keep_days=int(keep_days),
                min_keep_logs=int(min_keep_logs),
                max_delete=int(max_log_delete_per_run),
                fmt_db_dt_fn=fmt_db_dt_fn,
            )
        time_cost_ms = int((time.time() - t0) * 1000)
        detail = {
            "mode": "auto",
            "keep_days": int(keep_days),
            "deleted_count": int(deleted),
            "min_keep_logs": int(min_keep_logs),
            "max_delete_per_run": int(max_log_delete_per_run),
            "time_cost_ms": time_cost_ms,
            **meta,
        }
        oplog_written = _write_oplog(
            conn,
            op_logger=op_logger,
            logger=logger,
            level="info",
            module="system",
            action="logs_cleanup",
            target_type="operation_log",
            target_id=None,
            detail=detail,
        )
        job_state_written = _write_job_state(
            conn,
            job_repo=job_repo,
            job_key=job_key,
            last_run_time=fmt_db_dt_fn(now),
            last_run_detail=json.dumps({"deleted_count": deleted, "time_cost_ms": time_cost_ms, **meta}, ensure_ascii=False),
            logger=logger,
        )
        return True, {
            "due": True,
            "deleted_count": int(deleted),
            "oplog_persisted": bool(oplog_written),
            "job_state_persisted": bool(job_state_written),
            **meta,
        }
    except Exception as e:
        _safe_logger_emit(logger, "error", f"自动清理操作日志失败：{e}")
        time_cost_ms = int((time.time() - t0) * 1000)
        oplog_written = _write_oplog(
            conn,
            op_logger=op_logger,
            logger=logger,
            level="error",
            module="system",
            action="logs_cleanup",
            target_type="operation_log",
            target_id=None,
            detail={"mode": "auto", "time_cost_ms": time_cost_ms},
            error_code="auto_log_cleanup_failed",
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

