"""Read-only system metadata for the workbench; never a health check."""

from __future__ import annotations

import json
import math
import os
import sqlite3
import stat
from datetime import datetime
from typing import Any, Dict

from core.errors import AppError
from core.infrastructure.safe_files import stat_regular_file
from core.services.system.runtime_log_reader import (
    DIAGNOSTIC_EXTRA_FILES,
    ROTATED_LOG_RE,
    SECRET_FILE_NAME,
)
from core.services.system.system_config_service import SystemConfigService
from core.services.system.system_job_state_query_service import SystemJobStateQueryService
from core.services.system.system_maintenance_service import _parse_db_dt

_CONFIG_FIELDS = (
    "auto_backup_enabled", "auto_backup_interval_minutes",
    "auto_backup_cleanup_enabled", "auto_backup_keep_days",
    "auto_backup_cleanup_interval_minutes", "auto_log_cleanup_enabled",
    "auto_log_cleanup_keep_days", "auto_log_cleanup_interval_minutes",
)
_JOBS = ("auto_backup", "auto_backup_cleanup", "auto_log_cleanup")
_RESULT_COUNTS = (
    "time_cost_ms", "removed_count", "deleted_count", "total", "candidates",
    "min_keep", "kept_recent_count", "mtime_error_count", "unsafe_backup_count",
    "delete_error_count", "allow",
)
_RESULT_TEXT = ("filename", "error", "reason", "cutoff", "size_mb_status", "size_mb_error")
_FILE_LIMIT = 20
_DETAIL_LIMIT = 16384
_READ_ERRORS = (sqlite3.Error, AppError)


def _error(exc: Exception) -> Dict[str, str]:
    cause = exc.cause if isinstance(exc, AppError) and exc.cause is not None else exc
    return {"code": type(cause).__name__, "message": str(cause)[:1000]}


def _file_metadata(path: str) -> Dict[str, Any]:
    result = {"status": "not_read", "filename": None, "size_bytes": None,
              "modified_at": None, "error": None}
    if not path or path == ":memory:":
        return result
    result["filename"] = os.path.basename(path)
    try:
        info = stat_regular_file(path)
        modified = datetime.fromtimestamp(info.st_mtime).isoformat(timespec="seconds")
    except FileNotFoundError as exc:
        result.update(status="missing", error=_error(exc))
    except (OSError, ValueError, OverflowError) as exc:
        result.update(status="error", error=_error(exc))
    else:
        result.update(status="available", size_bytes=info.st_size, modified_at=modified)
    return result


def _database(conn, path: str) -> Dict[str, Any]:
    result = {"status": "not_read", "readable": None, "table_count": None,
              "read_scope": "schema_metadata", "integrity_status": "not_checked",
              "file": _file_metadata(path), "error": None}
    if conn is None:
        return result
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND substr(name, 1, 7) != 'sqlite_'"
        ).fetchone()[0]
    except _READ_ERRORS as exc:
        result.update(status="error", readable=False, error=_error(exc))
    else:
        result.update(status="available", readable=True, table_count=int(count))
    return result


def _matches_file(name: str, kind: str) -> bool:
    if kind == "backups":
        return name.startswith("aps_backup_") and name.endswith(".db")
    return name != SECRET_FILE_NAME and (
        name.endswith(".log") or bool(ROTATED_LOG_RE.match(name))
        or name in DIAGNOSTIC_EXTRA_FILES
    )


def _inventory(path: str, kind: str) -> Dict[str, Any]:
    result = {"status": "not_read", "count": None, "known_count": None,
              "files": [], "files_truncated": False, "issues": [], "error": None}
    if not path:
        return result
    try:
        directory = os.lstat(path)
        if stat.S_ISLNK(directory.st_mode):
            raise OSError("Metadata directory must not be a symbolic link")
        if not stat.S_ISDIR(directory.st_mode):
            raise NotADirectoryError("Metadata path is not a directory")
        names = sorted(name for name in os.listdir(path) if _matches_file(name, kind))
    except FileNotFoundError as exc:
        result.update(status="missing", error=_error(exc))
        return result
    except (OSError, ValueError) as exc:
        result.update(status="error", error=_error(exc))
        return result
    files = []
    for name in names:
        item = _file_metadata(os.path.join(path, name))
        if item["status"] == "available":
            files.append(item)
        else:
            result["issues"].append(item)
    files.sort(key=lambda item: (item["modified_at"], item["filename"]), reverse=True)
    result.update(
        status="partial" if result["issues"] else ("available" if files else "empty"),
        count=None if result["issues"] else len(files), known_count=len(files),
        files=files[:_FILE_LIMIT], files_truncated=len(files) > _FILE_LIMIT,
    )
    return result


