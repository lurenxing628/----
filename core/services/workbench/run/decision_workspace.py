"""Read the admission's original official timeline for comparison drill-down."""

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_run_candidate import reject
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import operation_labels, task_span
from core.services.workbench.facts.delivery_projection import delivery_summary
from core.services.workbench.facts.gantt_graph import candidate_gantt_graph, unavailable_graph

from .candidate_metrics import scoped_rows
from .decision_source import DecisionSource


def read_reference_workspace(conn, run_ref, *, selected_candidate_ref=None, comparison_mode="admission_official",
                             reference_candidate_ref=None, range_start=None, range_end=None, resource_view="selected_batches", batch_ref=None):
    if selected_candidate_ref is None or comparison_mode != "admission_official":
        reject("invalid_input", "受理时正式时间轴需要指定所选候选和正式基准模式。", 422)
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        source = DecisionSource(store, run_ref, selected_candidate_ref=selected_candidate_ref, comparison_mode=comparison_mode,
                                reference_candidate_ref=reference_candidate_ref, range_start=range_start, range_end=range_end, resource_view=resource_view)
        if source.baseline["state"] != "available":
            reject("entity_not_found", "这次排产受理时没有正式计划，所选候选仍可查看。", 404)
        data = _reference_workspace(source, batch_ref)
        return data, source.state()


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
    tasks = scoped_rows(all_tasks, batches, source.scope["range_start"], source.scope["range_end"])
    tasks.sort(key=lambda row: (row["start"] is None, row["start"] or "", row["operation_ref"], row["row_ref"]))
    unplanned = [row for row in unplanned if row["batch_ref"] in batches]
    unplanned.sort(key=lambda row: (row["sequence"] is None, row["sequence"] or 0, row["operation_ref"]))
    tasks = [dict(row, operation_effort=source.preparation.compact("reference", row["operation_ref"])) for row in tasks]
    unplanned = [dict(row, operation_effort=source.preparation.compact("reference", row["operation_ref"])) for row in unplanned]
    if full_view:
        from core.services.workbench.facts.decision_delivery import project_decision_delivery
        deliveries = project_decision_delivery(source.facts, all_tasks, batch_refs, deferred_ids=source.reference_deferred_ids)
    else:
        deliveries = source.completion.delivery("reference")
    deliveries = [row for row in deliveries if batch_ref is None or row["batch_ref"] == batch_ref]
    summary = delivery_summary(deliveries)
    timed = [row for row in all_tasks if row["start"] is not None and row["end"] is not None]
    if len(arranged) == len(all_tasks) and len(timed) == len(all_tasks) and all(row.get("interval_comparable", True) for row in timed):
        raw = [{"operation_ref": row["operation_ref"], "payload": {
            "machine_id": (row["machine"] or {}).get("ref"), "operator_id": (row["operator"] or {}).get("ref")}} for row in all_tasks]
        graph = candidate_gantt_graph(all_tasks, source.facts, raw)
        graph["scope"] = "admission_official"
    else:
        graph = unavailable_graph("admission_official", "正式归档包含多段安排或时间缺项，时间条保留各段事实。")
    capabilities = {"view": True, "adopt": False, "edit_draft": False, "report_actual": False, "export": False}
    gaps = [gap for row in tasks for gap in row["data_gaps"]]
    candidate = {"candidate_ref": source.selected_ref, "run_ref": source.run["run_ref"], "label": source.baseline["label"],
                 "kind": "admission_official", "status": "completed" if summary["incomplete_batch_count"] == 0 else "partial",
                 "task_count": len(all_tasks), "completeness": "complete" if summary["incomplete_batch_count"] == 0 else "partial",
                 "metrics": {}, "capabilities": capabilities, "data_gaps": gaps}
    return {"candidate": candidate, "reference": source.baseline, "plan_ref": source.baseline["plan_ref"], "scope": source.scope,
            "workspace_scope": {"resource_view": source.resource_view, "batch_refs": batch_refs,
                                "operation_refs": sorted({row["operation_ref"] for row in all_tasks} | set(source.scope["operation_refs"]))},
            "generation": {"run_ref": source.run["run_ref"], "accepted_at": source.run["accepted_at"], "finished_at": source.run["finished_at"],
                           "input": source.capture["input"], "baseline": source.baseline, "algorithm": None,
                           "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission", "data_gaps": gaps},
            "tasks": tasks, "task_count": len(tasks), "candidate_task_count": len(all_tasks), "tasks_complete": True,
            "task_span": task_span([row for row in tasks if row["start"] is not None and row["end"] is not None]), "candidate_span": task_span(timed),
            "gantt_graph": graph, "unplanned_operations": unplanned, "unplanned_operation_count": len(unplanned),
            "batch_ref": batch_ref, "time_scope": {"range_start": source.scope["range_start"], "range_end": source.scope["range_end"],
                "interval": "half_open_overlap", "time_basis": "factory_local", "unplanned_policy": "included_without_time_interval"},
            "capabilities": capabilities, "blocked_reasons": [], "data_gaps": gaps,
            "delivery_risks": {"items": deliveries, "summary": summary, "state": summary["state"], "batch_count": len(deliveries)}}
