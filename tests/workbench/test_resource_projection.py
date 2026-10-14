"""Shared resource facts distinguish independent demand and missing evidence."""

import pytest

from core.services.workbench.facts import resource_intervals, resource_projection
from core.services.workbench.facts.resource_projection import (
    ResourceTaskIndex,
    normalize_resource_calendar,
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

    def unexpected_parse(_row):
        pytest.fail("该来源已核实的区间应直接复用。")

    with monkeypatch.context() as scoped:
        scoped.setattr(resource_projection, "task_interval", unexpected_parse)
        scoped.setattr(resource_intervals, "task_interval", unexpected_parse)
        assert resource_cohort([rows], task_intervals=[parsed]) == [MACHINE, OPERATOR]
        index = ResourceTaskIndex(rows, start, end, task_intervals=parsed)
        window = index.window(MACHINE, saved)
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


def test_partial_calendar_preserves_known_subtotals_and_does_not_label_unknown_day_outside():
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
    minute_window = ResourceTaskIndex(minute_rows, first, last).window(MACHINE, minute_calendar)
    for fact in (minute_window, resource_summary([minute_window])):
        assert fact["state"] == "partial"
        assert fact["available_hours"] is fact["occupied_hours"] is fact["outside_calendar_hours"] is None
        assert fact["known_available_hours"] == fact["known_occupied_hours"] == 0.8
        assert fact["known_outside_calendar_hours"] == 0


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
    start, end = at("08:00:00"), at("10:00:00")
    saved = calendar(day_calendar(start, end, [(start, end)]))
    rows = [task("known", "op:k", start, at("09:00:00")), task("missing", "op:m", None, end)]
    parsed = {row["row_ref"]: resource_intervals.task_interval(row) for row in rows}
    partial = ResourceTaskIndex(rows, start, end, task_intervals=parsed).window(MACHINE, saved)
    assert partial["available_hours"] == 2 and partial["state"] == "partial"
    assert partial["occupied_hours"] is partial["span_occupied_hours"] is partial["task_count"] is None
    assert partial["known_occupied_hours"] == partial["known_span_occupied_hours"] == 1
    assert partial["known_task_count"] == partial["known_operation_count"] == partial["unknown_workload_count"] == 1
    assert partial["conflict"] is None
    assert partial["issues"] == [{"code": "task_time_unknown", "message": "保存任务的时间或点事件依据缺项，占用和负荷保留已知小计。", "field": "task_time"}]
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
    monday, tuesday, wednesday = "2026-09-07", "2026-09-08", "2026-09-09"
    start, boundary, end = at("00:00:00", monday), at("00:00:00", tuesday), at("00:00:00", wednesday)
    rows = [task("day", "op:day", at("08:00:00", monday), boundary),
            task("retained", "op:retained", at("16:00:00", monday), at("08:00:00", tuesday), locked=True),
            task("short", "op:short", at("09:00:00", tuesday), at("10:00:00", tuesday))]
    saved = calendar(day_calendar(start, boundary, [(at("08:00:00", monday), at("16:00:00", monday))]),
                     day_calendar(boundary, end, [(at("08:00:00", tuesday), at("10:00:00", tuesday))]))
    index = ResourceTaskIndex(rows, start, end, pressure_threshold=0.95)
    calendar_reads = []
    original_days = resource_projection._calendar_days

    def record_days(value, low, high):
        calendar_reads.append(value)
        return original_days(value, low, high)

    monkeypatch.setattr(resource_projection, "_calendar_days", record_days)
    normalized = normalize_resource_calendar(saved, start, end)
    days = index.periods(MACHINE, normalized, grain="day")
    assert [row["utilization_ratio"] for row in days] == [1, 0.5]
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
    assert saved["days"][0]["start"] == start


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
