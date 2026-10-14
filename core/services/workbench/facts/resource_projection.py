"""Shared archived-resource occupancy, demand, daily pressure and detail facts.

Task identity/time is indexed once for the comparison window. Calendar capacity
and workload availability remain independent; unknown days never become outside
calendar time or zero capacity. All arithmetic keeps its original precision.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import IntervalIndex, hours, instant, intersection, union
from core.services.capacity.plan_calendar_limits import MAX_CALENDAR_DATES
from core.services.capacity.resource_utilization_metrics import ResourceUtilizationMetrics

from .candidate_tasks import _resource
from .resource_intervals import KINDS, ResourceIntervals, details, resource_cohort, task_interval
from .resource_summary import resource_summary

RESOURCE_METRIC_VERSION = "decision-resource-v4"
__all__ = ["ResourceTaskIndex", "normalize_resource_calendar", "resource_cohort", "resource_summary", "resource_day_bounds", "resource_period_bounds", "RESOURCE_METRIC_VERSION"]

_INSIDE_FIELDS = ("occupied_hours", "summed_load_hours", "outside_calendar_hours", "overlap_hours")
_SPAN_FIELDS = ("span_occupied_hours", "span_summed_hours", "span_overlap_hours", "overlap_span_hours")


def saved_resource_tasks(rows, facts, resources, *, operation_refs=None):
    """Feed verified saved arrangements to the common cohort without rich DTOs."""
    for row in rows:
        if operation_refs is not None and row["operation_ref"] not in operation_refs:
            continue
        payload = row["payload"]
        task = {"row_ref": row["row_ref"], "source": payload["source"]}
        for kind in KINDS:
            key = kind, payload[kind + "_id"]
            if key not in resources:
                resources[key] = _resource(facts, kind, key[1], [])
            task[kind] = resources[key]
        yield task


def _days(low, high):
    if low == high:
        yield low, high
    while low < high:
        boundary = high if low.date() == date.max else datetime.combine(low.date() + timedelta(days=1), time.min)
        end = min(high, boundary)
        yield low, end
        low = end


def resource_day_bounds(start, end):
    """Factory-local half-open natural-day slices of an already selected window."""
    return _days(instant(start), instant(end))


def resource_period_bounds(start, end, grain="day"):
    """Clip natural hours, days or Monday-based weeks to the selected window."""
    low, high = instant(start), instant(end)
    if grain == "day" or low == high:
        yield from _days(low, high)
        return
    while low < high:
        if grain == "hour":
            step = low.replace(minute=0, second=0, microsecond=0) - low + timedelta(hours=1)
        elif grain == "week":
            step = datetime.combine(low.date(), time.min) - low + timedelta(days=7 - low.weekday())
        else:
            raise ValueError("Expected hour, day or week resource grain")
        stop = low + min(high - low, step)
        yield low, stop
        low = stop


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


def _calendar_days(calendar, low, high) -> List[Dict[str, Any]]:
    if calendar is not None and "days" in calendar:
        return calendar["days"]
    # Legacy/current snapshot adapters supply the same explicit full-window
    # calendar projection. Its capacity state applies to each clipped day.
    available = calendar is not None and calendar["state"] == "available"
    windows = calendar["windows"] if available else None
    issues = calendar.get("issues", []) if calendar is not None else [
        _issue("calendar_unavailable", "保存的资源班表缺项，容量未知。")]
    return [{"date": start.date().isoformat(), "start": start.isoformat(), "end": end.isoformat(),
             "state": "available" if available else "unavailable", "windows": windows, "issues": issues}
            for start, end in _days(low, high)]


class _CalendarDay(NamedTuple):
    date: str
    low: datetime
    high: datetime
    available: bool
    windows: List[Tuple[datetime, datetime]]
    shifts: List[Tuple[datetime, datetime, str]]
    issues: List[Dict[str, Any]]


class _ResourceCalendar:
    """One resource's calendar geometry, shared by all compared task indexes."""

    def __init__(self, calendar, low, high):
        self.days = []
        for row in _calendar_days(calendar, low, high):
            first, last = instant(row["start"]), instant(row["end"])
            available = row["state"] == "available"
            shifts = []
            for window in row["windows"] if available else []:
                if window["allow_normal"] or window["allow_urgent"]:
                    start, end = instant(window["start"]), instant(window["end"])
                    shifts.append((start, end, window.get("policy_date") or start.date().isoformat()))
            self.days.append(_CalendarDay(row["date"], first, last, available,
                union((start, end) for start, end, _ in shifts), shifts, row.get("issues", [])))
        self.known_days = [day for day in self.days if day.available]
        self.windows = union(value for day in self.known_days for value in day.windows)
        self.known_coverage = union((day.low, day.high) for day in self.known_days)


