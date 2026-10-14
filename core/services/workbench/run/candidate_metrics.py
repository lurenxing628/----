"""Candidate comparison metrics from the same verified admission capture only."""

from core.models.workbench_run_candidate import local_time
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.facts.candidate_tasks import tasks_projection
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.changeovers import changeover_projection
from core.services.workbench.facts.resource_pressure import pressure_from_index
from core.services.workbench.facts.resource_projection import (
    RESOURCE_METRIC_VERSION,
    ResourceTaskIndex,
    resource_cohort,
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


def changeovers(rows, facts, available=True, *, start=None, end=None, next_operation_refs=None):
    projected = changeover_projection(rows, start=start, end=end, work_available=available,
                                     next_operation_refs=next_operation_refs)
    reason = "；".join(item["message"] for item in projected["issues"]) if projected["count"] is None and projected["issues"] else None
    return {"value": projected["count"], "reason": reason}


def candidate_resource_cohort(store, source, official_tasks):
    """Fix the denominator to every saved candidate plus its formal baseline."""
    pools = [official_tasks, source.tasks]
    for candidate in source.catalog:
        if candidate["candidate_ref"] == source.candidate["candidate_ref"] or candidate["status"] != "completed":
            continue
        raw = store.tasks(candidate["candidate_ref"])
        if len(raw) != candidate["task_count"]:
            corrupt()
        pools.append(tasks_projection(raw, candidate, source.facts))
    return resource_cohort(pools)


def resource_comparison(before, after, capture, facts, start, end, baseline_available, cohort=None):
    resources = cohort if cohort is not None else resource_cohort([before, after])
    factory = ArchivedCalendar(facts.archive)
    specs = [dict(resource, saved_id=factory.bindings.get((resource["kind"], resource["ref"]))) for resource in resources]
    indexes = [ResourceTaskIndex(tasks, start, end, work_available=enabled)
               for tasks, enabled in ((before, baseline_available), (after, True))]
    result = []
    for resource, (_, calendar) in zip(resources, factory.iter_resources(specs, start, end)):
        sides = [pressure_from_index(index, resource, calendar) for index in indexes]
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
