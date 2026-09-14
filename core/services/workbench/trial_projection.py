"""Public saved-origin tasks, real comparison metrics and explicit unknowns."""

import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import ACTIONS

from .trial_calendar import original_duration
from .trial_capacity import trial_capacity
from .trial_protection import TrialProtection
from .zero_duration import point_event_dto
from .zero_duration_evidence import trial_point_evidence


def tasks_projection(rows, draft_ref, checked, live):
    by_operation = {row["operation_ref"]: row["task_ref"] for row in rows}
    protected_rows = TrialProtection(live)
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
        "due_date": batch["due_date"], "locked": original["locked"] or bool(blocked),
        **{key: current[key] for key in ("machine_ref", "operator_ref", "start", "end")},
        "original": {key: original["arrangement"][key] for key in ("machine_ref", "operator_ref", "start", "end")},
        "hours": hours, "duration_reason": duration_reason,
        "changed": current != original["arrangement"],
        "predecessor_refs": [by_operation[ref] for ref in original["predecessor_operation_refs"] if ref in by_operation],
        "predecessor_operation_refs": original["predecessor_operation_refs"],
        "execution_at_creation": original["execution"], "execution": live["execution"].get(row["operation_ref"]),
        "edit_context": {"can_change": editable, "blocked_reasons": [value for value in (blocked, duration_reason) if value]},
        "issues": by_task[row["task_ref"]]}
    _display_fields(task)
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


def comparison(tasks, checked):
    groups = defaultdict(list)
    for task in tasks:
        groups[task["batch_ref"]].append(task)
    deliveries = []
    for batch_ref, group in groups.items():
        first = group[0]
        finish = max(row["end"] for row in group)
        original = max(row["original"]["end"] for row in group)
        risk, late, due_exclusive = _delivery_risk(first["due_date"], finish, checked)
        deliveries.append({"batch_ref": batch_ref, "batch_id": first["batch_id"], "part_name": first["part_name"],
            "quantity": first["batch_quantity"], "priority": first["priority"], "due_date": first["due_date"],
            "due_exclusive": due_exclusive, "baseline_finish": original, "finish": finish,
            "risk": risk, "late_hours": late,
            "improvement_hours": (datetime.fromisoformat(original) - datetime.fromisoformat(finish)).total_seconds() / 3600,
            "changed": any(row["changed"] for row in group),
            "moved": any(row["machine_ref"] != row["original"]["machine_ref"] for row in group)})
    measurable = all(row["late_hours"] is not None for row in deliveries)
    return {"basis": "draft_original", "batches": deliveries, "changed_operations": sum(row["changed"] for row in tasks),
            "moved_operations": sum(row["machine_ref"] != row["original"]["machine_ref"] for row in tasks),
            "late_count": sum(row["risk"] == "overdue" for row in deliveries) if measurable else None,
            "total_delay_hours": sum(row["late_hours"] for row in deliveries) if measurable else None,
            "changeovers": None, "changeover_reason": "未对试调执行真实换型成本评估。"}


def _delivery_risk(value, finish, checked):
    try:
        due = date.fromisoformat(value)
        limit = datetime.combine(due + timedelta(days=1), datetime.min.time())
        late = max(0.0, (datetime.fromisoformat(finish) - limit).total_seconds() / 3600)
        risk = "overdue" if datetime.fromisoformat(finish) >= limit else "on_time"
        if checked["constraints_status"] == "blocked":
            risk, late = "unavailable", None
        return risk, late, limit.isoformat()
    except (ValueError, TypeError, OverflowError):
        return "invalid_data", None, None


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
            task["data_gaps"].append({"field": key, "storage_type": type(task[key]).__name__, "message": "这一项的原始内容格式不对，不能直接显示；原始数据没有改动。"})
        task[key] = value


def draft_projection(head, rows, checked, live, context_factory):
    ref, admission = head["draft_ref"], head["admission"]
    binding = write_snapshot(head, rows, live)
    context = {"write_token": None, "expires_at": None,
               "capabilities": {action: False for action in ACTIONS}, "blocked_reasons": []}
    if head["status"] == "editing":
        context = context_factory(ref, ACTIONS, binding)
    else:
        context["blocked_reasons"] = [{"code": "draft_closed", "message": "该草稿已保存或明确放弃，只能读取原记录。"}]
    tasks = tasks_projection(rows, ref, checked, live)
    if head["status"] != "editing":
        for task in tasks:
            task["edit_context"]["can_change"] = False
            task["edit_context"]["blocked_reasons"].extend(context["blocked_reasons"])
    unplanned = _unplanned(admission, rows)
    return {"draft_ref": ref, "status": head["status"], "base": admission["input"]["base"],
            "base_identity": admission["source"]["identity"], "scope": admission["input"]["scope"],
            "baseline": {"plan_ref": admission["baseline"]["plan_ref"], "version": admission["baseline"]["version"]},
            "created_at": head["created_at"], "updated_at": head["updated_at"], "tasks": tasks,
            "task_count": len(tasks), "tasks_complete": True, "validation": checked,
            "unplanned_operations": unplanned, "scope_complete": not unplanned,
            "validation_at_last_write": head["validation"], "write_context": context,
            "resources": resources_projection(live), "comparison": comparison(tasks, checked),
            "capacity": trial_capacity(rows, live),
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
    from core.models.workbench_trial_codec import fingerprint

    return {"draft_ref": head["draft_ref"], "revision": head["revision"], "status": head["status"],
            "admission_hash": head["admission_hash"], "facts_hash": live["facts_hash"],
            "rows_hash": fingerprint([(row["row_ref"], row["current"]) for row in rows])}
