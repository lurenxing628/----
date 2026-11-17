"""Read-only file/event union; maintenance events never carry file capabilities."""

import json
from datetime import datetime

from core.models.content import StoredJsonCorrupt, read_stored_json
from core.services.system.maintenance.telemetry import (
    classify_maintenance_result,
    extract_maintenance_result_values,
    parse_job_time,
)
from core.services.workbench.facts.system_reads import backup_records
from core.services.workbench.facts.system_redaction import public_system_text
from core.services.workbench.messages import stored_utc_text
from core.shared.strict_json import canonical_json
from data.repositories.system_job_state_repo import SystemJobStateRepository
from data.repositories.workbench_system_maintenance_repo import WorkbenchSystemMaintenanceRepository

_AUDIT_LIMIT = 500
_JOBS = {"auto_backup_cleanup": ("cleanup", "备份清理"),
         "auto_log_cleanup": ("logs_cleanup", "操作日志清理")}
_FILE_ACTIONS = {"download": False, "restore": False, "delete": False}


def _journal_time(value):
    """外部维护日志（system_journal）的 updated_at；作业状态时间走 parse_job_time。"""
    if not isinstance(value, str):
        return None
    try:
        value = value.replace(" ", "T", 1)
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        return parsed.isoformat(timespec="seconds")
    except ValueError:
        return None


def _event(kind, source, identity, time, status, summary, detail):
    body = public_system_text(json.dumps(detail, ensure_ascii=False, sort_keys=True, allow_nan=False), 32768)
    return {"key": canonical_json([source, str(identity)]),
            "record_kind": kind + "_event", "type": kind, "time": time, "status": status,
            "summary": summary, "body": body, "event_ref": str(identity), "event_source": source,
            "file_capabilities": dict(_FILE_ACTIONS)}


def _restore_records(journal, records):
    rows = []
    for record in records:
        if record["action"] != "restore":
            continue
        event = journal.public(record)
        filename = event["filename"] or "文件名未读取"
        rows.append(_event("restore", "external_maintenance_journal", event["job_ref"],
                           _journal_time(event["updated_at"]), event["state"], "恢复 · " + filename, event))
    return rows


def _readable_detail(raw):
    """存的维护结果明细；读不出来或字段值不合要求时为 None。

    维护页遇到坏记录也要能打开，由调用方把它显示成排障信息：解码失败只捕获 StoredJsonCorrupt，
    合法 JSON 里的字段问题只捕获准入函数 extract_maintenance_result_values 抛的 ValueError。
    """
    try:
        detail = read_stored_json(raw, dict)
    except StoredJsonCorrupt:
        return None
    try:
        extract_maintenance_result_values(detail)
    except ValueError:
        return None
    return detail


def _detail(value):
    detail = _readable_detail(value)
    return {"unparsed_detail": public_system_text(str(value or ""), 8192)} if detail is None else detail


def _cleanup_audits(conn):
    records = WorkbenchSystemMaintenanceRepository(conn).cleanup_audit_rows(_AUDIT_LIMIT + 1)
    rows, present = [], set()
    for record in records[:_AUDIT_LIMIT]:
        present.add(record["action"])
        parsed_detail = _detail(record["detail"])
        state = classify_maintenance_result(
            parsed_detail,
            record["action"],
            log_level=record["log_level"],
            error_message=record["error_message"],
            success_status="succeeded",
        )
        label = "备份清理" if record["action"] == "cleanup" else "操作日志清理"
        detail = {"audit_id": record["id"], "action": record["action"], "level": record["log_level"],
                  "detail": parsed_detail, "error_message": record["error_message"],
                  "basis": "persisted_operation_audit_not_file_existence"}
        time = stored_utc_text(record["log_time"]).replace(" ", "T", 1) if record["log_time"] else None
        rows.append(_event("cleanup", "operation_audit", record["id"], time, state, label, detail))
    return rows, present, len(records) > _AUDIT_LIMIT


def _latest_cleanup(conn, audited_actions):
    rows, issues = [], []
    for job in SystemJobStateRepository(conn).list_all():
        if job.job_key not in _JOBS and job.job_key != "auto_backup":
            continue
        if job.last_run_time is None and job.last_run_detail is None:
            continue
        label = "自动备份" if job.job_key == "auto_backup" else _JOBS[job.job_key][1]
        detail, field_issues, timestamp = _job_detail(job, label)
        issues.extend(field_issues)
        if job.job_key == "auto_backup":
            continue
        action, label = _JOBS[job.job_key]
        if action in audited_actions:
            continue
        state = classify_maintenance_result(detail, job.job_key, success_status="succeeded")
        rows.append(_event("cleanup", "latest_job_state_only", job.job_key, timestamp, state,
                           label + " · 仅最近状态", {"job_key": job.job_key, "detail": detail,
                           "basis": "latest_job_state_not_complete_history"}))
        issues.append({"code": "cleanup_latest_state_only", "message": label + "没有读到对应的操作记录，这里只有最近一次的状态，不是完整历史。"})
    return rows, issues


def maintenance_records(conn, backup_dir, journal, *, journal_records):
    """Caller owns the database read snapshot. Journal validation failures propagate."""
    files, issues = backup_records(backup_dir)
    rows = [{**row, "record_kind": "backup_file"} for row in files]
    rows.extend(_restore_records(journal, journal_records))
    audits, present, truncated = _cleanup_audits(conn)
    latest, latest_issues = _latest_cleanup(conn, present)
    rows.extend(audits)
    rows.extend(latest)
    sources = issues + latest_issues
    sources.append({"code": "maintenance_sources", "message":
                    f"这里分三部分列出：备份文件的基本信息、已核对的恢复操作记录、最近 {_AUDIT_LIMIT} 条清理记录；记录里的文件现在不一定还在。"})
    if truncated:
        sources.append({"code": "cleanup_audit_window_truncated", "message": "清理记录超过本次能读的条数，这里不是完整历史。"})
    return rows, sources


def _job_detail(job, label):
    """Report malformed persisted job fields without publishing parser input."""
    issues = []
    parsed = parse_job_time(job.last_run_time)
    timestamp = None if parsed.value is None else parsed.value.isoformat(timespec="seconds")
    if parsed.state == "invalid":
        issues.append({"code": "maintenance_last_time_invalid", "job_key": job.job_key,
                       "message": label + "：上次执行时间记录异常，系统会在下次执行后重新记录。"})
    raw = job.last_run_detail
    if raw is None or raw == "":
        return {}, issues, timestamp
    detail = _readable_detail(raw)
    if detail is None:
        message = "上次结果记录异常，详细内容请让维护人员查看日志。"
        issues.append({"code": "maintenance_last_detail_invalid", "job_key": job.job_key,
                       "message": label + "：" + message})
        detail = {"record_error": message}
    return detail, issues, timestamp
