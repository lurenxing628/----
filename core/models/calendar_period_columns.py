"""One date per spreadsheet row, with separate readable columns per work period."""

from core.errors import ValidationError

from .calendar_periods import MAX_WORK_PERIODS, decode_periods, normalize_periods

PERIOD_COLUMNS = ("period_count",) + tuple(f"period_{index}_{field}"
                                        for index in range(2, MAX_WORK_PERIODS + 1)
                                        for field in ("start", "end", "day"))
PERIOD_CLOCKS = tuple(key for key in PERIOD_COLUMNS if key.endswith(("_start", "_end")))
PERIOD_DAYS = tuple(key for key in PERIOD_COLUMNS if key.endswith("_day"))


def period_column_label(key):
    if key == "period_count":
        return "工作时段数"
    _, index, field = key.split("_")
    return "第" + index + "段" + {"start": "开始", "end": "结束", "day": "开始日期"}[field]


def parse_period_columns(values):
    """No count means no replacement. Complete periods are required for replacement."""
    if not set(values) & set(PERIOD_COLUMNS):
        return {}
    count = str(values.get("period_count", ""))
    if not count.isdigit() or not 0 <= int(count) <= MAX_WORK_PERIODS:
        raise ValidationError(f"分段时间须同时填写工作时段数（0 至 {MAX_WORK_PERIODS}）；0 表示没有工作时段。",
                              field="period_count")
    count, periods = int(count), []
    for index in range(1, MAX_WORK_PERIODS + 1):
        start, end, day = (("shift_start", "shift_end", None) if index == 1 else
                           (f"period_{index}_start", f"period_{index}_end", f"period_{index}_day"))
        if index <= count:
            label = values.get(day, "当天") if day else "当天"
            if label not in ("当天", "次日"):
                raise ValidationError("开始日期请选择当天或次日。", field=day)
            periods.append({"start": values.get(start), "end": values.get(end), "day_offset": int(label == "次日")})
        elif index > 1 and any(key in values for key in (start, end, day)):
            raise ValidationError("填写的分段时间超过工作时段数，请核对。", field="period_count")
    return {"periods": normalize_periods(periods)}


def export_period_columns(row):
    result = dict.fromkeys(PERIOD_COLUMNS, "")
    periods = decode_periods(row.get("periods_json"))
    if periods is None:
        return result
    result["period_count"] = str(len(periods))
    if periods:
        result.update(shift_start=periods[0]["start"], shift_end=periods[0]["end"])
    for index, period in enumerate(periods[1:], 2):
        result.update({f"period_{index}_start": period["start"], f"period_{index}_end": period["end"],
                       f"period_{index}_day": "次日" if period["day_offset"] else "当天"})
    return result
