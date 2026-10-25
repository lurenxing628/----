"""Shared resource facts distinguish independent demand and missing evidence."""

import pytest

from core.services.capacity import plan_calendar_intervals
from core.services.capacity.plan_calendar_intervals import IntervalIndex, instant
from core.services.capacity.resource_utilization_metrics import ResourceUtilizationMetrics
from core.services.workbench.facts import resource_calendar, resource_intervals, resource_projection
from core.services.workbench.facts.resource_calendar import normalize_resource_calendar
from core.services.workbench.facts.resource_projection import (
    ResourceTaskIndex,
    resource_cohort,
    resource_summary,
)

MACHINE = {"ref": "m:lathe", "kind": "machine", "label": "归档设备"}
OPERATOR = {"ref": "o:worker", "kind": "operator", "label": "归档人员"}
DAY = "2026-09-09"


def at(hour, day=DAY):
    return day + "T" + hour


def task(row, operation, start, end, **values):
    return {"row_ref": row, "operation_ref": operation, "batch_ref": "b:one", "batch_label": "批次",
            "process_label": operation, "source": "internal", "machine": MACHINE, "operator": OPERATOR,
            "start": start, "end": end, **values}


def day_calendar(start, end, windows, *, state="available"):
    return {"date": start[:10], "start": start, "end": end, "state": state, "issues": [] if state == "available" else [
        {"code": "calendar_unavailable", "message": "保存班表缺项。"}],
            "windows": [{"start": low, "end": high, "allow_normal": True, "allow_urgent": False}
                        for low, high in windows] if state == "available" else None}


def calendar(*days):
    return {"days": list(days)}


def test_operation_segments_merge_before_independent_demand_and_conflict_sweep(monkeypatch):
    start, end = at("08:00:00"), at("11:00:00")
    rows = [task("a1", "op:a", start, at("10:00:00")), task("a2", "op:a", at("09:00:00"), end),
            task("b", "op:b", at("09:00:00"), at("10:00:00")),
            task("c", "op:c", at("09:00:00"), at("10:00:00"))]
    saved = calendar(day_calendar(start, end, [(start, end)]))
    parsed = {row["row_ref"]: resource_intervals.task_interval(row) for row in rows}
    normalized_inputs, original_union = [], plan_calendar_intervals.union

    def unexpected_parse(_row):
        pytest.fail("该来源已核实的区间应直接复用。")

    def record_raw_union(values):
        values = list(values)
        normalized_inputs.append(values)
        return original_union(values)

    with monkeypatch.context() as scoped:
        scoped.setattr(resource_intervals, "task_interval", unexpected_parse)
        assert resource_cohort([rows], task_intervals=[parsed]) == [MACHINE, OPERATOR]
        index = ResourceTaskIndex(rows, start, end, task_intervals=parsed)
        scoped.setattr(plan_calendar_intervals, "union", record_raw_union)
        window = index.window(MACHINE, saved)
    # Internal normalized calendar and occupancy results construct indexes directly.
    assert normalized_inputs == []
    assert window["occupied_hours"] == 3
    assert window["summed_load_hours"] == 5
    assert window["overlap_hours"] == window["span_overlap_hours"] == 2
    assert window["overlap_span_hours"] == 1
    assert window["demand_ratio"] == pytest.approx(5 / 3)
    assert window["task_count"] == 4 and window["operation_count"] == 3
    assert all(intervals._tree is None for intervals in index._resources.values())
    assert index.segments(MACHINE) == [{"start": start, "end": at("09:00:00"), "concurrent_operations": 1},
                                       {"start": at("09:00:00"), "end": at("10:00:00"), "concurrent_operations": 3},
                                       {"start": at("10:00:00"), "end": end, "concurrent_operations": 1}]
    day = index.days(MACHINE, saved, details=True)[0]
    assert day["operation_count"] == 3
    assert day["conflicts"] == [{"start": at("09:00:00"), "end": at("10:00:00"),
                                 "operation_refs": ["op:a", "op:b", "op:c"], "row_refs": ["a1", "a2", "b", "c"]}]
    # Two disjoint segments of one operation within a day still count once.
    split = ResourceTaskIndex([task("s1", "op:a", start, at("09:00:00")),
                               task("s2", "op:a", at("10:00:00"), end)], start, end)
    assert split.days(MACHINE, saved)[0]["operation_count"] == 1
    # Multiplicity changes leave adjacent overlap pieces; their span stays one union.
    varied = ResourceUtilizationMetrics(
        [(instant(start), instant(at("12:00:00"))), (instant(at("09:00:00")), instant(end)),
         (instant(at("10:00:00")), instant(at("13:00:00"))), (instant(at("09:00:00")), instant(at("09:00:00")))],
        [(instant(at("12:00:00")), instant(at("13:00:00"))), (instant(start), instant(at("10:00:00"))),
         (instant(at("09:00:00")), instant(at("12:00:00"))), (instant(start), instant(start))])
    assert varied.span_overlap.intervals == [(instant(at("09:00:00")), instant(at("12:00:00")))]
    value = varied.window(instant(start), instant(at("13:00:00")))
    assert value["available_hours"] == value["occupied_hours"] == value["span_occupied_hours"] == 5
    assert value["summed_load_hours"] == 9 and value["overlap_hours"] == 4 and value["span_overlap_hours"] == 3


