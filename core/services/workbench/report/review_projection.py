"""One ledger projection, one plan-finish cohort, no second completion reducer."""

from __future__ import annotations

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.execution.actual_gantt_scope import matches_execution_resource
from core.services.workbench.facts.execution_values import execution_deviation, hour_totals, local_time

from .review_export_labels import export_labels
from .review_legacy import legacy_review
from .review_records import actual_resource, project_records, resource_directory

STATUS_LABELS = {"complete": "已完工", "partial": "部分完成", "started": "已开工", "paused": "已暂停",
                 "exception": "异常", "unreported": "待报工"}


def resource(facts, kind, key):
    return facts["resources"][kind].get(str(key), {"ref": None, "label": "未填写"})


def project_operation(row, projection, label, facts, as_of):
    planned_start, planned_end = local_time(row.get("start_time")), local_time(row.get("end_time"))
    confirmed_finish = projection["confirmed_finish"]
    deviation = execution_deviation(planned_end, projection, as_of)
    complete = deviation["complete"]
    batch = resource(facts, "batch", row["batch_id"])
    machine, operator = resource(facts, "machine", row.get("machine_id")), resource(facts, "operator", row.get("operator_id"))
    invalid_time = any(gap["code"] == "invalid_legacy_sequence" for gap in projection["data_gaps"])
    status = "invalid" if invalid_time and not complete else projection["execution_state"]
    return {"operation_ref": projection["operation_ref"], "task_ref": facts["task_refs"][row["schedule_id"]],
            "batch_ref": batch["ref"], "batch_label": batch["label"], "operation_label": label["operation_label"],
            "operation_source": row.get("source"),
            "planned_start": planned_start, "planned_end": planned_end, "actual_start": projection["first_actual_start"],
            "confirmed_finish": confirmed_finish, "completion_basis": projection["completion_basis"],
            "execution_state": status, "ledger_execution_state": projection["execution_state"],
            "execution_label": "记录的时间或先后顺序不对，要复核" if status == "invalid" else STATUS_LABELS[status],
            **{key: projection[key] for key in ("target_quantity", "target_basis", "known_completed_quantity", "remaining_quantity",
                "quantity_complete", "unknown_record_count", "records_complete", "data_quality")},
            "machine_ref": machine["ref"], "machine_label": machine["label"],
            "operator_ref": operator["ref"], "operator_label": operator["label"],
            **{key: deviation[key] for key in ("due", "complete", "unclosed", "late_open", "finish_late",
                                               "finish_deviation_minutes", "elapsed_since_planned_minutes")},
            "data_gaps": [gap["message"] for gap in projection["data_gaps"]], "execution_data_gaps": projection["data_gaps"],
            **legacy_review(projection)}


def _resource_selected(scope, operation, projection):
    # 外协本来就不占本厂设备和人员：既不算「未填写」，旧记录里误填的设备人员也不算，与资源工时汇总同一口径。
    if operation["operation_source"] == "external":
        return False
    ref = None if scope.resource_ref == "unassigned" else scope.resource_ref
    return matches_execution_resource(operation, projection, scope.resource_type, ref)


def _selected(scope, operation, projection):
    end = operation["planned_end"]
    if scope.plan_finish_date_from and (end is None or not scope.plan_finish_date_from <= end[:10] <= scope.plan_finish_date_to):
        return False
    if scope.batch_ref and operation["batch_ref"] != scope.batch_ref:
        return False
    if scope.query.strip().casefold() not in (operation["batch_label"] + " " + operation["operation_label"]).casefold():
        return False
    if scope.focus == "unreported":
        selected = operation["execution_state"] == "unreported"
    elif scope.focus == "data_gaps":
        selected = operation["data_quality"] != "complete"
    else:
        selected = scope.focus == "all" or bool(operation[scope.focus])
    return selected and (not scope.resource_ref or _resource_selected(scope, operation, projection))


def _project_entry(row, label, projection, facts, directory, as_of):
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
    return operation, events


def project_cohort(facts, as_of):
    projections = {row["operation_ref"]: row for row in facts["ledger"]["projections"]}
    directory = resource_directory(facts)
    operations, records, labels = [], [], {}
    for row, label in zip(facts["rows"], facts["labels"]):
        projection = projections[facts["operation_refs"][row["op_id"]]]
        operation, events = _project_entry(row, label, projection, facts, directory, as_of)
        if _selected(facts["scope"], operation, projection):
            operations.append(operation)
            records.extend(events)
            labels[operation["operation_ref"]] = export_labels(label, operation, directory)
    return operations, records, labels


def project_detail(facts, as_of, operation_ref):
    projection = next((row for row in facts["ledger"]["projections"] if row["operation_ref"] == operation_ref), None)
    if projection is not None:
        directory = resource_directory(facts)
        for row, label in zip(facts["rows"], facts["labels"]):
            if facts["operation_refs"][row["op_id"]] != operation_ref:
                continue
            operation, records = _project_entry(row, label, projection, facts, directory, as_of)
            if _selected(facts["scope"], operation, projection):
                return {"operation": operation, "records": records}
            break
    raise WorkbenchCommandRejected("entity_not_found", "这道工序不在当前筛选结果里，详情没有打开。请调整筛选条件后重新点这一行。", 404)


def validate_selected_refs(scope, facts):
    for kind, ref in (("batch", scope.batch_ref), (scope.resource_type, scope.resource_ref)):
        if ref and ref != "unassigned":
            identity = facts["reader"].plans.entities.get(ref)
            historical = kind in ("machine", "operator") and ref in facts["choices"][kind]
            if identity is None or identity.kind != kind or (not identity.active and not historical):
                raise WorkbenchCommandRejected("entity_not_found", "筛选记录已失效或类型不符，请重新选择。", 404)
