"""Public saved-origin tasks, real comparison metrics and explicit unknowns."""

import math
from collections import defaultdict

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import ACTIONS
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.delivery_completeness import archived_deferred_operation_evidence
from core.services.workbench.facts.delivery_projection import (
    delivery_batch_delta,
    delivery_summary,
    project_delivery_batch,
    task_intervals,
)
from core.services.workbench.facts.preflight_checks import stored_date
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.resource_projection import RESOURCE_METRIC_VERSION
from core.services.workbench.facts.zero_duration import point_event_dto
from core.services.workbench.facts.zero_duration_evidence import trial_point_evidence

from .arrangements import same_arrangement
from .calendar import original_duration
from .capacity import trial_capacity
from .effort import operation_effort_ledger
from .preparation import apply_changeovers, apply_preparation, preparation_projection, trial_changeovers
from .protection import TrialProtection


def tasks_projection(rows, draft_ref, checked, live, frozen=None):
    by_operation = {row["operation_ref"]: row["task_ref"] for row in rows}
    protected_rows = TrialProtection(live, frozen)
    by_task = _task_issue_index(checked["issues"])
    return [_task_projection(row, draft_ref, by_operation, protected_rows, by_task, live) for row in rows]


def _task_issue_index(issues):
    by_task = defaultdict(list)
    for item in issues:
        for key in ("task_ref", "related_task_ref"):
            if item.get(key) is not None:
                by_task[item[key]].append(item)
    return by_task


def _task_projection(row, draft_ref, by_operation, protected_rows, by_task, live):
    original, current = row["original"], row["current"]
    op, batch = original["operation"], original["batch"]
    hours, duration_reason = _hours(original)
    blocked = protected_rows.check(row)
    editable = blocked is None and duration_reason is None
    task = {"task_ref": row["task_ref"], "row_ref": row["row_ref"], "draft_ref": draft_ref,
        "operation_ref": row["operation_ref"], "source_task_ref": row["source_task_ref"],
        "source_row_ref": row["source_row_ref"], "batch_ref": original["batch_ref"],
        "batch_id": batch["batch_id"], "part_no": batch["part_no"], "part_name": (original.get("part") or {}).get("part_name"),
        "process_label": op["op_type_name"], "sequence": op["seq"], "piece_id": op["piece_id"],
        "source": op["source"], "quantity": hours.get("quantity"), "priority": batch["priority"],
        "batch_quantity": _public_value(batch["quantity"]),
        # 不能改的才画成锁定：正式计划里的锁定标记不再起作用，不拿它当依据。
        "due_date": batch["due_date"], "locked": bool(blocked),
        **{key: current[key] for key in ("machine_ref", "operator_ref", "start", "end")},
        "original": {key: original["arrangement"][key] for key in ("machine_ref", "operator_ref", "start", "end")},
        "hours": hours, "duration_reason": duration_reason,
        "changed": not same_arrangement(current, original["arrangement"]),
        "predecessor_refs": [by_operation[ref] for ref in original["predecessor_operation_refs"] if ref in by_operation],
        "predecessor_operation_refs": original["predecessor_operation_refs"],
        "execution_at_creation": original["execution"], "execution": live["execution"].get(row["operation_ref"]),
        "edit_context": {"can_change": editable, "blocked_reasons": [value for value in (blocked, duration_reason) if value]},
        "issues": by_task[row["task_ref"]]}
    _display_fields(task)
    anchor = original.get("execution_anchor")
    if anchor is not None:
        task["execution_anchor"] = {key: anchor["arrangement"][key] for key in ("machine_ref", "operator_ref", "start", "end")}
        task["execution_anchor"].update(basis=anchor["basis"], message=anchor["message"])
    if current["start"] == current["end"] and duration_reason is None:
        witness = trial_point_evidence(original, current)
        task.update(point_event_dto(witness.at, witness.at))
    return task


def _hours(original):
    try:
        return original_duration(original), None
    except WorkbenchCommandRejected as exc:
        op = original["operation"]
        return {"setup_hours": _public_value(op["setup_hours"]), "unit_hours": _public_value(op["unit_hours"]),
                "total_hours": None, "quantity": None, "basis": "unknown"}, {"code": exc.code, "message": str(exc)}


