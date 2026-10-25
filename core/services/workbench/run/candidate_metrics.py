"""Candidate comparison metrics from the same verified admission capture only."""

from core.models.workbench_run_candidate import local_time
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.facts.changeovers import changeover_projection
from core.services.workbench.facts.resource_calendar import normalize_resource_calendar
from core.services.workbench.facts.resource_pressure import pressure_from_index
from core.services.workbench.facts.resource_projection import (
    RESOURCE_METRIC_VERSION,
    ResourceTaskIndex,
    resource_summary,
)


def scoped_rows(rows, batch_refs, start, end):
    """Select displayed task rows; changeover sequences are formed before this."""
    low, high = local_time(start), local_time(end)
    result = []
    for row in rows:
        if row["batch_ref"] not in batch_refs:
            continue
        if row["start"] is None or row["end"] is None:
            result.append(row)
            continue
        first, last = local_time(row["start"]), local_time(row["end"])
        if first == last:
            if low <= first < high:
                result.append(row)
        elif first < high and last > low:
            result.append(row)
    return result


def changeovers(rows, available=True, *, start, end, next_operation_refs, task_intervals):
    projected = changeover_projection(rows, start=start, end=end, work_available=available,
                                     next_operation_refs=next_operation_refs, task_intervals=task_intervals)
    reason = "；".join(item["message"] for item in projected["issues"]) if projected["count"] is None and projected["issues"] else None
    return {"value": projected["count"], "reason": reason}


def resource_comparison(before, after, start, end, baseline_available, resources, *, calendar_archive,
                        task_intervals, reference_task_intervals):
    factory = ArchivedCalendar(calendar_archive)
    specs = [dict(resource, saved_id=factory.bindings.get((resource["kind"], resource["ref"]))) for resource in resources]
    indexes = [ResourceTaskIndex(tasks, start, end, work_available=enabled, task_intervals=intervals)
               for tasks, enabled, intervals in ((before, baseline_available, reference_task_intervals),
                                                 (after, True, task_intervals))]
    result = []
    for resource, (_, calendar) in zip(resources, factory.iter_resources(specs, start, end)):
        normalized_calendar = normalize_resource_calendar(calendar, start, end)
        sides = [pressure_from_index(index, resource, normalized_calendar) for index in indexes]
        previous, current = (side["peak_utilization"] for side in sides)
        result.append({"resource_ref": resource["ref"], "kind": resource["kind"], "label": resource["label"],
                       "before": sides[0], "after": sides[1],
                       "delta": None if previous is None or current is None else current - previous})
    common = {"metric_version": RESOURCE_METRIC_VERSION, "source": "archived_resource_calendar",
              "start": start, "end": end, "time_basis": "factory_local", "cohort_basis": "all_saved_candidates_and_admission_official",
              "cohort": resources,
              **{side: {kind: resource_summary([row[side]["window_metrics"] for row in result], kind=kind,
                                              identity_issues=index.identity_issues, work_available=index.work_available) for kind in ("machine", "operator")}
                 for side, index in zip(("before", "after"), indexes)}}
    return result, common
