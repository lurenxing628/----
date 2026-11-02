"""Read the admission's original official timeline for comparison drill-down."""

from core.models.workbench_run_candidate import reject
from core.services.workbench.facts.candidate_tasks import operation_labels, task_span
from core.services.workbench.facts.delivery_projection import delivery_summary
from core.services.workbench.facts.gantt_graph import candidate_gantt_graph, unavailable_graph
from core.shared.strict_json import clone_json

from .candidate_metrics import scoped_rows
from .decision_session import decision_read


def read_reference_workspace(conn, run_ref, *, bind_snapshot, selected_candidate_ref=None,
                             comparison_mode="admission_official", batch_ref=None, **query):
    if selected_candidate_ref is None or comparison_mode != "admission_official":
        reject("invalid_input", "受理时正式时间轴需要指定所选候选和正式基准模式。", 422)
    with decision_read(conn, run_ref, selected_candidate_ref=selected_candidate_ref, comparison_mode=comparison_mode,
                       **query) as source:
        if source.baseline["state"] != "available":
            reject("entity_not_found", "这次排产受理时没有正式计划，所选候选仍可查看。", 404)
        snapshot = bind_snapshot({"kind": "run-decision-reference", **source.scope, "batch_ref": batch_ref}, source.state())
        return _reference_workspace(source, batch_ref), snapshot


def _reference_workspace(source, batch_ref):
    full_view = source.resource_view == "full_candidate"
    all_tasks = source.official_details["tasks"] if full_view else source.before_tasks
    batch_refs = sorted(set(source.scope["batch_refs"]) | {row["batch_ref"] for row in all_tasks if row["batch_ref"] is not None}) if full_view else source.scope["batch_refs"]
    if batch_ref is not None and batch_ref not in batch_refs:
        reject("entity_not_found", "该批次不在这次排产的归档范围，请重新选择。", 404)
    arranged = {row["operation_ref"] for row in all_tasks}
    unplanned = []
    for ref in source.scope["operation_refs"]:
        if ref in arranged:
            continue
        item, _ = operation_labels(source.facts, ref)
        deferred = source.facts.operations[ref] in source.reference_deferred_ids
        item.update(row_ref=None, status="skipped" if deferred else "unscheduled",
                    reason={"code": "material_deferred" if deferred else "official_operation_unscheduled",
                            "message": "原正式来源将这道工序保留为待料暂缓。" if deferred else "受理时的正式安排尚未覆盖这道工序。"})
        unplanned.append(item)
    batches = {batch_ref} if batch_ref is not None else set(batch_refs) | ({None} if full_view else set())
    tasks = scoped_rows(
        all_tasks,
        batches,
        source.scope["range_start"],
        source.scope["range_end"],
        task_intervals=source.task_intervals("reference"),
    )
    tasks.sort(key=lambda row: (row["start"] is None, row["start"], row["operation_ref"], row["row_ref"]))
    unplanned = [row for row in unplanned if row["batch_ref"] in batches]
    unplanned.sort(key=lambda row: (row["sequence"] is None, row["sequence"], row["operation_ref"]))
    tasks = [dict(row, operation_effort=source.preparation.compact("reference", row["operation_ref"])) for row in tasks]
    unplanned = [dict(row, operation_effort=source.preparation.compact("reference", row["operation_ref"])) for row in unplanned]
    if full_view:
        from core.services.workbench.facts.decision_delivery import project_decision_delivery
        deliveries = project_decision_delivery(
            source.facts,
            all_tasks,
            batch_refs,
            deferred_ids=source.reference_deferred_ids,
            intervals=source.task_intervals("reference"),
        )
    else:
        deliveries = source.completion.delivery("reference")
    deliveries = [row for row in deliveries if batch_ref is None or row["batch_ref"] == batch_ref]
    summary = delivery_summary(deliveries)
    timed = [row for row in all_tasks if row["start"] is not None and row["end"] is not None]
    if len(arranged) != len(all_tasks) or len(timed) != len(all_tasks) or not all(row["interval_comparable"] for row in timed):
        graph = unavailable_graph("admission_official", "正式归档包含多段安排或时间缺项，时间条保留各段事实。")
    elif any(
        row["start"] != row["end"] and row[kind] is not None and row[kind]["ref"] is None
        for row in all_tasks
        for kind in ("machine", "operator")
    ):
        graph = unavailable_graph("admission_official", "正式归档缺少原采用或受理时的永久资源身份，时间条保留各段事实。")
    else:
        resource_keys = {
            row["row_ref"]: (
                None if row["machine"] is None else row["machine"]["ref"],
                None if row["operator"] is None else row["operator"]["ref"],
            )
            for row in all_tasks
        }
        graph = candidate_gantt_graph(
            all_tasks,
            source.facts,
            resource_keys,
            scope="admission_official",
            unavailable_reason="正式归档未保存完整的工艺前后关系，暂时无法显示关联线和关键链。",
            task_intervals=source.task_intervals("reference"),
        )
    capabilities = {"view": True, "adopt": False, "edit_draft": False, "report_actual": False, "export": False}
    gaps = [gap for row in tasks for gap in row["data_gaps"]]
    candidate = {"candidate_ref": source.selected_ref, "run_ref": source.run["run_ref"], "label": source.baseline["label"],
                 "kind": "admission_official", "status": "completed" if summary["incomplete_batch_count"] == 0 else "partial",
                 "task_count": len(all_tasks), "completeness": "complete" if summary["incomplete_batch_count"] == 0 else "partial",
                 "metrics": {}, "capabilities": capabilities, "data_gaps": gaps}
    return {"candidate": candidate, "reference": dict(source.baseline), "plan_ref": source.baseline["plan_ref"], "scope": source.scope,
            "workspace_scope": {"resource_view": source.resource_view, "batch_refs": batch_refs,
                                "operation_refs": sorted({row["operation_ref"] for row in all_tasks} | set(source.scope["operation_refs"]))},
            "generation": {"run_ref": source.run["run_ref"], "accepted_at": source.run["accepted_at"], "finished_at": source.run["finished_at"],
                           "input": clone_json(source.capture["input"]), "baseline": dict(source.baseline), "algorithm": None,
                           "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission", "data_gaps": gaps},
            "tasks": tasks, "task_count": len(tasks), "candidate_task_count": len(all_tasks), "tasks_complete": True,
            "task_span": task_span([row for row in tasks if row["start"] is not None and row["end"] is not None]), "candidate_span": task_span(timed),
            "gantt_graph": graph, "unplanned_operations": unplanned, "unplanned_operation_count": len(unplanned),
            "batch_ref": batch_ref, "time_scope": {"range_start": source.scope["range_start"], "range_end": source.scope["range_end"],
                "interval": "half_open_overlap", "time_basis": "factory_local", "unplanned_policy": "included_without_time_interval"},
            "capabilities": capabilities, "blocked_reasons": [], "data_gaps": gaps,
            "delivery_risks": {"items": deliveries, "summary": summary, "state": summary["state"], "batch_count": len(deliveries)}}
