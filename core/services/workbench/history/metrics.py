"""History values from the saved sources and the existing decision projections."""

from types import SimpleNamespace
from typing import List, Optional, Union, cast

from core.services.capacity.plan_calendar_intervals import hours, instant
from core.services.workbench.facts.candidate_projection import dispositions
from core.services.workbench.facts.candidate_tasks import task_span
from core.services.workbench.facts.candidate_values import number
from core.services.workbench.facts.completion_scope import project_completion_summary
from core.services.workbench.facts.decision_metrics import (
    admission_operations,
    delivery_metric_values,
    metric_definitions,
    metric_value,
)
from core.services.workbench.facts.preflight_checks import PreflightChecks
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.preparation_projection import (
    metric_summary as effort_metric,
)
from core.services.workbench.facts.preparation_projection import (
    preparation_summary,
)
from core.services.workbench.facts.resource_intervals import task_interval
from core.services.workbench.facts.resource_projection import resource_cohort
from core.services.workbench.facts.trial_origin import delivery_origin as trial_delivery_origin
from core.services.workbench.run.decision_resource_engine import DecisionResources
from core.services.workbench.run.preflight import batch_dependencies, classify, task_row
from core.services.workbench.trial.capacity import capacity_tasks as trial_resource_tasks
from core.services.workbench.trial.preparation import preparation_projection, trial_changeovers
from core.services.workbench.trial.projection import comparison as trial_comparison
from core.services.workbench.trial.projection import scenario_comparison
from data.repositories.workbench_preflight_facts_repo import PREFLIGHT_TABLES

from .conditions_source import ConditionSource
from .metric_gate import COVERAGE_FIELDS, metric_reason
from .metric_window import history_window

_VALUE_FIELDS = ("value", "state", "known_subtotal", "known_count", "unknown_count", "total_count",
                 "scope", "metric_version", "reason")
_RESOURCE_FIELDS = ("numerator_hours", "denominator_hours", "unknown_workload_count")


def _public_reason(value):
    return {key: value[key] for key in ("code", "message")} if value else None


def _source(packet, path):
    return {"kind": packet["kind"], "ref": packet["ref"], "path": path}


def _metric(item, definition, packet, path):
    value = {key: item[key] for key in _VALUE_FIELDS}
    value["reason"] = _public_reason(value["reason"])
    value.update(unit=definition["unit"], source=_source(packet, path))
    value.update({key: sorted(set(item[key])) if item.get(key) is not None else None for key in COVERAGE_FIELDS})
    value.update({key: item.get(key) for key in _RESOURCE_FIELDS})
    return value


def _missing(definition, packet, reason, *, scope=None, version=None, path=None):
    item = metric_value(None, unknown=1, scope=scope or definition["scope"],
                        metric_version=version or definition["metric_version"],
                        reason=reason or metric_reason("history_metric_not_recorded", "保存来源未记录此指标。"))
    return _metric(item, definition, packet, path)


def _numeric(raw) -> Optional[Union[int, float]]:
    value = number(raw, "history_metric", [])
    return value if type(value) is int or type(value) is float else None


def _count(raw):
    value = number(raw, "history_count", [], integer=True)
    return value if type(value) is int else None


def _object(value):
    return value if type(value) is dict else {}


def _quantity(packet, refs, batches):
    definition = {"unit": "件"}
    if refs is None:
        item = metric_value(None, unknown=1, scope="selected_batches",
                            reason=metric_reason("batch_quantity_missing", "保存来源缺少所选批次的数量与真实成员。"))
    else:
        measured = {ref: _numeric(batches.get(ref, {}).get("quantity")) for ref in refs}
        known = {ref: value for ref, value in measured.items() if value is not None}
        unknown = len(refs) - len(known)
        subtotal = sum(known.values()) if known or not refs else None
        item = metric_value(None if unknown else subtotal, total=len(refs), unknown=unknown, subtotal=subtotal,
                            scope="selected_batches", covered_refs=known,
                            reason=metric_reason("batch_quantity_missing", "部分所选批次未保存可确认的数量，显示已知小计。") if unknown else None)
    return _metric(item, definition, packet, "Batches.quantity")


