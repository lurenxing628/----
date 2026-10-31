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


def capacity_tasks(rows, field, *, intervals_by_row):
    result = []
    for row in rows:
        original = row["original"]
        current = row["current"] if field == "current" else original["arrangement"]
        task = {"row_ref": row["row_ref"], "task_ref": row["task_ref"], "operation_ref": row["operation_ref"],
                "source": original["operation"]["source"], "start": current["start"], "end": current["end"],
                **{kind: {"ref": current[kind + "_ref"], "label": None} if current[kind + "_ref"] is not None else None
                   for kind in ("machine", "operator")}}
        if task["start"] == task["end"]:
            span = intervals_by_row.get(row["row_ref"])
            if span is not None and span[0] == span[1]:
                task.update(point_event_dto(span[0], span[1]))
        result.append(task)
    return result


def trial_capacity(rows, archive, *, source_ref, trial_intervals):
    current_intervals = trial_intervals["current_by_row"]
    original_intervals = trial_intervals["original_by_row"]
    tasks = capacity_tasks(rows, "current", intervals_by_row=current_intervals)
    original = capacity_tasks(rows, "original", intervals_by_row=original_intervals)
    start, end = min(row["start"] for row in tasks), max(row["end"] for row in tasks)
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
