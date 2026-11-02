"""Trial occupancy from its saved origin's calendar and permanent resource IDs."""

from core.services.capacity.plan_calendar_windows import public_archived_calendar
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.facts.resource_projection import (
    RESOURCE_METRIC_VERSION,
    ResourceTaskIndex,
    resource_cohort,
    resource_summary,
)
from core.services.workbench.facts.zero_duration import point_event_dto


def _resource(ref):
    return {"ref": ref, "label": None} if ref is not None else None


def capacity_tasks(rows, field, *, intervals_by_row, occupancy_by_row):
    """One side's capacity tasks and their intervals.

    A row whose occupancy is its actual report segments yields one task per segment, each with its own
    internal ``row_ref``; every other row stays one task under its own row reference.
    """
    tasks, intervals = [], {}
    for row in rows:
        original = row["original"]
        current = row["current"] if field == "current" else original["arrangement"]
        span = intervals_by_row[row["row_ref"]]
        common = {"task_ref": row["task_ref"], "operation_ref": row["operation_ref"], "source": original["operation"]["source"]}
        segments = occupancy_by_row[row["row_ref"]] if span is not None and span[0] < span[1] else None
        if segments is not None and segments != ((*span, current["machine_ref"], current["operator_ref"]),):
            for index, (start, end, machine_ref, operator_ref) in enumerate(segments, 1):
                row_ref = row["row_ref"] + "#" + str(index)
                tasks.append({"row_ref": row_ref, **common, "start": start.isoformat(), "end": end.isoformat(),
                              "machine": _resource(machine_ref), "operator": _resource(operator_ref)})
                intervals[row_ref] = start, end
            continue
        task = {"row_ref": row["row_ref"], **common, "start": current["start"], "end": current["end"],
                **{kind: _resource(current[kind + "_ref"]) for kind in ("machine", "operator")}}
        if task["start"] == task["end"] and span is not None and span[0] == span[1]:
            task.update(point_event_dto(span[0], span[1]))
        tasks.append(task)
        intervals[row["row_ref"]] = span
    return tasks, intervals


def trial_capacity(rows, archive, *, source_ref, trial_intervals):
    tasks, current_intervals = capacity_tasks(rows, "current", intervals_by_row=trial_intervals["current_by_row"],
                                              occupancy_by_row=trial_intervals["current_occupancy_by_row"])
    original, original_intervals = capacity_tasks(rows, "original", intervals_by_row=trial_intervals["original_by_row"],
                                                  occupancy_by_row=trial_intervals["original_occupancy_by_row"])
    start, end = min(row["current"]["start"] for row in rows), max(row["current"]["end"] for row in rows)
    scope = {"start": start, "end": end, "basis": "selected_trial_only", "source": "archived_resource_calendar",
             "metric_version": RESOURCE_METRIC_VERSION, "time_basis": "factory_local"}
    factory = ArchivedCalendar(archive, source_ref=source_ref)
    cohort = resource_cohort([original, tasks], task_intervals=[original_intervals, current_intervals])
    specs = [dict(row, saved_id=factory.bindings.get((row["kind"], row["ref"]))) for row in cohort]
    index = ResourceTaskIndex(tasks, start, end, task_intervals=current_intervals)
    output = []
    for resource, (_, calendar) in zip(cohort, factory.iter_resources(specs, start, end)):
        value = index.window(resource, calendar)
        # Established aliases keep wall-clock span and concurrent-span meanings.
        output.append({"resource_type": resource["kind"], "resource_ref": resource["ref"], "label": resource["label"],
                       "state": calendar["state"], "calendar": public_archived_calendar(calendar), "window_metrics": value,
                       "arranged_hours": value["span_summed_hours"], "occupied_hours": value["span_occupied_hours"],
                       "overlap_hours": value["overlap_span_hours"], "available_hours": value["available_hours"],
                       "available_occupied_hours": value["occupied_hours"], "outside_available_hours": value["outside_calendar_hours"],
                       "utilization": value["utilization_ratio"], "segments": index.segments(resource)})
    common = {**scope, "cohort_basis": "trial_original_and_current", "cohort": cohort,
              **{kind: resource_summary([row["window_metrics"] for row in output], kind=kind,
                                        identity_issues=index.identity_issues) for kind in ("machine", "operator")}}
    state = "available" if all(row["window_metrics"]["state"] == "complete" for row in output) else "partial"
    return {**scope, "state": state, "resources": output, "resource_common": common, "reason": None}