def _logs(conn, path: str) -> Dict[str, Any]:
    result = _inventory(path, "logs")
    result.update(files_state=result["status"], content_status="not_read", entry_count=None,
                  operation_record_count=None, operation_records_state="not_read",
                  operation_records_error=None)
    if conn is not None:
        try:
            count = int(conn.execute("SELECT COUNT(*) FROM OperationLogs").fetchone()[0])
        except _READ_ERRORS as exc:
            result.update(operation_records_state="error", operation_records_error=_error(exc))
        else:
            result.update(operation_record_count=count,
                          operation_records_state="available" if count else "empty")
    file_state, record_state = result["files_state"], result["operation_records_state"]
    if record_state != "not_read":
        if file_state in ("available", "empty") and record_state in ("available", "empty"):
            result["status"] = "empty" if file_state == record_state == "empty" else "available"
        else:
            result["status"] = "error" if file_state == record_state == "error" else "partial"
    result["error"] = result["error"] or result["operation_records_error"]
    return result


def _config(conn, backup_keep_days_default: int) -> Dict[str, Any]:
    result = {"status": "not_read", "values": None, "stored_values": None,
              "defaulted_fields": None, "dirty_fields": None, "dirty_reasons": None,
              "stored_count": None, "writes_performed": False, "error": None}
    if conn is None:
        return result
    try:
        service = SystemConfigService(conn)
        snapshot = service.get_snapshot_readonly(backup_keep_days_default=backup_keep_days_default)
        stored = {key: service.get_value_with_presence(key) for key in _CONFIG_FIELDS}
    except _READ_ERRORS as exc:
        result.update(status="error", error=_error(exc))
        return result
    stored_values = {key: value for key, (present, value) in stored.items() if present}
    result.update(
        status="partial" if snapshot.dirty_fields else ("available" if stored_values else "empty"),
        values={key: getattr(snapshot, key) for key in _CONFIG_FIELDS},
        stored_values=stored_values, stored_count=len(stored_values),
        defaulted_fields=[key for key, (present, _) in stored.items() if not present],
        dirty_fields=list(snapshot.dirty_fields), dirty_reasons=dict(snapshot.dirty_reasons),
    )
    return result


def _result_numbers(detail: Dict[str, Any]) -> Dict[str, Any]:
    values = {}
    for field in _RESULT_COUNTS:
        if field not in detail:
            continue
        value = detail[field]
        if type(value) is not int or value < 0:
            raise ValueError("Invalid task result number: " + field)
        values[field] = value
    if "size_mb" in detail:
        value = detail["size_mb"]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError("Invalid task result number: size_mb")
        values["size_mb"] = value
    return values


def _result_text(detail: Dict[str, Any]) -> Dict[str, Any]:
    values = {}
    for field in _RESULT_TEXT:
        if field not in detail or detail[field] is None:
            continue
        value = detail[field]
        if not isinstance(value, str):
            raise ValueError("Invalid task result text: " + field)
        if field == "filename" and ("/" in value or "\\" in value):
            raise ValueError("Task result filename must not contain a path")
        values[field] = value[:1000]
    return values


def _result_values(raw: str) -> Dict[str, Any]:
    if not isinstance(raw, str) or len(raw) > _DETAIL_LIMIT:
        raise ValueError("Task result is not text or exceeds the metadata limit")
    detail = json.loads(raw)
    if not isinstance(detail, dict):
        raise ValueError("Task result must be a JSON object")
    values = _result_numbers(detail)
    values.update(_result_text(detail))
    if "skipped" in detail:
        if type(detail["skipped"]) is not bool:
            raise ValueError("Invalid task result flag: skipped")
        values["skipped"] = detail["skipped"]
    return values


def _result_status(values: Dict[str, Any], kind: str) -> str:
    if values.get("error"):
        return "failed"
    partial = any(values.get(key, 0) > 0 for key in (
        "mtime_error_count", "unsafe_backup_count", "delete_error_count"
    ))
    if partial or values.get("size_mb_error") or values.get("size_mb_status") == "stat_failed":
        return "partial"
    if values.get("skipped") or values.get("reason") == "backup_dir_not_exists":
        return "skipped"
    complete = {"auto_backup": bool(values.get("filename")),
                "auto_backup_cleanup": "removed_count" in values,
                "auto_log_cleanup": "deleted_count" in values}
    return "completed" if complete[kind] else "unknown"


