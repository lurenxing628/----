"""Date-key policies projected to disjoint, priority-aware local windows."""

import heapq
import math
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Any, Dict

from core.errors import ValidationError

from .plan_calendar_intervals import (
    HOUR_MICROSECONDS,
    IntervalIndex,
    hours,
    instant,
    interval_microseconds,
    public_intervals,
    union,
    union_sorted,
    wire,
)
from .plan_calendar_issues import issue

_MEASURES = ("available_hours", "effective_hours", "normal_available_hours", "normal_effective_hours",
             "urgent_available_hours", "urgent_effective_hours")


def unavailable(basis, code) -> Dict[str, Any]:
    return dict(state="unavailable", basis=basis, windows=None, issues=[issue(code)],
                **dict.fromkeys(_MEASURES))


def _overlay(windows):
    """Today owns overlap with yesterday, matching policy_for_datetime precedence."""
    events = defaultdict(list)
    for index, row in enumerate(windows):
        events[row["start"]].append((index, True))
        events[row["end"]].append((index, False))
    live, heap, previous, chosen, result = set(), [], None, None, []
    for at, changes in sorted(events.items()):
        if previous is not None and previous < at and chosen is not None:
            row = dict(windows[chosen], start=previous, end=at)
            if result and result[-1]["end"] == previous and result[-1]["policy_date"] == row["policy_date"]:
                result[-1]["end"] = at
            else:
                result.append(row)
        for index, active in changes:
            if active:
                live.add(index)
                heapq.heappush(heap, -index)
            else:
                live.discard(index)
        while heap and -heap[0] not in live:
            heapq.heappop(heap)
        chosen, previous = (-heap[0] if heap else None), at
    return result


def measures(windows, durations):
    result: Dict[str, float] = dict.fromkeys(_MEASURES, 0.0)
    for row, duration in zip(windows, durations):
        for mode in ("", "normal_", "urgent_"):
            allowed = row["allow_normal"] or row["allow_urgent"] if not mode else row["allow_" + mode[:-1]]
            if allowed:
                result[mode + "available_hours"] += duration
                result[mode + "effective_hours"] += duration * row["efficiency"]
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError("Nonfinite calendar capacity")
    return {key: value / HOUR_MICROSECONDS for key, value in result.items()}


def policy_projection(engine, first_day, last_day, start, end, operator_id=None) -> Dict[str, Any]:
    windows, failures, day = [], [], first_day
    basis = "personal_or_operator_shift_calendar" if operator_id is not None else "global_calendar"
    while True:
        try:
            day_str = day.isoformat()
            policy = engine._policy_for_date(day_str, operator_id)
            if policy.shift_hours > 24:
                return unavailable(basis, "calendar_window_limit")
            for low, high in policy.work_windows():
                low, high = max(low, start), min(high, end)
                if low < high:
                    windows.append({"start": low, "end": high, "policy_date": day_str,
                                    "allow_normal": policy.is_priority_allowed("normal"),
                                    "allow_urgent": policy.is_priority_allowed("urgent"),
                                    "efficiency": policy.efficiency, "provenance": engine.provenance(day_str, operator_id)})
        except (ValidationError, ValueError, TypeError, OverflowError):
            failures.append(day)
        if day == last_day:
            break
        day += timedelta(days=1)
    windows = _overlay(windows)
    for day in failures:
        low = max(start, datetime.combine(day, time.min))
        high = min(end, datetime.combine(day, time.min) + timedelta(days=2)) if day.toordinal() <= (
            datetime.max.date().toordinal() - 2) else end
        # A valid newer date policy owns its whole window even when yesterday's
        # profile is broken. Only uncovered, potentially affected time is unknown.
        overriding = IntervalIndex([(row["start"], row["end"]) for row in windows
                                    if row["policy_date"] > day.isoformat()])
        if low < high and overriding.hours_between(low, high) + 1e-9 < interval_microseconds(low, high) / HOUR_MICROSECONDS:
            result = unavailable(basis, "calendar_invalid")
            result["issues"][0]["policy_date"] = day.isoformat()
            return result
    durations = [interval_microseconds(row["start"], row["end"]) for row in windows]
    try:
        capacity = measures(windows, durations)
    except ValueError:
        return unavailable(basis, "calendar_invalid")
    for row in windows:
        row["start"], row["end"] = wire(row["start"]), wire(row["end"])
    return dict(state="available", basis=basis, windows=windows, issues=[], **capacity)


