"""One metric catalog and coverage-aware values for the run decision overview."""

from core.models.workbench_run_candidate import local_time

from .candidate_projection import metrics as saved_metrics
from .decision_delivery import project_decision_delivery
from .delivery_projection import delivery_summary
from .preflight_dependencies import material_deferred_ids
from .preparation_projection import (
    PREPARATION_METRIC_VERSION,
    PREPARATION_METRICS,
    preparation_delta,
)
from .resource_projection import RESOURCE_METRIC_VERSION

METRIC_VERSION = PREPARATION_METRIC_VERSION

# The saved resource statistics use the optimizer's schedule span. Calendar-window
# capacity statistics belong to the resource-impact stage and have their own scope.
_CATALOG = (
    ("expected_operation_count", "应排工序", "completeness", "工序", 0, "neutral", "full_admission", "admission", True),
    ("scheduled_operation_count", "已排工序", "completeness", "工序", 0, "higher", "full_admission", "candidate_tasks", True),
    ("unplanned_operation_count", "其他未安排工序", "completeness", "工序", 0, "lower", "full_admission", "candidate_tasks", True),
    ("deferred_operation_count", "缺料未安排工序", "completeness", "工序", 0, "neutral", "full_admission", "admission", True),
    ("overdue_count", "超期批次", "delivery", "批次", 0, "lower", "full_admission", "archived_delivery", True),
    ("total_tardiness_hours", "总拖期", "delivery", "小时", 2, "lower", "full_admission", "archived_delivery", True),
    ("makespan_hours", "安排总时长", "time", "小时", 2, "lower", "full_candidate", "saved_algorithm", True),
    ("weighted_tardiness_hours", "算法加权拖期", "time", "小时", 2, "lower", "saved_algorithm_batches", "saved_algorithm", False),
    ("elapsed_seconds", "计算用时", "time", "秒", 2, "neutral", "candidate_search", "saved_algorithm", True),
    ("changeover_count", "算法工种切换", "preparation", "次", 0, "lower", "full_candidate", "saved_algorithm", False),
    ("machine_used_count", "算法使用设备", "resources", "台", 0, "neutral", "saved_schedule_resources", "saved_algorithm", False),
    ("operator_used_count", "算法使用人员", "resources", "人", 0, "neutral", "saved_schedule_resources", "saved_algorithm", False),
    ("machine_busy_hours_total", "算法设备占用", "resources", "小时", 2, "neutral", "saved_schedule_resources", "saved_algorithm", False),
    ("operator_busy_hours_total", "算法人员占用", "resources", "小时", 2, "neutral", "saved_schedule_resources", "saved_algorithm", False),
    ("machine_util_avg", "算法设备占用率", "resources", "%", 1, "neutral", "saved_schedule_resources", "saved_algorithm", False),
    ("operator_util_avg", "算法人员占用率", "resources", "%", 1, "neutral", "saved_schedule_resources", "saved_algorithm", False),
    ("changed_operation_count", "调整工序", "stability", "工序", 0, "lower", "full_admission", "candidate_comparison", True),
    ("machine_change_count", "换设备工序", "stability", "工序", 0, "lower", "full_admission", "candidate_comparison", True),
)
RESOURCE_METRICS = (
    ("available_hours", "可排总时长", "小时", 2, "neutral", False),
    ("occupied_hours", "班内已占", "小时", 2, "neutral", False),
    ("summed_load_hours", "班内工序区间累加", "小时", 2, "neutral", False),
    ("outside_calendar_hours", "安排跨度跨非工作时段", "小时", 2, "neutral", False),
    ("overlap_hours", "班内重复计时", "小时", 2, "lower", False),
    ("utilization_ratio", "占用比例", "%", 1, "neutral", False),
    ("high_pressure_count", "高负荷资源", "项", 0, "lower", True),
    ("zero_capacity_task_count", "零容量工作证据", "项", 0, "neutral", False),
    ("conflict_resource_count", "班表内安排冲突", "项", 0, "lower", False),
    ("unknown_day_resource_count", "班表未知资源", "项", 0, "lower", False),
    ("balance_cv", "占用分布差异", "比值", 3, "lower", False),
    ("used_resource_count", "范围内使用资源", "项", 0, "neutral", False),
)


def metric_definitions():
    names = ("key", "label", "group", "unit", "precision", "improvement", "scope", "source", "common")
    resources = [(kind + "_" + key, "高负荷" + prefix if key == "high_pressure_count" else prefix + label,
                  "resources", count_unit if unit == "项" else unit, precision, improvement,
                  "fixed_resource_window", "archived_resource_calendar", common)
                 for kind, prefix, count_unit in (("machine", "设备", "台"), ("operator", "人员", "人"))
                 for key, label, unit, precision, improvement, common in RESOURCE_METRICS]
    preparation = [(key, label, "preparation", "小时", 3, "neutral", "full_admission", "runtime_operation_effort", common)
                   for key, label, _field, _group, common in PREPARATION_METRICS]
    events = (("type_changeover_count", "工种切换次数", "preparation", "次", 0, "lower", "fixed_changeover_window", "archived_changeover_events", True),
              ("changed_machine_count", "有切换设备数", "preparation", "台", 0, "lower", "fixed_changeover_window", "archived_changeover_events", False))
    return [{**dict(zip(names, row)), "metric_version": RESOURCE_METRIC_VERSION if row[7] == "archived_resource_calendar" else METRIC_VERSION}
            for row in _CATALOG + tuple(resources) + tuple(preparation) + events]


