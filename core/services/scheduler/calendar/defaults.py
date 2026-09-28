"""Factory defaults shared by live calendars, forms and archived projections."""

from core.errors import ValidationError
from core.models.calendar_periods import DEFAULT_WORK_PERIODS, decode_periods, normalize_periods
from data.repositories.calendar_defaults_repo import CalendarDefaultsRepository


def default_periods_from_row(row):
    if row is None:
        return normalize_periods(DEFAULT_WORK_PERIODS)
    periods = decode_periods(row["periods_json"])
    if not periods:
        raise ValidationError("默认工作时间至少需要一个工作时段，请重新维护。", field="periods")
    return periods


def read_default_periods(conn):
    return default_periods_from_row(CalendarDefaultsRepository(conn).get() if conn is not None else None)