def resources_projection(live):
    tables = live["facts"]["tables"]
    refs = {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
    result = {"machines": [], "operators": [], "authorizations": []}
    for kind, table, bucket in (("machine", "Machines", "machines"), ("operator", "Operators", "operators")):
        for row in tables[table]:
            ref = refs.get((kind, row[kind + "_id"]))
            if ref is not None:
                result[bucket].append({"ref": ref, "business_code": row[kind + "_id"],
                                       "label": row["name"], "status": row["status"]})
    result["authorizations"] = [{"machine_ref": refs["machine", row["machine_id"]],
                                  "operator_ref": refs["operator", row["operator_id"]]}
                                 for row in tables["OperatorMachine"]
                                 if ("machine", row["machine_id"]) in refs and ("operator", row["operator_id"]) in refs]
    return result


def _delivery_origin(admission, rows, facts=None):
    source = admission["source"]
    if "capture" in source:
        capture = source["capture"]
        facts = facts if facts is not None else GenerationFacts(capture)
        selected = set(capture["input"]["batch_refs"])
        batches = {ref: facts.tables["Batches"][key] for (kind, key), ref in facts.entity_refs.items()
                   if kind == "batch" and ref in selected}
        operations = facts.tables["BatchOperations"].values()
        deferred = material_deferred_ids((source.get("dispositions") or {}).values(), capture["input"])
        deferred_issues = []
    else:
        batches = {row["original"]["batch_ref"]: row["original"]["batch"] for row in rows}
        operations = admission["facts"]["tables"]["BatchOperations"]
        if "deferred_operation_ids" in source:
            deferred, deferred_issues = set(source["deferred_operation_ids"]), source["deferred_operation_issues"]
        else:
            from core.models.workbench_command import canonical_json

            version = source.get("identity", {}).get("version")
            history = [row for row in admission["facts"]["tables"].get("ScheduleHistory", []) if row["version"] == version]
            summary = (history[0]["result_summary"] if len(history) == 1
                       else canonical_json({"material_policy": source.get("material_policy", {})}))
            deferred, deferred_issues = archived_deferred_operation_evidence({"summary": summary})
        selected = {batch["batch_id"] for batch in batches.values()}
        pending = {operation["batch_id"] for operation in operations if operation["id"] in deferred} - selected
        if pending:
            tables = admission["facts"]["tables"]
            batch_rows = {batch["batch_id"]: batch for batch in tables["Batches"]}
            refs = {item["entity_key"]: item["ref"] for item in tables["WorkbenchEntityRefs"]
                    if item["kind"] == "batch" and item["active"] == 1}
            for batch_id in sorted(pending):
                if batch_id not in batch_rows or batch_id not in refs:
                    from core.models.workbench_trial import reject

                    reject("trial_snapshot_invalid", "保存来源中待料批次的资料或永久编号缺失，请核对保存记录。")
                batches[refs[batch_id]] = batch_rows[batch_id]
    by_batch = defaultdict(list)
    for operation in operations:
        by_batch[operation["batch_id"]].append(dict(operation, op_id=operation["id"]))
    return batches, by_batch, deferred, deferred_issues


def _delivery_arrangements(rows, field):
    by_batch = defaultdict(list)
    for row in rows:
        original = row["original"]
        arrangement = original["arrangement"] if field == "original" else row["current"]
        projected = {"schedule_id": row["row_ref"], "op_id": original["operation"]["id"],
                     "batch_id": original["batch"]["batch_id"], "start_time": arrangement["start"],
                     "end_time": arrangement["end"]}
        if arrangement["start"] == arrangement["end"]:
            if row.get("_delivery_source_unknown"):
                projected["point_evidence_issue"] = "trial_source_unavailable"
            else:
                trial_point_evidence(original, arrangement)
                projected["_point_work"] = True
        by_batch[projected["batch_id"]].append(projected)
    return by_batch


def _delivery_side(batches, operations, arrangements, deferred, uncertain, blocked_batches=()):
    intervals = task_intervals([row for group in arrangements.values() for row in group])
    return {ref: project_delivery_batch(batch, ref, arrangements[batch["batch_id"]],
                                       operations[batch["batch_id"]], intervals, False,
                                       uncertain + (["trial_constraints_blocked"] if None in blocked_batches
                                                    or batch["batch_id"] in blocked_batches else []),
                                       deferred_operation_ids=deferred)
            for ref, batch in batches.items()}


def _blocked_delivery_batches(checked, tasks, rows):
    if checked["constraints_status"] != "blocked":
        return set()
    sources = {row["row_ref"]: row for row in rows}
    originals = {row["task_ref"]: row["original"] for row in rows}
    for task in tasks:
        source = sources.get(task.get("source_row_ref")) or sources.get(task["row_ref"])
        if source is not None:
            originals[task["task_ref"]] = source["original"]
    blocked = set()
    issues = checked.get("issues", [])
    if not issues:
        return {None}
    for item in issues:
        if item.get("severity") != "blocker":
            continue
        if item["code"] == "trial_base_date_invalid":
            if item.get("field") == "due_date":
                continue
            original = originals.get(item.get("task_ref"))
            if "field" not in item and original is not None:
                ready = original["batch"].get("ready_date")
                if ready is None or isinstance(ready, str) and stored_date(ready) is not None:
                    continue
        related = [originals[key]["batch"]["batch_id"] for key in (item.get("task_ref"), item.get("related_task_ref"))
                   if key in originals]
        blocked.update(related or [None])
    return blocked


def comparison(tasks, checked, rows, admission, origin_issues=(), facts=None):
    groups = defaultdict(list)
    for task in tasks:
        groups[task["batch_ref"]].append(task)
    batches, operations, deferred, deferred_issues = _delivery_origin(admission, rows, facts)
    origin_issues = list(origin_issues) + list(deferred_issues)
    before = _delivery_side(batches, operations, _delivery_arrangements(rows, "original"), deferred, origin_issues)
    blocked = _blocked_delivery_batches(checked, tasks, rows)
    after = _delivery_side(batches, operations, _delivery_arrangements(rows, "current"), deferred, origin_issues, blocked)
    deliveries = []
    for batch_ref, batch in batches.items():
        group, previous, current = groups[batch_ref], before[batch_ref], after[batch_ref]
        delta = delivery_batch_delta(previous, current)
        deliveries.append({"batch_ref": batch_ref, "batch_id": batch["batch_id"], "part_name": current["part_label"],
            "quantity": _public_value(batch["quantity"]), "priority": _public_value(batch["priority"]),
            "due_date": current["due_date"], "due_state": current["due_state"], "due_issue": current["due_issue"],
            "due_exclusive": current["delivery_deadline_exclusive"], "baseline_finish": previous["planned_finish"],
            "finish": current["planned_finish"], "partial_baseline_finish": previous["partial_planned_finish"],
            "partial_finish": current["partial_planned_finish"], "completion_state": current["completion_state"],
            "risk": current["risk"], "late_hours": current["delay_hours"], "before": previous, "after": current, **delta,
            "improvement_hours": None if delta["finish_delta_hours"] is None else -delta["finish_delta_hours"],
            "changed": any(row["changed"] for row in group),
            "moved": any(row["machine_ref"] != row["original"]["machine_ref"] for row in group)})
    summary, original_summary = delivery_summary(list(after.values())), delivery_summary(list(before.values()))
    return {"basis": "draft_original", "batches": deliveries, "changed_operations": sum(row["changed"] for row in tasks),
            "moved_operations": sum(row["machine_ref"] != row["original"]["machine_ref"] for row in tasks),
            "late_count": summary["overdue_count"], "total_delay_hours": summary["total_tardiness_hours"],
            "delivery_summary": summary, "before_delivery_summary": original_summary,
            "changeovers": None, "changeover_reason": "原试调来源的工种资料缺失。"}


def scenario_comparison(saved, head, rows):
    """Reproject a historical saved view from its immutable source, without writing it."""
    if head is None:
        projected = []
        for task in saved["tasks"]:
            batch = {"batch_id": task["batch_id"], "part_no": task["part_no"], "part_name": task["part_name"],
                     "quantity": task["batch_quantity"], "priority": task["priority"], "due_date": task["due_date"]}
            projected.append({"row_ref": task["row_ref"], "task_ref": task["task_ref"], "current": task,
                              "original": {"batch": batch, "batch_ref": task["batch_ref"],
                                           "operation": {"id": task["operation_ref"]}, "arrangement": task["original"]},
                              "_delivery_source_unknown": True})
        admission = {"source": {}, "facts": {"tables": {"BatchOperations": []}}}
        return comparison(saved["tasks"], saved["validation"], projected, admission, ["trial_source_unavailable"])
    projected = scenario_rows(saved, rows)
    return comparison(saved["tasks"], saved["validation"], projected, head["admission"])


def scenario_rows(saved, rows):
    originals = {row["row_ref"]: row for row in rows}
    if {task["source_row_ref"] for task in saved["tasks"]} != set(originals):
        from core.models.workbench_trial import reject

        reject("trial_snapshot_invalid", "保存的试调工序与原草稿范围不一致，请核对保存记录。")
    projected = [dict(originals[task["source_row_ref"]], row_ref=task["row_ref"], task_ref=task["task_ref"],
                      current=dict(originals[task["source_row_ref"]]["current"],
                                   **{key: task[key] for key in ("start", "end", "machine_ref", "operator_ref")}))
                 for task in saved["tasks"]]
    return projected


def scenario_capacity(saved, head, rows):
    if head is None:
        return dict(saved["capacity"], state="unavailable", source="archived_resource_calendar",
                    metric_version=RESOURCE_METRIC_VERSION, resource_common=None,
                    reason="原草稿保存的日历来源缺失，资源容量未知。", resources=[])
    admission = head["admission"]
    facts = GenerationFacts(admission["source"]["capture"]) if "capture" in admission["source"] else None
    archive = facts.archive if facts is not None else admission["facts"]
    return trial_capacity(scenario_rows(saved, rows), archive, source_ref=admission["source"]["identity"])


def _public_value(value):
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    return None


def _display_fields(task):
    task["data_gaps"] = []
    for key in ("part_no", "part_name", "process_label", "sequence", "piece_id", "source", "quantity", "priority", "due_date"):
        value = _public_value(task[key])
        if value is None and task[key] is not None:
            task["data_gaps"].append({"field": key, "storage_type": type(task[key]).__name__, "message": "原始内容格式无效，暂无法显示。"})
        task[key] = value


def draft_projection(head, rows, checked, live, context_factory, frozen=None):
    ref, admission = head["draft_ref"], head["admission"]
    binding = write_snapshot(head, rows, live)
    context = {"write_token": None, "expires_at": None,
               "capabilities": {action: False for action in ACTIONS}, "blocked_reasons": []}
    if head["status"] == "editing":
        context = context_factory(ref, ACTIONS, binding)
    else:
        context["blocked_reasons"] = [{"code": "draft_closed", "message": "该草稿已保存或明确放弃，只能读取原记录。"}]
    tasks = tasks_projection(rows, ref, checked, live, frozen)
    facts = GenerationFacts(admission["source"]["capture"]) if "capture" in admission["source"] else None
    archive = facts.archive if facts is not None else admission["facts"]
    if head["status"] != "editing":
        for task in tasks:
            task["edit_context"]["can_change"] = False
            task["edit_context"]["blocked_reasons"].extend(context["blocked_reasons"])
    unplanned = _unplanned(admission, rows)
    ledger = operation_effort_ledger(rows, admission)
    pairs, preparation = preparation_projection(rows, admission, ledger, current_evidence={"kind": "trial", "draft_ref": ref})
    apply_preparation(tasks, unplanned, pairs)
    compared = comparison(tasks, checked, rows, admission, facts=facts)
    compared["preparation_common"] = preparation
    apply_changeovers(compared, trial_changeovers(rows, admission))
    return {"draft_ref": ref, "status": head["status"], "base": admission["input"]["base"],
            "base_identity": admission["source"]["identity"], "scope": admission["input"]["scope"],
            "baseline": {"plan_ref": admission["baseline"]["plan_ref"], "version": admission["baseline"]["version"]},
            "created_at": head["created_at"], "updated_at": head["updated_at"], "tasks": tasks,
            "task_count": len(tasks), "tasks_complete": True, "validation": checked,
            "unplanned_operations": unplanned, "scope_complete": not unplanned,
            "validation_at_last_write": head["validation"], "write_context": context,
            "resources": resources_projection(live), "operation_effort": ledger,
            "comparison": compared,
            "capacity": trial_capacity(rows, archive, source_ref=admission["source"]["identity"]),
            "time_scope": {"start": min(row["start"] for row in tasks), "end": max(row["end"] for row in tasks),
                           "time_basis": "factory_local", "selection": "complete_base"}}


def _unplanned(admission, rows):
    scope = admission["source"].get("dispositions")
    if scope is None:
        return []
    scheduled = {row["operation_ref"] for row in rows}
    fields = ("operation_ref", "batch_ref", "piece_id", "sequence", "status", "predecessor_refs")
    return [{**{key: row[key] for key in fields}, "reason": {"code": "base_operation_unscheduled",
             "message": "排产时选中的这道工序没有保存安排，这里仍然照样列出。"}}
            for ref, row in scope.items() if ref not in scheduled]


def write_snapshot(head, rows, live):
    return {"draft_ref": head["draft_ref"], "revision": head["revision"], "status": head["status"],
            "facts": live["facts"], "execution": live["execution"], "baseline": live["baseline"],
            "rows": [(row["row_ref"], row["current"]) for row in rows]}