def _scope(packet, batch_refs=None, operation_refs=None, *, batches=None, demand=None, reason=None):
    available = batch_refs is not None and operation_refs is not None
    return {"state": "complete" if available and reason is None else "partial" if available else "unavailable",
            "batch_refs": sorted(batch_refs) if batch_refs is not None else None,
            "operation_refs": sorted(operation_refs) if operation_refs is not None else None,
            "batch_count": len(batch_refs) if batch_refs is not None else None,
            "operation_count": len(operation_refs) if operation_refs is not None else None,
            "demand_hours": demand, "batch_quantity": _quantity(packet, batch_refs, batches or {}),
            "reason": reason if reason else None if available else metric_reason(
                "history_scope_not_recorded", "保存来源缺少可核对的批次与工序成员。")}


def _demand(rows):
    pending = [row for row in rows if row.get("source") != "external"
               and row.get("allocation_state") in ("new_schedule", "unplanned", "deferred", "unknown")]
    return effort_metric(pending, "required_standard_hours")["value"]


def _admission_count_values(packet, operation_refs, *, reader):
    facts, settings = packet["facts"], packet["capture"]["input"]
    saved = dispositions(packet.get("receipt"))
    deferred = material_deferred_ids((saved or {}).values(), settings)
    reason = None
    if saved is None and settings.get("material_strategy") == "stage" and settings.get("ready_check") is True:
        condition = reader.condition_source(packet)
        tables = {name: condition.table(name) for name in PREFLIGHT_TABLES}
        if any(rows is None for rows in tables.values()) or not set(operation_refs) <= set(facts.execution):
            reason = metric_reason("admission_deferred_scope_missing", "保存的物料、工序或报工资料缺项，应排与待料范围尚待确认。")
        else:
            try:
                checks = PreflightChecks(tables)
                reverse = {key: ref for ref, key in facts.operations.items()}
                view = SimpleNamespace(operation_ref=lambda op: reverse[op["id"]])
                rows = []
                by_batch = {}
                for ref in operation_refs:
                    operation = facts.tables["BatchOperations"][facts.operations[ref]]
                    by_batch.setdefault(operation["batch_id"], []).append(operation)
                for batch_ref in settings["batch_refs"]:
                    batch = dict(condition.batches[batch_ref], ref=batch_ref)
                    ops = by_batch.get(batch["batch_id"], [])
                    batch_rows = []
                    for operation in ops:
                        projection = facts.execution[reverse[operation["id"]]]
                        row = task_row(view, batch, operation, projection)
                        ready, _release = checks.operation_readiness(batch, operation, settings)
                        row["status"], row["issues"] = classify(checks, batch, operation, projection, settings, ready)
                        batch_rows.append(row)
                    batch_dependencies(batch, ops, batch_rows)
                    rows.extend(batch_rows)
                deferred = material_deferred_ids(rows, settings)
            except KeyError:
                reason = metric_reason("admission_deferred_scope_missing", "旧归档缺少分类所需字段，应排与待料范围尚待确认。")
    expected = {ref for ref in operation_refs if facts.operations[ref] not in deferred}
    result = {}
    for key, value in (("expected_operation_count", len(expected)), ("deferred_operation_count", len(operation_refs) - len(expected))):
        item = metric_value(value if reason is None else None, total=len(operation_refs),
                            unknown=len(operation_refs) if reason else 0, state="unavailable" if reason else "complete", reason=reason)
        item["covered_operation_refs"] = sorted(operation_refs) if reason is None else None
        result[key] = item
    return result


