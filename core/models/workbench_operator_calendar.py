"""个人工作日历的私有输入契约。不是 HTTP DTO。

个人日历的语义就是"这个人这天几点到几点上班"，所以界面和文件都以班次起止为准，工时由领域层按起止
算出来，用户不直接填。这样就没有全局日历那种"工时和推出来的班次结束互相打架"的问题。
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from core.errors import ValidationError

#: 一次范围清除最多覆盖的天数，与日历文件的跨度上限一致。
MAX_OPERATOR_RANGE_DAYS = 1096
_FIELDS = frozenset(("type", "shiftStart", "shiftEnd", "eff", "allowNormal", "allowUrgent", "note"))
_DOMAIN_FIELDS = {"shiftStart": "shift_start", "shiftEnd": "shift_end", "eff": "efficiency",
                  "allowNormal": "allow_normal", "allowUrgent": "allow_urgent", "note": "remark",
                  "type": "day_type"}
_INPUTS = {
    "upsert": frozenset(("date", "fields")),
    "delete": frozenset(("date",)),
    "range_clear": frozenset(("start_date", "end_date")),
}
TIME = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]\Z")


def operator_calendar_date(value: Any, field: str = "date") -> str:
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValidationError("日期必须为 YYYY-MM-DD。", field=field)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValidationError("日期不存在，请核对年月日。", field=field) from exc


def operator_clock(value: Any, field: str) -> str:
    """班次时刻只收 HH:MM，秒必须为零，跨零点由结束早于开始表达。"""
    if type(value) is not str or TIME.fullmatch(value) is None:
        raise ValidationError("时刻必须填成 08:00 这样的 24 小时制，分钟到分为止。", field=field)
    return value


def _object(value: Any, allowed, field: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise ValidationError("提交内容格式不对，这次操作没有执行。请刷新页面后重试。", field=field)
    if any(type(key) is not str or key not in allowed for key in value):
        raise ValidationError("提交内容含有不支持的项，这次操作没有执行。请刷新页面后重试。", field=field)
    return value


def _efficiency(raw: Any, path: str) -> float:
    if type(raw) is bool or type(raw) not in (int, float):
        raise ValidationError("效率必须填数字。", field=path)
    number = float(raw)
    if not math.isfinite(number) or number <= 0 or number > 200:
        raise ValidationError("效率须大于 0 且不超过 200%。", field=path)
    return number


def _clock_value(key: str, raw: Any, path: str) -> Optional[str]:
    if raw is None:
        if key == "shiftStart":
            raise ValidationError("班次开始必须填写。", field=path)
        return None
    return operator_clock(raw, path)


def _note(raw: Any, path: str) -> Optional[str]:
    if raw is None:
        return None
    if type(raw) is not str:
        raise ValidationError("备注必须是文字或 null。", field=path)
    return raw.strip() or None


def _choice(key: str, raw: Any, path: str) -> str:
    choices = ("work", "rest") if key == "type" else ("yes", "no")
    if type(raw) is not str or raw not in choices:
        raise ValidationError("请选择有效的日历选项。", field=path)
    return raw


def _field_value(key: str, raw: Any) -> Any:
    path = "fields." + key
    if key == "eff":
        return _efficiency(raw, path)
    if key in ("shiftStart", "shiftEnd"):
        return _clock_value(key, raw, path)
    if key == "note":
        return _note(raw, path)
    return _choice(key, raw, path)


def _fields(value: Any) -> Dict[str, Any]:
    fields = _object(value, _FIELDS, "fields")
    result = {key: _field_value(key, raw) for key, raw in fields.items()}
    if result.get("type") == "rest":
        rest = {"allowNormal": "no", "allowUrgent": "no"}
        if any(key in result and result[key] != expected for key, expected in rest.items()):
            raise ValidationError("休息日的普通件和急件都不可排产。", field="fields")
        result.update(rest)
        # 休息日没有班次可言，交给领域层按零工时处理。
        result.pop("shiftEnd", None)
    elif "shiftStart" not in result:
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
    payload = _object(payload, _INPUTS[action], "input")
    if action == "range_clear":
        start = operator_calendar_date(payload.get("start_date"), "start_date")
        end = operator_calendar_date(payload.get("end_date"), "end_date")
        count = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        if not 1 <= count <= MAX_OPERATOR_RANGE_DAYS:
            raise ValidationError(
                f"日期范围必须有序，且包含首尾不超过 {MAX_OPERATOR_RANGE_DAYS} 天。", field="end_date")
        return {"start_date": start, "end_date": end}
    result: Dict[str, Any] = {"date": operator_calendar_date(payload.get("date"))}
    if action == "upsert":
        fields = _fields(payload.get("fields", {}))
        if "type" not in fields:
            raise ValidationError("请选择这一天是上班还是休息。", field="fields.type")
        result["fields"] = fields
    return result


def operator_domain_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """映射成领域层字段名与单位；取值合法性仍归 CalendarAdmin。"""
    patch = {_DOMAIN_FIELDS[name]: value for name, value in fields.items()}
    if "type" in fields:
        patch["day_type"] = "workday" if fields["type"] == "work" else "holiday"
    if "eff" in fields:
        patch["efficiency"] = fields["eff"] / 100.0
    return patch


def operator_range_dates(start_date: str, end_date: str) -> List[str]:
    start = date.fromisoformat(start_date)
    count = (date.fromisoformat(end_date) - start).days + 1
    return [(start + timedelta(days=offset)).isoformat() for offset in range(count)]
