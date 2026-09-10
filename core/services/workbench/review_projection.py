"""One ledger projection, one plan-finish cohort, no second completion reducer."""

from __future__ import annotations

from core.models.workbench_command import WorkbenchCommandRejected

from .review_export_labels import export_labels
from .review_legacy import legacy_review
from .review_records import actual_resource, project_records, resource_directory
from .review_values import hour_totals, local_time, minutes

STATUS_LABELS = {"complete": "已完工", "partial": "部分完成", "started": "生产中", "paused": "已暂停",
                 "exception": "异常中", "unreported": "暂无现场反馈"}


def resource(facts, kind, key):
    return facts["resources"][kind].get(str(key), {"ref": None, "label": "未填写"})


def project_operation(row, projection, label, facts, as_of):
    planned_start, planned_end = local_time(row.get("start_time")), local_time(row.get("end_time"))
    complete = projection["execution_state"] == "complete"
    confirmed_finish = projection["confirmed_finish"]
    end_delta = minutes(planned_end, confirmed_finish)
    due = planned_end is not None and planned_end <= as_of
    elapsed = minutes(planned_end, as_of) if due and not complete else None
    batch = resource(facts, "batch", row["batch_id"])
    machine, operator = resource(facts, "machine", row.get("machine_id")), resource(facts, "operator", row.get("operator_id"))
    invalid_time = any(gap["code"] == "invalid_legacy_sequence" for gap in projection["data_gaps"])
    status = "invalid" if invalid_time and not complete else projection["execution_state"]
    return {"operation_ref": projection["operation_ref"], "task_ref": facts["task_refs"][row["schedule_id"]],
            "batch_ref": batch["ref"], "batch_label": batch["label"], "operation_label": label["operation_label"],
            "planned_start": planned_start, "planned_end": planned_end, "actual_start": projection["first_actual_start"],
            "confirmed_finish": confirmed_finish, "completion_basis": projection["completion_basis"],
            "execution_state": status, "ledger_execution_state": projection["execution_state"],
            "execution_label": "事实时间或顺序异常，需复核" if status == "invalid" else STATUS_LABELS[status],
            **{key: projection[key] for key in ("target_quantity", "target_basis", "known_completed_quantity", "remaining_quantity",
                "quantity_complete", "unknown_record_count", "records_complete", "data_quality")},
            "machine_ref": machine["ref"], "machine_label": machine["label"],
            "operator_ref": operator["ref"], "operator_label": operator["label"],
            "due": due, "complete": complete, "unclosed": due and not complete,
            "late_open": elapsed is not None and elapsed > 10, "finish_late": end_delta is not None and end_delta > 10,
            "finish_deviation_minutes": end_delta, "elapsed_since_planned_minutes": elapsed,
            "data_gaps": [gap["message"] for gap in projection["data_gaps"]], "execution_data_gaps": projection["data_gaps"],
            **legacy_review(projection)}


def _selected(scope, operation, events):
    end = operation["planned_end"]
    if scope.plan_finish_date_from and (end is None or not scope.plan_finish_date_from <= end[:10] <= scope.plan_finish_date_to):
        return False
    if scope.batch_ref and operation["batch_ref"] != scope.batch_ref:
        return False
    if scope.query.strip().casefold() not in (operation["batch_label"] + " " + operation["operation_label"]).casefold():
        return False
    if scope.resource_ref:
        key = scope.resource_type + "_ref"
        values = [operation[key]] + [event[key] for event in events]
        if (None if scope.resource_ref == "unassigned" else scope.resource_ref) not in values:
            return False
    if scope.focus == "unreported":
        return operation["execution_state"] == "unreported"
    if scope.focus == "data_gaps":
        return operation["data_quality"] != "complete"
    return scope.focus == "all" or bool(operation[scope.focus])


def project_cohort(facts, as_of):
    projections = {row["operation_ref"]: row for row in facts["ledger"]["projections"]}
    directory = resource_directory(facts)
    operations, records, labels = [], [], {}
    for row, label in zip(facts["rows"], facts["labels"]):
        projection = projections[facts["operation_refs"][row["op_id"]]]
        operation = project_operation(row, projection, label, facts, as_of)
        events = project_records(projection, operation, directory, as_of)
        operation.update(hour_totals(events))
        operation.update({"event_count": len(projection["legacy_facts"]), "record_count": len(events),
                          "production_report_count": len(projection["reports"])})
        for kind in ("machine", "operator"):
            refs = list(dict.fromkeys(event[kind + "_ref"] for event in events if event[kind + "_ref"] is not None))
            actual = actual_resource(directory, kind, refs[0] if len(refs) == 1 else None)
            operation.update({"actual_" + kind + "_ref": actual["ref"], "actual_" + kind + "_refs": refs,
                "actual_" + kind + "_label": " / ".join(actual_resource(directory, kind, ref)["label"] for ref in refs) or actual["label"]})
        if _selected(facts["scope"], operation, events):
            operations.append(operation)
            records.extend(events)
            labels[operation["operation_ref"]] = export_labels(label, operation, directory)
    return operations, records, labels


def validate_selected_refs(scope, facts):
    directory = resource_directory(facts)
    for kind, ref in (("batch", scope.batch_ref), (scope.resource_type, scope.resource_ref)):
        if ref and ref != "unassigned":
            identity = facts["reader"].plans.entities.get(ref)
            historical = kind in directory and ref in directory[kind]
            if identity is None or identity.kind != kind or (not identity.active and not historical):
                raise WorkbenchCommandRejected("entity_not_found", "筛选对象不存在或类型不符，未静默忽略条件。", 404)
