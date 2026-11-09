"""个人工作日历的私有输入契约。不是 HTTP DTO。

个人日历与全局日历一样以工作时段为准，工时与首尾包络时刻统一由领域层按工作时段派生，用户不直接填工时。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

from core.errors import ValidationError
from core.models.workbench_calendar import calendar_date, calendar_fields
from core.models.workbench_resource_input import resource_object

#: 一次范围清除最多覆盖的天数，与日历文件的跨度上限一致。
MAX_OPERATOR_RANGE_DAYS = 1096
_INPUTS = {
    "upsert": frozenset(("date", "fields")),
    "delete": frozenset(("date",)),
    "range_clear": frozenset(("start_date", "end_date")),
}


def normalize_operator_calendar_input(action: str, payload: Any) -> Dict[str, Any]:
    """纯输入规范化：不读库、不看时钟、不取默认行。

    upsert: {date, fields:{type, periods?, eff, allowNormal, allowUrgent, note?}}
    delete: {date}。range_clear: {start_date, end_date}，含首尾。
    工时不在字段里：它由工作时段算出来，见模块说明。
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
        fields = calendar_fields(payload.get("fields", {}))
        if "type" not in fields:
            raise ValidationError("请选择这一天是上班还是休息。", field="fields.type")
        result["fields"] = fields
    return result


__all__ = [
    "MAX_OPERATOR_RANGE_DAYS",
    "normalize_operator_calendar_input",
]