def available_intervals(projection, priority=None):
    if projection["state"] != "available":
        return None
    flag = "allow_normal" if priority == "normal" else "allow_urgent"
    return union_sorted((instant(row["start"]), instant(row["end"])) for row in projection["windows"]
                         if (row[flag] if priority is not None else row["allow_normal"] or row["allow_urgent"]))


def apply_resource(base: Dict[str, Any], raw, kind, downtime_rows, start, end) -> Dict[str, Any]:
    basis = "global_calendar_machine_availability" if kind == "machine" else "personal_or_operator_shift_calendar"
    if raw is None:
        return unavailable(basis, "resource_missing")
    if raw["status"] not in (("active", "inactive", "maintain") if kind == "machine" else ("active", "inactive")):
        return unavailable(basis, "resource_status_unknown")
    result = dict(base, basis=basis, status=raw["status"])
    if result["state"] != "available":
        return result
    downtime = []
    for row in downtime_rows:
        try:
            low, high = instant(row["start_time"]), instant(row["end_time"])
            if low >= high or row["status"] != "active":
                raise ValueError("Invalid downtime")
        except ValueError:
            return unavailable(basis, "downtime_invalid")
        if low < end and high > start:
            downtime.append((max(start, low), min(end, high)))
    downtime = union(downtime)
    if not downtime:
        # A checked resource without intersecting downtime shares the policy's
        # read-only windows and capacity. State never mutates that base.
        result.update(downtime_windows=[], downtime_scope_hours=0.0, downtime_available_hours=0.0)
        if raw["status"] != "active":
            result.update(windows=[], **dict.fromkeys(_MEASURES, 0.0))
        return result
    result["downtime_windows"] = public_intervals(downtime)
    remaining, durations = _subtract_windows(base["windows"], downtime)
    remaining_measures = measures(remaining, durations)
    windows = remaining if raw["status"] == "active" else []
    result.update(windows=windows, **(remaining_measures if raw["status"] == "active" else dict.fromkeys(_MEASURES, 0.0)))
    result["downtime_scope_hours"] = hours(downtime)
    result["downtime_available_hours"] = base["available_hours"] - remaining_measures["available_hours"]
    return result


def _subtract_windows(windows, downtime):
    """Linear sweep; do not rescan the entire downtime list for every work day."""
    result, durations, j = [], [], 0
    for row in windows:
        start, end = instant(row["start"]), instant(row["end"])
        while j < len(downtime) and downtime[j][1] <= start:
            j += 1
        k, cursor = j, start
        while k < len(downtime) and downtime[k][0] < end:
            low, high = downtime[k]
            if cursor < low:
                stop = min(low, end)
                result.append(dict(row, start=wire(cursor), end=wire(stop)))
                durations.append(interval_microseconds(cursor, stop))
            cursor = max(cursor, high)
            k += 1
        if cursor < end:
            result.append(dict(row, start=wire(cursor), end=wire(end)))
            durations.append(interval_microseconds(cursor, end))
    return result, durations


def project_resource_calendars(engine, facts, ids, first, last, start, end, *, global_calendar=None):
    if global_calendar is None:
        global_calendar = policy_projection(engine, first, last, start, end)
    downtime = defaultdict(list)
    for row in facts["downtimes"]:
        downtime[row["machine_id"]].append(row)
    personal_operators = {row["operator_id"] for row in facts["personal"]}
    shift_bases = {}
    for kind in ("machine", "operator"):
        records = {row[kind + "_id"]: row for row in facts[kind + "s"]}
        for key in ids.get(kind, ()):
            raw = records.get(key)
            if kind == "machine":
                base = global_calendar
            elif engine._personal_error is None and key not in personal_operators:
                profile = engine.shift_profiles.get(key)
                shift_key = None if profile is None else profile["shift_profile_id"]
                if shift_key not in shift_bases:
                    shift_bases[shift_key] = (
                        global_calendar
                        if shift_key is None and global_calendar["state"] == "available"
                        else policy_projection(engine, first, last, start, end, key)
                    )
                base = shift_bases[shift_key]
            else:
                # 有个人日历的人逐人投影；个人日历表坏了时确认不了谁没有个人日历，每个人都走这里报日历无效。
                base = policy_projection(engine, first, last, start, end, key)
            yield kind, key, raw, apply_resource(base, raw, kind, downtime[key] if kind == "machine" else [], start, end)
