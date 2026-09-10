"""Reconcile commits and executor evidence; no time-based retry or lease expiry."""

import json
from datetime import datetime

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF
from core.services.scheduler import schedule_service
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository


def recover_unfinished_runs(conn, *, executor_is_active=None, clock=None):
    """Host evidence returns True/False/None. Foreign-process absence is not assumed.

    The existing scheduler lock proves no local worker is active only while held.
    Missing or inconclusive foreign executor evidence keeps the run unresolved.
    """
    if conn.in_transaction:
        raise RuntimeError("Run recovery must own the outer transaction")
    repo = WorkbenchRunRepository(conn)
    repo.require_schema()
    lock = schedule_service._RUN_SCHEDULE_LOCK
    if not lock.acquire(blocking=False):
        return {"recovered": [], "pending": [], "scheduling_busy": True}
    try:
        with TransactionManager(conn).transaction(begin_immediate=True):
            recovered, pending = [], []
            now = (clock or datetime.now)().isoformat(timespec="seconds")
            for row in repo.unfinished():
                repo.require_admission(row)
                reconciled = _reconcile_result(conn, repo, row)
                if reconciled is True:
                    recovered.append(row["run_ref"])
                    continue
                if reconciled is False:
                    pending.append(row["run_ref"])
                    continue
                active = _executor_evidence(row, executor_is_active)
                if active is False and not conn.execute("SELECT 1 FROM WorkbenchRunCandidates WHERE run_ref=? LIMIT 1", (row["run_ref"],)).fetchone():
                    result = {"state": "interrupted", "result_persisted": False, "candidates": [],
                              "error": {"code": "run_interrupted", "message": "已核实没有候选结果及活动执行者；运行已中断，未自动重跑。"}}
                    repo.finish(row["run_ref"], "interrupted", result, now)
                    recovered.append(row["run_ref"])
                else:
                    if active is not True:
                        repo.awaiting_reconciliation(row["run_ref"])
                    pending.append(row["run_ref"])
            return {"recovered": recovered, "pending": pending, "scheduling_busy": False}
    finally:
        lock.release()


def _executor_evidence(row, probe):
    if row["executor_ref"] is None or row["executor_ref"] == PROCESS_EXECUTOR_REF:
        return False
    if probe is None:
        return None
    active = probe(row["executor_ref"])
    if active is not None and type(active) is not bool:
        raise TypeError("Executor evidence must be True, False or None")
    return active


def _reconcile_result(conn, repo, row):
    receipt = repo.receipt(row["run_ref"])
    if receipt is None:
        return None
    result = json.loads(receipt["result_json"])
    if result["state"] != receipt["state"] or not WorkbenchRunResultRepository(conn).consistent(row["run_ref"], result):
        repo.awaiting_reconciliation(row["run_ref"])
        return False
    conn.execute("UPDATE WorkbenchRunJobs SET state=?,stage='finished',finished_at=?,error_json=? WHERE run_ref=?",
                 (receipt["state"], receipt["recorded_at"], json.dumps(result.get("error")), row["run_ref"]))
    return True
