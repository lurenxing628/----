from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from core.infrastructure.errors import ValidationError
from core.models.enums import CALENDAR_DAY_TYPE_STORED_VALUES, YESNO_VALUES, CalendarDayType
from core.services.common.normalize import is_blank_value
from core.services.common.number_utils import parse_finite_float
from core.services.scheduler import CalendarService

from .scheduler_utils import _normalize_calendar_date, _normalize_day_type, _normalize_yesno


def canonicalize_calendar_date(value: Any) -> str:
    try:
        return CalendarService._normalize_date(value)  # type: ignore[attr-defined]
    except ValidationError:
        return _normalize_calendar_date(value)


def calendar_baseline_extra_state(*, holiday_default_efficiency: float) -> Dict[str, Any]:
    return {"holiday_default_efficiency": float(holiday_default_efficiency)}


def require_holiday_default_efficiency(value: Optional[float]) -> float:
    if value is None:
        raise ValidationError("“假期工作效率”配置缺失，无法继续工作日历 Excel 导入。")
    return float(value)


def normalize_calendar_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_rows: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["日期"] = canonicalize_calendar_date(item.get("日期"))
        item["类型"] = _normalize_day_type(item.get("类型"))
        item["允许普通件"] = _normalize_yesno(item.get("允许普通件"))
        item["允许急件"] = _normalize_yesno(item.get("允许急件"))
        normalized_rows.append(item)
    return normalized_rows


def build_calendar_row_validators(
    *, holiday_default_efficiency: float
) -> List[Callable[[Dict[str, Any]], Optional[str]]]:
    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        return validate_calendar_import_row(row, holiday_default_efficiency=holiday_default_efficiency)

    return [validate_row]


def validate_calendar_import_row(row: Dict[str, Any], *, holiday_default_efficiency: float) -> Optional[str]:
    if is_blank_value(row.get("日期")):
        return "“日期”不能为空"
    try:
        row["日期"] = CalendarService._normalize_date(row.get("日期"))  # type: ignore[attr-defined]
    except ValidationError as exc:
        return exc.message

    row["类型"] = _normalize_day_type(row.get("类型"))
    if row["类型"] not in CALENDAR_DAY_TYPE_STORED_VALUES:
        return "“类型”不合法，可填写：工作日 / 假期 / 周末 / 节假日；也兼容英文标准值 workday/holiday。"

    hours_error = _apply_shift_hours(row)
    if hours_error:
        return hours_error
    efficiency_error = _apply_efficiency(row, holiday_default_efficiency=holiday_default_efficiency)
    if efficiency_error:
        return efficiency_error
    return _apply_yes_no_flags(row)


def _apply_shift_hours(row: Dict[str, Any]) -> Optional[str]:
    raw_hours = row.get("可用工时")
    if raw_hours is None or str(raw_hours).strip() == "":
        row["可用工时"] = 8 if row["类型"] == CalendarDayType.WORKDAY.value else 0
        return None
    try:
        value = parse_finite_float(raw_hours, field="可用工时")
    except ValidationError as exc:
        return exc.message
    if value < 0:
        return "“可用工时”不能为负数"
    row["可用工时"] = value
    return None


def _apply_efficiency(row: Dict[str, Any], *, holiday_default_efficiency: float) -> Optional[str]:
    raw_efficiency = row.get("效率")
    if raw_efficiency is None or str(raw_efficiency).strip() == "":
        row["效率"] = 1.0 if row["类型"] == CalendarDayType.WORKDAY.value else holiday_default_efficiency
        return None
    try:
        value = parse_finite_float(raw_efficiency, field="效率")
    except ValidationError as exc:
        return exc.message
    if value <= 0:
        return "“效率”必须大于 0"
    row["效率"] = value
    return None


def _apply_yes_no_flags(row: Dict[str, Any]) -> Optional[str]:
    row["允许普通件"] = _normalize_yesno(row.get("允许普通件"))
    if row["允许普通件"] not in YESNO_VALUES:
        return "“允许普通件”不合法，可填写：是 / 否；也兼容英文标准值 yes/no/true/false/1/0。"
    row["允许急件"] = _normalize_yesno(row.get("允许急件"))
    if row["允许急件"] not in YESNO_VALUES:
        return "“允许急件”不合法，可填写：是 / 否；也兼容英文标准值 yes/no/true/false/1/0。"
    return None
