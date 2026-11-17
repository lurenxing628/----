"""Public saved-origin tasks, real comparison metrics and explicit unknowns."""

import math
from collections import defaultdict

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import ACTIONS
from core.services.workbench.facts.delivery_projection import (
    DeliveryBatch,
    DeliveryTask,
    delivery_batch_delta,
    delivery_summary,
    parse_stored_due_date,
    project_delivery_batch,
)
from core.services.workbench.facts.operation_effort_evidence import saved_operation_efforts
from core.services.workbench.facts.trial_origin import invalid_trial_snapshot
from core.services.workbench.facts.trial_policy import public_source_identity
from core.services.workbench.facts.zero_duration import point_event_dto
from core.shared.stored_dates import stored_date

from .arrangements import same_arrangement
from .calendar import original_duration
from .capacity import trial_capacity
from .effort import operation_effort_ledger
from .preparation import DraftLabels, apply_changeovers, apply_preparation, preparation_projection, trial_changeovers


def tasks_projection(rows, draft_ref, checked, live, protection, *, trial_intervals):
    """protection: 与 checked 同一次核对得到的 TrialProtection。"""
    by_operation = {row["operation_ref"]: row["task_ref"] for row in rows}
    by_task = _task_issue_index(checked["issues"])
    tasks = []
    for row in rows:
        blocked = protection.check(row)
        task = _task_projection(row, draft_ref, by_operation, by_task, trial_intervals,
                                source_task_ref=row["source_task_ref"], source_row_ref=row["source_row_ref"],
                                locked=bool(blocked), execution=live["execution"][row["operation_ref"]])
        reason = task["duration_reason"]
        task["edit_context"] = {"can_change": blocked is None and reason is None,
                                "blocked_reasons": [value for value in (blocked, reason) if value]}
        tasks.append(task)
    return tasks


def scenario_tasks(saved, rows, *, trial_intervals):
    """A saved scenario's public tasks, projected again by the draft's task projection from its bound draft rows
    (``rows`` is ``bind_scenario_rows`` of ``saved["tasks"]``, in the same order). The stored task holds only what
    the save saw live, its execution and lock; the issues are the saved validation's, under the scenario's refs, and
    the lineage names the draft row each task came from."""
    by_operation = {row["operation_ref"]: row["task_ref"] for row in rows}
    by_task = _task_issue_index(saved["validation"]["issues"])
    tasks = []
    for stored, row in zip(saved["tasks"], rows):
        task = _task_projection(row, saved["draft_ref"], by_operation, by_task, trial_intervals,
                                source_task_ref=row["draft_task_ref"], source_row_ref=row["draft_row_ref"],
                                locked=stored["locked"], execution=stored["execution"])
        task["edit_context"] = scenario_edit_context()
        tasks.append(task)
    return tasks


def scenario_edit_context():
    """Every task of a saved scenario is read-only."""
    return {"can_change": False,
            "blocked_reasons": [{"code": "scenario_readonly", "message": "试调方案已保存，只能查看不能改。"}]}


def _task_issue_index(issues):
    by_task = defaultdict(list)
    for item in issues:
        for key in ("task_ref", "related_task_ref"):
            if item.get(key) is not None:
                by_task[item[key]].append(item)
    return by_task


