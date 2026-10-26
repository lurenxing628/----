"""Shared archived-resource occupancy, demand, daily pressure and detail facts.

Task identity/time is indexed once for the comparison window. Calendar capacity
and workload availability remain independent; unknown days never become outside
calendar time or zero capacity. All arithmetic keeps its original precision.
"""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, NamedTuple, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import IntervalIndex, hours, instant, intersection, union
from core.services.capacity.plan_calendar_limits import MAX_CALENDAR_DATES
from core.services.capacity.resource_utilization_metrics import ResourceUtilizationMetrics

from .resource_calendar import normalize_resource_calendar
from .resource_intervals import (
    KINDS,
    ResourceIntervals,
    identity_issue,
    occupying_tasks,
    resource_cohort,
    sweep_details,
)
from .resource_summary import resource_summary

RESOURCE_METRIC_VERSION = "decision-resource-v4"
__all__ = ["ResourceTaskIndex", "resource_cohort", "resource_summary", "RESOURCE_METRIC_VERSION"]

_INSIDE_FIELDS = ("occupied_hours", "summed_load_hours", "outside_calendar_hours", "overlap_hours")
_SPAN_FIELDS = ("span_occupied_hours", "span_summed_hours", "span_overlap_hours", "overlap_span_hours")


def _issue(code, message, field=None):
    result = {"code": code, "message": message}
    if field is not None:
        result["field"] = field
    return result


def _issues(values):
    result, seen = [], set()
    for item in values:
        value = {key: item[key] for key in ("code", "message", "field") if key in item}
        key = (value["code"], value.get("field"), value.get("message"))
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result


class _ResourceValues(NamedTuple):
    raw: Dict[str, Any]
    known_day_count: int
    calendar_complete: bool
    capacity: Optional[float]
    known_capacity: Optional[float]
    ratio: Optional[float]
    demand: Optional[float]
    known_ratio: Optional[float]
    known_demand: Optional[float]
    high_pressure: Optional[bool]
    zero_capacity_task: Optional[bool]
    conflict: Optional[bool]
    demand_overload: Optional[bool]
    zero_capacity_reason: Optional[Dict[str, str]]


def _daily_signals(capacity, occupied, span, *, calendar_available, work_available, work_complete, potential_work, threshold=0.9):
    ratio = occupied / capacity if calendar_available and work_available and capacity > 0 else None
    pressure = True if ratio is not None and ratio >= threshold else (
        None if potential_work and (not calendar_available or not work_complete) else False)
    if not calendar_available:
        zero_task = None if potential_work else False
    elif capacity == 0:
        # A saved reservation can pause during rest. Its span is no work fragment.
        zero_task = None if span > 0 or not work_complete else False
    else:
        zero_task = False
    return ratio, pressure, zero_task


