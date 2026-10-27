"""Factory defaults shared by live calendars, forms and archived projections."""

from typing import Any, Dict, List

from core.errors import ValidationError
from core.models.calendar_periods import DEFAULT_WORK_PERIODS, decode_periods, normalize_periods
from data.repositories.calendar_defaults_repo import CalendarDefaultsRepository


def default_periods_from_row(row: Any) -> List[Dict[str, Any]]:
    periods = normalize_periods(DEFAULT_WORK_PERIODS) if row is None else decode_periods(row["periods_json"])
    if not periods:
        raise ValidationError("默认工作时间至少需要一个工作时段，请重新维护。", field="periods")
    return periods


def read_default_periods(conn: Any, *, capture: Any = None) -> List[Dict[str, Any]]:
    row = (capture.index("WorkbenchCalendarDefaults", "singleton").get(1) if capture is not None
           else CalendarDefaultsRepository(conn).get() if conn is not None else None)
    return default_periods_from_row(row)
