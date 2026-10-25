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
from core.services.workbench.facts.resource_intervals import resource_identity_issues, task_interval
from core.services.workbench.facts.resource_pressure import legacy_day, pressure_from_index
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


class ResourcePressureMetrics:
    """One official plan window's resource-pressure facts, each projected once per snapshot.

    Normalized tasks, the resource cohort and the window index are built on first use.
    Capture records each streamed resource's compact metrics; analysis projects only the
    resources capture could not stream, plus the daily rows of one requested resource.
    """

    def __init__(self, plan_tasks, time_scope, factory):
        # Projected official tasks paired one-to-one with their stored rows.
        self._plan_tasks = plan_tasks
        self.start, self.end = time_scope["range_start"], time_scope["range_end"]
        self.factory = factory
        self.summaries = {}
        self._tasks = self._intervals = self._cohort = self._index = None

    def _normalized(self):
        if self._tasks is None:
            tasks, rows = self._plan_tasks
            self._tasks = [dict(task, row_ref=task["task_ref"], source=raw["source"],
                                **{kind: {"ref": task[kind + "_ref"], "label": raw[kind + "_name"]}
                                   if task[kind + "_ref"] is not None else None for kind in ("machine", "operator")})
                           for task, raw in zip(tasks, rows)]
            self._intervals = {task["row_ref"]: task_interval(task) for task in self._tasks}
        return self._tasks, self._intervals

    def _cohort_members(self):
        if self._cohort is None:
            tasks, intervals = self._normalized()
            cohort = resource_cohort([tasks], task_intervals=[intervals])
            self._cohort = cohort, {(resource["kind"], resource["ref"]): resource for resource in cohort}
        return self._cohort

    @property
    def cohort(self):
        return self._cohort_members()[0]

    @property
    def index(self):
        if self._index is None:
            tasks, intervals = self._normalized()
            self._index = ResourceTaskIndex(tasks, self.start, self.end, source="current_transaction_snapshot",
                                            retain_statistics_values=False, task_intervals=intervals)
        return self._index

    @property
    def identity_issues(self):
        # Identity gaps need no calendar geometry: a window too wide for the index stays readable
        # when no internal resource has to be projected, and reports the same gaps either way.
        if self._index is not None:
            return self._index.identity_issues
        tasks, intervals = self._normalized()
        return resource_identity_issues(tasks, self.start, self.end, task_intervals=intervals)

    def record(self, kind, ref, calendar):
        """Keep one streamed cohort resource's compact metrics; its calendar geometry is released at once."""
        resource = self._cohort_members()[1].get((kind, ref))
        if resource is not None:
            self.summaries[kind, ref] = pressure_from_index(self.index, resource, calendar, include_days=False)
            self.index.release(resource)

    def resource_values(self, days_ref=None):
        """Each cohort resource with its metrics; ``days_ref`` also projects that resource's days."""
        summaries, detailed = self.summaries, {}
        needed = [resource for resource in self.cohort
                  if (resource["kind"], resource["ref"]) not in summaries or resource["ref"] == days_ref]
        if needed:
            index, factory = self.index, self.factory
            calendars = (factory.iter_resources([dict(row, saved_id=factory.bindings.get((row["kind"], row["ref"])))
                                                 for row in needed], self.start, self.end)
                         if factory is not None else ((row["ref"], None) for row in needed))
            index.retain_statistics_values = days_ref is not None
            for resource, (_, calendar) in zip(needed, calendars):
                key = resource["kind"], resource["ref"]
                if key not in summaries:
                    summaries[key] = pressure_from_index(index, resource, calendar, include_days=False)
                if resource["ref"] == days_ref:
                    detailed[key] = dict(summaries[key], days=[legacy_day(day) for day in index.days(resource, calendar)])
                index.release(resource)
            index.retain_statistics_values = False
        result = []
        for resource in self.cohort:
            key = resource["kind"], resource["ref"]
            result.append((resource, detailed[key] if key in detailed else summaries[key]))
        return result


def _constraint_projection(calendar, ids, resources, identities, rows, start, end, schema_version, plan_ref, time_scope, plan_tasks):
    factory = calendar_from_sources(calendar["sources"], schema_version=schema_version, identities=identities,
                                    plan_ref=plan_ref, scope=time_scope)
    metrics = ResourcePressureMetrics(plan_tasks, time_scope, factory)
    specs = {(kind, key): {"kind": kind, "saved_id": key,
                          "ref": public_resource(kind, key, resources, None)["resource_ref"]}
             for kind in ("machine", "operator") for key in ids[kind]}
    states = {}
    if factory is None:
        constraints = TaskConstraints(calendar)
        unknown = _check_tasks(rows, start, end, constraints)
        return constraints, unknown, ["unavailable" for _ in specs], metrics

    def lookup(kind, key):
        # Exhaust this one-resource stream so its operator policy cache is
        # released before the next operator is projected.
        projected, = (value for _, value in factory.iter_resources([specs[kind, key]], start, end))
        states[kind, key] = projected["state"]
        metrics.record(kind, specs[kind, key]["ref"], projected)
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
        metrics.record(spec["kind"], spec["ref"], projected)
    return constraints, unknown, list(states.values()), metrics


def capture_resource_pressure(conn, *, entry, scope, resources, identities, plan_span, context, captured_calendar, plan_tasks):
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
    constraints, unknown, states, metrics = _constraint_projection(calendar, ids, resources, identities, rows, start, end,
                                                                  captured_calendar.schema_rows, scope.plan_ref, time_scope, plan_tasks)
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
                 "calendar": calendar, "occupancy": None}, metrics
