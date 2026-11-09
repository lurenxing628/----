"""Structured work periods. Clock text is only a label; offsets own night shifts.

本模块是工作时段与休息日规则的领域实现，报错只用中立字段名（periods / allowNormal / allowUrgent）；
工作台表单、默认工作时间接口、班次档、日历文件各自把它映射到自己的路径，各只映射一次。
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, NoReturn

from core.errors import ValidationError
from core.shared.strict_json import load_strict_json

MAX_WORK_PERIODS = 8
DEFAULT_WORK_PERIODS = [{"start": "08:30", "end": "11:50", "day_offset": 0},
                        {"start": "13:30", "end": "17:30", "day_offset": 0}]

_CLOCK_RE = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]\Z")


def _clock(value):
    if not isinstance(value, str) or not _CLOCK_RE.fullmatch(value):
        raise ValidationError("工作时段请填写小时和分钟，例如 08:00。", field="periods")
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def normalize_periods(value: Any) -> List[Dict[str, Any]]:
    """[] explicitly means no work. Never sort invalid input."""
    if not isinstance(value, list):
        raise ValidationError("工作时段必须按列表提交。", field="periods")
    if len(value) > MAX_WORK_PERIODS:
        raise ValidationError("工作时段必须逐段填写，每天最多 8 段。", field="periods")
    result, previous_end, first_start = [], None, None
    for item in value:
        item, low, high = _period_bounds(item, first=not result)
        first_start = low if first_start is None else first_start
        if previous_end is not None and low < previous_end:
            raise ValidationError("工作时段应按时间先后填写，不能重叠。", field="periods")
        if high > first_start + 1440:
            raise ValidationError("一天的全部工作时段不能跨越超过 24 小时。", field="periods")
        result.append(item)
        previous_end = high
    return result


def _period_bounds(item, *, first):
    if not isinstance(item, dict) or set(item) - {"start", "end", "day_offset"}:
        raise ValidationError("工作时段字段不正确。", field="periods")
    offset = item.get("day_offset", 0)
    if type(offset) is not int or offset not in (0, 1) or (first and offset != 0):
        raise ValidationError("首段须从当天开始，后续时段可选择当天或次日。", field="periods")
    start, end = _clock(item.get("start")), _clock(item.get("end"))
    low = start + offset * 1440
    high = end + offset * 1440 + (1440 if end <= start else 0)
    return {"start": item["start"], "end": item["end"], "day_offset": offset}, low, high


def apply_rest_day_rules(fields: Dict[str, Any]) -> None:
    """休息日规则的唯一实现：不上班，没有工作时段，普通件和急件都不可排产。

    全局与个人日历的单日、范围表单和个人日历文件共用；班次档只有时段，走它的时段部分 ``reject_rest_day_periods``。
    省略的项按此补齐，填了相反的值直接拒绝，不替用户改。全局日历文件按导入路线图 4.5 的裁决保留“假期加班”，不走这里。
    字段名沿用工作台日历补丁的口径（periods / allowNormal / allowUrgent）。
    """
    for key in ("allowNormal", "allowUrgent"):
        if fields.get(key, "no") != "no":
            raise ValidationError("休息日的普通件和急件都不可排产。", field=key)
    reject_rest_day_periods(fields.get("periods", []))
    fields.update(periods=[], allowNormal="no", allowUrgent="no")


def reject_rest_day_periods(periods: List[Dict[str, Any]]) -> None:
    """休息日没有工作时段：已规范化的时段非空就拒绝。"""
    if periods:
        raise ValidationError("休息日不能填写工作时段。", field="periods")


def decode_periods(raw: Any) -> List[Dict[str, Any]]:
    return normalize_periods(load_stored_periods(raw))


def _corrupt_periods() -> NoReturn:
    raise ValidationError("已保存的工作时段损坏，请重新维护该日历或班次。", field="periods") from None


def load_stored_periods(raw: Any) -> Any:
    """Strictly decode stored periods text; the caller normalizes the list once."""
    if type(raw) is not str:
        _corrupt_periods()
    value = load_strict_json(raw, on_malformed=_corrupt_periods)
    if value is None:
        raise ValidationError("已保存的工作时段不能为空值。", field="periods")
    return value


def encode_periods(periods: List[Dict[str, Any]]) -> str:
    """Stored text for periods already produced by ``normalize_periods``."""
    return json.dumps(periods, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _minutes(clock_text: str) -> int:
    return int(clock_text[:2]) * 60 + int(clock_text[3:])


def period_windows(day, periods):
    base = datetime.combine(day, datetime.min.time())
    return tuple((base + timedelta(minutes=_minutes(p["start"]) + p["day_offset"] * 1440),
                  base + timedelta(minutes=_minutes(p["end"]) + p["day_offset"] * 1440
                                   + (1440 if p["end"] <= p["start"] else 0))) for p in periods)


def period_hours(periods):
    total_minutes = 0
    for p in periods:
        start, end = _minutes(p["start"]), _minutes(p["end"])
        total_minutes += end - start + (1440 if end <= start else 0)
    return total_minutes / 60


def shift_pattern_fields(row):
    return {"day_offset": row["day_offset"], "is_rest": bool(row["is_rest"]), "periods": decode_periods(row["periods_json"])}