def _task_projection(row, draft_ref, by_operation, by_task, trial_intervals, *, source_task_ref, source_row_ref,
                     locked, execution):
    """One trial row as a task: everything but its edit context comes from the row, its draft and these facts."""
    original, current = row["original"], row["current"]
    op, batch = original["operation"], original["batch"]
    hours, duration_reason = _hours(original, point_proven=row["row_ref"] in trial_intervals["original_points_by_row"])
    task = {"task_ref": row["task_ref"], "row_ref": row["row_ref"], "draft_ref": draft_ref,
        "operation_ref": row["operation_ref"], "source_task_ref": source_task_ref,
        "source_row_ref": source_row_ref, "batch_ref": original["batch_ref"],
        "batch_id": batch["batch_id"], "part_no": batch["part_no"], "part_name": original["part"]["part_name"],
        "process_label": op["op_type_name"], "sequence": op["seq"], "piece_id": op["piece_id"],
        "source": op["source"], "quantity": hours.get("quantity"), "priority": batch["priority"],
        "batch_quantity": _public_value(batch["quantity"]),
        # 不能改的才画成锁定：正式计划里的锁定标记不再起作用，不拿它当依据。
        "due_date": batch["due_date"], "locked": locked,
        **{key: current[key] for key in ("machine_ref", "operator_ref", "start", "end")},
        "original": {key: original["arrangement"][key] for key in ("machine_ref", "operator_ref", "start", "end")},
        "hours": hours, "duration_reason": duration_reason,
        "changed": not same_arrangement(current, original["arrangement"]),
        "predecessor_refs": [by_operation[ref] for ref in original["predecessor_operation_refs"] if ref in by_operation],
        "predecessor_operation_refs": original["predecessor_operation_refs"],
        "execution_at_creation": original["execution"],
        "execution": execution,
        "issues": by_task[row["task_ref"]]}
    _display_fields(task)
    # 原值先由 _display_fields 记下读不出的存储类型（如 BLOB）；交期再与候选、基线、正式参考同一解析，
    # 明确交期、9999-12-31 未指定、缺失和无效分别表达，不从空值猜。
    task["due_date"], _deadline, task["due_state"], task["due_issue"] = parse_stored_due_date(batch["due_date"])
    anchor = original.get("execution_anchor")
    if anchor is not None:
        task["execution_anchor"] = {key: anchor["arrangement"][key] for key in ("machine_ref", "operator_ref", "start", "end")}
        task["execution_anchor"].update(basis=anchor["basis"], message=anchor["message"])
    # Only a zero-length row its point basis proves is a point event; an unproven one stays a plain arrangement.
    witness = trial_intervals["current_points_by_row"].get(row["row_ref"])
    if witness is not None and duration_reason is None:
        task.update(point_event_dto(witness.at, witness.at))
    return task


def _hours(original, *, point_proven):
    try:
        return original_duration(original, point_proven=point_proven), None
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


def scenario_resources_snapshot(live):
    public = resources_projection(live)
    tables = live["facts"]["tables"]
    refs = live["preflight_facts"].refs
    return {
        **public,
        "suppliers": [
            {
                "supplier_id": row["supplier_id"],
                "ref": refs.get(("supplier", row["supplier_id"])),
                "name": row["name"],
                "status": row["status"],
            }
            for row in tables["Suppliers"]
        ],
        "op_types": [
            {
                "op_type_id": row["op_type_id"],
                "ref": refs.get(("op_type", row["op_type_id"])),
                "name": row["name"],
            }
            for row in tables["OpTypes"]
        ],
    }


def public_scenario_resources(saved_resources):
    """The saved resources a scenario shows; ``saved_resources`` was read for this request only."""
    return {key: saved_resources[key] for key in ("machines", "operators", "authorizations")}


def _delivery_arrangements(rows):
    """Each batch's arranged ``(row_ref, op_id)``; both sides share them and differ only in their intervals."""
    by_batch = defaultdict(list)
    for row in rows:
        original = row["original"]
        by_batch[original["batch"]["batch_id"]].append((row["row_ref"], original["operation"]["id"]))
    return by_batch


def _delivery_side(batches, operations, arrangements, deferred, scope_issues, blocked_batches=(), *, intervals):
    result = {}
    for ref, batch in batches.items():
        key = batch["batch_id"]
        blocked = ("trial_constraints_blocked",) if None in blocked_batches or key in blocked_batches else ()
        item = DeliveryBatch(batch, ref, frozenset(row["op_id"] for row in operations[key]),
                             tuple(DeliveryTask(op_id, intervals[row_ref][1]) for row_ref, op_id in arrangements[key]),
                             False, blocked)
        result[ref] = project_delivery_batch(item, deferred_operation_ids=deferred, scope_issues=scope_issues)
    return result