def test_normalized_interval_index_reuses_union_and_preserves_half_open_finish_boundaries(monkeypatch):
    first, boundary, second, last = (instant(at(hour)) for hour in ("08:00:00", "09:00:00", "10:00:00", "11:00:00"))
    raw = IntervalIndex([(second, last), (first, boundary), (boundary, boundary)])
    raw_usage = ResourceUtilizationMetrics([(first, last)], [(second, last), (first, boundary), (boundary, boundary)])

    def unexpected_union(_values):
        pytest.fail("规范化区间直接建索引，应复用原合并结果。")

    monkeypatch.setattr(plan_calendar_intervals, "union", unexpected_union)
    normalized = IntervalIndex.from_normalized(raw.intervals)
    assert normalized.intervals == raw.intervals and normalized.prefix == raw.prefix
    assert normalized.hours_between(first, last) == 2
    assert normalized.hours_between(boundary, second) == normalized.hours_between(boundary, boundary) == 0
    assert [normalized.contains(at) for at in (first, boundary, second, last)] == [True, False, True, False]
    assert [normalized.contains(at, ending=True) for at in (first, boundary, second, last)] == [False, True, False, True]
    normalized_usage = ResourceUtilizationMetrics.from_normalized_availability([(first, last)], raw_usage.calendar.available.intervals)
    assert normalized_usage.window(first, last) == raw_usage.window(first, last)
    unknown_usage = ResourceUtilizationMetrics([(first, last)], None).window(first, last)
    assert unknown_usage["available_hours"] is None and unknown_usage["reason"] == "calendar_unavailable"
    assert ResourceUtilizationMetrics.from_normalized_availability([(first, last)], None).window(first, last) == unknown_usage

    from bisect import bisect_right
    from datetime import timedelta

    from core.services.capacity.resource_utilization_metrics import METRIC_VERSION, _WeightedIndex

    def original_before(index, point):
        position = bisect_right(index.starts, point) - 1
        if position < 0:
            return 0.0
        row = (index.rows if isinstance(index, _WeightedIndex) else index.intervals)[position]
        seconds = (min(point, row[1]) - row[0]).total_seconds()
        return index.prefix[position] + (seconds * row[2] if len(row) == 3 else seconds)

    fractional = [(first + timedelta(microseconds=17), boundary + timedelta(microseconds=31)),
                  (second + timedelta(microseconds=41), last + timedelta(microseconds=59))]
    points = [first, fractional[0][0], first + timedelta(minutes=30), fractional[0][1],
              boundary + timedelta(minutes=30), fractional[1][0], fractional[1][1], last + timedelta(seconds=1)]
    indexes = [IntervalIndex.from_normalized([]), _WeightedIndex([]), IntervalIndex.from_normalized(fractional),
               _WeightedIndex([(low, high, count) for (low, high), count in zip(fractional, (3, 2))])]
    for index in indexes:
        for point in points:
            assert index._before(point) == original_before(index, point)
            assert index.hours_between(point, point) == 0
        for low, high in ((first, points[-1]), (fractional[0][1], fractional[1][0]), (points[2], points[6])):
            assert index.hours_between(low, high) == (original_before(index, high) - original_before(index, low)) / 3600.0

    usage = ResourceUtilizationMetrics.from_normalized_availability(
        [(fractional[0][0], fractional[1][1]), (points[2], fractional[0][1])], fractional, source="actual")
    unrounded = usage.window(first, points[-1], precision=None)
    with monkeypatch.context() as scoped:
        scoped.setattr(IntervalIndex, "_before", original_before)
        scoped.setattr(_WeightedIndex, "_before", original_before)
        assert unrounded == usage.window(first, points[-1], precision=None)
    metadata = {"metric_version": METRIC_VERSION, "source": "actual", "reason": None}
    fields = {"available_hours", "occupied_hours", "summed_load_hours", "overlap_hours", "outside_calendar_hours",
              "utilization_ratio", "span_occupied_hours", "span_summed_hours", "span_overlap_hours"}
    assert set(unrounded) == fields | set(metadata)
    assert {key: unrounded[key] for key in metadata} == metadata
    for precision in (0, 3, 6):
        expected = {key: round(unrounded[key], precision) if unrounded[key] is not None else None for key in fields}
        assert usage.window(first, points[-1], precision=precision) == {**expected, **metadata}
    assert usage.window(first, points[-1]) == usage.window(first, points[-1], precision=6)
    unrounded["occupied_hours"] = -1
    assert usage.window(first, points[-1], precision=None)["occupied_hours"] != -1
    zero = ResourceUtilizationMetrics.from_normalized_availability([], []).window(first, first, precision=None)
    assert zero["reason"] == "zero_available_capacity" and zero["utilization_ratio"] is None
    assert all(zero[key] == 0 for key in fields - {"utilization_ratio"})

    ordered_points = [points[0], points[0], *points[1:4], points[3], *points[4:], points[-1]]
    for index in indexes:
        assert list(index.prefix_values_at_sorted([])) == []
        assert list(index.prefix_values_at_sorted(iter(ordered_points))) == [index._before(point) for point in ordered_points]
    usages = [usage, ResourceUtilizationMetrics.from_normalized_availability(usage.span.intervals, None),
              ResourceUtilizationMetrics.from_normalized_availability(usage.span.intervals, []),
              ResourceUtilizationMetrics.from_normalized_availability([], fractional)]
    for calculator in usages:
        assert list(calculator.windows_at_boundaries([])) == []
        assert list(calculator.windows_at_boundaries([first])) == []
        for precision in (None, 6):
            actual = list(calculator.windows_at_boundaries(iter(ordered_points), precision=precision))
            expected = [calculator.window(low, high, precision=precision) for low, high in zip(ordered_points, ordered_points[1:])]
            assert actual == expected and len(actual) == len(ordered_points) - 1
        assert list(calculator.windows_at_boundaries(ordered_points, precision=6)) == [
            calculator.window(low, high) for low, high in zip(ordered_points, ordered_points[1:])]

    consumed = []

    def observed_boundaries():
        for point in ordered_points:
            consumed.append(point)
            yield point

    stream = usage.windows_at_boundaries(observed_boundaries())
    assert consumed == []
    assert next(stream) == usage.window(ordered_points[0], ordered_points[1], precision=None)
    assert consumed == ordered_points[:2]
    remaining = list(stream)
    assert remaining == [usage.window(low, high, precision=None) for low, high in zip(ordered_points[1:], ordered_points[2:])]
    assert len({id(result) for result in remaining}) == len(remaining)


