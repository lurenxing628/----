"""One-run input only. No ScheduleConfig mutation or business-code selection."""

import re
from datetime import date, datetime, timedelta
from typing import NoReturn

from core.models.workbench_command import WorkbenchCommandRejected

MAX_BATCH_REFS = 5000
INPUT_FIELDS = ("batch_refs", "start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy")
# 可选项：不带 material_strategy 按整批齐套；不带 hold_window 按交付设置推算不重排时段（见 hold_window_bounds）。
OPTIONAL_FIELDS = frozenset(("material_strategy", "hold_window"))
_HOLD_MESSAGE = "不重排时段要填完整的开始和结束时刻（精确到分），开始要早于结束，并且在排产日期范围内。"


def reject(message) -> NoReturn:
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
    if not isinstance(value, dict) or set(value) - OPTIONAL_FIELDS != set(INPUT_FIELDS):
        reject("排产检查的条件不完整或有多余项，请刷新页面后重新选择。")
    refs = _batch_refs(value["batch_refs"])
    start, end = local_date(value["start_date"]), local_date(value["end_date"])
    if end < start:
        reject("结束日期不能早于开始日期。")
    if type(value["ready_check"]) is not bool or value["missing_resource_policy"] not in ("auto_assign", "exclude"):
        reject("齐套检查或缺设备人员时的规则不正确，请重新选择。")
    if value["completed_policy"] != "preserve_actuals":
        reject("已开工和已完工的记录必须保留，不能取消保护。")
    strategy = value.get("material_strategy", "strict")
    if strategy not in ("strict", "stage", "split"):
        reject("请选择整批齐套、按工序齐套或预检分批开工。")
    if strategy != "strict" and not value["ready_check"]:
        reject("按工序放行和分批开工需要开启齐套检查。")
    if "hold_window" in value:
        _hold_window(value["hold_window"], start, end)
    return {**value, "batch_refs": sorted(refs)}


def _batch_refs(refs):
    if not isinstance(refs, list) or len(refs) > MAX_BATCH_REFS or not all(public_ref(ref) for ref in refs):
        reject("请从批次列表里勾选批次，一次最多 5000 批。")
    if len(set(refs)) != len(refs):
        reject("批次选择里有重复，请重新核对范围。")
    return refs


def _minute(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}", value) is None:
        reject(_HOLD_MESSAGE)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        reject(_HOLD_MESSAGE)


def _hold_window(value, start_day, end_day):
    """本次不重排时段：null 表示不设；对象两端精确到分，落在排产日期范围 [起日 00:00, 止日次日 00:00] 内。"""
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"start", "end"}:
        reject(_HOLD_MESSAGE)
    start, end = _minute(value["start"]), _minute(value["end"])
    low = datetime.combine(start_day, datetime.min.time())
    if not low <= start < end or end > datetime.combine(end_day, datetime.min.time()) + timedelta(days=1):
        reject(_HOLD_MESSAGE)


def stored_hold_window_valid(value):
    """排产记录里存下的不重排时段读得懂：null，或两端精确到分、开始早于结束。不抛异常，供回显判断数据缺口。"""
    if value is None:
        return True
    if not isinstance(value, dict) or set(value) != {"start", "end"}:
        return False
    try:
        start, end = (datetime.fromisoformat(value[key]) for key in ("start", "end"))
    except (TypeError, ValueError):
        return False
    return all(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}", value[key]) for key in ("start", "end")) and start < end


def hold_window_bounds(value):
    """已校验的 hold_window 对象转成 (开始, 结束)；null 返回 None。"""
    if value is None:
        return None
    return datetime.fromisoformat(value["start"]), datetime.fromisoformat(value["end"])


def preflight_window(value):
    start = datetime.combine(local_date(value["start_date"]), datetime.min.time())
    end = datetime.combine(local_date(value["end_date"]) + timedelta(days=1), datetime.min.time())
    return start.isoformat(), end.isoformat()


def issue(code, message, **context):
    return {"code": code, "message": message, **context}