def _run(reader, packet, window):
    candidate = packet.get("candidate")
    ref = candidate["candidate_ref"] if candidate is not None else None
    if packet.get("capture") is None:
        return {}, _scope(packet), "unavailable"
    if candidate is None:
        facts, settings = packet["facts"], packet["capture"]["input"]
        operation_refs, _deferred, _skipped = admission_operations(facts, settings, None)
        batches = {ref: facts.tables["Batches"].get(key, {}) for (kind, key), ref in facts.entity_refs.items() if kind == "batch"}
        window.update(state="unavailable", reason=metric_reason("history_result_missing", "此事件尚未保存任务安排，资源集合与占用未知。"))
        values = _admission_count_values(packet, operation_refs, reader=reader)
        return values, _scope(packet, settings["batch_refs"], operation_refs, batches=batches), "unavailable"
    source = reader.run_source(packet["ref"], ref, range_start=window["start"], range_end=window["end"])
    data = reader.decision(packet["ref"], window["start"], window["end"], candidate_ref=ref)
    selected = next((item for item in data["candidates"] if item["candidate_ref"] == ref), None)
    values = {} if selected is None else {key: dict(item) for key, item in selected["metrics"].items()}
    if selected is not None:
        values.update(source.preparation.metrics(ref))
        values.update(source.changeovers.metrics(ref))
        tasks = source.tasks(ref)
        scheduled_refs = sorted({task["operation_ref"] for task in tasks})
        for definition in metric_definitions():
            key = definition["key"]
            if key not in values:
                continue
            item = dict(values[key])
            if definition["scope"] == "full_admission" and definition["source"] not in (
                    "archived_delivery", "runtime_operation_effort"):
                item["covered_operation_refs"] = list(source.scope["operation_refs"])
            elif definition["scope"] == "full_candidate":
                item["covered_operation_refs"] = scheduled_refs
            elif definition["scope"] == "saved_schedule_resources":
                kind = "machine" if key.startswith("machine_") else "operator"
                item["covered_resource_refs"] = sorted({task[kind]["ref"] for task in tasks
                    if task.get(kind) is not None and task[kind].get("ref") is not None})
            if definition["scope"] == "fixed_resource_window" and key.endswith(("utilization_ratio", "balance_cv")):
                kind = key.split("_", 1)[0]
                summary = selected["coverage"]["resources"][kind]
                item.update(numerator_hours=summary["numerator_hours"], denominator_hours=summary["denominator_hours"])
            values[key] = item
    window["cohort"] = {kind + "_refs": list(data["resource_cohort"][kind + "_refs"]) for kind in ("machine", "operator")}
    if selected is not None:
        summaries = selected["coverage"]["resources"]
        if any(summaries[kind]["state"] in ("partial", "unavailable") for kind in ("machine", "operator")):
            window.update(state="partial", reason=metric_reason("resource_evidence_incomplete", "部分归档班表或安排资料缺项。"))
    facts = packet["facts"]
    batches = {ref: facts.tables["Batches"].get(key, {}) for (kind, key), ref in facts.entity_refs.items() if kind == "batch"}
    demand = _demand(source.preparation.rows(ref)) if selected is not None else None
    scope = _scope(packet, source.scope["batch_refs"], source.scope["operation_refs"], batches=batches, demand=demand)
    return values, scope, "available" if selected is not None and candidate["status"] == "completed" else "unavailable"


def _trial_preparation(saved, head, projected):
    if head is not None:
        pairs, _common = preparation_projection(projected, head["admission"], saved.get("operation_effort"),
            current_evidence={"kind": "scenario", "scenario_ref": saved["scenario_ref"]})
        arranged = {row["operation_ref"] for row in projected}
        return [dict(pair["after"], operation_ref=ref, arranged=ref in arranged) for ref, pair in pairs.items()]
    return None


def _trial_resources(packet, projected, window, calendar):
    admission = packet["head"]["admission"]
    archive = admission["facts"]
    original, tasks = (trial_resource_tasks(projected, side) for side in ("original", "current"))
    intervals = {key: {row["row_ref"]: task_interval(row) for row in rows}
                 for key, rows in (("reference", original), (packet["ref"], tasks))}
    cohort = resource_cohort([original, tasks], task_intervals=[intervals["reference"], intervals[packet["ref"]]])
    resources = [{"kind": kind, "ref": ref, "saved_id": saved_id}
                 for (kind, ref), saved_id in calendar.bindings.items()]
    view = SimpleNamespace(calendar_archive=archive, context={"resources": resources}, run={"run_ref": packet["ref"]},
        scope={"range_start": window["start"], "range_end": window["end"]},
        resource_cohort={"resources": cohort}, resource_before_tasks=original,
        rows=[{"candidate_ref": packet["ref"], "status": "completed"}], baseline={"state": "available"},
        resource_tasks=lambda _key: tasks, computation_key=lambda key: key, task_intervals=lambda key: intervals[key])
    engine = DecisionResources(view, calendar=calendar)
    values = engine.metrics(packet["ref"])
    summaries = {kind: engine.summary(packet["ref"], kind) for kind in ("machine", "operator")}
    for kind, summary in summaries.items():
        for field in ("utilization_ratio", "balance_cv"):
            values[kind + "_" + field].update(numerator_hours=summary["numerator_hours"], denominator_hours=summary["denominator_hours"])
    window["cohort"] = {kind + "_refs": sorted(row["ref"] for row in cohort if row["kind"] == kind) for kind in ("machine", "operator")}
    if any(summary["state"] in ("partial", "unavailable") for summary in summaries.values()):
        window.update(state="partial", reason=metric_reason("resource_evidence_incomplete", "部分归档班表或安排资料缺项。"))
    return values


