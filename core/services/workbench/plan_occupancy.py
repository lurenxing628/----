"""Selected-plan-only resource occupancy, not plant-wide or execution reservations.

As in gantt_resource_load, only the caller-selected plan rows are input. No other
version, current formal schedule or external supplier cycle is added. Unlike its
summed daily numerator/noon denominator, fragments of one operation are unioned,
concurrent operations are swept into segments, and available occupancy is the
intersection with actual calendar windows. Utilization is occupied available
wall-clock hours / available wall-clock hours (0..1); overbooking, out-of-calendar
hours and capacity shortfall are separate, not a normal utilization above 100%.
Efficiency-weighted normal/urgent capacities remain separate calendar facts.

Machine capacity uses global_calendar_machine_availability and does not promise
personnel coverage. Missing capacity stays null; known arrangement and overlap
hours remain visible. DB/schema errors propagate. Caller owns the read snapshot.
"""

from collections import defaultdict

from core.models.workbench_command import WorkbenchCommandRejected

from .plan_calendar_context import issue, public_resource, selected_context
from .plan_calendar_intervals import hours, instant, intersection, segments, union, wire
from .plan_calendar_windows import available_intervals
from .plan_occupancy_constraints import TaskConstraints


def _occupancy_groups(rows, start, end, constraints):
    groups = defaultdict(lambda: defaultdict(list))
    unknown = set()
    for row in rows:
        source = str(row["source"]).strip().lower() if row["source"] is not None else None
        if row.get("_point_work"):
            source = "internal"
        if source == "external":
            continue
        if source != "internal":
            unknown.add(row["op_id"])
            continue
        low, high = max(start, instant(row["start_time"])), min(end, instant(row["end_time"]))
        constraints.check(row, low, high)
        for kind in ("machine", "operator"):
            key = row[kind + "_id"]
            if key not in (None, ""):
                groups[kind, str(key)][row["op_id"]].append((low, high))
    return groups, unknown


def _resource_occupancy(kind, key, operations, calendar, resources, label):
    intervals = [interval for fragments in operations.values() for interval in union(fragments)]
    swept = segments(intervals)
    occupied = union(intervals)
    arranged_hours, occupied_hours = hours(intervals), hours(occupied)
    overlap_hours = hours([(low, high) for low, high, count in swept if count > 1])
    row = public_resource(kind, key, resources, None)
    row["label"] = calendar["label"] if calendar is not None else label
    available = available_intervals(calendar) if calendar is not None else None
    capacity_measures, utilization, insufficient = _capacity_measures(available, occupied, arranged_hours, occupied_hours)
    measures = {"arranged_hours": arranged_hours, "occupied_hours": occupied_hours,
                "overlap_hours": overlap_hours, "excess_arranged_hours": arranged_hours - occupied_hours,
                **capacity_measures}
    row.update({name: round(value, 6) if value is not None else None for name, value in measures.items()})
    row.update(state="available" if available is not None else "unavailable", operation_count=len(operations),
               capacity_basis=calendar["basis"] if calendar is not None else "unknown",
               utilization=utilization,
               has_overlap=overlap_hours > 1e-9,
               capacity_insufficient=insufficient,
               issues=calendar["issues"] if calendar is not None else [issue("calendar_unavailable")],
               segments=[{"start": wire(low), "end": wire(high), "concurrent_operations": count}
                         for low, high, count in swept])
    return row


def _capacity_measures(available, occupied, arranged_hours, occupied_hours):
    if available is None:
        return {"available_hours": None, "available_occupied_hours": None,
                "outside_available_hours": None, "capacity_shortfall_hours": None}, None, None
    capacity = hours(available)
    in_calendar = hours(intersection(occupied, available))
    outside = max(0.0, occupied_hours - in_calendar)
    shortage = max(0.0, arranged_hours - capacity)
    utilization = round(in_calendar / capacity, 6) if capacity > 0 else None
    return {"available_hours": capacity, "available_occupied_hours": in_calendar,
            "outside_available_hours": outside, "capacity_shortfall_hours": shortage}, utilization, outside > 1e-9 or shortage > 1e-9


def project_plan_occupancy(conn, *, entry, scope, rows, resources, plan_span, calendar_facts):
    """calendar_facts is the private result of project_plan_calendar in this read."""
    rows, start, end, time_scope, context = selected_context(conn, entry, scope, rows, resources, plan_span)
    if calendar_facts["context"] != context:
        raise WorkbenchCommandRejected("snapshot_stale", "班表和安排不是同一个计划或同一个时间范围，系统不会把两份数据硬拼在一起。请刷新后重试。")
    constraints = TaskConstraints(calendar_facts)
    groups, unknown = _occupancy_groups(rows, start, end, constraints)
    calendars = calendar_facts["resources"]
    labels = {(kind, str(row[kind + "_id"])): row[kind + "_name"] for row in rows for kind in ("machine", "operator")}
    public = [_resource_occupancy(kind, key, operations, calendars[kind].get(key) if calendars is not None else None,
                                  resources, labels[kind, key])
              for (kind, key), operations in sorted(groups.items())]
    issues = constraints.public()
    if unknown:
        issues.append(issue("assignment_source_unknown", operation_count=len(unknown)))
    states = [row["state"] for row in public]
    state = "available" if all(value == "available" for value in states) else "unavailable" if all(
        value == "unavailable" for value in states) else "partial"
    if unknown:
        state = "partial" if public else "unavailable"
    dto = {"state": state, "plan_ref": scope.plan_ref, "time_scope": time_scope,
           "basis": "selected_plan_only", "resources": public, "issues": issues}
    return dto, {"context": context, "constraints": constraints.private(), "unknown_source_operations": sorted(unknown),
                 "calendar": calendar_facts, "occupancy": public}
