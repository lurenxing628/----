"""Reuse CalendarEngine over calendar and shift facts read once into one bounded snapshot."""

from core.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.calendar_periods import encode_periods
from core.services.scheduler.calendar.defaults import default_periods_from_row
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.scheduler.calendar.operator_shift import index_shift_facts


def _calendar_row(row, model):
    if row["shift_hours"] is None or row["efficiency"] is None:
        raise ValidationError("工作日历里有单独设过的日期缺了班时或效率。请到工作日历补填。", field="shift_hours")
    return model.from_row(row)


class SnapshotCalendarEngine(CalendarEngine):
    def __init__(self, facts):
        shifts = index_shift_facts(facts["profiles"], facts["patterns"])
        super().__init__(None, shift_facts=shifts)
        self.shift_profiles = shifts.profiles
        self._default_rows = tuple(facts.get("defaults", ()))
        self._personal_error = None
        self.global_rows = {str(row["date"]): row for row in facts["global"]}
        self.personal_rows = {(row["operator_id"], str(row["date"])): row for row in facts["personal"]}

    def default_periods(self):
        if self._default_periods is None:
            periods = default_periods_from_row(next(iter(self._default_rows), None))
            self._default_periods = periods
            self._default_periods_json = encode_periods(periods)
            _, self._default_period_hours = self._period_facts_for_json(self._default_periods_json, periods)
        return self._default_periods

    def _resolve_calendar_row(self, date_str, op_id):
        personal = self.personal_rows.get((op_id, date_str))
        if personal is not None:
            return _calendar_row(personal, OperatorCalendar)
        if date_str not in self._public_calendar_rows:
            row = self.global_rows.get(date_str)
            self._public_calendar_rows[date_str] = _calendar_row(row, WorkCalendar) if row is not None else self._default_for_date(date_str)
        return self._public_calendar_rows[date_str]

    def provenance(self, day, operator_id):
        if (operator_id, day) in self.personal_rows:
            return "personal_calendar"
        base = "work_calendar" if day in self.global_rows else "domain_default"
        return base + "_operator_shift" if operator_id in self.shift_profiles else base