def normalize_resource_calendar(calendar, start, end):
    """Normalize the common saved calendar once; raw legacy callers use this too."""
    return calendar if isinstance(calendar, _ResourceCalendar) else _ResourceCalendar(calendar, instant(start), instant(end))


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
    def __init__(self, resource, intervals, calendar, low, high, work_available, source, threshold, unknown_issues):
        self.resource, self.intervals = resource, intervals
        self.low, self.high, self.work_available, self.source = low, high, work_available, source
        self.threshold = threshold
        self.calendar = normalize_resource_calendar(calendar, low, high)
        self.days, self.known_days = self.calendar.days, self.calendar.known_days
        self.windows = self.calendar.windows
        self.metrics = ResourceUtilizationMetrics(intervals.intervals, self.windows)
        self.known_span = IntervalIndex(intersection(self.metrics.span.intervals, self.calendar.known_coverage))
        self.work_complete = work_available and not intervals.unknown
        self.work_state = "complete" if self.work_complete else "partial" if work_available and intervals.rows else "unavailable"
        self.work_issues = []
        if not work_available:
            self.work_issues.append(_issue("arrangements_unavailable", "比较对象的安排归档缺项，占用和负荷未知。"))
        elif intervals.unknown:
            self.work_issues.extend(unknown_issues)

    def _values(self, low, high, calendar_days, *, potential_work=None):
        known_day_count = sum(day.available for day in calendar_days)
        capacity_complete = known_day_count == len(calendar_days)
        raw = self.metrics.window(low, high, precision=None)
        raw["overlap_span_hours"] = raw["span_overlap_hours"]
        raw["span_overlap_hours"] = raw["span_summed_hours"] - raw["span_occupied_hours"]
        # Only known natural-day slices support an outside-calendar conclusion.
        raw["outside_calendar_hours"] = self.known_span.hours_between(low, high) - raw["occupied_hours"]
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
        values = self._values(low, high, calendar_days, potential_work=task_count > 0 or not self.work_complete)
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

    def _days_in(self, low, high):
        return [day if low <= day.low and day.high <= high else day._replace(low=max(low, day.low), high=min(high, day.high))
                for day in self.days if day.low < high and day.high > low
                or low == high and day.low <= low <= day.high]

    def window(self, low=None, high=None):
        low, high = self.low if low is None else low, self.high if high is None else high
        days = self._days_in(low, high)
        result = self.cell(low, high, days, whole=low == self.low and high == self.high)
        # Peak and pressure cover every archived day, independently of the UI page.
        peak, high_pressure, zero_capacity_task, zero_days = None, False, False, 0
        high_periods, overload_count, conflict_count = [], 0, 0
        high_unknown = overload_unknown = conflict_unknown = False
        zero_capacity_reason = None
        for day in days:
            first, last = day.low, day.high
            value = self._values(first, last, [day])
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
        result.update(known_peak_utilization=peak,
                      peak_utilization=peak if result["calendar_state"] == "complete" and self.work_complete else None,
                      daily_peak_utilization=peak if result["calendar_state"] == "complete" and self.work_complete else None,
                      high_pressure=high_pressure, zero_capacity_task=zero_capacity_task, zero_capacity_days=zero_days,
                      zero_capacity_reason=zero_capacity_reason,
                      demand_overload=True if overload_count else None if overload_unknown else False,
                      high_pressure_period_count=None if high_unknown else len(high_periods),
                      known_high_pressure_period_count=len(high_periods), high_pressure_periods=high_periods,
                      demand_overload_period_count=None if overload_unknown else overload_count,
                      conflict_period_count=None if conflict_unknown else conflict_count)
        return result

    def details(self, low, high, days):
        rows = self.intervals.overlapping(low, high)
        natural = _details(rows, self.intervals.unknown, low, high)
        windows = union(value for day in days if day.available for value in day.windows)
        clipped = [(first, last, task) for start, end, task in rows
                   for first, last in intersection([(max(start, low), min(end, high))], windows)]
        working = _details(clipped, self.intervals.unknown, low, high)
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
                 task_intervals=None):
        self.low, self.high = instant(start), instant(end)
        if self.low > self.high:
            raise WorkbenchCommandRejected("invalid_input", "资源比较窗口的结束不能早于开始。", 422)
        last = (self.high - timedelta(microseconds=1)).date() if self.low < self.high else self.low.date()
        if (last - self.low.date()).days + 1 > MAX_CALENDAR_DATES:
            raise WorkbenchCommandRejected("invalid_input", "资源比较窗口超过 3660 天，请缩小时间范围。", 422)
        self.work_available, self.source = work_available, source
        self.pressure_threshold = pressure_threshold
        self.identity_issues = []
        self._unknown_issues = defaultdict(list)
        rows, unknown = defaultdict(list), defaultdict(list)
        for task in tasks:
            interval = task_interval(task) if task_intervals is None else task_intervals[task["row_ref"]]
            if task.get("source") == "external" or interval is not None and interval[0] == interval[1]:
                continue
            if interval is not None and not (interval[0] < self.high and interval[1] > self.low):
                continue
            for kind in KINDS:
                value = task.get(kind)
                if value is None or value.get("ref") is None:
                    self.identity_issues.append({**_issue("resource_identity_unknown", "保存任务缺少永久资源身份，资源汇总保留覆盖缺口。", kind), "kind": kind})
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

    def _measurement(self, resource, calendar):
        key = (resource["kind"], resource["ref"])
        intervals = self._resources.get(key, self._empty)
        measurement = _ResourceMeasurement(resource, intervals, calendar, self.low, self.high, self.work_available,
                                           self.source, self.pressure_threshold, self._unknown_issues.get(key, []))
        # Keep the current resource's sweep for an immediately requested legacy
        # segment DTO. Full-cohort summaries do not retain every resource sweep.
        self._last_sweep = key, measurement.metrics.segments
        return measurement

    def window(self, resource, calendar, *, start=None, end=None):
        return self._measurement(resource, calendar).window(instant(start) if start is not None else None,
                                                            instant(end) if end is not None else None)

    def segments(self, resource):
        """Known concurrency spans, reusing the same independent-operation sweep."""
        key = (resource["kind"], resource["ref"])
        intervals = self._resources.get(key, self._empty)
        if self._last_sweep is not None and self._last_sweep[0] == key:
            intervals._swept = self._last_sweep[1]
        return [{"start": low.isoformat(), "end": high.isoformat(), "concurrent_operations": count}
                for low, high, count in intervals.swept] if self.work_available else []

    def days(self, resource, calendar, *, dates=None, details=False):
        if dates is not None and not dates:
            return []
        selected = set(dates) if dates is not None else None
        return [row for row in self.periods(resource, calendar, grain="day", details=details)
                if selected is None or row["date"] in selected]

    def periods(self, resource, calendar, *, grain="day", start=None, end=None, details=False):
        measurement = self._measurement(resource, calendar)
        low = max(self.low, instant(start)) if start is not None else self.low
        high = min(self.high, instant(end)) if end is not None else self.high
        if measurement.days:
            low = max(low, measurement.days[0].low)
            high = min(high, measurement.days[-1].high)
        if low > high:
            return []
        bounds = []
        if grain == "shift":
            groups = defaultdict(list)
            for day in measurement._days_in(low, high):
                for start, end, policy_date in day.shifts:
                    first, last = max(low, day.low, start), min(high, day.high, end)
                    if first < last:
                        groups[policy_date].append((first, last))
                if not day.available or not intersection(day.windows, [(day.low, day.high)]):
                    bounds.append((day.low, day.high, day.date, "rest" if day.available else "unknown"))
            bounds.extend((first, last, first.date().isoformat(), None)
                          for values in groups.values() for first, last in union(values))
            bounds.sort(key=lambda row: (row[0], row[1]))
        else:
            bounds = [(first, last, first.date().isoformat(), None) for first, last in resource_period_bounds(low, high, grain)]
        result = []
        for first, last, group, placeholder in bounds:
            days = measurement._days_in(first, last)
            cell = measurement.window(first, last) if grain == "week" else measurement.cell(first, last, days)
            key = grain + ":" + first.isoformat() + "/" + last.isoformat()
            cell.update(key=key, bucket_key=key, group_key=group if grain == "shift" else key, date=group, grain=grain,
                        start=first.isoformat(), end=last.isoformat(), placeholder=placeholder)
            if grain != "week":
                signal = {"date": group, "start": first.isoformat(), "end": last.isoformat(),
                          **{field: cell[field] for field in ("available_hours", "occupied_hours", "summed_load_hours", "utilization_ratio", "demand_ratio")}}
                daily_peak = measurement.window(first, last)["daily_peak_utilization"] if grain == "shift" else cell["peak_utilization"]
                cell.update(daily_peak_utilization=daily_peak,
                            high_pressure_period_count=None if cell["high_pressure"] is None else int(cell["high_pressure"]),
                            known_high_pressure_period_count=int(cell["high_pressure"] is True),
                            high_pressure_periods=[signal] if cell["high_pressure"] is True else [],
                            demand_overload_period_count=None if cell["demand_overload"] is None else int(cell["demand_overload"]),
                            conflict_period_count=None if cell["conflict"] is None else int(cell["conflict"]))
            if details:
                cell.update(measurement.details(first, last, days) if self.work_available else
                            {"conflicts": [], "tasks": [], "reservation_overlaps": [], "reservations": [], "contribution_operation_count": None,
                             "known_contribution_operation_count": None,
                             "reservation_overlap_basis": "reservation_span_overlap"})
            result.append(cell)
        return result


# The public ``details`` query option describes the DTO; the imported sweep keeps
# its separate function identity so the option cannot shadow the implementation.
_details = details