class _ResourceMeasurement:
    def __init__(self, resource, intervals, calendar, low, high, work_available, source, threshold, unknown_issues,
                 *, retain_statistics_values=True):
        self.resource, self.intervals = resource, intervals
        self.low, self.high, self.work_available, self.source = low, high, work_available, source
        self.threshold = threshold
        self.retain_statistics_values = retain_statistics_values
        self.calendar = normalize_resource_calendar(calendar, low, high)
        self.days, self.known_days = self.calendar.days, self.calendar.known_days
        self.windows = self.calendar.windows
        self.metrics = ResourceUtilizationMetrics.from_normalized_availability(intervals.intervals, self.windows)
        self.known_span = IntervalIndex.from_normalized(intersection(self.metrics.span.intervals, self.calendar.known_coverage))
        self.work_complete = work_available and not intervals.unknown
        self.work_state = "complete" if self.work_complete else "partial" if work_available and intervals.rows else "unavailable"
        self.work_issues = []
        if not work_available:
            self.work_issues.append(_issue("arrangements_unavailable", "比较对象的安排归档缺项，占用和负荷未知。"))
        elif intervals.unknown:
            self.work_issues.extend(unknown_issues)
        self._value_cache, self._window_statistics_cache, self._period_statistics_cache = {}, {}, {}
        self._day_filter_summary = None

    @staticmethod
    def _day_key(calendar_days):
        return tuple((day.date, day.low, day.high, day.available) for day in calendar_days)

    def values(self, low, high, calendar_days, *, potential_work=None, prepared=None, retain=True):
        """Reuse retained interval facts; transient folds consume the same formula."""
        key = low, high, self._day_key(calendar_days)
        variants = self._value_cache.get(key)
        if variants:
            original = next(iter(variants.values()))
            potential_work = (original.raw["span_occupied_hours"] > 0 or not self.work_complete
                              if potential_work is None else potential_work)
            if potential_work in variants:
                return variants[potential_work]
        value = self._values(low, high, calendar_days, potential_work=potential_work, prepared=prepared)
        if retain:
            potential_work = (value.raw["span_occupied_hours"] > 0 or not self.work_complete
                              if potential_work is None else potential_work)
            self._value_cache.setdefault(key, {})[potential_work] = value
        return value

    def _values(self, low, high, calendar_days, *, potential_work=None, prepared=None):
        known_day_count = sum(day.available for day in calendar_days)
        capacity_complete = known_day_count == len(calendar_days)
        if prepared is None:
            raw = self.metrics.window(low, high, precision=None)
            known_span_hours = self.known_span.hours_between(low, high)
        else:
            raw, known_span_hours = prepared
        raw["overlap_span_hours"] = raw["span_overlap_hours"]
        raw["span_overlap_hours"] = raw["span_summed_hours"] - raw["span_occupied_hours"]
        # Only known natural-day slices support an outside-calendar conclusion.
        raw["outside_calendar_hours"] = known_span_hours - raw["occupied_hours"]
        known_capacity = raw["available_hours"] if known_day_count else None
        capacity = known_capacity if capacity_complete else None
        occupied, load = (raw[key] if capacity_complete and self.work_complete else None
                          for key in ("occupied_hours", "summed_load_hours"))
        known_occupied, known_load = (raw[key] if known_day_count and self.work_available else None
                                      for key in ("occupied_hours", "summed_load_hours"))
        ratio = occupied / capacity if occupied is not None and capacity is not None and capacity > 0 else None
        demand = load / capacity if load is not None and capacity is not None and capacity > 0 else None
        known_ratio = known_occupied / known_capacity if known_occupied is not None and known_capacity is not None and known_capacity > 0 else None
        known_demand = known_load / known_capacity if known_load is not None and known_capacity is not None and known_capacity > 0 else None
        if potential_work is None:
            potential_work = raw["span_occupied_hours"] > 0 or not self.work_complete
        _, high_pressure, zero_capacity_task = _daily_signals(
            raw["available_hours"], raw["occupied_hours"], raw["span_occupied_hours"], calendar_available=capacity_complete,
            work_available=self.work_available, work_complete=self.work_complete, potential_work=potential_work, threshold=self.threshold)
        if self.work_available and raw["outside_calendar_hours"] > 0:
            zero_capacity_task = None
        conflict = True if self.work_available and raw["overlap_hours"] > 0 else (
            None if potential_work and (not capacity_complete or not self.work_complete) else False)
        demand_overload = True if demand is not None and demand > 1 else (
            None if potential_work and (not capacity_complete or not self.work_complete) else False)
        zero_capacity_reason = _issue("actual_work_fragments_not_recorded", "此时段无可排容量；安排跨度未提供实际工作片段。") if (
            zero_capacity_task is None and (raw["outside_calendar_hours"] > 0 or capacity_complete and capacity == 0)) else None
        return _ResourceValues(raw, known_day_count, capacity_complete, capacity, known_capacity, ratio, demand,
                               known_ratio, known_demand, high_pressure, zero_capacity_task, conflict, demand_overload, zero_capacity_reason)

    def cell(self, low, high, calendar_days, *, whole=False):
        if whole:
            task_count, operation_count = len(self.intervals.rows), len(self.intervals.operations)
        else:
            task_count, operation_count = self.intervals.counts(low, high)
        values = self.values(low, high, calendar_days, potential_work=self.potential_work(low, high, whole=whole))
        raw, capacity_complete = values.raw, values.calendar_complete
        known_days, capacity, known_capacity = values.known_day_count, values.capacity, values.known_capacity
        result: Dict[str, Any] = {key: raw[key] if capacity_complete and self.work_complete else None for key in _INSIDE_FIELDS}
        result.update({key: raw[key] if self.work_complete else None for key in _SPAN_FIELDS})
        result.update({"known_" + key: raw[key] if known_days and self.work_available else None for key in _INSIDE_FIELDS})
        result.update({"known_" + key: raw[key] if self.work_available else None for key in _SPAN_FIELDS})
        occupied = result["occupied_hours"]
        complete = capacity_complete and self.work_complete
        state = "complete" if complete else "partial" if known_days or self.work_available else "unavailable"
        result.update({"resource_ref": self.resource["ref"], "resource_kind": self.resource["kind"], "label": self.resource.get("label"),
                       "state": state, "available_hours": capacity, "known_available_hours": known_capacity,
                       "utilization_ratio": values.ratio, "demand_ratio": values.demand,
                       "known_utilization_ratio": values.known_ratio, "known_demand_ratio": values.known_demand,
                       "peak_utilization": values.ratio, "known_peak_utilization": values.known_ratio,
                       "high_pressure": values.high_pressure, "demand_overload": values.demand_overload,
                       "zero_capacity_task": values.zero_capacity_task, "conflict": values.conflict,
                       "pressure_threshold": self.threshold,
                       "calendar_state": "complete" if capacity_complete else "partial" if known_days else "unavailable",
                       "outside_calendar_basis": "reservation_span_outside_work_calendar",
                       "conflict_basis": "work_calendar_reservation_overlap",
                       "actual_work_state": "not_recorded",
                       "zero_capacity_reason": values.zero_capacity_reason,
                       "unknown_days": len(calendar_days) - known_days,
                       "zero_capacity_days": 0 if whole else int(capacity_complete and capacity == 0),
                       "task_count": task_count if self.work_complete else None,
                       "operation_count": operation_count if self.work_complete else None,
                       "known_task_count": task_count if self.work_available else None,
                       "known_operation_count": operation_count if self.work_available else None,
                       "work_available": self.work_available, "work_state": self.work_state,
                       "unknown_workload_count": len(self.intervals.unknown),
                       "numerator_hours": occupied, "denominator_hours": capacity,
                       "issues": _issues([item for day in calendar_days for item in day.issues] + self.work_issues),
                       "metric_version": RESOURCE_METRIC_VERSION, "source": self.source})
        return result

    def potential_work(self, low, high, *, whole=False):
        if whole:
            task_count = len(self.intervals.rows)
        elif low == high:
            task_count = 0
        else:
            task_count = bisect_left(self.intervals.starts, high) - bisect_right(self.intervals.ends, low)
        return task_count > 0 or not self.work_complete

    def window(self, low=None, high=None):
        low, high = self.low if low is None else low, self.high if high is None else high
        days = self.calendar.days_in(low, high)
        result = self.cell(low, high, days, whole=low == self.low and high == self.high)
        result.update(self.window_statistics(low, high, days))
        return result

    def window_statistics(self, low, high, days):
        key = low, high, self._day_key(days)
        if key in self._window_statistics_cache:
            return self._window_statistics_cache[key]
        complete = all(day.available for day in days) and self.work_complete
        # Peak and pressure cover every archived day, independently of the UI page.
        peak, high_pressure, zero_capacity_task, zero_days = None, False, False, 0
        high_periods, overload_count, conflict_count = [], 0, 0
        high_unknown = overload_unknown = conflict_unknown = False
        unknown_periods, unavailable_periods = 0, 0
        zero_capacity_reason = None
        full_natural_window = (low < high and low == self.low and high == self.high and self.calendar.natural_day_window
                               and days and days[0].low == low and days[-1].high == high)
        prepared_days = None
        if full_natural_window and len(days) > 1:
            boundaries = [days[0].low] + [day.high for day in days]
            raw_days = self.metrics.windows_at_boundaries(boundaries, precision=None)
            known_prefix = self.known_span.prefix_values_at_sorted(boundaries)
            previous_known = next(known_prefix)
            prepared_days = zip(raw_days, known_prefix)
        for day in days:
            first, last = day.low, day.high
            prepared = None
            if prepared_days is not None:
                raw_day, current_known = next(prepared_days)
                prepared = raw_day, (current_known - previous_known) / 3600.0
                previous_known = current_known
            value = self.values(first, last, [day], prepared=prepared,
                                retain=self.retain_statistics_values if prepared is not None else True)
            day_complete = value.calendar_complete and self.work_complete
            unknown_periods += int(not day_complete)
            unavailable_periods += int(not day_complete and not value.known_day_count and not self.work_available)
            ratio, pressure, zero_task = value.known_ratio, value.high_pressure, value.zero_capacity_task
            if value.zero_capacity_reason is not None:
                zero_capacity_reason = value.zero_capacity_reason
            if pressure is True:
                high_periods.append({"date": day.date, "start": first.isoformat(), "end": last.isoformat(),
                    "available_hours": value.capacity,
                    "occupied_hours": value.raw["occupied_hours"] if value.calendar_complete and self.work_complete else None,
                    "summed_load_hours": value.raw["summed_load_hours"] if value.calendar_complete and self.work_complete else None,
                    "utilization_ratio": value.ratio, "demand_ratio": value.demand})
            overload_count += int(value.demand_overload is True)
            conflict_count += int(value.conflict is True)
            high_unknown |= pressure is None
            overload_unknown |= value.demand_overload is None
            conflict_unknown |= value.conflict is None
            if ratio is not None:
                peak = ratio if peak is None else max(peak, ratio)
            if pressure is True or pressure is None and high_pressure is False:
                high_pressure = pressure
            if zero_task is True or zero_task is None and zero_capacity_task is False:
                zero_capacity_task = zero_task
            zero_days += int(day.available and value.capacity == 0)
        result = {"known_peak_utilization": peak, "peak_utilization": peak if complete else None,
                  "daily_peak_utilization": peak if complete else None,
                  "high_pressure": high_pressure, "zero_capacity_task": zero_capacity_task, "zero_capacity_days": zero_days,
                  "zero_capacity_reason": zero_capacity_reason,
                  "demand_overload": True if overload_count else None if overload_unknown else False,
                  "high_pressure_period_count": None if high_unknown else len(high_periods),
                  "known_high_pressure_period_count": len(high_periods), "high_pressure_periods": high_periods,
                  "demand_overload_period_count": None if overload_unknown else overload_count,
                  "conflict_period_count": None if conflict_unknown else conflict_count}
        self._window_statistics_cache[key] = result
        if full_natural_window:
            self._day_filter_summary = {"state": "complete" if not unknown_periods else
                "unavailable" if unavailable_periods == len(days) else "partial",
                **{field: result[field] for field in (
                    "high_pressure", "demand_overload", "zero_capacity_task", "high_pressure_period_count",
                    "demand_overload_period_count", "conflict_period_count", "high_pressure_periods", "daily_peak_utilization")},
                "conflict": True if conflict_count else None if conflict_unknown else False,
                "period_peak_utilization": result["daily_peak_utilization"], "unknown_period_count": unknown_periods}
        return result

    def period_statistics(self, low, high, days, grain, group, *, whole=False):
        """Light interval facts for full-scope filtering, without task/detail DTOs."""
        key = low, high, grain, group, whole, self._day_key(days)
        if key in self._period_statistics_cache:
            return self._period_statistics_cache[key]
        value = self.values(low, high, days, potential_work=self.potential_work(low, high, whole=whole))
        complete = value.calendar_complete and self.work_complete
        result = {"state": "complete" if complete else "partial" if value.known_day_count or self.work_available else "unavailable",
                  "available_hours": value.capacity,
                  "occupied_hours": value.raw["occupied_hours"] if complete else None,
                  "summed_load_hours": value.raw["summed_load_hours"] if complete else None,
                  "utilization_ratio": value.ratio, "demand_ratio": value.demand,
                  "high_pressure": value.high_pressure, "demand_overload": value.demand_overload,
                  "zero_capacity_task": value.zero_capacity_task, "conflict": value.conflict}
        if grain == "week":
            result.update(self.window_statistics(low, high, days))
        else:
            signal = {"date": group, "start": low.isoformat(), "end": high.isoformat(),
                      **{field: result[field] for field in (
                          "available_hours", "occupied_hours", "summed_load_hours", "utilization_ratio", "demand_ratio")}}
            daily_peak = self.window_statistics(low, high, days)["daily_peak_utilization"] if grain == "shift" else value.ratio
            result.update(daily_peak_utilization=daily_peak,
                          high_pressure_period_count=None if value.high_pressure is None else int(value.high_pressure),
                          known_high_pressure_period_count=int(value.high_pressure is True),
                          high_pressure_periods=[signal] if value.high_pressure is True else [],
                          demand_overload_period_count=None if value.demand_overload is None else int(value.demand_overload),
                          conflict_period_count=None if value.conflict is None else int(value.conflict))
        self._period_statistics_cache[key] = result
        return result

    def details(self, low, high, days):
        rows = self.intervals.overlapping(low, high)
        natural = sweep_details(rows, self.intervals.unknown, low, high)
        windows = union(value for day in days if day.available for value in day.windows)
        clipped = [(first, last, task) for start, end, task in rows
                   for first, last in intersection([(max(start, low), min(end, high))], windows)]
        working = sweep_details(clipped, self.intervals.unknown, low, high)
        complete = all(day.available for day in days)
        known_calendar = any(day.available for day in days)
        tasks, reservations = [], []
        for (start, end, raw), task in zip(rows, natural["tasks"]):
            span = (min(end, high) - max(start, low)).total_seconds() / 3600
            occupied = hours(intersection([(max(start, low), min(end, high))], windows))
            item = {**task, "span_hours": span, "occupied_hours": occupied if complete else None,
                    "known_occupied_hours": occupied if known_calendar else None, "locked": raw.get("locked")}
            reservations.append(item)
            if occupied > 0 or not complete:
                tasks.append(item)
        tasks.extend({**task, "span_hours": None, "occupied_hours": None, "known_occupied_hours": None, "locked": None}
                     for task in natural["tasks"][len(rows):])
        known_contributors = {task["operation_ref"] for task in tasks
                              if task["operation_ref"] is not None and task["known_occupied_hours"] is not None and task["known_occupied_hours"] > 0}
        return {"conflicts": working["conflicts"], "tasks": tasks, "reservation_overlaps": natural["conflicts"],
                "reservations": reservations, "contribution_operation_count": len(known_contributors) if complete and self.work_complete else None,
                "known_contribution_operation_count": len(known_contributors) if known_calendar else None,
                "reservation_overlap_basis": "reservation_span_overlap"}


