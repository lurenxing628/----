"""Maintenance telemetry keeps each write in its own transaction."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from core.infrastructure.logging import safe_log
from core.infrastructure.transaction import TransactionManager
from core.shared.strict_parse import is_exact_non_negative_number

_PARTIAL_ERROR_COUNT_KEYS = (
    "mtime_error_count",
    "unsafe_backup_count",
    "delete_error_count",
)
_COMPLETE_COUNT_KEY_BY_KIND = {
    "auto_backup_cleanup": "removed_count",
    "cleanup": "removed_count",
    "auto_log_cleanup": "deleted_count",
    "logs_cleanup": "deleted_count",
}
_INT_METRIC_KEYS = (
    "time_cost_ms",
    "removed_count",
    "deleted_count",
    "total",
    "candidates",
    "min_keep",
    "kept_recent_count",
    "mtime_error_count",
    "unsafe_backup_count",
    "delete_error_count",
    "allow",
    "keep_days",
    "min_keep_logs",
    "max_delete_per_run",
    "kept_count",
    "remaining_count",
    "deleted_wal_shm_count",
    "removed_empty_dir_count",
    "scanned_dir_count",
    "RetentionDays",
    "KeepCount",
)
_OVERVIEW_RESULT_COUNT_KEYS = (
    "time_cost_ms",
    "removed_count",
    "deleted_count",
    "total",
    "candidates",
    "min_keep",
    "kept_recent_count",
    "mtime_error_count",
    "unsafe_backup_count",
    "delete_error_count",
    "allow",
)
_RESULT_TEXT_KEYS = (
    "filename",
    "error",
    "reason",
    "cutoff",
    "size_mb_status",
    "size_mb_error",
)


def _is_non_negative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def extract_maintenance_result_values(detail: Mapping[str, Any]) -> Dict[str, Any]:
    """统一校验维护任务结果明细字段并提取系统概况投影值。"""
    for field in _INT_METRIC_KEYS:
        if field not in detail:
            continue
        if not _is_non_negative_int(detail[field]):
            raise ValueError("Invalid task result number: " + field)
    values: Dict[str, Any] = {
        field: detail[field]
        for field in _OVERVIEW_RESULT_COUNT_KEYS
        if field in detail
    }
    if "size_mb" in detail:
        value = detail["size_mb"]
        if value is not None and not is_exact_non_negative_number(value):
            raise ValueError("Invalid task result number: size_mb")
        values["size_mb"] = value
    for field in _RESULT_TEXT_KEYS:
        if field not in detail or detail[field] is None:
            continue
        value = detail[field]
        if not isinstance(value, str):
            raise ValueError("Invalid task result text: " + field)
        if field == "filename" and ("/" in value or "\\" in value):
            raise ValueError("Task result filename must not contain a path")
        values[field] = value[:1000]
    if "skipped" in detail:
        if type(detail["skipped"]) is not bool:
            raise ValueError("Invalid task result flag: skipped")
        values["skipped"] = detail["skipped"]
    return values


def classify_maintenance_result(
    values: Mapping[str, Any],
    kind: str,
    *,
    log_level: str = "",
    error_message: Any = None,
    success_status: str = "completed",
) -> str:
    """统一的自动维护结果状态判定合同（任务写入、系统概况与维护历史记录共用）。"""
    normalized_level = str(log_level or "").strip().upper()
    if normalized_level in ("ERROR", "CRITICAL") or (
        isinstance(error_message, str) and bool(error_message.strip())
    ):
        return "failed"
    if "unparsed_detail" in values or "record_error" in values:
        return "unknown"
    error = values.get("error")
    if error and error.strip():
        return "failed"
    has_partial_count = any(
        values.get(key) not in (None, 0)
        for key in _PARTIAL_ERROR_COUNT_KEYS
    )
    if (
        has_partial_count
        or bool(values.get("size_mb_error"))
        or values.get("size_mb_status") == "stat_failed"
    ):
        return "partial"
    if values.get("skipped") is True or values.get("reason") == "backup_dir_not_exists":
        return "skipped"
    if kind in ("auto_backup", "backup"):
        if values.get("filename"):
            return "partial" if normalized_level in ("WARN", "WARNING") else success_status
        return "unknown"
    count_key = _COMPLETE_COUNT_KEY_BY_KIND.get(kind)
    if count_key is not None and count_key in values:
        if normalized_level in ("", "INFO"):
            return success_status
        if normalized_level in ("WARN", "WARNING"):
            return "partial"
    return "unknown"


def maintenance_oplog_level(status: str) -> str:
    if status == "partial":
        return "warning"
    return "info"


def write_oplog(conn, *, op_logger, logger, level: str, **kwargs) -> None:
    try:
        with TransactionManager(conn).transaction():
            if level == "error":
                op_logger.error(**kwargs)
            elif level == "warning":
                ok = op_logger.log("WARNING", **kwargs)
                if ok:
                    safe_log(
                        logger,
                        "warning",
                        f"[{kwargs.get('module')}] 警告：{kwargs.get('action')}（{kwargs.get('target_type') or ''} {kwargs.get('target_id') or ''}）",
                    )
            else:
                op_logger.info(**kwargs)
    except Exception as exc:
        safe_log(logger, "warning", f"系统维护 telemetry 写入 OperationLogs 失败：{exc}")


def write_job_state(conn, *, job_repo, job_key: str, last_run_time: str, last_run_detail: str, logger) -> None:
    try:
        with TransactionManager(conn).transaction():
            job_repo.set_last_run(job_key, last_run_time=last_run_time, last_run_detail=last_run_detail)
    except Exception as exc:
        safe_log(logger, "warning", f"系统维护 telemetry 写入 SystemJobState 失败：{exc}")
