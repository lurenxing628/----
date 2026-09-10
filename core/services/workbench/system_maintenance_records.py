"""Read-only file/event union; maintenance events never carry file capabilities."""

import json
import os
from datetime import datetime

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from data.repositories.system_job_state_repo import SystemJobStateRepository

from .system_reads import backup_records
from .system_redaction import public_system_text

_AUDIT_LIMIT = 500
_JOURNAL_LIMIT = 2000
_JOBS = {"auto_backup_cleanup": ("cleanup", "备份清理", "removed_count"),
         "auto_log_cleanup": ("logs_cleanup", "操作日志清理", "deleted_count")}
_FILE_ACTIONS = {"download": False, "restore": False, "delete": False}


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        value = value.replace(" ", "T", 1)
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        return parsed.isoformat(timespec="seconds")
    except ValueError:
        return None


def _event(kind, source, identity, time, status, summary, detail):
    body = public_system_text(json.dumps(detail, ensure_ascii=False, sort_keys=True), 32768)
    return {"key": input_fingerprint({"source": source, "identity": identity, "time": time, "body": body}),
            "record_kind": kind + "_event", "type": kind, "time": _timestamp(time), "status": status,
            "summary": summary, "body": body, "event_ref": str(identity), "event_source": source,
            "file_capabilities": dict(_FILE_ACTIONS)}


def _restore_records(journal):
    try:
        names = os.listdir(journal.directory)
    except FileNotFoundError:
        names = []
    if sum(name.endswith(".json") for name in names) > _JOURNAL_LIMIT:
        raise WorkbenchCommandRejected("maintenance_record_capacity", "外置维护记录超过读取上限，未截断或伪装为空记录。", 413)
    rows = []
    for record in journal.records():
        if record["action"] != "restore":
            continue
        event = journal.public(record)
        filename = event["filename"] or "目标文件未确认"
        rows.append(_event("restore", "external_maintenance_journal", event["job_ref"], event["updated_at"],
                           event["state"], "恢复 · " + filename, event))
    return rows


def _detail(value):
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
    except (TypeError, ValueError):
        parsed = None
    return parsed if isinstance(parsed, dict) else {"unparsed_detail": public_system_text(str(value or ""), 8192)}


def _cleanup_audits(conn):
    records = [dict(row) for row in conn.execute(
        "SELECT id,log_time,log_level,module,action,detail,error_message FROM OperationLogs "
        "WHERE module='system' AND action IN ('cleanup','logs_cleanup') ORDER BY id DESC LIMIT ?",
        (_AUDIT_LIMIT + 1,))]
    rows, present = [], set()
    for record in records[:_AUDIT_LIMIT]:
        present.add(record["action"])
        state = "failed" if record["log_level"] in ("ERROR", "CRITICAL") or record["error_message"] else (
            "succeeded" if record["log_level"] == "INFO" else "unknown")
        label = "备份清理" if record["action"] == "cleanup" else "操作日志清理"
        detail = {"audit_id": record["id"], "action": record["action"], "level": record["log_level"],
                  "detail": _detail(record["detail"]), "error_message": record["error_message"],
                  "basis": "persisted_operation_audit_not_file_existence"}
        rows.append(_event("cleanup", "operation_audit", record["id"], record["log_time"], state, label, detail))
    return rows, present, len(records) > _AUDIT_LIMIT


def _latest_cleanup(conn, audited_actions):
    rows, issues = [], []
    for job in SystemJobStateRepository(conn).list_all():
        if job.job_key not in _JOBS:
            continue
        action, label, count_key = _JOBS[job.job_key]
        if action in audited_actions:
            continue
        if job.last_run_time is None and job.last_run_detail is None:
            continue
        detail = _detail(job.last_run_detail)
        count = detail.get(count_key)
        known = type(count) is int and count >= 0
        state = "failed" if isinstance(detail.get("error"), str) and detail["error"] else (
            "succeeded" if known else "unknown")
        rows.append(_event("cleanup", "latest_job_state_only", job.job_key, job.last_run_time, state,
                           label + " · 仅最近状态", {"job_key": job.job_key, "detail": detail,
                           "basis": "latest_job_state_not_complete_history"}))
        issues.append({"code": "cleanup_latest_state_only", "message": label + "未读到对应操作审计，所列仅最近状态，不是完整历史。"})
    return rows, issues


def maintenance_records(conn, backup_dir, journal):
    """Caller owns the database read snapshot. Journal validation failures propagate."""
    files, issues = backup_records(backup_dir)
    rows = [{**row, "record_kind": "backup_file"} for row in files]
    if journal is None:
        issues.append({"code": "restore_event_source_unconfigured", "message": "外置维护目录未配置，恢复事件不可读取；备份文件仅展示已读元信息。"})
    else:
        rows.extend(_restore_records(journal))
    audits, present, truncated = _cleanup_audits(conn)
    latest, latest_issues = _latest_cleanup(conn, present)
    rows.extend(audits)
    rows.extend(latest)
    sources = issues + latest_issues
    sources.append({"code": "maintenance_sources", "message":
                    f"备份文件元信息、已校验外置恢复记录、最近 {_AUDIT_LIMIT} 条清理审计分别列示；事件不代表文件当前存在。"})
    if truncated:
        sources.append({"code": "cleanup_audit_window_truncated", "message": "清理审计超过最近读取窗口，不代表完整历史。"})
    return rows, sources
