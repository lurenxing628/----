"""Public saved-origin tasks, real comparison metrics and explicit unknowns."""

import math
from collections import defaultdict

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import ACTIONS
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.delivery_projection import (
    delivery_batch_delta,
    delivery_summary,
    project_delivery_batch,
    task_intervals,
)
from core.services.workbench.facts.operation_effort_evidence import saved_operation_efforts
from core.services.workbench.facts.preflight_checks import stored_date
from core.services.workbench.facts.trial_origin import delivery_origin, operation_contexts
from core.services.workbench.facts.zero_duration import point_event_dto
from core.services.workbench.facts.zero_duration_evidence import trial_point_evidence

from .arrangements import same_arrangement
from .calendar import original_duration
from .capacity import trial_capacity
from .effort import operation_effort_ledger
from .preparation import apply_changeovers, apply_preparation, preparation_projection, trial_changeovers


def tasks_projection(rows, draft_ref, checked, live, protection):
    """protection: 与 checked 同一次核对得到的 TrialProtection。"""
    by_operation = {row["operation_ref"]: row["task_ref"] for row in rows}
    by_task = _task_issue_index(checked["issues"])
    return [_task_projection(row, draft_ref, by_operation, protection, by_task, live) for row in rows]


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
        "execution_at_creation": original["execution"], "execution": live["execution"][row["operation_ref"]],
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
    refs = live["preflight_facts"].refs
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


def _delivery_arrangements(rows, field):
    by_batch = defaultdict(list)
    for row in rows:
        original = row["original"]
        arrangement = original["arrangement"] if field == "original" else row["current"]
        projected = {"schedule_id": row["row_ref"], "op_id": original["operation"]["id"],
                     "batch_id": original["batch"]["batch_id"], "start_time": arrangement["start"],
                     "end_time": arrangement["end"]}
        if arrangement["start"] == arrangement["end"]:
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


def _blocked_delivery_batches(checked, rows):
    if checked["constraints_status"] != "blocked":
        return set()
    originals = {row["task_ref"]: row["original"] for row in rows}
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


def comparison(tasks, checked, rows, admission, facts=None, *, origin=None):
    groups = defaultdict(list)
    for task in tasks:
        groups[task["batch_ref"]].append(task)
    batches, operations, deferred, deferred_issues = delivery_origin(admission, rows, facts) if origin is None else origin
    before = _delivery_side(batches, operations, _delivery_arrangements(rows, "original"), deferred, deferred_issues)
    blocked = _blocked_delivery_batches(checked, rows)
    after = _delivery_side(batches, operations, _delivery_arrangements(rows, "current"), deferred, deferred_issues, blocked)
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


def source_projection(rows, admission, *, facts=None):
    """Prepare one source archive, delivery grouping and operation scope for these rows."""
    if facts is None and "capture" in admission["source"]:
        facts = GenerationFacts(admission["source"]["capture"])
    archive = facts.archive if facts is not None else admission["facts"]
    origin = delivery_origin(admission, rows, facts)
    contexts = operation_contexts(rows, admission, facts, origin=origin)
    return facts, archive, origin, contexts


def draft_projection(head, rows, checked, live, context_factory, protection, *, source_prepared, scenario_ref):
    ref, admission = head["draft_ref"], head["admission"]
    if scenario_ref is None:
        binding = write_snapshot(head, rows, live)
        context = {"write_token": None, "expires_at": None,
                   "capabilities": {action: False for action in ACTIONS}, "blocked_reasons": []}
        if head["status"] == "editing":
            context = context_factory(ref, ACTIONS, binding)
        else:
            context["blocked_reasons"] = [{"code": "draft_closed", "message": "该草稿已保存或明确放弃，只能读取原记录。"}]
        current_evidence = {"kind": "trial", "draft_ref": ref}
    else:
        current_evidence = {"kind": "scenario", "scenario_ref": scenario_ref}
    tasks = tasks_projection(rows, ref, checked, live, protection)
    facts, archive, origin, contexts = (
        source_projection(rows, admission, facts=live["source_facts"])
        if source_prepared is None
        else source_prepared
    )
    if scenario_ref is None and head["status"] != "editing":
        for task in tasks:
            task["edit_context"]["can_change"] = False
            task["edit_context"]["blocked_reasons"].extend(context["blocked_reasons"])
    unplanned = unplanned_operations(contexts)
    before_efforts = saved_operation_efforts(admission["source"].get("operation_effort"))
    ledger = operation_effort_ledger(rows, admission, before_efforts=before_efforts)
    pairs, preparation = preparation_projection(rows, admission, ledger,
        current_evidence=current_evidence, contexts=contexts, before_efforts=before_efforts)
    apply_preparation(tasks, unplanned, pairs)
    compared = comparison(tasks, checked, rows, admission, facts=facts, origin=origin)
    compared["preparation_common"] = preparation
    if scenario_ref is None:
        apply_changeovers(compared, trial_changeovers(rows, admission, facts=facts))
    result = {"draft_ref": ref, "status": head["status"], "base": admission["input"]["base"],
            "base_identity": admission["source"]["identity"], "scope": admission["input"]["scope"],
            "baseline": {"plan_ref": admission["baseline"]["plan_ref"], "version": admission["baseline"]["version"]},
            "created_at": head["created_at"], "updated_at": head["updated_at"], "tasks": tasks,
            "task_count": len(tasks), "tasks_complete": True, "validation": checked,
            "unplanned_operations": unplanned, "scope_complete": not unplanned,
            "validation_at_last_write": head["validation"],
            "resources": resources_projection(live), "operation_effort": ledger,
            "comparison": compared,
            "capacity": trial_capacity(rows, archive, source_ref=admission["source"]["identity"]),
            "time_scope": {"start": min(row["start"] for row in tasks), "end": max(row["end"] for row in tasks),
                           "time_basis": "factory_local", "selection": "complete_base"}}
    if scenario_ref is None:
        result["write_context"] = context
    return result


def unplanned_operations(contexts):
    fields = ("operation_ref", "batch_ref", "piece_id", "sequence", "status", "predecessor_refs")
    result = []
    for ref, context in contexts.items():
        if context["arranged"]:
            continue
        op = context["operation"]
        disposition = context.get("disposition")
        item = ({key: disposition[key] for key in fields} if disposition is not None else
                {"operation_ref": ref, "batch_ref": context["batch_ref"], "piece_id": op["piece_id"],
                 "sequence": op["seq"], "status": op["status"]})
        item["reason"] = {"code": "base_operation_unscheduled", "message":
            "这道工序在基础方案中因待料暂缓安排。" if context["deferred"] else "这道工序在基础方案中没有安排。"}
        result.append(item)
    return result


def write_snapshot(head, rows, live):
    return {"draft_ref": head["draft_ref"], "revision": head["revision"], "status": head["status"],
            "facts": live["facts"], "execution": live["execution"], "baseline": live["baseline"],
            "rows": [(row["row_ref"], row["current"]) for row in rows]}
