"""One ledger projection, one plan-finish cohort, no second completion reducer."""

from __future__ import annotations

from core.models.enums import read_source_type
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.execution.processing_hours import hour_totals
from core.services.report.plan_labels import planned_review_labels
from core.services.workbench.execution.actual_gantt_scope import matches_execution_resource
from core.services.workbench.facts.execution_values import execution_deviation, local_dt, local_time

from .review_export_labels import export_labels
from .review_records import actual_resource, project_records, resource_directory

STATUS_LABELS = {"complete": "已完工", "partial": "部分完成", "started": "已开工", "unreported": "待报工"}


def resource(facts, kind, key):
    return facts["resources"][kind].get(str(key), {"ref": None, "label": "未填写"})


def project_operation(row, projection, label, facts, as_of):
    planned_start = local_time(row["start_time"])
    planned_end_dt = local_dt(row["end_time"])
    planned_end = planned_end_dt.isoformat() if planned_end_dt is not None else None
    confirmed_finish = projection["confirmed_finish"]
    deviation = execution_deviation(planned_end_dt, projection, as_of)
    batch = resource(facts, "batch", row["batch_id"])
    machine, operator = resource(facts, "machine", row["machine_id"]), resource(facts, "operator", row["operator_id"])
    status = projection["execution_state"]
    return {"operation_ref": projection["operation_ref"], "task_ref": facts["task_refs"][row["schedule_id"]],
            "batch_ref": batch["ref"], "batch_label": batch["label"], "operation_label": label["operation_label"],
            "operation_source": read_source_type(row["source"]),
            "planned_start": planned_start, "planned_end": planned_end, "actual_start": projection["first_actual_start"],
            "confirmed_finish": confirmed_finish, "completion_basis": projection["completion_basis"],
            "execution_state": status, "ledger_execution_state": projection["execution_state"],
            "execution_label": STATUS_LABELS[status],
            **{key: projection[key] for key in ("target_quantity", "target_basis", "known_completed_quantity", "remaining_quantity",
                "quantity_complete", "unknown_record_count", "records_complete", "data_quality")},
            "machine_ref": machine["ref"], "machine_label": machine["label"],
            "operator_ref": operator["ref"], "operator_label": operator["label"],
            **{key: deviation[key] for key in ("due", "complete", "unclosed", "late_open", "finish_late",
                                               "finish_deviation_minutes", "elapsed_since_planned_minutes")},
            "data_gaps": [gap["message"] for gap in projection["data_gaps"]], "execution_data_gaps": projection["data_gaps"]}


def _resource_selected(scope, operation, projection):
    # 外协本来就不占本厂设备和人员：既不算「未填写」，旧记录里误填的设备人员也不算，与资源工时汇总同一口径。
    if operation["operation_source"] == "external":
        return False
    ref = None if scope.resource_ref == "unassigned" else scope.resource_ref
    return matches_execution_resource(operation, projection, scope.resource_type, ref)


def _selected(scope, operation, projection, *, needle):
    if needle not in (operation["batch_label"] + " " + operation["operation_label"]).casefold():
        return False
    if scope.focus == "unreported":
        selected = operation["execution_state"] == "unreported"
    elif scope.focus == "data_gaps":
        selected = operation["data_quality"] != "complete"
    else:
        selected = scope.focus == "all" or bool(operation[scope.focus])
    return selected and (not scope.resource_ref or _resource_selected(scope, operation, projection))


def _complete_entry(operation, projection, directory):
    events = project_records(projection, operation, directory)
    operation.update(hour_totals(events))
    operation["production_report_count"] = len(projection["reports"])
    for kind in ("machine", "operator"):
        refs = list(dict.fromkeys(event[kind + "_ref"] for event in events if event[kind + "_ref"] is not None))
        resolved = [actual_resource(directory, kind, ref) for ref in refs]
        actual = resolved[0] if len(resolved) == 1 else actual_resource(directory, kind, None)
        operation.update({"actual_" + kind + "_ref": actual["ref"], "actual_" + kind + "_refs": refs,
            "actual_" + kind + "_label": " / ".join(item["label"] for item in resolved) or actual["label"]})
    return operation, events


def project_cohort(facts, as_of):
    needle = facts["scope"].query.strip().casefold()
    projections = {row["operation_ref"]: row for row in facts["ledger"]["projections"]}
    directory = resource_directory(facts)
    clock = local_dt(as_of)
    operations, records, labels = [], [], {}
    for row in facts["rows"]:
        # 工序名参与关键字筛选，所以每行都算标签；只有选中的行留给导出。
        label = planned_review_labels(row)
        projection = projections[facts["operation_refs"][row["op_id"]]]
        operation = project_operation(row, projection, label, facts, clock)
        if _selected(facts["scope"], operation, projection, needle=needle):
            operation, events = _complete_entry(operation, projection, directory)
            operations.append(operation)
            records.extend(events)
            labels[operation["operation_ref"]] = label
    return operations, records, labels


def project_export_rows(rows, labels):
    return [export_labels(labels[row["operation_ref"]], row) for row in rows]


def project_detail(facts, as_of, operation_ref):
    needle = facts["scope"].query.strip().casefold()
    row = next((row for row in facts["rows"] if facts["operation_refs"][row["op_id"]] == operation_ref), None)
    if row is not None:
        # 台账按计划行的工序取齐，计划行在就必有它的投影。
        projection = next(item for item in facts["ledger"]["projections"] if item["operation_ref"] == operation_ref)
        operation = project_operation(row, projection, planned_review_labels(row), facts, local_dt(as_of))
        if _selected(facts["scope"], operation, projection, needle=needle):
            directory = resource_directory(facts)
            operation, records = _complete_entry(operation, projection, directory)
            return {"operation": operation, "records": records}
    raise WorkbenchCommandRejected("entity_not_found", "这道工序不在当前筛选结果里，详情没有打开。请调整筛选条件后重新点这一行。", 404)
