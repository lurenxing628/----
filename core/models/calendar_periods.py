"""Structured work periods. Clock text is only a label; offsets own night shifts."""

import json
import re
from datetime import datetime, timedelta

from core.errors import ValidationError

MAX_WORK_PERIODS = 8
DEFAULT_WORK_PERIODS = [{"start": "08:30", "end": "11:50", "day_offset": 0},
                        {"start": "13:30", "end": "17:30", "day_offset": 0}]


def _clock(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValidationError("工作时段请填写小时和分钟，例如 08:00。", field="periods")
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def normalize_periods(value):
    """None means legacy; [] explicitly means no work. Never sort invalid input."""
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > MAX_WORK_PERIODS:
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


def decode_periods(raw):
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise ValidationError("已保存的工作时段损坏，请重新维护该日历或班次。", field="periods") from None
    # JSON null is not a valid stored alternative to legacy SQL NULL.
    if value is None:
        raise ValidationError("已保存的工作时段不能为空值。", field="periods")
    return normalize_periods(value)


def encode_periods(value):
    normalized = normalize_periods(value)
    return None if normalized is None else json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def period_windows(day, periods):
    base = datetime.combine(day, datetime.min.time())
    return tuple((base + timedelta(minutes=_clock(p["start"]) + p["day_offset"] * 1440),
                  base + timedelta(minutes=_clock(p["end"]) + p["day_offset"] * 1440
                                   + (1440 if p["end"] <= p["start"] else 0))) for p in periods)


def period_hours(periods):
    return sum((high - low).total_seconds() for low, high in
               period_windows(datetime(2000, 1, 1).date(), periods)) / 3600


def payload_periods(payload):
    """The public array wins only when explicitly provided, including an empty day."""
    return normalize_periods(payload["periods"]) if "periods" in payload else decode_periods(payload.get("periods_json"))


def period_summary(periods, start="08:00"):
    """Legacy display columns remain an envelope; shift_hours is the actual sum."""
    if not periods:
        return start, None, 0.0
    return periods[0]["start"], periods[-1]["end"], period_hours(periods)


def shift_pattern_fields(row):
    return {**{key: row[key] for key in ("day_offset", "shift_start", "shift_end")},
            "is_rest": bool(row["is_rest"]), "periods": decode_periods(row.get("periods_json"))}
