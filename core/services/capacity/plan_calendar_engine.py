"""Reuse CalendarEngine over calendar and shift facts read once into one bounded snapshot."""

from datetime import date

from core.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.models.calendar_periods import encode_periods
from core.services.scheduler.calendar.defaults import default_periods_from_row
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.scheduler.calendar.operator_shift import index_shift_facts


def _calendar_row(row, model):
    # Defaults apply to an absent date, not to a damaged explicit row.
    for field in ("shift_hours", "efficiency"):
        if row[field] is None or row[field] == "":
            raise ValidationError("工作日历里有单独设过的日期缺了班时或效率。请到工作日历补填。", field=field)
    if not isinstance(row["day_type"], str) or row["day_type"].strip().lower() not in ("workday", "weekend", "holiday"):
        raise ValidationError("工作日历里有日期的类型不认识，只能是工作日、周末或节假日。请到工作日历核对。", field="day_type")
    if any(not isinstance(row[name], str) or row[name].strip().lower() not in ("yes", "no")
           for name in ("allow_normal", "allow_urgent")):
        raise ValidationError("工作日历里有日期的普通件或急件许可填得不对。请到工作日历核对。", field="priority")
    return model.from_row(row)


def _calendar_index(rows, *, personal=False):
    index = {}
    for row in rows:
        raw = row["date"]
        if type(raw) is date:
            day = raw.isoformat()
        elif isinstance(raw, str):
            try:
                day = date.fromisoformat(raw).isoformat()
            except ValueError:
                raise ValidationError("工作日历里有日期格式不对。请按 2026-09-13 这样的写法到工作日历改正。", field="date") from None
            if day != raw:
                raise ValidationError("工作日历里有日期写法不规范。请按 2026-09-13 这样的写法到工作日历改正。", field="date")
        else:
            raise ValidationError("工作日历里有记录不是合法日期。请到工作日历核对日期。", field="date")
        key = (row["operator_id"], day) if personal else day
        if key in index:
            raise ValidationError("工作日历里同一天出现了两条记录。请到工作日历删掉重复的一条。", field="date")
        # Normalize lookup keys only; keep typed source rows for private snapshots.
        index[key] = row
    return index


def _deferred_index(rows, *, personal=False):
    """Index one calendar table, or keep its rejection for every policy that reads it."""
    try:
        return _calendar_index(rows, personal=personal), None
    except ValidationError as exc:
        return {}, exc.with_traceback(None)


class SnapshotCalendarEngine(CalendarEngine):
    def __init__(self, facts):
        shifts = index_shift_facts(facts["profiles"], facts["patterns"])
        super().__init__(None, shift_facts=shifts)
        # 人员 -> 班次档案（含轮换日范围）；投影按它分组共享同一班次的人员。
        self.shift_profiles = shifts.profiles
        self._default_rows = tuple(facts.get("defaults", ()))
        self.legacy_defaults = facts.get("legacy_defaults", False)
        # 坏日历表的错误留给真正读它的策略抛出：个人日历表坏了不连累全局与设备日历，
        # 全局表坏了也不连累当天已有个人日历的人员。
        self.global_rows, self._global_error = _deferred_index(facts["global"])
        self.personal_rows, self._personal_error = _deferred_index(facts["personal"], personal=True)

    def default_periods(self):
        if self._default_periods is None:
            if self.legacy_defaults:
                periods = [{"start": "08:00", "end": "16:00", "day_offset": 0}]
            else:
                periods = default_periods_from_row(next(iter(self._default_rows), None))
            self._default_periods = periods
            self._default_periods_json = encode_periods(periods)
            _, self._default_period_hours = self._period_facts_for_json(self._default_periods_json, periods)
        return self._default_periods

    def _default_for_date(self, date_str):
        row = super()._default_for_date(date_str)
        if self.legacy_defaults and row.day_type == "workday":
            row.shift_start, row.shift_end, row.shift_hours, row.periods_json = "08:00", "16:00", 8.0, None
        return row

    def _resolve_calendar_row(self, date_str, op_id):
        # 重抛同一个错误对象前清掉旧 traceback，逐日重抛才不会越叠越长、拖住已结束的调用帧。
        if op_id is not None and self._personal_error is not None:
            raise self._personal_error.with_traceback(None)
        personal = self.personal_rows.get((op_id, date_str))
        if personal is not None:
            return _calendar_row(personal, OperatorCalendar)
        if self._global_error is not None:
            raise self._global_error.with_traceback(None)
        if date_str not in self._public_calendar_rows:
            row = self.global_rows.get(date_str)
            self._public_calendar_rows[date_str] = _calendar_row(row, WorkCalendar) if row is not None else self._default_for_date(date_str)
        return self._public_calendar_rows[date_str]

    def provenance(self, day, operator_id):
        if (operator_id, day) in self.personal_rows:
            return "personal_calendar"
        base = "work_calendar" if day in self.global_rows else "domain_default"
        return base + "_operator_shift" if operator_id in self.shift_profiles else base