def _blocked_delivery_batches(checked, rows):
    if checked["constraints_status"] != "blocked":
        return set()
    originals = {row["task_ref"]: row["original"] for row in rows}
    blocked = set()
    issues = checked["issues"]
    if not issues:
        return {None}
    for item in issues:
        if item["severity"] != "blocker":
            continue
        if item["code"] == "trial_base_date_invalid":
            if item.get("field") == "due_date":
                continue
            original = originals.get(item.get("task_ref"))
            if "field" not in item and original is not None:
                ready = original["batch"]["ready_date"]
                if ready is None or isinstance(ready, str) and stored_date(ready) is not None:
                    continue
        related = [originals[key]["batch"]["batch_id"] for key in (item.get("task_ref"), item.get("related_task_ref"))
                   if key in originals]
        blocked.update(related or [None])
    return blocked


def comparison(tasks, checked, rows, origin, *, trial_intervals):
    original_by_row = trial_intervals["original_by_row"]
    current_by_row = trial_intervals["current_by_row"]
    groups = defaultdict(list)
    for task in tasks:
        groups[task["batch_ref"]].append(task)
    batches, operations = origin.batches, origin.operations
    deferred, deferred_issues = origin.deferred, tuple(origin.deferred_issues)
    arranged = _delivery_arrangements(rows)
    before = _delivery_side(
        batches,
        operations,
        arranged,
        deferred,
        deferred_issues,
        intervals=original_by_row,
    )
    blocked = _blocked_delivery_batches(checked, rows)
    after = _delivery_side(
        batches,
        operations,
        arranged,
        deferred,
        deferred_issues,
        blocked,
        intervals=current_by_row,
    )
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


def draft_projection(head, rows, checked, live, context_factory, protection, *, scenario_ref, trial_intervals):
    ref, admission = head["draft_ref"], head["admission"]
    origin = live["origin"]
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
    tasks = tasks_projection(rows, ref, checked, live, protection, trial_intervals=trial_intervals)
    contexts = origin.contexts(rows)
    if scenario_ref is None and head["status"] != "editing":
        for task in tasks:
            task["edit_context"]["can_change"] = False
            task["edit_context"]["blocked_reasons"].extend(context["blocked_reasons"])
    unplanned = unplanned_operations(contexts)
    before_efforts = saved_operation_efforts(admission["source"]["operation_effort"], on_corrupt=invalid_trial_snapshot)
    ledger, after_efforts = operation_effort_ledger(rows, admission, before_efforts=before_efforts)
    pairs, preparation = preparation_projection(admission, before_efforts, after_efforts,
        current_evidence=current_evidence, contexts=contexts)
    apply_preparation(tasks, unplanned, pairs)
    compared = comparison(tasks, checked, rows, origin, trial_intervals=trial_intervals)
    compared["preparation_common"] = preparation
    if scenario_ref is None:
        apply_changeovers(compared, trial_changeovers(rows, DraftLabels(origin), trial_intervals=trial_intervals))
    # The head, its admission and the ledger belong to this request, and nothing changes them after this projection.
    result = {"draft_ref": ref, "status": head["status"], "base": admission["input"]["base"],
            "base_identity": public_source_identity(admission["source"]), "scope": admission["input"]["scope"],
            "baseline": {"plan_ref": admission["baseline"]["plan_ref"], "version": admission["baseline"]["version"]},
            "created_at": head["created_at"], "updated_at": head["updated_at"], "tasks": tasks,
            "task_count": len(tasks), "tasks_complete": True, "validation": checked,
            "unplanned_operations": unplanned, "scope_complete": not unplanned,
            "validation_at_last_write": head["validation"],
            "resources": resources_projection(live), "operation_effort": ledger,
            "comparison": compared,
            "capacity": trial_capacity(
                rows,
                origin.calendar_tables,
                source_ref=public_source_identity(admission["source"]),
                trial_intervals=trial_intervals,
            ),
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
            "revisions": live["revisions"], "data_context_ref": live["data_context_ref"],
            "rows": [(row["row_ref"], row["current"]) for row in rows]}