def test_partial_calendar_preserves_known_subtotals_and_does_not_label_unknown_day_outside():
    from core.services.workbench.run.decision_resource_engine import _period_summary

    start, midnight, end = at("23:00:00"), at("00:00:00", "2026-09-10"), at("02:00:00", "2026-09-10")
    rows = [task("a", "op:a", start, end), task("right", "op:right", end, at("03:00:00", "2026-09-10"))]
    saved = calendar(day_calendar(start, midnight, [(start, midnight)]),
                     day_calendar(midnight, end, [], state="unavailable"))
    index = ResourceTaskIndex(rows, start, end)
    whole = index.window(MACHINE, saved)
    assert whole["state"] == "partial" and whole["unknown_days"] == 1
    assert whole["available_hours"] is whole["occupied_hours"] is whole["outside_calendar_hours"] is None
    assert whole["known_available_hours"] == whole["known_occupied_hours"] == 1
    assert whole["known_outside_calendar_hours"] == 0
    assert whole["span_occupied_hours"] == whole["span_summed_hours"] == 3
    assert whole["high_pressure"] is True and whole["known_peak_utilization"] == 1
    assert whole["peak_utilization"] is None
    assert whole["zero_capacity_task"] is None
    measurement = index._measurement(MACHINE, saved)
    point = instant(midnight)
    zero_days = measurement.calendar.days_in(point, point)
    assert zero_days == [day._replace(low=point, high=point) for day in measurement.days]
    assert [day.available for day in zero_days] == [True, False]
    zero = measurement.cell(point, point, zero_days)
    assert zero["calendar_state"] == "partial" and zero["unknown_days"] == 1
    assert zero["available_hours"] is None and zero["known_available_hours"] == 0
    zero_index = ResourceTaskIndex(rows, midnight, midnight)
    zero_index.window(MACHINE, measurement.calendar)
    assert zero_index.day_filter_summary(MACHINE, measurement.calendar) is None
    assert measurement.calendar.days_in(instant(at("23:30:00")), point) == [
        measurement.days[0]._replace(low=instant(at("23:30:00")))]
    assert measurement.calendar.days_in(point, instant(at("01:00:00", "2026-09-10"))) == [
        measurement.days[1]._replace(high=instant(at("01:00:00", "2026-09-10")))]
    selected = index.days(MACHINE, saved, dates=["2026-09-10"], details=True)
    assert len(selected) == 1 and selected[0]["span_occupied_hours"] == 2
    assert selected[0]["outside_calendar_hours"] is selected[0]["known_outside_calendar_hours"] is None
    assert selected[0]["zero_capacity_task"] is None
    assert [row["row_ref"] for row in selected[0]["tasks"]] == ["a"]
    assert selected[0]["contribution_operation_count"] is selected[0]["known_contribution_operation_count"] is None
    assert index.days(MACHINE, saved, dates=[]) == []
    confirmed_zero = calendar(day_calendar(start, midnight, []),
                              day_calendar(midnight, end, [], state="unavailable"))
    value = index.window(MACHINE, confirmed_zero)
    assert value["zero_capacity_task"] is None
    assert value["zero_capacity_reason"]["code"] == "actual_work_fragments_not_recorded"
    # Known minutes share one interval total; an unknown third day stays unknown.
    monday, tuesday, wednesday, thursday = "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10"
    first, last = at("00:00:00", monday), at("00:00:00", thursday)
    minute_rows = [task("six", "op:six", at("08:00:00", monday), at("08:06:00", monday)),
                   task("forty-two", "op:forty-two", at("08:00:00", tuesday), at("08:42:00", tuesday))]
    minute_calendar = calendar(
        day_calendar(first, at("00:00:00", tuesday), [(minute_rows[0]["start"], minute_rows[0]["end"])]),
        day_calendar(at("00:00:00", tuesday), at("00:00:00", wednesday), [(minute_rows[1]["start"], minute_rows[1]["end"])]),
        day_calendar(at("00:00:00", wednesday), last, [], state="unavailable"))
    minute_index = ResourceTaskIndex(minute_rows, first, last)
    minute_window = minute_index.window(MACHINE, minute_calendar)
    minute_filter = minute_index.day_filter_summary(MACHINE, minute_calendar)
    assert minute_filter == _period_summary(minute_index.period_facts(MACHINE, minute_calendar),
                                           minute_window["daily_peak_utilization"])
    assert minute_window["conflict"] is None and minute_filter["conflict"] is False
    assert minute_filter["unknown_period_count"] == 1 and minute_filter["state"] == "partial"
    for fact in (minute_window, resource_summary([minute_window])):
        assert fact["state"] == "partial"
        assert fact["available_hours"] is fact["occupied_hours"] is fact["outside_calendar_hours"] is None
        assert fact["known_available_hours"] == fact["known_occupied_hours"] == 0.8
        assert fact["known_outside_calendar_hours"] == 0
    transient_minutes = ResourceTaskIndex(minute_rows, first, last, retain_statistics_values=False)
    assert transient_minutes.window(MACHINE, minute_calendar) == minute_window
    assert transient_minutes.day_filter_summary(MACHINE, minute_calendar) == minute_filter
    transient_measurement = transient_minutes._measurement(MACHINE, minute_calendar)
    assert len(transient_measurement._value_cache) == 1


