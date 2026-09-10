"""One-run input only. No ScheduleConfig mutation or business-code selection."""

import re
from datetime import date, datetime, timedelta

from core.models.workbench_command import WorkbenchCommandRejected

MAX_BATCH_REFS = 5000
INPUT_FIELDS = ("batch_refs", "start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy")


def reject(message):
    raise WorkbenchCommandRejected("invalid_input", message, 422)


def public_ref(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{48}", value) is not None


def local_date(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        reject("计划窗口必须填写完整日期。")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "计划窗口日期不存在。", 422) from exc
    if parsed.year < 1900 or parsed == date.max:
        reject("计划窗口日期超出支持范围。")
    return parsed


def normalize_preflight_input(value):
    if not isinstance(value, dict) or set(value) != set(INPUT_FIELDS):
        reject("排产前检查参数不完整或包含不支持的字段。")
    refs = value["batch_refs"]
    if not isinstance(refs, list) or len(refs) > MAX_BATCH_REFS or not all(public_ref(ref) for ref in refs):
        reject("请选择最多5000个明确批次，不能使用批次号或全库范围替代永久引用。")
    if len(set(refs)) != len(refs):
        reject("批次选择存在重复引用，请重新核对范围。")
    start, end = local_date(value["start_date"]), local_date(value["end_date"])
    if end < start:
        reject("结束日期不能早于开始日期。")
    if type(value["ready_check"]) is not bool or value["missing_resource_policy"] not in ("auto_assign", "exclude"):
        reject("齐套检查或缺资源策略不正确。")
    if value["completed_policy"] != "preserve_actuals":
        reject("已有开工和完工事实必须保留，不能解除执行保护。")
    return {**value, "batch_refs": sorted(refs)}


def preflight_window(value):
    start = datetime.combine(local_date(value["start_date"]), datetime.min.time())
    end = datetime.combine(local_date(value["end_date"]) + timedelta(days=1), datetime.min.time())
    return start.isoformat(), end.isoformat()


def issue(code, message, **context):
    return {"code": code, "message": message, **context}
