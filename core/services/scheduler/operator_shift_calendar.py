"""Apply an explicit shift to a valid global day policy, after personal overrides.

The anchor is a cycle phase reference, not the first employment date. A shift
can move the clock window but cannot reopen a global non-working day, add hours
beyond that day's capacity, change efficiency, or relax either priority flag.
Like CalendarEngine's existing date cache, these reads live within one request
or scheduling read snapshot; a subsequent request gets a new engine.
"""

from dataclasses import replace
from datetime import date, datetime, timedelta

from core.errors import ValidationError
from core.services.common.datetime_normalize import normalize_hhmm
from data.repositories.operator_shift_repo import OperatorShiftRepository


class OperatorShiftCalendar:
    def __init__(self, conn, logger=None):
        self.repo = OperatorShiftRepository(conn, logger=logger)

    def apply_policy(self, policy, operator_id):
        profile = self.repo.profile_for_operator(operator_id)
        if profile is None:
            return policy
        self._validate_profile(profile)
        try:
            anchor = date.fromisoformat(profile["anchor_date"])
            current = date.fromisoformat(policy.date_str)
        except (ValueError, TypeError):
            raise ValidationError("人员班次的轮换基准日期无效，不能推测排班。", field="shift_profile") from None
        offset = (current - anchor).days % profile["cycle_days"]
        day = self.repo.pattern_day(profile["profile_id"], offset)
        if day is None:
            raise ValidationError("人员班次缺少当天的轮换规则，不能回退到默认班次。", field="shift_profile")
        start = normalize_hhmm(day["shift_start"], field="班次开始", allow_none=False)
        end = normalize_hhmm(day["shift_end"], field="班次结束", allow_none=False)
        if start is None or end is None:
            raise ValidationError("人员班次缺少开始或结束时间。", field="shift_profile")
        start_time, end_time = datetime.strptime(start, "%H:%M").time(), datetime.strptime(end, "%H:%M").time()
        begin, finish = datetime.combine(current, start_time), datetime.combine(current, end_time)
        if finish <= begin:
            finish += timedelta(days=1)
        hours = 0.0 if day["is_rest"] else (finish - begin).total_seconds() / 3600
        return replace(policy, shift_start=start_time, shift_hours=min(policy.shift_hours, hours))

    @staticmethod
    def _validate_profile(profile):
        if profile["profile_id"] is None or profile["status"] != "active":
            raise ValidationError("人员关联的班次不存在或已停用，请先维护班次。", field="shift_profile")
        days = profile["cycle_days"]
        if (type(days) is not int or not 1 <= days <= 366 or profile["day_count"] != days
                or profile["first_day"] != 0 or profile["last_day"] != days - 1):
            raise ValidationError("人员班次的轮换日期不完整，不能推测缺失安排。", field="shift_profile")
