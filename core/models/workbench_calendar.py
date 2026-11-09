"""Private calendar input and server-held preview contracts, not HTTP DTOs."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from core.errors import ValidationError
from core.models.calendar_periods import apply_rest_day_rules, normalize_periods
from core.models.workbench_resource_input import resource_object

# Reuse CalendarEngine.MAX_CALENDAR_DAYS' domain magnitude, counting inclusive dates.
# The prototype has no day-count cap; this is an adapter admission bound, not a UI limit.
MAX_CALENDAR_RANGE_DAYS = 36500
CALENDAR_PREVIEW_TTL_SECONDS = 900
TIME = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]\Z")
_FIELDS = frozenset(("type", "periods", "eff", "allowNormal", "allowUrgent", "note"))
_DOMAIN_FIELDS = {"periods": "periods", "eff": "efficiency", "allowNormal": "allow_normal",
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


def operator_clock(value: Any, field: str) -> str:
    """班次时刻只收 HH:MM，秒必须为零，跨零点由结束早于开始表达。"""
    if type(value) is not str or TIME.fullmatch(value) is None:
        raise ValidationError("时刻必须填成 08:00 这样的 24 小时制，分钟到分为止。", field=field)
    return value


def _note(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if type(raw) is not str:
        raise ValidationError("备注必须是文字或 null。", field="note")
    return raw.strip() or None


def _choice(key: str, raw: Any) -> str:
    choices = ("work", "rest") if key == "type" else ("yes", "no")
    if type(raw) is not str or raw not in choices:
        raise ValidationError("请选择有效的日历选项。", field=key)
    return raw


def _eff(value: Any) -> float:
    if type(value) not in (int, float):
        raise ValidationError("效率必须填数字。", field="eff")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValidationError("效率须大于 0 且不超过 200%。", field="eff") from exc
    if not math.isfinite(number) or number <= 0 or number > 200:
        raise ValidationError("效率须大于 0 且不超过 200%。", field="eff")
    return number


def _field_value(key: str, raw: Any) -> Any:
    if key == "periods":
        return normalize_periods(raw)
    if key == "eff":
        return _eff(raw)
    if key == "note":
        return _note(raw)
    return _choice(key, raw)


def form_field_error(exc: ValidationError) -> ValidationError:
    """日历领域规则只报中立字段名；表单入口把表单里有的字段映射到界面路径 ``fields.*``，只在这一处做。

    不是表单字段的（例如跨出 9999-12-31 报的 ``date``）原样保留，不造一条界面上没有的路径。
    """
    return ValidationError(exc.message, field=f"fields.{exc.field}" if exc.field in _FIELDS else exc.field)


def calendar_fields(value: Any) -> Dict[str, Any]:
    """全局与个人日历表单共用的字段规范化（单日、范围同一份）。

    下层规则只报中立字段名，表单路径 ``fields.*`` 只在这里加一次。休息日规则见 ``apply_rest_day_rules``。
    """
    raw = resource_object(value, _FIELDS, "fields")
    try:
        result = {key: _field_value(key, val) for key, val in raw.items()}
        if result.get("type") == "rest":
            apply_rest_day_rules(result)
    except ValidationError as exc:
        raise form_field_error(exc) from exc
    return result


def normalize_calendar_input(action: str, payload: Any) -> Dict[str, Any]:
    """Pure, idempotent input normalization; no DB, clock, token or default-row reads.

    upsert: {date, fields:{type:work|rest, periods:[...], eff:(0..200] percent,
    allowNormal:yes|no, allowUrgent:yes|no, note:str|null}}. Omission is no change.
    delete: {date}. preview: {start_date,end_date,scope:all|weekday|weekend,
    operation:upsert|delete,fields:{...}}. confirm: {preview_ref} only.
    Dates/months are ISO/one-based, never the prototype's zero-based month keys.
    eff stays in percent here so normalizing twice cannot divide it twice.
    Ranges include both endpoints and admit up to 36500 dates before filtering.
    """
    if type(action) is not str or action not in _INPUTS:
        raise ValidationError("不支持的日历操作。", field="action")
    payload = resource_object(payload, _INPUTS[action], "input")
    if action == "confirm":
        ref = payload.get("preview_ref")
        if type(ref) is not str or re.fullmatch(r"[0-9a-f]{32}", ref) is None:
            raise ValidationError("这份变更清单已失效，请重新点「预览变更」。", field="preview_ref")
        return {"preview_ref": ref}
    if action in ("upsert", "delete"):
        result: Dict[str, Any] = {"date": calendar_date(payload.get("date"))}
        if action == "upsert":
            result["fields"] = calendar_fields(payload.get("fields", {}))
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
    fields = calendar_fields(payload.get("fields", {}))
    if operation == "delete" and fields:
        raise ValidationError("选择清除设置时不能再填其他项。", field="fields")
    return {"start_date": start, "end_date": end, "scope": scope, "operation": operation, "fields": fields}


def calendar_domain_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Map normalized private UI units/names; validation still belongs to CalendarAdmin."""
    patch = {_DOMAIN_FIELDS[name]: value for name, value in fields.items()}
    if "type" in fields:
        patch["day_type"] = "workday" if fields["type"] == "work" else "holiday"
    if "eff" in fields:
        patch["efficiency"] = fields["eff"] / 100.0
    return patch


def require_periods_when_rest_turns_work(day: str, row: Optional[Dict[str, Any]], patch: Dict[str, Any]) -> None:
    """原来存成假期的一天改成工作日时，必须同时给出工作时段；不替用户沿用假期的空时段存成 0 工时工作日。

    显式提交空数组 [] 仍表示"明确零工时工作日"；已是工作日的行省略时段表示不改；没存过的日期另由各入口决定。
    """
    if row is not None and row["day_type"] == "holiday" and patch.get("day_type") == "workday" and "periods" not in patch:
        raise ValidationError(day + " 原来是假期或休息日，改成工作日时请填写工作时段。", field="periods")


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
    WorkbenchCommandService transaction. Prepared models belong to that operation;
    confirmation prepares current models under the write lock. No write_token is stored here.
    """

    preview_ref: str
    created_at: str
    expires_at: str
    request: Dict[str, Any]
    dates: List[str]
    days: List[Dict[str, Any]]
