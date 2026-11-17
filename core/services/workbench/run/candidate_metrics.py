"""Candidate comparison metrics from the same verified admission capture only."""

from core.models.workbench_run_candidate import local_time
from core.services.workbench.facts.archived_calendar import ArchivedCalendar, archived_calendar_tables
from core.services.workbench.facts.changeovers import changeover_projection
from core.services.workbench.facts.resource_calendar import normalize_resource_calendar
from core.services.workbench.facts.resource_pressure import pressure_from_index
from core.services.workbench.facts.resource_projection import (
    RESOURCE_METRIC_VERSION,
    ResourceTaskIndex,
    resource_summary,
)


def scoped_rows(rows, batch_refs, start, end, *, task_intervals):
    """Select displayed task rows; changeover sequences are formed before this."""
    low, high = local_time(start), local_time(end)
    result = []
    for row in rows:
        if row["batch_ref"] not in batch_refs:
            continue
        first, last = task_intervals[row["row_ref"]]
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
    """Each resource's whole-window peak on both sides; the window facts only feed the cohort totals."""
    factory = ArchivedCalendar(archived_calendar_tables(calendar_archive))
    specs = [dict(resource, saved_id=factory.bindings.get((resource["kind"], resource["ref"]))) for resource in resources]
    indexes = [ResourceTaskIndex(tasks, start, end, work_available=enabled, task_intervals=intervals,
                                 retain_statistics_values=False)
               for tasks, enabled, intervals in ((before, baseline_available, reference_task_intervals),
                                                 (after, True, task_intervals))]
    result, windows = [], ([], [])
    for resource, (_, calendar) in zip(resources, factory.iter_resources(specs, start, end)):
        normalized_calendar = normalize_resource_calendar(calendar, start, end)
        sides = [pressure_from_index(index, resource, normalized_calendar, include_days=False) for index in indexes]
        for index, side, side_windows in zip(indexes, sides, windows):
            side_windows.append(side["window_metrics"])
            index.release(resource)
        previous, current = (side["peak_utilization"] for side in sides)
        result.append({"resource_ref": resource["ref"], "kind": resource["kind"], "label": resource["label"],
                       **{name: {"state": side["state"], "peak_utilization": side["peak_utilization"]}
                          for name, side in zip(("before", "after"), sides)},
                       "delta": None if previous is None or current is None else current - previous})
    common = {"metric_version": RESOURCE_METRIC_VERSION, "source": "archived_resource_calendar",
              "start": start, "end": end, "time_basis": "factory_local", "cohort_basis": "all_saved_candidates_and_admission_official",
              "cohort": resources,
              **{side: {kind: resource_summary(side_windows, kind=kind, identity_issues=index.identity_issues,
                                              work_available=index.work_available) for kind in ("machine", "operator")}
                 for side, index, side_windows in zip(("before", "after"), indexes, windows)}}
    return result, common
