"""Reuse CalendarEngine and OperatorShiftCalendar with bounded in-memory readers."""

from collections import defaultdict
from datetime import date

from core.infrastructure.errors import ValidationError
from core.models.calendar import OperatorCalendar, WorkCalendar
from core.services.scheduler.calendar_engine import CalendarEngine
from core.services.scheduler.operator_shift_calendar import OperatorShiftCalendar
from data.repositories.operator_shift_repo import OperatorShiftRepository


class _ShiftRows(OperatorShiftRepository):
    """Connection-free overrides for the two reads used by apply_policy."""

    def __init__(self, facts):
        self.profiles = {row["operator_id"]: dict(row) for row in facts["profiles"]}
        self.patterns = {(row["profile_id"], row["day_offset"]): row for row in facts["patterns"]}
        offsets = defaultdict(list)
        for row in facts["patterns"]:
            offsets[row["profile_id"]].append(row["day_offset"])
        for profile in self.profiles.values():
            days = offsets[profile["profile_id"]]
            profile.update(day_count=len(days), first_day=min(days) if days else None, last_day=max(days) if days else None)

    def profile_for_operator(self, operator_id):
        return self.profiles.get(operator_id)

    def pattern_day(self, profile_id, offset):
        row = self.patterns.get((profile_id, offset))
        if row is not None and (type(row["is_rest"]) is not int or row["is_rest"] not in (0, 1)):
            raise ValidationError("人员班表里的休息标记不合法。请到工作日历核对人员班表。", field="shift_profile")
        return row


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


class SnapshotCalendarEngine(CalendarEngine):
    def __init__(self, facts):
        super().__init__(None)
        self.global_rows = _calendar_index(facts["global"])
        self.personal_rows = _calendar_index(facts["personal"], personal=True)
        self.operator_shift_calendar = OperatorShiftCalendar(None)
        self._shift_rows = _ShiftRows(facts)
        self.operator_shift_calendar.repo = self._shift_rows

    def _resolve_calendar_row(self, date_str, op_id):
        personal = self.personal_rows.get((op_id, date_str))
        if personal is not None:
            return _calendar_row(personal, OperatorCalendar)
        row = self.global_rows.get(date_str)
        return _calendar_row(row, WorkCalendar) if row is not None else self._default_for_date(date_str)

    def provenance(self, day, operator_id):
        if (operator_id, day) in self.personal_rows:
            return "personal_calendar"
        base = "work_calendar" if day in self.global_rows else "domain_default"
        return base + "_operator_shift" if operator_id in self._shift_rows.profiles else base