def metric_value(value, *, total=1, unknown=0, subtotal=None, state=None, scope="full_admission", reason=None, covered_refs=None, metric_version=METRIC_VERSION):
    result = {"value": value, "state": state or ("partial" if unknown and total > unknown else "unavailable" if unknown else "complete"),
              "known_subtotal": value if subtotal is None else subtotal, "known_count": total - unknown,
              "unknown_count": unknown, "total_count": total, "scope": scope, "metric_version": metric_version,
              "reason": reason}
    if covered_refs is not None:
        result["covered_batch_refs"] = sorted(covered_refs)
    return result


def admission_operations(facts, settings, disposition):
    selected = set(settings["batch_refs"])
    refs = {ref for ref, key in facts.operations.items()
            if facts.entity_refs.get(("batch", facts.tables["BatchOperations"].get(key, {}).get("batch_id"))) in selected}
    deferred_ids = material_deferred_ids((disposition or {}).values(), settings)
    deferred = {ref for ref in refs if facts.operations[ref] in deferred_ids}
    skipped = {ref for ref in refs if (disposition or {}).get(ref, {}).get("status") == "skipped"} - deferred
    return refs, deferred, skipped


def delivery_coverage(facts, tasks, batch_refs, deferred_refs, *, candidate=None, items=None):
    if items is None:
        deferred_ids = {facts.operations[ref] for ref in deferred_refs}
        items = project_decision_delivery(facts, tasks, batch_refs, deferred_ids=deferred_ids, candidate=candidate)
    summary = delivery_summary(items)
    coverage = {**summary, "state": "complete" if summary["complete_batch_count"] == summary["batch_count"] else "partial",
                "delivery_state": summary["state"]}
    return coverage, delivery_metric_values(summary)


def delivery_metric_values(summary):
    unknown = summary["unknown_due_count"]
    reason = {"code": "delivery_evidence_incomplete", "message": "部分批次的工序安排或交期资料缺失，已列出资料齐全批次的结果。"} if unknown else None
    result = {}
    for key, subtotal in (("overdue_count", summary["known_overdue_count"]),
                          ("total_tardiness_hours", summary["known_tardiness_hours"])):
        result[key] = metric_value(summary[key], total=summary["due_evaluation_count"], unknown=unknown, subtotal=subtotal,
                                   state=summary["state"], reason=reason, covered_refs=summary["known_batch_refs"])
        result[key].update({name: summary[name] for name in ("due_eligible_count", "excluded_due_count", "invalid_due_count", "due_evaluation_count")})
    return result


def candidate_metrics(candidate, tasks, facts, disposition, batch_refs, *, delivery_items, operation_scope):
    refs, deferred, skipped = operation_scope
    expected = refs - deferred
    has_result = candidate["status"] == "completed"
    scheduled = {row["operation_ref"] for row in tasks} & expected
    missing = expected - scheduled
    input_known = disposition is not None and refs == set(disposition)
    state = "unavailable" if not has_result or not input_known else "partial" if missing or skipped else "complete"
    schedulable = {"state": state, "expected_count": len(expected), "scheduled_count": len(scheduled) if has_result else None,
                   "missing_count": len(missing) if has_result else None, "skipped_count": len(skipped), "deferred_count": len(deferred)}
    coverage, values = delivery_coverage(facts, tasks, batch_refs, deferred, candidate=candidate, items=delivery_items)
    if not has_result:
        coverage["state"] = "unavailable"
    saved = saved_metrics(candidate["artifact"], [])
    for definition in metric_definitions():
        key = definition["key"]
        if key in values or key not in saved:
            continue
        item = saved[key]
        if key == "elapsed_seconds" and candidate["artifact"].get("generation_policy_version") == "unified_search_v1":
            values[key] = metric_value(None, total=0, state="not_applicable", scope=definition["scope"],
                                       reason=item["reason"])
            continue
        value = item["value"] if has_result else None
        values[key] = metric_value(value, unknown=int(value is None), scope=definition["scope"],
                                   reason=item["reason"] if value is None else None)
        if key == "weighted_tardiness_hours":
            completion = (candidate["artifact"].get("metrics") or {}).get("completion")
            incomplete = completion.get("incomplete_batch_ids") if type(completion) is dict else None
            if type(incomplete) is list:
                known = set(batch_refs) - {facts.entity_refs.get(("batch", key)) for key in incomplete}
                values[key] = metric_value(value, subtotal=value, total=len(batch_refs), unknown=len(batch_refs) - len(known),
                                           scope=definition["scope"], covered_refs=known, state="unavailable" if value is None else None)
            else:
                values[key]["state"] = "unavailable"
                values[key]["value"] = None
                values[key]["reason"] = {"code": "algorithm_batch_scope_missing", "message": "排产存档缺少算法交付评价的批次范围。"}
    for key, value in (("expected_operation_count", len(expected)), ("scheduled_operation_count", len(scheduled)),
                       ("unplanned_operation_count", len(missing)), ("deferred_operation_count", len(deferred))):
        known = input_known and (has_result or key in ("expected_operation_count", "deferred_operation_count"))
        values[key] = metric_value(value if known else None, total=len(refs), unknown=0 if known else len(refs),
                                   state="complete" if known else "unavailable")
    return {"schedulable": schedulable, "delivery": coverage}, values