def test_known_zero_capacity_external_and_point_tasks_use_saved_assignments():
    start, end = at("08:00:00"), at("10:00:00")
    point_machine = {**MACHINE, "ref": "m:point"}
    external_machine = {**MACHINE, "ref": "m:external"}
    rows = [task("a", "op:a", start, end, source=None),
            task("point", "op:p", start, start, machine=point_machine, event_kind="point", occupies_resources=False),
            task("external", "op:e", start, end, source="external", machine=external_machine)]
    assert resource_cohort([rows]) == [MACHINE, OPERATOR]
    index = ResourceTaskIndex(rows, start, end)
    zero = index.window(MACHINE, calendar(day_calendar(start, end, [])))
    assert zero["available_hours"] == zero["occupied_hours"] == zero["summed_load_hours"] == 0
    assert zero["span_occupied_hours"] == zero["outside_calendar_hours"] == 2
    assert zero["zero_capacity_task"] is None and zero["utilization_ratio"] is None
    assert zero["calendar_state"] == "complete" and zero["actual_work_state"] == "not_recorded"
    assert zero["zero_capacity_reason"]["code"] == "actual_work_fragments_not_recorded"
    assert zero["task_count"] == zero["operation_count"] == 1


def test_unknown_workload_and_absent_arrangements_keep_capacity_and_idle_semantics_independent():
    from core.services.workbench.run.decision_resource_engine import _period_summary

    start, end = at("08:00:00"), at("10:00:00")
    saved = calendar(day_calendar(start, end, [(start, end)]))
    rows = [task("known", "op:k", start, at("09:00:00")), task("missing", "op:m", None, end)]
    parsed = {row["row_ref"]: resource_intervals.task_interval(row) for row in rows}
    partial_index = ResourceTaskIndex(rows, start, end, task_intervals=parsed)
    partial = partial_index.window(MACHINE, saved)
    partial_filter = partial_index.day_filter_summary(MACHINE, saved)
    assert partial_filter == _period_summary(partial_index.period_facts(MACHINE, saved), partial["daily_peak_utilization"])
    assert partial["unknown_days"] == 0 and partial_filter["unknown_period_count"] == 1
    assert partial["available_hours"] == 2 and partial["state"] == "partial"
    assert partial["occupied_hours"] is partial["span_occupied_hours"] is partial["task_count"] is None
    assert partial["known_occupied_hours"] == partial["known_span_occupied_hours"] == 1
    assert partial["known_task_count"] == partial["known_operation_count"] == partial["unknown_workload_count"] == 1
    assert partial["conflict"] is None
    assert partial["issues"] == [{"code": "task_time_unknown", "message": "保存任务的时间或点事件依据缺项，占用和负荷保留已知小计。", "field": "task_time"}]
    transient_single = ResourceTaskIndex(rows, start, end, task_intervals=parsed, retain_statistics_values=False)
    assert transient_single.window(MACHINE, saved) == partial
    assert len(transient_single._measurement(MACHINE, saved)._value_cache) == 1
    details = ResourceTaskIndex(rows, start, end).periods(MACHINE, saved, details=True)[0]
    assert details["contribution_operation_count"] is None and details["known_contribution_operation_count"] == 1
    absent = ResourceTaskIndex([], start, end, work_available=False).window(MACHINE, saved)
    assert absent["available_hours"] == 2
    assert absent["occupied_hours"] is absent["known_occupied_hours"] is absent["task_count"] is None
    assert absent["issues"][0]["code"] == "arrangements_unavailable"
    absent_zero = ResourceTaskIndex([], start, end, work_available=False).window(MACHINE, calendar(day_calendar(start, end, [])))
    assert absent_zero["zero_capacity_task"] is None
    idle = ResourceTaskIndex([], start, end).window(MACHINE, saved)
    assert idle["state"] == "complete" and idle["occupied_hours"] == idle["utilization_ratio"] == 0
    assert idle["high_pressure"] is idle["zero_capacity_task"] is idle["conflict"] is False
    idle_unknown = ResourceTaskIndex([], start, end).window(MACHINE, calendar(day_calendar(start, end, [], state="unavailable")))
    assert idle_unknown["zero_capacity_task"] is False
    zero_index = ResourceTaskIndex([task("clipped", "op:clipped", at("07:00:00"), at("09:00:00"))], start, start)
    zero_calendar = calendar(day_calendar(start, start, [], state="unavailable"))
    zero_week = zero_index.periods(MACHINE, zero_calendar, grain="week")[0]
    assert zero_week["task_count"] == zero_week["operation_count"] == 1
    assert zero_week["conflict"] is None
    assert zero_week["high_pressure"] is zero_week["zero_capacity_task"] is False
    zero_fact = zero_index.period_facts(MACHINE, zero_calendar, grain="week")[0]
    assert {field: zero_week[field] for field in zero_fact} == zero_fact
    assert zero_index.day_filter_summary(MACHINE, zero_calendar) is None
    transient_zero = ResourceTaskIndex([task("clipped", "op:clipped", at("07:00:00"), at("09:00:00"))],
                                       start, start, retain_statistics_values=False)
    assert transient_zero.periods(MACHINE, zero_calendar, grain="week")[0] == zero_week
    assert transient_zero._measurement(MACHINE, zero_calendar)._value_cache == zero_index._measurement(MACHINE, zero_calendar)._value_cache
    missing_identity = ResourceTaskIndex([task("lost", "op:lost", start, end, machine=None)], start, end)
    assert missing_identity.identity_issues == [{"code": "resource_identity_unknown",
                                               "message": "保存任务缺少永久资源身份，资源汇总保留覆盖缺口。",
                                               "field": "machine", "kind": "machine"}]