def _trial(packet, window, *, reader=None):
    saved, head = packet.get("saved"), packet.get("head")
    if saved is None:
        return {}, _scope(packet), "unavailable"
    projected = packet["rows"] if head is not None else []
    comparison = saved.get("comparison") or {}
    if "delivery_summary" not in comparison:
        comparison = (trial_comparison(saved["tasks"], saved["validation"], projected, head["admission"])
                      if head is not None else scenario_comparison(saved, None))
    values = delivery_metric_values(comparison["delivery_summary"])
    efforts = _trial_preparation(saved, head, projected)
    if efforts is not None:
        values.update(preparation_summary(efforts)["metrics"])
    elif comparison.get("preparation_common") is not None:
        values.update(comparison["preparation_common"]["after"])
    tasks, unplanned = saved.get("tasks", []), saved.get("unplanned_operations", [])
    operations = {row["operation_ref"] for row in tasks + unplanned}
    scheduled = {row["operation_ref"] for row in tasks}
    batches = {row["batch_ref"] for row in comparison.get("batches", [])}
    batches.update(row["batch_ref"] for row in tasks + unplanned if row.get("batch_ref") is not None)
    condition = (reader.condition_source(packet) if reader is not None else ConditionSource(packet)) if head is not None else None
    deferred, ordinary = None, None
    completion_reason = metric_reason("trial_pending_members_missing", "保存的未安排数量与实际工序身份不齐，应排、待料和其他未安排范围待确认。")
    if condition is not None:
        _batches, _operations, deferred_ids, deferred_issues = trial_delivery_origin(head["admission"], projected)
        operations = set(condition.operations)
        batches = set(condition.batches)
        if not deferred_issues:
            effort_by_ref = {row["operation_ref"]: row for row in efforts or []}
            missing = []
            for ref in sorted(operations - scheduled):
                operation = condition.operations[ref]
                missing.append({**effort_by_ref.get(ref, {}), "operation_ref": ref, "sequence": operation["seq"],
                    "batch_ref": condition.original_entity_refs.get(("batch", operation["batch_id"])), "arranged": False,
                    "source": operation["source"], "allocation_state": "deferred" if operation["id"] in deferred_ids else "unplanned"})
            completion = project_completion_summary([row["after"] for row in comparison["batches"]], missing)
            deferred, ordinary = set(completion["deferred_operation_refs"]), set(completion["unplanned_operation_refs"])
    else:
        roles = {row["operation_ref"]: (row.get("operation_effort") or {}).get("after", {}).get("allocation_state") for row in unplanned}
        known_deferred = {ref for ref, role in roles.items() if role == "deferred"}
        known_ordinary = {ref for ref, role in roles.items() if role == "unplanned"}
        fields = ("operation_count", "scheduled_operation_count", "deferred_operation_count", "ordinary_unscheduled_operation_count")
        counts = [[_count((row.get("after") or {}).get(field)) for field in fields] for row in comparison.get("batches", [])]
        counts_known = type(comparison.get("batches")) is list and all(value is not None for row in counts for value in row)
        if counts_known:
            # The full check above excludes None from every Optional[int] count.
            known_counts = cast(List[List[int]], counts)
            totals = [sum(row[index] for row in known_counts) for index in range(len(fields))]
        else:
            totals = None
        if all(role in ("deferred", "unplanned") for role in roles.values()) and totals == [
                len(operations), len(scheduled), len(known_deferred), len(known_ordinary)]:
            deferred, ordinary = known_deferred, known_ordinary
    for key, value in (("expected_operation_count", len(operations - deferred) if deferred is not None else None),
                       ("scheduled_operation_count", len(scheduled)),
                       ("unplanned_operation_count", len(ordinary) if ordinary is not None else None),
                       ("deferred_operation_count", len(deferred) if deferred is not None else None),
                       ("changed_operation_count", comparison.get("changed_operations")),
                       ("machine_change_count", comparison.get("moved_operations"))):
        item = metric_value(value, total=len(operations) if value is not None else max(1, len(operations)),
                            unknown=max(1, len(operations)) if value is None else 0,
                            state="unavailable" if value is None else "complete", scope="complete_trial",
                            reason=completion_reason if value is None and key in (
                                "expected_operation_count", "unplanned_operation_count", "deferred_operation_count") else None)
        item["covered_operation_refs"] = sorted(operations - deferred) if key == "expected_operation_count" and deferred is not None else (
            sorted(operations) if value is not None else None)
        values[key] = item
    timed_tasks = [(task, task_interval(task)) for task in tasks]
    valid_tasks = [task for task, interval in timed_tasks if interval is not None]
    span = task_span(valid_tasks)
    makespan = hours([(instant(span["start"]), instant(span["end"]))]) if span is not None else None
    missing_times = len(tasks) - len(valid_tasks)
    values["makespan_hours"] = metric_value(makespan if not missing_times else None, total=max(1, len(tasks)),
        unknown=missing_times if tasks else 1, subtotal=makespan, scope="full_candidate",
        reason=metric_reason("trial_arrangement_time_missing", "部分保存安排缺少可核对的时间区间，总时长保留已知跨度。") if missing_times or not tasks else None)
    values["makespan_hours"]["covered_operation_refs"] = sorted({task["operation_ref"] for task in valid_tasks})
    common = (trial_changeovers(projected, head["admission"], start=window["start"], end=window["end"],
                               next_operation_refs=operations)
              if head is not None and window["start"] is not None else None)
    if common is not None:
        after = common["after"]
        arrangements = [task for task, interval in timed_tasks if task.get("source") != "external"
                        and not (interval is not None and interval[0] == interval[1])]
        covered_refs = sorted({row["operation_ref"] for row in arrangements})
        for key, field in (("type_changeover_count", "count"), ("changed_machine_count", "changed_machine_count")):
            item = metric_value(after[field], total=max(len(arrangements), after["unknown_count"]), unknown=after["unknown_count"],
                                subtotal=after["known_" + field], state=after["state"], scope=common["scope"],
                                metric_version=common["metric_version"], reason=metric_reason("changeover_sequence_incomplete",
                                    "部分保存安排的工种、时间或实际顺序缺项。") if after["state"] != "complete" else None)
            item["covered_operation_refs"] = covered_refs
            values[key] = item
    if condition is not None and window["start"] is not None:
        values.update(_trial_resources(packet, projected, window, condition.calendar))
    else:
        window.update(state="unavailable", reason=metric_reason("history_resource_archive_missing", "原试调草稿或资源窗口缺项，归档容量未知。"))
    quantity_batches = condition.batches if condition is not None else {
        row["batch_ref"]: {"quantity": row.get("batch_quantity")} for row in tasks}
    scope = _scope(packet, batches, operations, batches=quantity_batches,
                   demand=_demand(efforts) if efforts is not None else None,
                   reason=None if head is not None else metric_reason("history_original_archive_missing", "原草稿归档缺失，保留保存视图的结果。"))
    return values, scope, "available" if head is not None else "partial"