def project_official_core_metrics(tasks, operation_refs, deferred_refs, available, delivery_items, *, metric_keys=None):
    """Project the saved official arrangement without reading its source archive."""
    refs = set(operation_refs)
    tasks = [task for task in tasks if task["operation_ref"] in refs]
    summary = delivery_summary(delivery_items)
    coverage = {**summary, "state": "complete" if summary["complete_batch_count"] == summary["batch_count"] else "partial",
                "delivery_state": summary["state"]}
    reason = {"code": "official_algorithm_metric_missing", "message": "排产时的正式计划未保存这项计算指标。"}
    values = {definition["key"]: metric_value(None, state="unavailable", unknown=1, scope=definition["scope"], reason=reason)
              for definition in metric_definitions() if metric_keys is None or definition["key"] in metric_keys}
    values.update(delivery_metric_values(summary))
    deferred = set(deferred_refs) & refs
    expected = refs - deferred
    scheduled = {task["operation_ref"] for task in tasks} & expected
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
    timed = all(task.get("interval_comparable", True) and task["start"] is not None and task["end"] is not None for task in tasks)
    span = ((max(local_time(task["end"]) for task in tasks) - min(local_time(task["start"]) for task in tasks)).total_seconds() / 3600.0
            if available and tasks and timed else None)
    values["makespan_hours"] = metric_value(span, unknown=int(span is None), scope="full_candidate")
    return values, {"schedulable": counts, "delivery": coverage}


def operation_change_metrics(comparisons, operation_refs, reference_available, *, selected_available=True):
    """Count complete admission comparisons with the shared availability rules."""
    if not reference_available or not selected_available:
        reason = ({"code": "reference_required", "message": "选择一个已产出候选作为比较基准。"} if not reference_available else
                  {"code": "candidate_result_unavailable", "message": "该候选没有产出任务安排，工序变化待确定。"})
        return {key: metric_value(None, unknown=len(operation_refs), total=len(operation_refs), reason=reason)
                for key in ("changed_operation_count", "machine_change_count")}
    changed = unknown = machines = machine_unknown = 0
    for row in comparisons:
        changed += bool(row["changed_fields"])
        unknown += not row["changed_fields"] and "unknown" in row["change_kinds"]
        machines += row["machine_changed"] is True
        machine_unknown += row["before"] is not None and row["after"] is not None and row["machine_changed"] is None
    reason = {"code": "arrangement_comparison_incomplete", "message": "部分工序有多段安排，或缺少时间、来源、设备人员编号，已列出可确认的调整数量。"}
    return {"changed_operation_count": metric_value(None if unknown else changed, total=len(operation_refs), unknown=unknown,
                                                    subtotal=changed, reason=reason if unknown else None),
            "machine_change_count": metric_value(None if machine_unknown else machines, total=len(operation_refs), unknown=machine_unknown,
                                                 subtotal=machines, reason=reason if machine_unknown else None)}


def metric_deltas(values, reference_values, *, work_scope_comparable):
    return {definition["key"]: metric_delta(definition, values[definition["key"]], reference_values.get(definition["key"], {}),
                                             work_scope_comparable=work_scope_comparable) for definition in metric_definitions()}


def metric_delta(definition, selected, previous, *, work_scope_comparable=True):
    if definition["source"] == "runtime_operation_effort":
        return preparation_delta(selected, previous)
    value, reference = selected["value"], previous.get("value")
    if definition["source"] == "archived_changeover_events":
        same_coverage = selected.get("covered_operation_refs") == previous.get("covered_operation_refs")
    else:
        same_coverage = (selected["total_count"] == previous.get("total_count")
                         and selected.get("covered_batch_refs") == previous.get("covered_batch_refs")
                         and selected.get("covered_resource_refs") == previous.get("covered_resource_refs"))
    if definition["key"] in ("makespan_hours", "changeover_count"):
        same_coverage = same_coverage and work_scope_comparable
    state = "unavailable" if value is None or reference is None else "comparable" if same_coverage else "different_coverage"
    difference = value - reference if state == "comparable" else None
    improvement = definition["improvement"]
    direction = "neutral" if difference is None else "equal" if difference == 0 else "neutral" if improvement == "neutral" else (
        "better" if (difference < 0) == (improvement == "lower") else "worse")
    return {"value": difference, "state": state, "direction": direction, "reference_value": reference, "selected_value": value}