def _job_result(raw: Any, kind: str) -> Dict[str, Any]:
    result = {"status": "not_recorded", "values": None, "error": None}
    if raw is None or raw == "":
        return result
    try:
        values = _result_values(raw)
    except (ValueError, TypeError, OverflowError) as exc:
        result.update(status="invalid", error=_error(exc))
    else:
        result.update(status=_result_status(values, kind), values=values)
    return result


def _maintenance_job(service, kind: str, initial: Dict[str, Any]):
    job = {"kind": kind, "status": initial["status"], "last_run_time": None,
           "last_run_time_status": "not_read", "result": None, "error": initial["error"]}
    if service is None:
        return job, False
    try:
        record = service.get(kind)
    except _READ_ERRORS as exc:
        job.update(status="error", error=_error(exc))
        return job, False
    if record is None:
        job["status"] = "empty"
        return job, False
    parsed = _parse_db_dt(record.last_run_time)
    detail = _job_result(record.last_run_detail, kind)
    incomplete = parsed.state != "valid" or detail["status"] in ("invalid", "unknown", "not_recorded")
    job.update(status="partial" if incomplete else "available",
               last_run_time=parsed.value.isoformat() if parsed.value else None,
               last_run_time_status=parsed.state, result=detail)
    return job, True


def _maintenance_state(states, count: int) -> str:
    if all(state == "error" for state in states):
        return "error"
    if any(state in ("error", "partial") for state in states):
        return "partial"
    return "available" if count else "empty"


def _maintenance(conn) -> Dict[str, Any]:
    result = {"status": "not_read", "record_count": None, "known_record_count": None,
              "jobs": [], "error": None}
    service = None
    if conn is not None:
        try:
            service = SystemJobStateQueryService(conn)
        except _READ_ERRORS as exc:
            result.update(status="error", error=_error(exc))
    outcomes = [_maintenance_job(service, kind, result) for kind in _JOBS]
    result["jobs"] = [job for job, _ in outcomes]
    if service is not None:
        count = sum(exists for _, exists in outcomes)
        states = [job["status"] for job in result["jobs"]]
        result.update(
            status=_maintenance_state(states, count),
            record_count=None if "error" in states else count,
            known_record_count=None if all(state == "error" for state in states) else count,
            error=next((job["error"] for job in result["jobs"] if job["error"]), None),
        )
    return result


def _present(section: Dict[str, Any], name: str) -> Dict[str, Any]:
    state = section.pop("status")
    messages = {
        "available": "已读取本机信息。", "empty": "暂无对应记录或文件。",
        "missing": "配置的目录不存在。", "not_read": "数据来源未提供，尚未读取。",
        "error": "读取失败，请查看错误详情。",
        "partial": "部分信息未能读取或存在异常，请核对详情。",
    }
    qualifications = {
        "database": "可读取不代表已通过数据库完整性检查。",
        "backups": "仅查看文件信息，尚未校验备份内容。",
        "logs": "仅统计文件和操作记录，尚未读取日志正文。",
        "config": "按现有规则读取有效值与缺省值，未保存或修正配置。",
        "maintenance": "仅显示最近留存的自动任务结果，不代表当前运行健康。",
    }
    section.update(state=state, message=messages[state] + " " + qualifications[name])
    return section


def build_system_overview(
    conn, *, db_path: str, backup_dir: str, log_dir: str, backup_keep_days_default: int = 7
) -> Dict[str, Any]:
    """Project the supplied connection and paths without opening a database.

    ``conn`` follows the application's sqlite3.Row connection contract. ``state``
    describes reading, not health: available/empty/missing/not_read/error/partial.
    Missing or failed reads have null counts; partial inventories give known_count.
    Config values are effective read-only values; stored_values and defaulted_fields
    distinguish persistence. Only the three registered automatic tasks are queried.
    File lists contain at most the latest 20 metadata entries; no contents are read.
    """
    backups = _inventory(backup_dir, "backups")
    backups["verification_status"] = "not_checked"
    backups["latest"] = backups["files"][0] if backups["status"] == "available" else None
    sections = {
        "database": _database(conn, db_path),
        "backups": backups,
        "logs": _logs(conn, log_dir),
        "config": _config(conn, backup_keep_days_default),
        "maintenance": _maintenance(conn),
    }
    return {name: _present(section, name) for name, section in sections.items()}
