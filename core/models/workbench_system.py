"""System-only request contracts; no resource namespace or database identities."""

import re
from datetime import datetime
from typing import TypedDict

from core.models.workbench_command import WorkbenchCommandRejected

CONFIG_FIELDS = (
    "auto_backup_enabled", "auto_backup_interval_minutes", "auto_backup_cleanup_enabled",
    "auto_backup_keep_days", "auto_backup_cleanup_interval_minutes", "auto_log_cleanup_enabled",
    "auto_log_cleanup_keep_days", "auto_log_cleanup_interval_minutes",
)
TERMINAL_STATES = frozenset(("succeeded", "failed", "rolled_back"))
JOB_STATES = TERMINAL_STATES | frozenset((
    "accepted", "checking", "protecting", "restoring", "verifying", "rolling_back",
    "rollback_failed", "recovery_required",
))
RESTORE_DISABLED = "恢复尚未接入启动恢复检查和全局写入隔离，当前不能安全切换数据库。"


class SystemQuery(TypedDict):
    query: str
    type: str
    status: str
    level: str
    file: str
    start: str
    end: str
    page: int
    page_size: int


def object_fields(value, required, optional=()):
    if type(value) is not dict or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise WorkbenchCommandRejected("invalid_input", "请求字段不完整或包含不支持的字段。", 400)
    return value


def config_input(value):
    object_fields(value, CONFIG_FIELDS)
    result = {}
    for key in CONFIG_FIELDS:
        raw = value[key]
        if key.endswith("_enabled"):
            valid = isinstance(raw, str) and raw in ("yes", "no")
        else:
            maximum = 365 if key.endswith("_days") else 1440
            valid = type(raw) is int and 1 <= raw <= maximum
        if not valid:
            raise WorkbenchCommandRejected("invalid_input", "维护配置须填写合法开关和范围内的整数：" + key, 422)
        result[key] = raw
    return result


def _query_dates(result):
    for key in ("start", "end"):
        if result[key]:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", result[key]):
                    raise ValueError()
                datetime.strptime(result[key], "%Y-%m-%d")
            except ValueError as exc:
                raise WorkbenchCommandRejected("invalid_input", "筛选日期无效。", 422) from exc
    if result["start"] and result["end"] and result["start"] > result["end"]:
        raise WorkbenchCommandRejected("invalid_input", "开始日期不能晚于结束日期。", 422)


def _query_pagination(value):
    result = {}
    for key, default in (("page", 1), ("page_size", 10)):
        raw = value.get(key, str(default))
        if not isinstance(raw, str) or not re.fullmatch(r"[1-9]\d{0,6}", raw):
            raise WorkbenchCommandRejected("invalid_input", "分页参数无效。", 400)
        result[key] = int(raw)
    if result["page_size"] not in (10, 25, 50):
        raise WorkbenchCommandRejected("invalid_input", "每页只能选择10、25或50条。", 400)
    return result


def query_input(value, kind) -> SystemQuery:
    allowed = {"query", "type", "status", "level", "file", "start", "end", "page", "page_size", "snapshot_ref"}
    object_fields(value, (), allowed)
    result = {key: value.get(key, "") for key in allowed - {"page", "page_size", "snapshot_ref"}}
    if any(not isinstance(item, str) or len(item) > 200 for item in result.values()):
        raise WorkbenchCommandRejected("invalid_input", "筛选值必须是长度不超过200的文本。", 400)
    _query_dates(result)
    choices = {"type": ("", "runtime", "operation") if kind == "logs" else
               ("", "manual", "auto", "before_restore", "unknown"),
               "status": ("", "recorded") if kind == "logs" else ("", "unverified"),
               "level": ("", "INFO", "WARNING", "WARN", "ERROR", "DEBUG", "CRITICAL", "UNKNOWN"),
               "file": ("", "aps.log", "aps_error.log", "launcher.log", "OperationLogs")}
    if any(result[key] not in items for key, items in choices.items()):
        raise WorkbenchCommandRejected("invalid_input", "不支持该日志来源、类型或状态筛选。", 400)
    pagination = _query_pagination(value)
    return SystemQuery(query=result["query"], type=result["type"], status=result["status"],
                       level=result["level"], file=result["file"], start=result["start"],
                       end=result["end"], page=pagination["page"], page_size=pagination["page_size"])


def filter_records(rows, query):
    text = query["query"].strip().lower()
    def matches(row):
        if any(query[key] and query[key] != row.get(key) for key in ("type", "status", "level", "file")):
            return False
        day = (row.get("time") or "")[:10]
        if (query["start"] and (not day or day < query["start"])) or (query["end"] and (not day or day > query["end"])):
            return False
        return not text or text in " ".join(str(row.get(key) or "") for key in ("summary", "body", "filename", "time", "file")).lower()
    return sorted((row for row in rows if matches(row)), key=lambda row: (row.get("time") or "", row["key"]), reverse=True)
