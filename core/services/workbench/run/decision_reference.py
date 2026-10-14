"""Business facts available in the admission's assembled official arrangement."""

from core.models.workbench_run_candidate import local_time
from core.services.workbench.facts.delivery_projection import delivery_summary

from .decision_delivery import decision_delivery_summary
from .decision_metrics import delivery_metric_values, metric_definitions, metric_value


def reference_delivery(source):
    return source.completion.delivery("reference")


def official_reference_metrics(source, *, metric_keys=None):
    available = source.baseline["state"] == "available"
    rows = reference_delivery(source)
    summary = delivery_summary(rows)
    coverage = decision_delivery_summary(rows)
    reason = {"code": "official_algorithm_metric_missing", "message": "排产时的正式计划未保存这项计算指标。"}
    values = {definition["key"]: metric_value(None, state="unavailable", unknown=1, scope=definition["scope"], reason=reason)
              for definition in metric_definitions() if metric_keys is None or definition["key"] in metric_keys}
    values.update(delivery_metric_values(summary))
    refs = set(source.scope["operation_refs"])
    deferred = {ref for ref in refs if source.facts.operations[ref] in source.reference_deferred_ids}
    expected = refs - deferred
    scheduled = {task["operation_ref"] for task in source.before_tasks} & expected
    missing = expected - scheduled
    state = "unavailable" if not available else "partial" if missing else "complete"
    counts = {"state": state, "expected_count": len(expected), "scheduled_count": len(scheduled) if available else None,
              "missing_count": len(missing) if available else None, "skipped_count": 0, "deferred_count": len(deferred)}
    for key, value in (("expected_operation_count", len(expected)), ("scheduled_operation_count", len(scheduled)),
                       ("unplanned_operation_count", len(missing)), ("deferred_operation_count", len(deferred)),
                       ("changed_operation_count", 0), ("machine_change_count", 0)):
        if metric_keys is not None and key not in metric_keys:
            continue
        values[key] = metric_value(value if available else None, total=len(refs), unknown=0 if available else len(refs),
                                   state="complete" if available else "unavailable")
    tasks = source.before_tasks
    timed = all(task.get("interval_comparable", True) and task["start"] is not None and task["end"] is not None for task in tasks)
    span = ((max(local_time(task["end"]) for task in tasks) - min(local_time(task["start"]) for task in tasks)).total_seconds() / 3600.0
            if available and tasks and timed else None)
    values["makespan_hours"] = metric_value(span, unknown=int(span is None), scope="full_candidate")
    return values, {"schedulable": counts, "delivery": coverage}
