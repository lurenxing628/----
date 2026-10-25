"""Capture dashboard calendar facts without a resource-by-date DTO grid.

The current transaction supplies one bounded source snapshot. Task feasibility
and later resource analysis project that snapshot with the same calendar factory;
only interval indexes, states and compact pressure metrics survive each streamed projection.
"""

from core.services.capacity.plan_calendar_intervals import instant
from core.services.capacity.plan_calendar_io import CalendarFacts, ProjectionLimit, snapshot_values
from core.services.capacity.plan_calendar_issues import issue
from core.services.capacity.plan_calendar_limits import MAX_CALENDAR_DATES
from core.services.capacity.plan_calendar_windows import policy_projection
from core.services.workbench.facts.current_resource_calendar import calendar_from_sources
from core.services.workbench.facts.resource_intervals import task_interval
from core.services.workbench.facts.resource_pressure import pressure_from_index
from core.services.workbench.facts.resource_projection import ResourceTaskIndex, resource_cohort
from core.services.workbench.plan.calendar import range_days
from core.services.workbench.plan.calendar_context import public_resource, resource_ids
from core.services.workbench.plan.occupancy_constraints import TaskConstraints


def _state(states):
    return "available" if all(value == "available" for value in states) else "unavailable" if all(
        value == "unavailable" for value in states) else "partial"


def _check_tasks(rows, start, end, constraints):
    unknown = set()
    for row in rows:
        source = "internal" if row.get("_point_work") else str(row["source"]).strip().lower()
        if source == "external":
            continue
        if source != "internal":
            unknown.add(row["op_id"])
            continue
        constraints.check(row, max(start, instant(row["start_time"])), min(end, instant(row["end_time"])))
    return sorted(unknown)


def _capture(conn, ids, rows, first, last, start, end, captured_calendar):
    reader = CalendarFacts(conn, captured=captured_calendar)
    reader.calendar(first.isoformat(), last.isoformat(), ids["operator"])
    reader.resources(ids["machine"], ids["operator"], [row["op_id"] for row in rows], start, end)
    return reader


def resource_pressure_tasks(facts):
    if facts._resource_pressure_tasks is None:
        tasks = [dict(task, row_ref=task["task_ref"], source=raw["source"],
                      **{kind: {"ref": task[kind + "_ref"], "label": raw[kind + "_name"]}
                         if task[kind + "_ref"] is not None else None for kind in ("machine", "operator")})
                 for task, raw in zip(facts.tasks, facts.task_rows)]
        facts._resource_pressure_tasks = tasks
        facts._resource_pressure_intervals = {task["row_ref"]: task_interval(task) for task in tasks}
    return facts._resource_pressure_tasks


def _constraint_projection(calendar, ids, resources, identities, rows, start, end, schema_version, plan_ref, time_scope, facts):
    factory = calendar_from_sources(calendar["sources"], schema_version=schema_version, identities=identities,
                                    plan_ref=plan_ref, scope=time_scope)
    specs = {(kind, key): {"kind": kind, "saved_id": key,
                          "ref": public_resource(kind, key, resources, None)["resource_ref"]}
             for kind in ("machine", "operator") for key in ids[kind]}
    states = {}
    if factory is None:
        constraints = TaskConstraints(calendar)
        unknown = _check_tasks(rows, start, end, constraints)
        return constraints, unknown, ["unavailable" for _ in specs], factory
    tasks = resource_pressure_tasks(facts)
    intervals = facts._resource_pressure_intervals
    cohort = resource_cohort([tasks], task_intervals=[intervals])
    facts._resource_pressure_cohort = cohort
    index = ResourceTaskIndex(tasks, start, end, source="current_transaction_snapshot",
                              retain_statistics_values=False, task_intervals=intervals)
    facts._resource_pressure_index = index
    facts._resource_pressure_window = (time_scope["range_start"], time_scope["range_end"])
    facts._resource_pressure_identity_issues = index.identity_issues
    by_ref = {(resource["kind"], resource["ref"]): resource for resource in cohort}

    def capture_pressure(spec, projected):
        key = spec["kind"], spec["ref"]
        resource = by_ref.get(key)
        if resource is not None:
            values = pressure_from_index(index, resource, projected, include_days=False)
            facts._resource_pressure_cache[key + (time_scope["range_start"], time_scope["range_end"])] = values
            # The summary owns no calendar geometry; release this resource before the next stream item.
            index._measurements.pop(key)

    def lookup(kind, key):
        # Exhaust this one-resource stream so its operator policy cache is
        # released before the next operator is projected.
        projected, = (value for _, value in factory.iter_resources([specs[kind, key]], start, end))
        states[kind, key] = projected["state"]
        capture_pressure(specs[kind, key], projected)
        return projected

    constraints = TaskConstraints(
        calendar,
        calendar_lookup=lookup,
        point_calendar=factory.engine,
    )
    unknown = _check_tasks(rows, start, end, constraints)
    remaining = [(key, spec) for key, spec in specs.items() if key not in states]
    for (key, spec), (_, projected) in zip(remaining, factory.iter_resources(
            [spec for _, spec in remaining], start, end)):
        states[key] = projected["state"]
        capture_pressure(spec, projected)
    return constraints, unknown, list(states.values()), factory


def capture_resource_pressure(conn, *, entry, scope, resources, identities, plan_span, context, captured_calendar, facts):
    rows, start, end, time_scope, binding = context.calendar_selection(entry, scope, resources, plan_span)
    first, last, dates = range_days(start, end)
    if any(row.get("_point_work") for row in rows):
        last = max(last, end.date())
        dates = (last - first).days + 1
    ids = {kind: resource_ids(rows, kind) for kind in ("machine", "operator")}
    calendar = {"context": binding, "state": "unavailable", "sources": None, "resources": None}
    try:
        if dates > MAX_CALENDAR_DATES:
            raise ProjectionLimit("calendar_range_limit")
        reader = _capture(conn, ids, rows, first, last, start, end, captured_calendar)
        calendar.update(sources=snapshot_values(reader.rows), fact_count=reader.count)
    except ProjectionLimit as exc:
        calendar["reason"] = str(exc)
    constraints, unknown, states, factory = _constraint_projection(calendar, ids, resources, identities, rows, start, end,
                                                                  captured_calendar.schema_rows, scope.plan_ref, time_scope, facts)
    if calendar["sources"] is not None:
        # 保存的日历表结构坏了（factory.engine 为 None）时全局班表同样算不出，不再拿空引擎去投影；坏日期等内容错误由引擎投影成不可用。
        global_state = (policy_projection(constraints.point_calendar, first, last, start, end)["state"]
                        if constraints.point_calendar is not None else "unavailable")
        calendar["state"] = _state([global_state] + states)
    issues = constraints.public()
    if unknown:
        issues.append(issue("assignment_source_unknown", operation_count=len(unknown)))
    state = _state(states)
    if unknown:
        state = "partial" if states else "unavailable"
    dto = {"state": state, "plan_ref": scope.plan_ref, "time_scope": time_scope, "basis": "selected_plan_only",
           "resource_count": sum(len(keys) for keys in ids.values()), "issues": issues,
           "calendar_state": calendar["state"]}
    return dto, {"context": binding, "constraints": constraints.private(), "unknown_source_operations": unknown,
                 "calendar": calendar, "occupancy": None}, factory
