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
        reject("排产日期范围必须填完整日期。")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "排产日期范围里的日期不存在。", 422) from exc
    if parsed.year < 1900 or parsed == date.max:
        reject("排产日期范围超出支持的年份。")
    return parsed


def normalize_preflight_input(value):
    if not isinstance(value, dict) or set(value) != set(INPUT_FIELDS):
        reject("排产检查的条件不完整或有多余项，请刷新页面后重新选择。")
    refs = value["batch_refs"]
    if not isinstance(refs, list) or len(refs) > MAX_BATCH_REFS or not all(public_ref(ref) for ref in refs):
        reject("请从批次列表里勾选批次，一次最多 5000 批。")
    if len(set(refs)) != len(refs):
        reject("批次选择里有重复，请重新核对范围。")
    start, end = local_date(value["start_date"]), local_date(value["end_date"])
    if end < start:
        reject("结束日期不能早于开始日期。")
    if type(value["ready_check"]) is not bool or value["missing_resource_policy"] not in ("auto_assign", "exclude"):
        reject("齐套检查或缺设备人员时的规则不正确，请重新选择。")
    if value["completed_policy"] != "preserve_actuals":
        reject("已开工和已完工的记录必须保留，不能取消保护。")
    return {**value, "batch_refs": sorted(refs)}


def preflight_window(value):
    start = datetime.combine(local_date(value["start_date"]), datetime.min.time())
    end = datetime.combine(local_date(value["end_date"]) + timedelta(days=1), datetime.min.time())
    return start.isoformat(), end.isoformat()


def issue(code, message, **context):
    return {"code": code, "message": message, **context}
