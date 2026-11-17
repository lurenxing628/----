"""One-run input only. No ScheduleConfig mutation or business-code selection."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import NoReturn, Sequence

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_load_limits import MAX_WINDOW_BATCHES, too_many_batches
from core.shared.key_sets import keys_conform
from core.shared.refs import is_ref

SCHEDULING_PREFERENCES_KEY = "workbench_scheduling_preferences"
SCHEDULING_PREFERENCES_ACTION = "scheduling.preferences.save"
SCHEDULING_PREFERENCES_SUBJECT = "scheduling-preferences"
INPUT_FIELDS = ("batch_refs", "start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy")
# 提交时可省略的项：不带 material_strategy 按整批齐套（规范后的输入总带上它）；不带 hold_window 按交付设置推算
# 不重排时段（见 hold_window_bounds）。
OPTIONAL_FIELDS = frozenset(("material_strategy", "hold_window", "time_budget_seconds"))
# 排产记录存下的是规范后的输入：规范补上 material_strategy、排产检查补上 time_budget_seconds，只有 hold_window 不设就不带。
STORED_OPTIONAL_FIELDS = frozenset(("hold_window",))
STORED_INPUT_FIELDS = frozenset(INPUT_FIELDS) | (OPTIONAL_FIELDS - STORED_OPTIONAL_FIELDS)
_HOLD_MESSAGE = "不重排时段要填完整的开始和结束时刻（精确到分），开始要早于结束，并且在排产日期范围内。"
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_MINUTE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]):[0-5][0-9]")


def reject(message, *, fields: Sequence[str] = ()) -> NoReturn:
    raise WorkbenchCommandRejected("invalid_input", message, 422, fields=fields)


def local_date(value, path):
    if not isinstance(value, str) or _DATE_RE.fullmatch(value) is None:
        reject("排产日期范围必须填完整日期。", fields=(path,))
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "排产日期范围里的日期不存在。", 422, fields=(path,)) from exc
    if parsed.year < 1900 or parsed == date.max:
        reject("排产日期范围超出支持的年份。", fields=(path,))
    return parsed


def normalize_preflight_input(value):
    if not keys_conform(value, INPUT_FIELDS, OPTIONAL_FIELDS):
        reject("排产检查的条件不完整或有多余项，请刷新页面后重新选择。")
    strategy = value.get("material_strategy", "strict")
    refs = _checked_values(value, strategy)
    return {**value, "material_strategy": strategy, "batch_refs": sorted(refs)}


def check_stored_input(value):
    """排产记录存下的规范输入（已解码的对象）：键集与值域按受理时同一套规则核对，不补任何默认值；
    不合格抛 WorkbenchCommandRejected。"""
    if not keys_conform(value, STORED_INPUT_FIELDS, STORED_OPTIONAL_FIELDS):
        reject("排产记录存下的排产条件不完整或有多余项。")
    _checked_values(value, value["material_strategy"])


def _checked_values(value, strategy):
    refs = _batch_refs(value["batch_refs"])
    dates = run_dates(value)
    if dates.end_date < dates.start.date():
        reject("结束日期不能早于开始日期。", fields=("end_date",))
    if type(value["ready_check"]) is not bool or value["missing_resource_policy"] not in ("auto_assign", "exclude"):
        reject("齐套检查或缺设备人员时的规则不正确，请重新选择。")
    if value["completed_policy"] != "preserve_actuals":
        reject("已开工和已完工的记录必须保留，不能取消保护。")
    if strategy not in ("strict", "stage"):
        reject("请选择整批齐套或按工序齐套。")
    if strategy == "stage" and not value["ready_check"]:
        reject("按工序齐套需要开启齐套检查。")
    if "hold_window" in value:
        _hold_window(value["hold_window"], dates)
    if "time_budget_seconds" in value and (type(value["time_budget_seconds"]) is not int or value["time_budget_seconds"] < 1):
        reject("计算时间要填大于或等于 1 的整数秒数。")
    return refs


def _batch_refs(refs):
    if not isinstance(refs, list):
        reject("请从批次列表里勾选批次。", fields=("batch_refs",))
    if len(refs) > MAX_WINDOW_BATCHES:
        reject(too_many_batches(MAX_WINDOW_BATCHES), fields=("batch_refs",))
    if not all(is_ref(ref) for ref in refs):
        reject("请从批次列表里勾选批次。", fields=("batch_refs",))
    if len(set(refs)) != len(refs):
        reject("批次选择里有重复，请重新核对范围。")
    return refs


def _minute(value):
    if not isinstance(value, str) or _MINUTE_RE.fullmatch(value) is None:
        reject(_HOLD_MESSAGE)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        reject(_HOLD_MESSAGE)


def _hold_window(value, dates):
    """本次不重排时段：null 表示不设；对象两端精确到分，落在排产日期范围 [起日 00:00, 止日次日 00:00] 内。"""
    if value is None:
        return
    if not keys_conform(value, ("start", "end")):
        reject(_HOLD_MESSAGE)
    start, end = _minute(value["start"]), _minute(value["end"])
    if not dates.start <= start < end or end > dates.end_exclusive:
        reject(_HOLD_MESSAGE)


def hold_window_bounds(value):
    """已校验的 hold_window 对象转成 (开始, 结束)；null 返回 None。"""
    if value is None:
        return None
    return datetime.fromisoformat(value["start"]), datetime.fromisoformat(value["end"])


@dataclass(frozen=True)
class RunDates:
    """排产日期范围：start 是起日 00:00，end_date 是止日（含当天），end_exclusive 是止日次日 00:00。"""

    start: datetime
    end_date: date

    @property
    def end_exclusive(self) -> datetime:
        return datetime.combine(self.end_date + timedelta(days=1), datetime.min.time())


def run_dates(settings) -> RunDates:
    """start_date/end_date 的唯一转换：准入（_checked_values）和准入后的读者都用它。
    同一作用域只调一次，结果随准入产物（如 PreparedPreflight.dates）或显式参数往下传。"""
    return RunDates(datetime.combine(local_date(settings["start_date"], "start_date"), datetime.min.time()),
                    local_date(settings["end_date"], "end_date"))


def preflight_window(dates: RunDates):
    """排产日期范围两端 [起日 00:00, 止日次日 00:00) 的本地时刻文本。"""
    return dates.start.isoformat(), dates.end_exclusive.isoformat()


def issue(code, message, **context):
    return {"code": code, "message": message, **context}