def _legacy(packet):
    saved = packet.get("parsed_summary")
    if saved is None:
        return {}, _scope(packet), "unavailable"
    version = "legacy-summary:" + str(saved.get("summary_schema_version") if saved.get("summary_schema_version") is not None else "unknown")
    algorithm = _object(saved.get("algo"))
    raw, counts = _object(algorithm.get("metrics")), _object(saved.get("counts"))
    values = {}
    for definition in metric_definitions():
        key = definition["key"]
        value = _count(raw.get(key)) if definition["unit"] in ("工序", "批次", "次", "台", "人") else _numeric(raw.get(key))
        scope = "legacy_saved_algorithm_batches" if key == "weighted_tardiness_hours" else "legacy_saved_schedule"
        if key in ("expected_operation_count", "scheduled_operation_count", "unplanned_operation_count"):
            field = {"expected_operation_count": "op_count", "scheduled_operation_count": "scheduled_ops", "unplanned_operation_count": "failed_ops"}[key]
            value, scope = _count(counts.get(field)), "legacy_summary_counts"
        elif key == "overdue_count":
            value, scope = _count(_object(saved.get("overdue_batches")).get("count")), "legacy_completed_batches_only"
        elif key == "total_tardiness_hours":
            scope = "legacy_completed_batches_only"
        elif key == "elapsed_seconds":
            milliseconds = _numeric(saved.get("time_cost_ms"))
            value, scope = milliseconds / 1000 if milliseconds is not None else None, "legacy_input_to_summary"
        elif key in ("machine_util_avg", "operator_util_avg") and raw.get("util_defined") is not True:
            value = None
        if value is not None:
            values[key] = metric_value(value, scope=scope, metric_version=version)
    scope = _scope(packet)
    scope.update(batch_count=_count(counts.get("batch_count")), operation_count=_count(counts.get("op_count")))
    return values, scope, "available"


