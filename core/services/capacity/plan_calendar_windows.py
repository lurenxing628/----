"""Date-key policies projected to disjoint, priority-aware local windows."""

import heapq
import math
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Any, Dict

from core.infrastructure.errors import ValidationError

from .plan_calendar_intervals import IntervalIndex, hours, instant, public_intervals, union, wire
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


def measures(windows):
    result: Dict[str, float] = dict.fromkeys(_MEASURES, 0.0)
    for row in windows:
        duration = (instant(row["end"]) - instant(row["start"])).total_seconds() / 3600.0
        for mode in ("", "normal_", "urgent_"):
            allowed = row["allow_normal"] or row["allow_urgent"] if not mode else row["allow_" + mode[:-1]]
            if allowed:
                result[mode + "available_hours"] += duration
                result[mode + "effective_hours"] += duration * row["efficiency"]
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError("Nonfinite calendar capacity")
    return {key: round(value, 6) for key, value in result.items()}


def policy_projection(engine, first_day, last_day, start, end, operator_id=None) -> Dict[str, Any]:
    windows, failures, day = [], [], first_day
    basis = "personal_or_operator_shift_calendar" if operator_id is not None else "global_calendar"
    while True:
        try:
            policy = engine._policy_for_date(day.isoformat(), operator_id)
            if policy.shift_hours > 24:
                return unavailable(basis, "calendar_window_limit")
            low, high = policy.work_window()
            low, high = max(low, start), min(high, end)
            if low < high:
                windows.append({"start": wire(low), "end": wire(high), "policy_date": day.isoformat(),
                                "allow_normal": policy.is_priority_allowed("normal"),
                                "allow_urgent": policy.is_priority_allowed("urgent"),
                                "efficiency": policy.efficiency, "provenance": engine.provenance(day.isoformat(), operator_id)})
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
        overriding = IntervalIndex([(instant(row["start"]), instant(row["end"])) for row in windows
                                    if row["policy_date"] > day.isoformat()])
        if low < high and overriding.hours_between(low, high) + 1e-9 < (high - low).total_seconds() / 3600:
            result = unavailable(basis, "calendar_invalid")
            result["issues"][0]["policy_date"] = day.isoformat()
            return result
    try:
        capacity = measures(windows)
    except ValueError:
        return unavailable(basis, "calendar_invalid")
    return dict(state="available", basis=basis, windows=windows, issues=[], **capacity)


def available_intervals(projection, priority=None):
    if projection["state"] != "available":
        return None
    flag = "allow_normal" if priority == "normal" else "allow_urgent"
    return union((instant(row["start"]), instant(row["end"])) for row in projection["windows"]
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
    result["downtime_windows"] = public_intervals(downtime)
    remaining = _subtract_windows(base["windows"], downtime)
    remaining_measures = measures(remaining)
    windows = remaining if raw["status"] == "active" else []
    result.update(windows=windows, **(remaining_measures if raw["status"] == "active" else measures([])))
    result["downtime_scope_hours"] = round(hours(downtime), 6)
    result["downtime_available_hours"] = round(base["available_hours"] - remaining_measures["available_hours"], 6)
    return result


def _subtract_windows(windows, downtime):
    """Linear sweep; do not rescan the entire downtime list for every work day."""
    result, j = [], 0
    for row in windows:
        start, end = instant(row["start"]), instant(row["end"])
        while j < len(downtime) and downtime[j][1] <= start:
            j += 1
        k, cursor = j, start
        while k < len(downtime) and downtime[k][0] < end:
            low, high = downtime[k]
            if cursor < low:
                result.append(dict(row, start=wire(cursor), end=wire(min(low, end))))
            cursor = max(cursor, high)
            k += 1
        if cursor < end:
            result.append(dict(row, start=wire(cursor), end=wire(end)))
    return result