class ResourceTaskIndex:
    """Normalize each task once; query one resource's window or selected days."""

    def __init__(self, tasks, start, end, *, work_available=True, source="archived_resource_calendar", pressure_threshold=0.9,
                 task_intervals=None, retain_statistics_values=True):
        self.low, self.high = instant(start), instant(end)
        if self.low > self.high:
            raise WorkbenchCommandRejected("invalid_input", "资源比较窗口的结束不能早于开始。", 422)
        last = (self.high - timedelta(microseconds=1)).date() if self.low < self.high else self.low.date()
        if (last - self.low.date()).days + 1 > MAX_CALENDAR_DATES:
            raise WorkbenchCommandRejected("invalid_input", "资源比较窗口超过 3660 天，请缩小时间范围。", 422)
        self.work_available, self.source = work_available, source
        self.pressure_threshold = pressure_threshold
        self.retain_statistics_values = retain_statistics_values
        self.identity_issues = []
        self._unknown_issues = defaultdict(list)
        rows, unknown = defaultdict(list), defaultdict(list)
        for task, interval in occupying_tasks(tasks, self.low, self.high, task_intervals=task_intervals):
            for kind in KINDS:
                value = task.get(kind)
                if value is None or value.get("ref") is None:
                    self.identity_issues.append(identity_issue(kind))
                    continue
                key = (kind, value["ref"])
                if interval is None or task.get("operation_ref") is None:
                    unknown[key].append(task)
                    self._unknown_issues[key].append(_issue("task_time_unknown", "保存任务的时间或点事件依据缺项，占用和负荷保留已知小计。", "task_time")
                        if interval is None else _issue("operation_identity_unknown", "保存任务缺少永久工序身份，独立工序负荷未知。", "operation_ref"))
                else:
                    rows[key].append((max(interval[0], self.low), min(interval[1], self.high), task))
        self._resources = {key: ResourceIntervals(rows[key], unknown[key]) for key in rows.keys() | unknown.keys()}
        self._empty = ResourceIntervals([], [])
        self._last_sweep = None
        self._measurements = {}

    def _measurement(self, resource, calendar, *, retain_statistics_values):
        key = (resource["kind"], resource["ref"])
        current = self._measurements.get(key)
        if current is not None and current[0] is calendar:
            self._last_sweep = key, current[1].metrics.segments
            return current[1]
        intervals = self._resources.get(key, self._empty)
        measurement = _ResourceMeasurement(resource, intervals, calendar, self.low, self.high, self.work_available,
                                           self.source, self.pressure_threshold, self._unknown_issues.get(key, []),
                                           retain_statistics_values=retain_statistics_values)
        # Keep the current resource's sweep for an immediately requested legacy
        # segment DTO. Full-cohort summaries do not retain every resource sweep.
        self._last_sweep = key, measurement.metrics.segments
        self._measurements[key] = calendar, measurement
        return measurement

    def release(self, resource):
        """Drop one resource's calendar measurement once the caller keeps its compact summary."""
        self._measurements.pop((resource["kind"], resource["ref"]))

    def window(self, resource, calendar, *, start=None, end=None):
        measurement = self._measurement(resource, calendar, retain_statistics_values=self.retain_statistics_values)
        return measurement.window(instant(start) if start is not None else None, instant(end) if end is not None else None)

    def window_with_days(self, resource, calendar):
        """Whole-window fold and its day rows; this measurement keeps each day's values for the day rows."""
        measurement = self._measurement(resource, calendar, retain_statistics_values=True)
        return measurement.window(None, None), self.days(resource, calendar)

    def day_filter_summary(self, resource, calendar):
        """Return full natural-day filtering facts from the first window fold."""
        return self._measurement(resource, calendar, retain_statistics_values=self.retain_statistics_values)._day_filter_summary

    def segments(self, resource):
        """Known concurrency spans, reusing the same independent-operation sweep."""
        key = (resource["kind"], resource["ref"])
        intervals = self._resources.get(key, self._empty)
        if self._last_sweep is not None and self._last_sweep[0] == key:
            intervals.adopt_sweep(self._last_sweep[1])
        return [{"start": low.isoformat(), "end": high.isoformat(), "concurrent_operations": count}
                for low, high, count in intervals.swept] if self.work_available else []

    def days(self, resource, calendar, *, dates=None, details=False):
        if dates is not None and not dates:
            return []
        selected = set(dates) if dates is not None else None
        return [row for row in self.periods(resource, calendar, grain="day", details=details)
                if selected is None or row["date"] in selected]

    def _period_bounds(self, measurement, grain, start, end):
        low = max(self.low, instant(start)) if start is not None else self.low
        high = min(self.high, instant(end)) if end is not None else self.high
        if measurement.days:
            low = max(low, measurement.days[0].low)
            high = min(high, measurement.days[-1].high)
        if low > high:
            return []
        return measurement.calendar.periods_between(grain, low, high)

    @staticmethod
    def _period_identity(first, last, group, placeholder, grain):
        key = grain + ":" + first.isoformat() + "/" + last.isoformat()
        return {"key": key, "bucket_key": key, "group_key": group if grain == "shift" else key,
                "date": group, "grain": grain, "start": first.isoformat(), "end": last.isoformat(), "placeholder": placeholder}

    def period_facts(self, resource, calendar, *, grain="day", start=None, end=None):
        measurement = self._measurement(resource, calendar, retain_statistics_values=self.retain_statistics_values)
        return [{**self._period_identity(first, last, group, placeholder, grain),
                 **measurement.period_statistics(first, last, measurement.calendar.days_in(first, last), grain, group,
                    whole=grain == "week" and first == self.low and last == self.high)}
                for first, last, group, placeholder in self._period_bounds(measurement, grain, start, end)]

    def periods(self, resource, calendar, *, grain="day", start=None, end=None, details=False, group_keys=None):
        measurement = self._measurement(resource, calendar, retain_statistics_values=self.retain_statistics_values)
        result = []
        for first, last, group, placeholder in self._period_bounds(measurement, grain, start, end):
            identity = self._period_identity(first, last, group, placeholder, grain)
            if group_keys is not None and identity["group_key"] not in group_keys:
                continue
            days = measurement.calendar.days_in(first, last)
            whole = grain == "week" and first == self.low and last == self.high
            cell = measurement.cell(first, last, days, whole=whole)
            cell.update(measurement.period_statistics(first, last, days, grain, group, whole=whole), **identity)
            if details:
                cell.update(measurement.details(first, last, days) if self.work_available else
                            {"conflicts": [], "tasks": [], "reservation_overlaps": [], "reservations": [], "contribution_operation_count": None,
                             "known_contribution_operation_count": None,
                             "reservation_overlap_basis": "reservation_span_overlap"})
            result.append(cell)
        return result