def _path(packet, definition):
    key, origin = definition["key"], definition["source"]
    if packet["kind"] == "legacy":
        if key == "elapsed_seconds":
            return "parsed_summary.time_cost_ms"
        if key == "overdue_count":
            return "parsed_summary.overdue_batches.count"
        if key in ("expected_operation_count", "scheduled_operation_count", "unplanned_operation_count"):
            field = {"expected_operation_count": "op_count", "scheduled_operation_count": "scheduled_ops", "unplanned_operation_count": "failed_ops"}[key]
            return "parsed_summary.counts." + field
        return "parsed_summary.algo.metrics." + key
    if packet["kind"] == "trial":
        if key == "scheduled_operation_count":
            return "saved.tasks"
        if packet.get("head") is not None and key in (
                "expected_operation_count", "deferred_operation_count", "unplanned_operation_count"):
            return "head.admission"
        if key == "makespan_hours":
            return "saved.tasks.start/end"
        if origin == "archived_resource_calendar":
            return "head.admission.facts"
        if origin == "runtime_operation_effort":
            return "saved.operation_effort" if packet.get("head") is not None else "saved.comparison.preparation_common.after"
        return "saved.comparison"
    if origin == "saved_algorithm":
        return "candidate.artifact." + ("elapsed_seconds" if key == "elapsed_seconds" else "metrics." + key)
    return {"runtime_operation_effort": "receipt.operation_effort", "admission": "capture.input",
            "archived_resource_calendar": "capture.facts_text", "archived_delivery": "capture.facts_text"}.get(origin, "raw_tasks")


def project_history_metrics(reader, descriptor, query):
    """One immutable result identity is projected once per request and window."""
    packet = reader.read(descriptor)
    window = history_window(packet, query)
    definitions = {row["key"]: row for row in metric_definitions()}
    keys = query["metric_keys"]
    issue = packet.get("source_issue")
    if issue is not None and not (packet["kind"] == "trial" and packet.get("saved") is not None):
        window.update(state="unavailable", reason=issue)
        return {"metrics": {key: _missing(definitions[key], packet, issue) for key in keys}, "scope": _scope(packet, reason=issue),
                "source": {"kind": packet["kind"], "ref": packet["ref"], "state": "unavailable", "reason": issue},
                "reading_context": {"resource_window": window, "metric_basis": "source_unavailable"}}
    candidate = packet.get("candidate")
    cache_key = (packet["kind"], packet["ref"], candidate["candidate_ref"] if candidate else None,
                 window["start"], window["end"], window["days"], tuple(keys))
    if cache_key not in reader.history_metrics_cache:
        if packet["kind"] == "run":
            values, scope, state = _run(reader, packet, window)
        elif packet["kind"] == "trial":
            values, scope, state = _trial(packet, window, reader=reader)
        else:
            values, scope, state = _legacy(packet)
            window.update(state="unavailable", reason=metric_reason("history_resource_archive_missing", "旧摘要未保存可重建容量的资源日历与安排来源。"))
        source_reason = issue if issue is not None else metric_reason("history_result_missing", "此事件未保存可用的结果来源。") if state == "unavailable" else None
        schema = (packet.get("parsed_summary") or {}).get("summary_schema_version")
        legacy_version = "legacy-summary:" + str(schema if schema is not None else "unknown")
        metrics = {key: _metric(values[key], definitions[key], packet, _path(packet, definitions[key])) if key in values
                   else _missing(definitions[key], packet, source_reason,
                                 scope="legacy_not_recorded" if packet["kind"] == "legacy" else None,
                                 version=legacy_version if packet["kind"] == "legacy" else None,
                                 path=_path(packet, definitions[key])) for key in keys}
        reader.history_metrics_cache[cache_key] = {"metrics": metrics, "scope": scope,
            "source": {"kind": packet["kind"], "ref": packet["ref"], "state": state, "reason": source_reason},
            "reading_context": {"resource_window": window, "metric_basis": "legacy_saved_summary" if packet["kind"] == "legacy" else "archived_shared_projection"}}
    return reader.history_metrics_cache[cache_key]