def test_unproven_formal_zero_interval_keeps_assigned_cohort_and_unknown_workload():
    start, end = at("08:00:00"), at("10:00:00")
    row = task("formal", "op:formal", start, start, interval_comparable=False)
    assert resource_cohort([[row]]) == [MACHINE, OPERATOR]
    value = ResourceTaskIndex([row], start, end, task_intervals={row["row_ref"]: resource_intervals.task_interval(row)}).window(
        MACHINE, calendar(day_calendar(start, end, [(start, end)])))
    assert value["available_hours"] == 2 and value["unknown_workload_count"] == 1
    assert value["span_occupied_hours"] is value["occupied_hours"] is value["utilization_ratio"] is None
    assert value["state"] == "partial" and value["work_state"] == "unavailable"


def test_resource_grains_keep_actual_work_windows_weekly_weights_and_rest_span_evidence(monkeypatch):
    from core.services.workbench.facts.resource_pressure import pressure_from_index
    from core.services.workbench.run.decision_resource_engine import _period_summary

    monday, tuesday, wednesday = "2026-09-07", "2026-09-08", "2026-09-09"
    start, boundary, end = at("00:00:00", monday), at("00:00:00", tuesday), at("00:00:00", wednesday)
    rows = [task("day", "op:day", at("08:00:00", monday), boundary),
            task("retained", "op:retained", at("16:00:00", monday), at("08:00:00", tuesday), locked=True),
            task("short", "op:short", at("09:00:00", tuesday), at("10:00:00", tuesday))]
    saved = calendar(day_calendar(start, boundary, [(at("08:00:00", monday), at("16:00:00", monday))]),
                     day_calendar(boundary, end, [(at("08:00:00", tuesday), at("10:00:00", tuesday))]))
    index = ResourceTaskIndex(rows, start, end, pressure_threshold=0.95)
    calendar_reads, measurement_reads, value_reads = [], [], []
    prepared_reads = []
    original_days = resource_calendar.calendar_days
    original_measurement = resource_projection._ResourceMeasurement.__init__
    original_values = resource_projection._ResourceMeasurement._values

    def record_days(value, low, high):
        calendar_reads.append(value)
        return original_days(value, low, high)

    def record_measurement(measurement, resource, *args, **values):
        measurement_reads.append((resource["ref"], id(measurement)))
        original_measurement(measurement, resource, *args, **values)

    def record_values(measurement, low, high, calendar_days, *, potential_work=None, prepared=None):
        if prepared is not None:
            prepared_reads.append((low, high))
        value = original_values(measurement, low, high, calendar_days, potential_work=potential_work, prepared=prepared)
        effective = (value.raw["span_occupied_hours"] > 0 or not measurement.work_complete
                     if potential_work is None else potential_work)
        value_reads.append((id(measurement), measurement.resource["kind"], measurement.resource["ref"], low, high,
                            tuple((day.date, day.low, day.high, day.available) for day in calendar_days), effective))
        return value

    monkeypatch.setattr(resource_calendar, "calendar_days", record_days)
    monkeypatch.setattr(resource_projection._ResourceMeasurement, "__init__", record_measurement)
    monkeypatch.setattr(resource_projection._ResourceMeasurement, "_values", record_values)
    normalized = normalize_resource_calendar(saved, start, end)
    window = index.window(MACHINE, normalized)
    window_reads = list(value_reads)
    assert len(window_reads) == 3
    assert prepared_reads == [(instant(start), instant(boundary)), (instant(boundary), instant(end))]
    day_facts = index.period_facts(MACHINE, normalized, grain="day")
    days = index.periods(MACHINE, normalized, grain="day")
    assert index.day_filter_summary(MACHINE, normalized) == _period_summary(day_facts, window["daily_peak_utilization"])
    assert "day_filter_summary" not in window
    assert [{field: row[field] for field in fact} for row, fact in zip(days, day_facts)] == day_facts
    assert value_reads == window_reads
    measurement = index._measurement(MACHINE, normalized)
    for day in measurement.days:
        cached = measurement.values(day.low, day.high, [day])
        assert cached == original_values(measurement, day.low, day.high, [day])
    assert [row["utilization_ratio"] for row in days] == [1, 0.5]
    assert window["available_hours"] == sum(row["available_hours"] for row in days) == 10
    assert window["occupied_hours"] == sum(row["occupied_hours"] for row in days) == 9
    assert window["daily_peak_utilization"] == max(row["daily_peak_utilization"] for row in day_facts) == 1
    assert days[0]["calendar_state"] == "complete" and days[0]["available_hours"] == 8
    assert days[0]["zero_capacity_task"] is None
    assert days[0]["zero_capacity_reason"]["code"] == "actual_work_fragments_not_recorded"
    week = index.periods(MACHINE, normalized, grain="week", details=True)[0]
    assert week["available_hours"] == 10 and week["occupied_hours"] == 9
    assert week["utilization_ratio"] == pytest.approx(0.9)
    assert week["daily_peak_utilization"] == 1 and week["high_pressure_period_count"] == 1
    assert [row["date"] for row in week["high_pressure_periods"]] == [monday]
    assert week["conflict"] is False and week["overlap_span_hours"] == 8
    assert week["zero_capacity_task"] is None and week["zero_capacity_reason"]["code"] == "actual_work_fragments_not_recorded"
    assert len(week["tasks"]) == len({row["row_ref"] for row in week["tasks"]}) == 2
    assert [row["occupied_hours"] for row in week["tasks"]] == [8, 1]
    shifts = index.periods(MACHINE, normalized, grain="shift")
    assert [(row["start"], row["end"]) for row in shifts] == [
        (at("08:00:00", monday), at("16:00:00", monday)), (at("08:00:00", tuesday), at("10:00:00", tuesday))]
    hours = index.periods(MACHINE, normalized, grain="hour", details=True)
    active = next(row for row in hours if row["start"] == at("08:00:00", monday))
    assert active["operation_count"] == 1 and active["occupied_hours"] == 1
    rest = next(row for row in hours if row["start"] == at("22:00:00", monday))
    assert rest["calendar_state"] == "complete" and rest["available_hours"] == rest["occupied_hours"] == 0
    assert rest["conflict"] is False and rest["conflicts"] == [] and rest["tasks"] == []
    assert rest["zero_capacity_task"] is None and rest["zero_capacity_reason"]["code"] == "actual_work_fragments_not_recorded"
    assert len(rest["reservation_overlaps"]) == 1 and len(rest["reservations"]) == 2
    assert rest["outside_calendar_hours"] == 1 and rest["outside_calendar_basis"] == "reservation_span_outside_work_calendar"
    assert all(row["metric_version"] == "decision-resource-v4" for row in hours)
    assert calendar_reads == [saved]
    assert len(measurement_reads) == 1 and measurement_reads[0][0] == MACHINE["ref"]
    assert len(value_reads) == len(set(value_reads))
    assert saved["days"][0]["start"] == start
    assert index.retain_statistics_values is measurement.retain_statistics_values is True
    before_pressure = len(value_reads)
    assert pressure_from_index(index, MACHINE, normalized)["window_metrics"] == window
    assert len(value_reads) == before_pressure
    transient = ResourceTaskIndex(rows, start, end, pressure_threshold=0.95, retain_statistics_values=False)
    assert transient.window(MACHINE, normalized) == window
    transient_measurement = transient._measurement(MACHINE, normalized)
    assert transient_measurement.retain_statistics_values is False
    assert len(transient_measurement._value_cache) == 1
    assert transient.day_filter_summary(MACHINE, normalized) == index.day_filter_summary(MACHINE, normalized)
    visible_keys = {days[0]["group_key"]}
    assert transient.periods(MACHINE, normalized, details=True, group_keys=visible_keys) == index.periods(
        MACHINE, normalized, details=True, group_keys=visible_keys)
    assert len(transient_measurement._value_cache) == 2
    day = transient_measurement.days[0]
    retained = transient_measurement.values(day.low, day.high, [day])
    before_hit = len(value_reads)
    assert transient_measurement.values(day.low, day.high, [day], retain=False) is retained
    assert len(value_reads) == before_hit
    key = day.low, day.high, transient_measurement._day_key([day])
    variants = dict(transient_measurement._value_cache[key])
    transient_measurement.values(day.low, day.high, [day], potential_work=False, retain=False)
    assert transient_measurement._value_cache[key] == variants
    day = transient_measurement.days[1]
    transient_measurement.values(day.low, day.high, [day], retain=False)
    assert len(transient_measurement._value_cache) == 2
    assert transient.periods(MACHINE, normalized, grain="week", details=True)[0] == week


