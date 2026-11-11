"""Factory defaults shared by live calendars, forms and archived projections."""

from typing import Any, Dict, List

from core.errors import ValidationError
from core.models.calendar_periods import DEFAULT_WORK_PERIODS, decode_periods, normalize_periods


def validate_default_periods(periods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not periods:
        raise ValidationError("默认工作时间至少需要一个工作时段，请重新维护。", field="periods")
    return periods


def default_periods_from_row(row: Any) -> List[Dict[str, Any]]:
    periods = normalize_periods(DEFAULT_WORK_PERIODS) if row is None else decode_periods(row["periods_json"])
    return validate_default_periods(periods)
