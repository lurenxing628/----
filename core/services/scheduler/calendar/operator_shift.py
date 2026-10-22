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
from core.models.calendar_periods import decode_periods
from core.services.common.datetime_normalize import normalize_hhmm
from data.repositories.operator_shift_repo import OperatorShiftRepository

from .period_offsets import offset_hours, period_offsets


class OperatorShiftCalendar:
    def __init__(self, conn, logger=None, *, capture=None):
        self.repo = OperatorShiftRepository(conn, logger=logger)
        self.capture = capture
        self._profiles = {}
        self._patterns = {}
        self._captured_patterns = None
        self._captured_pattern_ranges = {}

    def clear_cache(self):
        self._profiles.clear()
        self._patterns.clear()

    def discard_operator(self, operator_id):
        self._profiles.pop(operator_id, None)

    def _profile(self, operator_id):
        if operator_id not in self._profiles:
            profile = self._read_profile(operator_id)
            if profile is None:
                self._profiles[operator_id] = None
            else:
                self._validate_profile(profile)
                try:
                    anchor = date.fromisoformat(profile["anchor_date"])
                except (ValueError, TypeError):
                    raise ValidationError("人员班次的轮换基准日期无效，不能推测排班。", field="shift_profile") from None
                self._profiles[operator_id] = profile, anchor
        return self._profiles[operator_id]

    def _read_profile(self, operator_id):
        if self.capture is None:
            return self.repo.profile_for_operator(operator_id)
        linked = self.capture.index("WorkbenchOperatorProfiles", "operator_id").get(operator_id)
        if linked is None or linked["shift_profile_id"] is None:
            return None
        profile = self.capture.index("WorkbenchShiftProfiles", "profile_id").get(linked["shift_profile_id"], {})
        self._prepare_captured_patterns(self.capture)
        count, first, last = self._captured_pattern_ranges.get(profile.get("profile_id"), (0, None, None))
        return {"shift_profile_id": linked["shift_profile_id"],
                **{key: profile.get(key) for key in ("profile_id", "anchor_date", "cycle_days", "status")},
                "day_count": count, "first_day": first, "last_day": last}

    def _prepare_captured_patterns(self, capture):
        if self._captured_patterns is None:
            periods = {(row["profile_id"], row["day_offset"]): row["periods_json"]
                       for row in capture.table("WorkbenchShiftDayPeriods")}
            patterns, offsets = {}, {}
            for row in capture.table("WorkbenchShiftPatternDays"):
                key = row["profile_id"], row["day_offset"]
                patterns[key] = dict(row, periods_json=periods.get(key))
                offsets.setdefault(row["profile_id"], []).append(row["day_offset"])
            self._captured_patterns = patterns
            self._captured_pattern_ranges = {key: (len(days), min(days), max(days)) for key, days in offsets.items()}
        return self._captured_patterns

    def _read_pattern(self, profile_id, offset):
        if self.capture is None:
            return self.repo.pattern_day(profile_id, offset)
        patterns = self._prepare_captured_patterns(self.capture)
        return patterns.get((profile_id, offset))

    def apply_policy(self, policy, operator_id, *, prepare_periods=None):
        prepared = self._profile(operator_id)
        if prepared is None:
            return policy
        profile, anchor = prepared
        try:
            current = date.fromisoformat(policy.date_str)
        except (ValueError, TypeError):
            raise ValidationError("人员班次的轮换基准日期无效，不能推测排班。", field="shift_profile") from None
        offset = (current - anchor).days % profile["cycle_days"]
        key = profile["profile_id"], offset
        if key not in self._patterns:
            self._patterns[key] = self._pattern(profile["profile_id"], offset, current, prepare_periods)
        start_time, hours, periods_json, offsets = self._patterns[key]
        return replace(policy, shift_start=start_time, shift_hours=min(policy.shift_hours, hours),
                       periods_json=periods_json, _period_offsets=offsets)

    def _pattern(self, profile_id, offset, current, prepare_periods):
        day = self._read_pattern(profile_id, offset)
        if day is None:
            raise ValidationError("人员班次缺少当天的轮换规则，不能回退到默认班次。", field="shift_profile")
        start = normalize_hhmm(day["shift_start"], field="班次开始")
        end = normalize_hhmm(day["shift_end"], field="班次结束")
        if start is None or end is None:
            raise ValidationError("人员班次缺少开始或结束时间。", field="shift_profile")
        start_time, end_time = datetime.strptime(start, "%H:%M").time(), datetime.strptime(end, "%H:%M").time()
        begin, finish = datetime.combine(current, start_time), datetime.combine(current, end_time)
        if finish <= begin:
            finish += timedelta(days=1)
        hours = 0.0 if day["is_rest"] else (finish - begin).total_seconds() / 3600
        periods_json = day["periods_json"]
        offsets = None
        if periods_json is not None:
            if prepare_periods is None:
                offsets = period_offsets(decode_periods(periods_json))
                full_hours = offset_hours(offsets)
            else:
                offsets, full_hours = prepare_periods(periods_json)
            hours = 0.0 if day["is_rest"] else full_hours
        return start_time, hours, periods_json, offsets

    @staticmethod
    def _validate_profile(profile):
        if profile["profile_id"] is None or profile["status"] != "active":
            raise ValidationError("人员关联的班次不存在或已停用，请先维护班次。", field="shift_profile")
        days = profile["cycle_days"]
        if (type(days) is not int or not 1 <= days <= 366 or profile["day_count"] != days
                or profile["first_day"] != 0 or profile["last_day"] != days - 1):
            raise ValidationError("人员班次的轮换日期不完整，不能推测缺失安排。", field="shift_profile")