def test_selected_plan_conflict_segments_keep_night_reservations_and_three_operation_hours_distinct():
    from types import SimpleNamespace

    from core.services.capacity.plan_calendar_intervals import instant
    from core.services.workbench.plan.occupancy import _resource_occupancy

    saved = {**day_calendar(at("00:00:00"), at("00:00:00", "2026-09-10"), [(at("08:00:00"), at("09:00:00"))]),
             "label": "归档设备", "basis": "global_calendar_machine_availability"}
    day = (instant(at("08:00:00")), instant(at("09:00:00")))
    night = (instant(at("22:00:00")), instant(at("23:00:00")))
    refs = {"machine": {"M1": SimpleNamespace(ref=MACHINE["ref"])}}
    mixed = _resource_occupancy("machine", "M1", {ref: [day, night] for ref in ("one", "two", "three")}, saved, refs, "设备")
    assert mixed["overlap_hours"] == 2 and mixed["available_overlap_hours"] == 1
    assert mixed["has_overlap"] is True and mixed["capacity_insufficient"] is True
    assert mixed["conflict_segments"] == [{"start": at("08:00:00"), "end": at("09:00:00"), "concurrent_operations": 3}]
    assert len(mixed["segments"]) == 2
    rest = _resource_occupancy("machine", "M1", {"one": [night], "two": [night]}, saved, refs, "设备")
    assert rest["overlap_hours"] == 1 and rest["available_overlap_hours"] == 0
    assert rest["has_overlap"] is False and rest["capacity_insufficient"] is False and rest["conflict_segments"] == []
    assert rest["outside_available_hours"] == 1 and rest["outside_calendar_basis"] == "reservation_span_outside_work_calendar"
