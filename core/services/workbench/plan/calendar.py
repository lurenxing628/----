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

from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_io import CalendarFacts, ProjectionLimit
from core.services.capacity.plan_calendar_limits import MAX_CALENDAR_DATES, MAX_POLICY_CELLS
from core.services.capacity.plan_calendar_windows import (
    policy_projection,
    project_resource_calendars,
    public_projection,
    unavailable,
)

from .calendar_context import public_resource, resource_ids


def _resource_projections(engine, facts, ids, bounds, global_calendar, resources):
    first, last, start, end = bounds
    private, public = {"machine": {}, "operator": {}}, []
    for kind, key, raw, item in project_resource_calendars(
        engine, facts, ids, first, last, start, end, global_calendar=global_calendar
    ):
        item.update(public_resource(kind, key, resources, raw))
        private[kind][key] = item
        public.append(item)
    return public, private


def _unavailable_result(scope, time_scope, code):
    global_cal = unavailable("global_calendar", code)
    dto = {"state": "unavailable", "plan_ref": scope.plan_ref, "time_scope": time_scope,
           "global": global_cal, "resources": None,
           "issues": global_cal["issues"], "windows_complete": False}
    return dto, {"state": "unavailable", "reason": code, "sources": None, "resources": None}


def project_plan_calendar(conn, *, scope, resources, selected, include_windows: bool = True):
    """selected/resources must already belong to the plan, selected in this transaction."""
    rows, start, end, time_scope = selected.rows, selected.start, selected.end, selected.time_scope
    first, last, dates = selected.calendar_days
    ids = {kind: resource_ids(rows, kind) for kind in ("machine", "operator")}
    if dates > MAX_CALENDAR_DATES:
        return _unavailable_result(scope, time_scope, "calendar_range_limit")
    if dates * (1 + sum(len(value) for value in ids.values())) > MAX_POLICY_CELLS:
        return _unavailable_result(scope, time_scope, "calendar_cell_limit")
    reader = CalendarFacts(conn)
    try:
        reader.calendar(first.isoformat(), last.isoformat(), ids["operator"])
        reader.resources(ids["machine"], ids["operator"], [row["op_id"] for row in rows], start, end)
    except ProjectionLimit as exc:
        return _unavailable_result(scope, time_scope, str(exc))
    engine = SnapshotCalendarEngine(reader.rows)
    global_calendar = policy_projection(engine, first, last, start, end)
    public, private = _resource_projections(engine, reader.rows, ids, (first, last, start, end), global_calendar, resources)
    states = [global_calendar["state"]] + [item["state"] for item in public]
    state = "available" if all(item == "available" for item in states) else "unavailable" if all(
        item == "unavailable" for item in states) else "partial"
    wired = {}
    global_dto = public_projection(global_calendar, wired, include_windows=include_windows)
    public_dto = [public_projection(item, wired, include_windows=include_windows) for item in public]
    if include_windows:
        windows_complete = state != "unavailable"
    else:
        has_windows = bool(global_calendar.get("windows")) or any(
            bool(item.get("windows")) or bool(item.get("downtime_windows")) for item in public
        )
        windows_complete = not has_windows and state != "unavailable"
    dto = {"state": state, "plan_ref": scope.plan_ref, "time_scope": time_scope,
           "global": global_dto, "resources": public_dto, "issues": [],
           "windows_complete": windows_complete}
    facts = {"state": state, "sources": reader.rows, "resources": private}
    return dto, facts
