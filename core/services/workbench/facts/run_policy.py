"""Run-journal rulings over WorkbenchRunRepository facts: schema, admission lineage and the public projection."""

import json

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_job import TERMINAL_STATES
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository


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
            "accepted_at": row["accepted_at"], "started_at": row["started_at"], "finished_at": row["finished_at"],
            "receipt_ref": receipt["receipt_ref"] if receipt else None, "error": result.get("error") if result else None,
            "recovery_required": row["stage"] == "awaiting_reconciliation"}
