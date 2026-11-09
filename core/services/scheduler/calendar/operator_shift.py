"""Apply an explicit shift to a valid global day policy, after personal overrides.

The anchor is a cycle phase reference, not the first employment date. A shift
can move the clock window but cannot reopen a global non-working day, add hours
beyond that day's capacity, change efficiency, or relax either priority flag.
Like CalendarEngine's existing date cache, these reads live within one request
or scheduling read snapshot; a subsequent request gets a new engine.
"""

from collections import defaultdict
from dataclasses import replace
from datetime import date
from typing import Any, Dict, NamedTuple, Optional, Tuple

from core.errors import ValidationError
from core.shared.stored_dates import stored_day
from data.repositories.operator_shift_repo import OperatorShiftRepository


class ShiftFacts(NamedTuple):
    """Shift rows read together by one snapshot, already indexed for lookup."""

    profiles: Dict[Any, Dict[str, Any]]  # operator_id -> profile row with its pattern-day range
    patterns: Dict[Tuple[Any, Any], Any]  # (profile_id, day_offset) -> pattern row


def _pattern_index(rows):
    """Pattern days by (profile, offset) plus each profile's recorded offsets."""
    patterns, offsets = {}, defaultdict(list)
    for row in rows:
        patterns[row["profile_id"], row["day_offset"]] = row
        offsets[row["profile_id"]].append(row["day_offset"])
    return patterns, offsets


def _with_pattern_range(profile, offsets) -> Dict[str, Any]:
    days = offsets.get(profile["profile_id"], ())
    return dict(profile, day_count=len(days), first_day=min(days) if days else None,
                last_day=max(days) if days else None)


def index_shift_facts(profile_rows, pattern_rows) -> ShiftFacts:
    """Index one snapshot's operator profile rows and pattern-day rows."""
    patterns, offsets = _pattern_index(pattern_rows)
    return ShiftFacts({row["operator_id"]: _with_pattern_range(row, offsets) for row in profile_rows}, patterns)


class OperatorShiftCalendar:
    def __init__(self, conn, logger=None, *, capture=None, facts: Optional[ShiftFacts] = None):
        # Three sources: a snapshot's indexed facts, a run capture's business tables, or live per-person reads.
        self.repo = OperatorShiftRepository(conn, logger=logger)
        self.capture = capture
        self.facts = facts
        self._profiles = {}
        self._patterns = {}
        self._captured_index = None

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
                anchor = stored_day(profile["anchor_date"])
                if anchor is None:
                    raise ValidationError("人员班次的轮换基准日期无效，不能推测排班。", field="shift_profile")
                self._profiles[operator_id] = profile, anchor
        return self._profiles[operator_id]

    def _read_profile(self, operator_id):
        if self.facts is not None:
            return self.facts.profiles.get(operator_id)
        if self.capture is None:
            return self.repo.profile_for_operator(operator_id)
        linked = self.capture.index("WorkbenchOperatorProfiles", "operator_id").get(operator_id)
        if linked is None or linked["shift_profile_id"] is None:
            return None
        profile = self.capture.index("WorkbenchShiftProfiles", "profile_id").get(linked["shift_profile_id"], {})
        _, offsets = self._captured_patterns(self.capture)
        return _with_pattern_range({"shift_profile_id": linked["shift_profile_id"],
                                    **{key: profile.get(key) for key in ("profile_id", "anchor_date", "cycle_days", "status")}},
                                   offsets)

    def _captured_patterns(self, capture):
        if self._captured_index is None:
            self._captured_index = _pattern_index(capture.table("WorkbenchShiftPatternDays"))
        return self._captured_index

    def _read_pattern(self, profile_id, offset):
        if self.facts is not None:
            return self.facts.patterns.get((profile_id, offset))
        if self.capture is None:
            return self.repo.pattern_day(profile_id, offset)
        patterns, _ = self._captured_patterns(self.capture)
        return patterns.get((profile_id, offset))

    def apply_policy(self, policy, operator_id, *, prepare_periods):
        prepared = self._profile(operator_id)
        if prepared is None:
            return policy
        profile, anchor = prepared
        current = date.fromisoformat(policy.date_str)
        offset = (current - anchor).days % profile["cycle_days"]
        key = profile["profile_id"], offset
        if key not in self._patterns:
            self._patterns[key] = self._pattern(profile["profile_id"], offset, prepare_periods)
        hours, periods_json, offsets = self._patterns[key]
        return replace(policy, hours=min(policy.hours, hours), periods_json=periods_json, _period_offsets=offsets)

    def _pattern(self, profile_id, offset, prepare_periods):
        day = self._read_pattern(profile_id, offset)
        if day is None:
            raise ValidationError("人员班次缺少当天的轮换规则，不能回退到默认班次。", field="shift_profile")
        if type(day["is_rest"]) is not int or day["is_rest"] not in (0, 1):
            raise ValidationError("人员班表里的休息标记不合法。请到工作日历核对人员班表。", field="shift_profile")
        periods_json = day["periods_json"]
        offsets, full_hours = prepare_periods(periods_json)
        return (0.0 if day["is_rest"] else full_hours), periods_json, offsets

    @staticmethod
    def _validate_profile(profile):
        if profile["profile_id"] is None or profile["status"] != "active":
            raise ValidationError("人员关联的班次不存在或已停用，请先维护班次。", field="shift_profile")
        days = profile["cycle_days"]
        if (type(days) is not int or not 1 <= days <= 366 or profile["day_count"] != days
                or profile["first_day"] != 0 or profile["last_day"] != days - 1):
            raise ValidationError("人员班次的轮换日期不完整，不能推测缺失安排。", field="shift_profile")
