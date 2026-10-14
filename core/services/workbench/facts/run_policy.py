"""Run-journal rulings over WorkbenchRunRepository facts: schema, admission lineage and the public projection."""

import json

from core.models.objective import objective_choice_labels
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_job import TERMINAL_STATES
from core.services.workbench.facts.run_history_projection import _failure, scope_summary
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository

from .candidate_facts import _entity_refs, _index, _table
from .candidate_values import gap, stored_json, text


def _admitted_scope(row):
    """Selected workload and labels come from the immutable admission archive."""
    summary = scope_summary(row["normalized_input_json"])
    settings = json.loads(row["normalized_input_json"])
    archive = stored_json(row["facts_json"])
    refs = _entity_refs(archive)
    batches = _index(_table(archive, "Batches"), "batch_id")
    parts = _index(_table(archive, "Parts"), "part_no")
    batch_ids = {ref: key for (kind, key), ref in refs.items() if kind == "batch"}
    gaps = summary["data_gaps"]
    selected = []
    for ref in settings.get("batch_refs", []) if summary["batch_count"] is not None else []:
        batch = batches.get(batch_ids.get(ref), {})
        prefix = "batches." + ref + "."
        batch_id = text(batch.get("batch_id"), prefix + "batch_id", gaps)
        part_no = text(batch.get("part_no"), prefix + "part_no", gaps)
        part = parts.get(part_no, {})
        selected.append({"batch_ref": ref, "batch_id": batch_id, "part_no": part_no,
                         "part_label": text(part.get("part_name"), prefix + "part_label", gaps)})
    operations = _table(archive, "BatchOperations")
    complete_scope = summary["batch_count"] is not None and all(item["batch_id"] is not None for item in selected)
    operation_count = None
    if complete_scope and operations is not None:
        selected_ids = {item["batch_id"] for item in selected}
        operation_count = sum(item.get("batch_id") in selected_ids for item in operations)
    else:
        gaps.append(gap("operation_count"))
    config = _index(_table(archive, "ScheduleConfig"), "config_key")
    saved_objective = config.get("objective", {}).get("config_value")
    objective = text(saved_objective, "objective", gaps)
    labels = objective_choice_labels()
    if objective is not None and objective not in labels:
        gaps.append(gap("objective", "invalid_stored_value"))
    return {**summary, "operation_count": operation_count, "batches": selected,
            "objective": objective, "objective_label": labels.get(objective) if objective is not None else None}


def require_run_schema(repo):
    if repo.schema_issues():
        raise WorkbenchCommandRejected("run_schema_unavailable", "排产记录结构不完整，请联系维护人员。", 503)


def require_admission(repo, row):
    """The run row must be the one its scheduling.run command receipt admitted."""
    receipt = repo.admission_receipt(row["request_key"])
    if (receipt is None or receipt[0] != "scheduling.run" or receipt[1] != row["input_ref"]
            or json.loads(receipt[2])["data"] != {"run_ref": row["run_ref"]}):
        raise WorkbenchCommandRejected("run_result_inconsistent", "这次排产没有一致的接收结果记录，请让维护人员核对排产记录。", 500)


def public_run(conn, row):
    """The public run payload; refuses a row whose receipt, terminal state or candidate detail disagree."""
    repo = WorkbenchRunRepository(conn)
    require_admission(repo, row)
    receipt = repo.receipt(row["run_ref"])
    result = json.loads(receipt["result_json"]) if receipt else None
    if ((row["state"] in TERMINAL_STATES) != bool(receipt)
            or (receipt and (not isinstance(result, dict) or receipt["state"] != row["state"]
                             or result["state"] != receipt["state"]))):
        raise WorkbenchCommandRejected("run_result_inconsistent", "这次排产的最终状态和保存的结果不一致，请让维护人员核对排产记录。", 500)
    if receipt and not WorkbenchRunResultRepository(conn).consistent(row["run_ref"], result):
        raise WorkbenchCommandRejected("run_result_inconsistent", "候选方案明细和保存的结果不一致，请让维护人员核对排产记录。", 500)
    return {"run_ref": row["run_ref"], "job_ref": row["run_ref"], "state": row["state"], "stage": row["stage"],
            "progress": None, "plans": [], "plan_catalog_connected": False,
            "candidates": result["candidates"] if result else [], "result_persisted": bool(result and result["result_persisted"]),
            "scope_summary": _admitted_scope(row),
            "accepted_at": row["accepted_at"], "started_at": row["started_at"], "finished_at": row["finished_at"],
            "receipt_ref": receipt["receipt_ref"] if receipt else None, "error": _failure(row, result),
            "recovery_required": row["stage"] == "awaiting_reconciliation"}
