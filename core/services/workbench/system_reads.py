"""Bounded runtime/operation log windows and full backup metadata, without writes."""

import os
from datetime import datetime

from core.infrastructure.safe_files import stat_regular_file
from core.models.operation_log_labels import operation_log_summary
from core.models.operation_log_public_projection import public_operation_log_detail_text
from core.models.workbench_command import input_fingerprint
from core.services.system.operation_log_service import OperationLogService
from core.services.system.runtime_log_reader import LOG_FILE_CHOICES, NO_ANCHOR_HEAD, read_log_entries_tail
from core.services.workbench.system_redaction import public_system_text


def backup_signature(path):
    info = stat_regular_file(path)
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns, "inode": info.st_ino, "device": info.st_dev}


def backup_records(directory):
    rows, issues = [], []
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return rows, [{"code": "directory_missing", "message": "备份目录尚不存在。"}]
    for name in names:
        if not name.startswith("aps_backup_") or not name.endswith(".db"):
            continue
        try:
            signature = backup_signature(os.path.join(directory, name))
        except OSError:
            issues.append({"code": "file_unreadable", "message": "有备份文件无法读取或不是普通文件，未列为可操作目标。"})
            continue
        kind = next((suffix for suffix in ("before_restore", "manual", "auto") if "_" + suffix in name), "unknown")
        rows.append({"key": input_fingerprint({"name": name, **signature}), "filename": name,
                     "time": datetime.fromtimestamp(signature["mtime_ns"] / 1e9).strftime("%Y-%m-%dT%H:%M:%S"),
                     "size_bytes": signature["size"], "type": kind, "status": "unverified",
                     "file_exists": True, "verification_state": "not_checked", "last_run_result": None,
                     "summary": name, "body": "仅已读取文件元信息，没有本次完整性校验证据。", "_signature": signature})
    return rows, issues


def _runtime_rows(log_dir, name):
    path = os.path.join(log_dir, name)
    try:
        stat_regular_file(path)
    except FileNotFoundError:
        return [], {"source": name, "state": "missing", "window": 200, "count": None, "truncated": False}
    entries = read_log_entries_tail(path, max_entries=201)
    rows = []
    for index, item in enumerate(entries[:200]):
        time = item["head"][:19]
        try:
            time = datetime.strptime(time, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            time = None
        rows.append({"key": input_fingerprint({"file": name, "index": index, "entry": item}),
                     "time": time, "type": "runtime", "status": "recorded", "level": item["level"],
                     "file": name, "summary": public_system_text(item["head"], 1000),
                     "body": public_system_text(item["body"]),
                     "content_truncated": len(item["body"]) > 8192 or "中段已截断" in item["body"]})
    boundary_unknown = any(item["head"] == NO_ANCHOR_HEAD for item in entries)
    return rows, {"source": name, "state": "available" if rows else "empty", "window": 200,
                  "count": len(rows), "truncated": len(entries) > 200 or boundary_unknown,
                  "boundary_unknown": boundary_unknown}


def log_records(conn, log_dir, logger):
    rows, sources = [], []
    for name in LOG_FILE_CHOICES:
        try:
            items, state = _runtime_rows(log_dir, name)
            rows.extend(items)
            sources.append(state)
        except OSError:
            logger.exception("系统工作区运行日志读取失败")
            sources.append({"source": name, "state": "error", "window": 200, "count": None,
                            "truncated": False, "message": "日志文件无法读取，请检查文件状态。"})
    try:
        operations = OperationLogService(conn, logger=logger).list_recent(limit=501)
        for item in operations[:500]:
            summary = public_system_text(operation_log_summary(item.module, item.action), 1000)
            body = public_system_text(public_operation_log_detail_text(item.detail) + "\n" + str(item.error_message or ""))
            rows.append({"key": input_fingerprint({"operation": item.id, "time": item.log_time, "body": body}),
                         "time": str(item.log_time or "").replace(" ", "T") or None,
                         "type": "operation", "status": "recorded", "level": item.log_level,
                         "file": "OperationLogs", "summary": summary, "body": body,
                         "content_truncated": "展示长度已截断" in body})
        sources.append({"source": "OperationLogs", "state": "available" if operations else "empty",
                        "window": 500, "count": min(len(operations), 500), "truncated": len(operations) > 500})
    except Exception:
        logger.exception("系统工作区操作日志读取失败")
        sources.append({"source": "OperationLogs", "state": "error", "window": 500, "count": None,
                        "truncated": False, "message": "操作日志无法读取，未以空记录代替。"})
    return rows, sources
