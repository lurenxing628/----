"""个人工作日历的私有输入契约。不是 HTTP DTO。

个人日历的语义就是"这个人这天几点到几点上班"，所以界面和文件都以班次起止为准，工时由领域层按起止
算出来，用户不直接填。这样就没有全局日历那种"工时和推出来的班次结束互相打架"的问题。
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, Optional

from core.errors import ValidationError
from core.models.calendar_periods import normalize_periods
from core.models.workbench_calendar import (
    calendar_choice,
    calendar_date,
    calendar_note,
    operator_clock,
)
from core.models.workbench_resource_input import resource_object

#: 一次范围清除最多覆盖的天数，与日历文件的跨度上限一致。
MAX_OPERATOR_RANGE_DAYS = 1096
_FIELDS = frozenset(("type", "shiftStart", "shiftEnd", "eff", "allowNormal", "allowUrgent", "note", "periods"))
_INPUTS = {
    "upsert": frozenset(("date", "fields")),
    "delete": frozenset(("date",)),
    "range_clear": frozenset(("start_date", "end_date")),
}


def _efficiency(raw: Any, path: str) -> float:
    if type(raw) not in (int, float):
        raise ValidationError("效率必须填数字。", field=path)
    try:
        number = float(raw)
    except OverflowError as exc:
        raise ValidationError("效率须大于 0 且不超过 200%。", field=path) from exc
    if not math.isfinite(number) or number <= 0 or number > 200:
        raise ValidationError("效率须大于 0 且不超过 200%。", field=path)
    return number


def _clock_value(key: str, raw: Any, path: str) -> Optional[str]:
    if raw is None:
        if key == "shiftStart":
            raise ValidationError("班次开始必须填写。", field=path)
        return None
    return operator_clock(raw, path)


def _field_value(key: str, raw: Any) -> Any:
    path = "fields." + key
    if key == "periods":
        return normalize_periods(raw)
    if key == "eff":
        return _efficiency(raw, path)
    if key in ("shiftStart", "shiftEnd"):
        return _clock_value(key, raw, path)
    if key == "note":
        return calendar_note(raw, path)
    return calendar_choice(key, raw, path)


def apply_rest_day_rules(fields: Dict[str, Any]) -> None:
    rest = {"allowNormal": "no", "allowUrgent": "no"}
    for key, expected in rest.items():
        if key in fields and fields[key] != expected:
            raise ValidationError("休息日的普通件和急件都不可排产。", field="fields." + key)
    if fields.get("periods"):
        raise ValidationError("休息日不能填写工作时段。", field="fields.periods")
    fields.update(rest)
    # 休息日没有班次可言，交给领域层按零工时处理。
    fields.pop("shiftStart", None)
    fields.pop("shiftEnd", None)


def _fields(value: Any) -> Dict[str, Any]:
    fields = resource_object(value, _FIELDS, "fields")
    result = {key: _field_value(key, raw) for key, raw in fields.items()}
    if result.get("type") == "rest":
        apply_rest_day_rules(result)
    elif "shiftStart" not in result and not result.get("periods"):
        raise ValidationError("上班的日子必须填班次开始时刻。", field="fields.shiftStart")
    return result


def normalize_operator_calendar_input(action: str, payload: Any) -> Dict[str, Any]:
    """纯输入规范化：不读库、不看时钟、不取默认行。

    upsert: {date, fields:{type, shiftStart, shiftEnd?, eff, allowNormal, allowUrgent, note?}}
    delete: {date}。range_clear: {start_date, end_date}，含首尾。
    工时不在字段里：它由班次起止算出来，见模块说明。
    """
    if type(action) is not str or action not in _INPUTS:
        raise ValidationError("不支持的个人日历操作。", field="action")
    payload = resource_object(payload, _INPUTS[action], "input")
    if action == "range_clear":
        start = calendar_date(payload.get("start_date"), "start_date")
        end = calendar_date(payload.get("end_date"), "end_date")
        count = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        if not 1 <= count <= MAX_OPERATOR_RANGE_DAYS:
            raise ValidationError(
                f"日期范围必须有序，且包含首尾不超过 {MAX_OPERATOR_RANGE_DAYS} 天。", field="end_date")
        return {"start_date": start, "end_date": end}
    result: Dict[str, Any] = {"date": calendar_date(payload.get("date"))}
    if action == "upsert":
        fields = _fields(payload.get("fields", {}))
        if "type" not in fields:
            raise ValidationError("请选择这一天是上班还是休息。", field="fields.type")
        result["fields"] = fields
    return result


__all__ = [
    "MAX_OPERATOR_RANGE_DAYS",
    "apply_rest_day_rules",
    "normalize_operator_calendar_input",
]
