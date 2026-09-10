"""Real selected-plan calendars under the caller's SQLite read snapshot.

Machine basis is global_calendar_machine_availability: global shift windows,
machine state and machine downtime only. It is NOT a staffed scheduling promise.
Personnel use personal calendar overrides and OperatorShiftCalendar. Work-type,
skill and authorization checks belong to occupancy task issues, never to machine
capacity. Unlike old gantt_resource_load's noon sample, all windows are intersected
with the exact half-open Scope, including yesterday's night tail. Normal/urgent
permissions and efficiency remain explicit; no assumed 20-hour capacity.

Returns (public DTO, private snapshot facts). Only the DTO may be serialized.
No transaction ownership, plan selection, identity allocation or database writes.
Dense evaluation is capped at 3660 dates / 40000 resource-date cells / 50000 raw
facts; sparse enormous spans return explicit unavailable, never a shortened range.
"""

from collections import defaultdict
from datetime import date, timedelta

from .plan_calendar_context import public_resource, resource_ids, selected_context
from .plan_calendar_engine import SnapshotCalendarEngine
from .plan_calendar_io import CalendarFacts, ProjectionLimit, snapshot_values
from .plan_calendar_windows import apply_resource, policy_projection, unavailable

MAX_CALENDAR_DATES = 3660
MAX_POLICY_CELLS = 40000


def _range_days(start, end):
    first = start.date() - timedelta(days=1) if start.date() > date.min else date.min
    last = end.date() if start == end else (end - timedelta(seconds=1)).date()
    return first, last, (last - first).days + 1


def _resource_projections(engine, facts, ids, bounds, global_calendar, resources):
    first, last, start, end = bounds
    downtime = defaultdict(list)
    for row in facts["downtimes"]:
        downtime[row["machine_id"]].append(row)
    private, public = {"machine": {}, "operator": {}}, []
    for kind in ("machine", "operator"):
        records = {row[kind + "_id"]: row for row in facts[kind + "s"]}
        for key in ids[kind]:
            raw = records.get(key)
            base = global_calendar if kind == "machine" else policy_projection(engine, first, last, start, end, key)
            item = apply_resource(base, raw, kind, downtime[key] if kind == "machine" else [], start, end)
            item.update(public_resource(kind, key, resources, raw))
            private[kind][key] = item
            public.append(item)
    return public, private


def _unavailable_result(scope, time_scope, context, code):
    dto = {"state": "unavailable", "plan_ref": scope.plan_ref, "time_scope": time_scope,
           "global": unavailable("global_calendar", code), "resources": None,
           "issues": unavailable("global_calendar", code)["issues"]}
    return dto, {"context": context, "state": "unavailable", "reason": code, "sources": None, "resources": None}


def project_plan_calendar(conn, *, entry, scope, rows, resources, plan_span):
    """rows/resources must already belong to entry, selected in this transaction."""
    rows, start, end, time_scope, context = selected_context(conn, entry, scope, rows, resources, plan_span)
    first, last, dates = _range_days(start, end)
    point_days = [row["_point_work"] for row in rows if row.get("_point_work")]
    if point_days:
        last = max(last, end.date())
        dates = (last - first).days + 1
    ids = {kind: resource_ids(rows, kind) for kind in ("machine", "operator")}
    if dates > MAX_CALENDAR_DATES:
        return _unavailable_result(scope, time_scope, context, "calendar_range_limit")
    if dates * (1 + sum(len(value) for value in ids.values())) > MAX_POLICY_CELLS:
        return _unavailable_result(scope, time_scope, context, "calendar_cell_limit")
    reader = CalendarFacts(conn)
    try:
        reader.calendar(first.isoformat(), last.isoformat(), ids["operator"])
        reader.resources(ids["machine"], ids["operator"], [row["op_id"] for row in rows], start, end)
    except ProjectionLimit as exc:
        return _unavailable_result(scope, time_scope, context, str(exc))
    engine = SnapshotCalendarEngine(reader.rows)
    global_calendar = policy_projection(engine, first, last, start, end)
    public, private = _resource_projections(engine, reader.rows, ids, (first, last, start, end), global_calendar, resources)
    states = [global_calendar["state"]] + [item["state"] for item in public]
    state = "available" if all(item == "available" for item in states) else "unavailable" if all(
        item == "unavailable" for item in states) else "partial"
    dto = {"state": state, "plan_ref": scope.plan_ref, "time_scope": time_scope,
           "global": global_calendar, "resources": public, "issues": []}
    facts = {"context": context, "state": state, "sources": snapshot_values(reader.rows), "resources": private,
             "fact_count": reader.count, "policy_cells": dates * (1 + len(ids["operator"]))}
    return dto, facts
