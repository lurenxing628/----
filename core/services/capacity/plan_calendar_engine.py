"""Reuse CalendarEngine over calendar and shift facts read once into one bounded snapshot."""

from core.models.calendar import OperatorCalendar, WorkCalendar
from core.services.scheduler.calendar.defaults import default_periods_from_row
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.scheduler.calendar.operator_shift import index_shift_facts


class SnapshotCalendarEngine(CalendarEngine):
    def __init__(self, facts):
        shifts = index_shift_facts(facts["profiles"], facts["patterns"])
        super().__init__(None, shift_facts=shifts)
        self.shift_profiles = shifts.profiles
        self._default_rows = tuple(facts.get("defaults", ()))
        self.global_rows = {str(row["date"]): row for row in facts["global"]}
        self.personal_rows = {(row["operator_id"], str(row["date"])): row for row in facts["personal"]}

    def _read_default_periods(self):
        return default_periods_from_row(next(iter(self._default_rows), None))

    def _resolve_calendar_row(self, date_str, op_id):
        personal = self.personal_rows.get((op_id, date_str))
        if personal is not None:
            return OperatorCalendar.from_row(personal)
        if date_str not in self._public_calendar_rows:
            row = self.global_rows.get(date_str)
            self._public_calendar_rows[date_str] = WorkCalendar.from_row(row) if row is not None else self._default_for_date(date_str)
        return self._public_calendar_rows[date_str]

    def provenance(self, day, operator_id):
        if (operator_id, day) in self.personal_rows:
            return "personal_calendar"
        base = "work_calendar" if day in self.global_rows else "domain_default"
        return base + "_operator_shift" if operator_id in self.shift_profiles else base
