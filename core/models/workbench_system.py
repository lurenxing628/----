"""System-only request contracts; no resource namespace or database identities."""

import re
from datetime import datetime
from typing import Dict, Optional, TypedDict, overload

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
RESTORE_DISABLED = "此功能尚未开通，现在不能切换数据库。"
LOG_LEVELS = ("INFO", "WARNING", "ERROR", "DEBUG", "CRITICAL", "UNKNOWN")
# 日志导出里给用户看的中文标签；前端 SystemMaintenanceRecords.jsx 有同名字典，两边措辞必须一致。
LOG_SOURCE_LABELS = {"aps.log": "主日志（aps.log）", "aps_error.log": "错误日志（aps_error.log）",
                     "launcher.log": "启动日志（launcher.log）", "OperationLogs": "操作记录"}
LOG_RECORD_TYPE_LABELS = {"runtime": "运行日志", "operation": "操作记录"}
LOG_RECORD_STATUS_LABELS = {"recorded": "已记录"}
LOG_LEVEL_LABELS = {"INFO": "信息", "WARNING": "警告", "ERROR": "错误",
                    "DEBUG": "调试", "CRITICAL": "严重", "UNKNOWN": "未知"}
# 操作日志历史写的是 WARN，运行日志文件写的是 WARNING；读取时统一成 WARNING，存储不动。
_LOG_LEVEL_ALIASES = {"WARN": "WARNING"}


@overload
def normalize_log_level(value: str) -> str: ...


@overload
def normalize_log_level(value: None) -> None: ...


def normalize_log_level(value: Optional[str]) -> Optional[str]:
    """把同义的日志级别写法归一，供筛选匹配和返回值共用。"""
    if value is None:
        return None
    return _LOG_LEVEL_ALIASES.get(value, value)


def log_level_label(value: Optional[str]) -> str:
    """导出与展示用的中文级别名。"""
    level = normalize_log_level(value)
    if level is None:
        return "未读取"
    return LOG_LEVEL_LABELS.get(level, level or "未读取")


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
        raise WorkbenchCommandRejected("invalid_input", "提交内容不完整或含有不支持的项，这次操作没有执行。请刷新页面后重试。", 400)
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
            raise WorkbenchCommandRejected("invalid_input", "维护设置里有一项填写不对，这次保存没有生效。请检查开关和天数、分钟数后重新保存。", 422)
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
                raise WorkbenchCommandRejected("invalid_input", "筛选日期填写不对，请按 2026-09-13 这样填写。", 422) from exc
    if result["start"] and result["end"] and result["start"] > result["end"]:
        raise WorkbenchCommandRejected("invalid_input", "开始日期不能晚于结束日期。", 422)


def _query_pagination(value):
    result = {}
    for key, default in (("page", 1), ("page_size", 10)):
        raw = value.get(key, str(default))
        if not isinstance(raw, str) or not re.fullmatch(r"[1-9]\d{0,6}", raw):
            raise WorkbenchCommandRejected("invalid_input", "翻页位置已失效，请回到第 1 页重新查询。", 400)
        result[key] = int(raw)
    if result["page_size"] not in (10, 25, 50):
        raise WorkbenchCommandRejected("invalid_input", "每页只能选 10、25 或 50 条。", 400)
    return result


def query_input(value, kind) -> SystemQuery:
    allowed = {"query", "type", "status", "level", "file", "start", "end", "page", "page_size", "snapshot_ref"}
    object_fields(value, (), allowed)
    result: Dict[str, str] = {}
    for key in allowed - {"page", "page_size", "snapshot_ref"}:
        item = value.get(key, "")
        if not isinstance(item, str) or len(item) > 200:
            raise WorkbenchCommandRejected("invalid_input", "筛选条件最多 200 个字。", 400)
        result[key] = item
    _query_dates(result)
    result["level"] = normalize_log_level(result["level"])
    choices = {"type": ("", "runtime", "operation") if kind == "logs" else
               ("", "manual", "auto", "before_restore", "unknown", "restore", "cleanup"),
               "status": ("", "recorded") if kind == "logs" else ("", "unverified", "unknown") + tuple(sorted(JOB_STATES)),
               "level": ("",) + LOG_LEVELS,
               "file": ("", "aps.log", "aps_error.log", "launcher.log", "OperationLogs")}
    if any(result[key] not in items for key, items in choices.items()):
        raise WorkbenchCommandRejected("invalid_input", "不支持这个日志来源、类型或状态的筛选条件，请重新选择。", 400)
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
