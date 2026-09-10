"""Private calendar input and server-held preview contracts, not HTTP DTOs."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List

from core.errors import ValidationError

# Reuse CalendarEngine.MAX_CALENDAR_DAYS' domain magnitude, counting inclusive dates.
# The prototype has no day-count cap; this is an adapter admission bound, not a UI limit.
MAX_CALENDAR_RANGE_DAYS = 36500
CALENDAR_PREVIEW_TTL_SECONDS = 900
_FIELDS = frozenset(("type", "hours", "eff", "allowNormal", "allowUrgent", "note"))
_DOMAIN_FIELDS = {"hours": "shift_hours", "eff": "efficiency", "allowNormal": "allow_normal",
                  "allowUrgent": "allow_urgent", "note": "remark", "type": "day_type"}
_INPUTS = {
    "upsert": frozenset(("date", "fields")),
    "delete": frozenset(("date",)),
    "preview": frozenset(("start_date", "end_date", "scope", "operation", "fields")),
    "confirm": frozenset(("preview_ref",)),
}


def calendar_date(value: Any, field: str = "date") -> str:
    """Accept an actual ISO date only, not a timestamp or prototype zero-based key."""
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValidationError("日期必须为 YYYY-MM-DD。", field=field)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValidationError("日期不存在，请核对年月日。", field=field) from exc


def _object(value: Any, allowed, field: str) -> Dict[str, Any]:
    if type(value) is not dict:
        raise ValidationError("操作内容必须是 JSON 对象。", field=field)
    if any(type(key) is not str or key not in allowed for key in value):
        raise ValidationError("操作内容包含不允许的字段。", field=field)
    return value


def _number(value: Any, field: str, maximum: float, *, positive: bool = False) -> float:
    if type(value) not in (int, float):
        raise ValidationError("该字段必须是数字，不能是布尔值或数字字符串。", field=field)
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValidationError("数字超出范围。", field=field) from exc
    if not math.isfinite(number) or number < 0 or number > maximum or (positive and number == 0):
        raise ValidationError("数字超出范围；工时为 0 至 24，效率须大于 0 且不超过 200%。", field=field)
    return number if number else 0.0


def _field_value(key: str, raw: Any) -> Any:
    path = "fields." + key
    if key in ("hours", "eff"):
        return _number(raw, path, 24 if key == "hours" else 200, positive=key == "eff")
    if key == "note":
        if raw is None:
            return None
        if type(raw) is not str:
            raise ValidationError("备注必须是文字或 null。", field=path)
        return raw.strip() or None
    choices = ("work", "rest") if key == "type" else ("yes", "no")
    if type(raw) is not str or raw not in choices:
        raise ValidationError("请选择有效的日历选项。", field=path)
    return raw


def _fields(value: Any) -> Dict[str, Any]:
    fields = _object(value, _FIELDS, "fields")
    result = {key: _field_value(key, raw) for key, raw in fields.items()}
    if result.get("type") == "rest":
        rest = {"hours": 0.0, "allowNormal": "no", "allowUrgent": "no"}
        if any(key in result and result[key] != expected for key, expected in rest.items()):
            raise ValidationError("休息日必须为零工时，且普通件和急件均不可排产。", field="fields")
        result.update(rest)
    return result


def normalize_calendar_input(action: str, payload: Any) -> Dict[str, Any]:
    """Pure, idempotent input normalization; no DB, clock, token or default-row reads.

    upsert: {date, fields:{type:work|rest, hours:0..24, eff:(0..200] percent,
    allowNormal:yes|no, allowUrgent:yes|no, note:str|null}}. Omission is no change.
    delete: {date}. preview: {start_date,end_date,scope:all|weekday|weekend,
    operation:upsert|delete,fields:{...}}. confirm: {preview_ref} only.
    Dates/months are ISO/one-based, never the prototype's zero-based month keys.
    eff stays in percent here so normalizing twice cannot divide it twice.
    Ranges include both endpoints and admit up to 36500 dates before filtering.
    """
    if type(action) is not str or action not in _INPUTS:
        raise ValidationError("不支持的日历操作。", field="action")
    payload = _object(payload, _INPUTS[action], "input")
    if action == "confirm":
        ref = payload.get("preview_ref")
        if type(ref) is not str or re.fullmatch(r"[0-9a-f]{32}", ref) is None:
            raise ValidationError("日历预览引用无效。", field="preview_ref")
        return {"preview_ref": ref}
    if action in ("upsert", "delete"):
        result: Dict[str, Any] = {"date": calendar_date(payload.get("date"))}
        if action == "upsert":
            result["fields"] = _fields(payload.get("fields", {}))
        return result
    return _range_input(payload)


def _range_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    start = calendar_date(payload.get("start_date"), "start_date")
    end = calendar_date(payload.get("end_date"), "end_date")
    count = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if not 1 <= count <= MAX_CALENDAR_RANGE_DAYS:
        raise ValidationError(f"日期范围必须有序，且包含首尾不超过 {MAX_CALENDAR_RANGE_DAYS} 天。", field="end_date")
    scope, operation = payload.get("scope", "all"), payload.get("operation", "upsert")
    if type(scope) is not str or scope not in ("all", "weekday", "weekend"):
        raise ValidationError("请选择每天、仅工作日或仅周末。", field="scope")
    if type(operation) is not str or operation not in ("upsert", "delete"):
        raise ValidationError("范围操作只能保存或清除日历。", field="operation")
    fields = _fields(payload.get("fields", {}))
    if operation == "delete" and fields:
        raise ValidationError("清除配置不能同时设置字段。", field="fields")
    return {"start_date": start, "end_date": end, "scope": scope, "operation": operation, "fields": fields}


def calendar_domain_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Map normalized private UI units/names; validation still belongs to CalendarAdmin."""
    patch = {_DOMAIN_FIELDS[name]: value for name, value in fields.items()}
    if "type" in fields:
        patch["day_type"] = "workday" if fields["type"] == "work" else "holiday"
    if "eff" in fields:
        patch["efficiency"] = fields["eff"] / 100.0
    return patch


def calendar_range_dates(normalized: Dict[str, Any]) -> List[str]:
    """Match the prototype's weekday number, not an overridden working policy."""
    start = date.fromisoformat(normalized["start_date"])
    count = (date.fromisoformat(normalized["end_date"]) - start).days + 1
    days = [start + timedelta(days=offset) for offset in range(count)]
    return [day.isoformat() for day in days if normalized["scope"] == "all"
            or (normalized["scope"] == "weekend") == (day.weekday() >= 5)]


@dataclass(frozen=True)
class CalendarRangePreview:
    """Private server-held preview. Never reconstruct this object from client JSON.

    HTTP assembly must retain it by preview_ref with its edit context, return only
    a display projection, and pass the original object to confirm inside the outer
    WorkbenchCommandService transaction. Fingerprinting also detects accidental
    mutation of its nested dictionaries. No write_token is stored here.
    """

    preview_ref: str
    created_at: str
    expires_at: str
    request: Dict[str, Any]
    dates: List[str]
    days: List[Dict[str, Any]]
    fingerprint: str

    def facts(self) -> Dict[str, Any]:
        return {"preview_ref": self.preview_ref, "created_at": self.created_at, "expires_at": self.expires_at,
                "request": self.request, "dates": self.dates, "days": self.days}
