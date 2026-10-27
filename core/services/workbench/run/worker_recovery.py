"""Reconcile commits and executor evidence; no time-based retry or lease expiry."""

from datetime import datetime

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import canonical_json
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF
from core.services.scheduler.schedule_lock import RUN_SCHEDULE_LOCK
from core.services.workbench.facts.candidate_values import stored_json
from core.services.workbench.facts.decision_read_model import build_failure_read_models
from core.services.workbench.facts.decision_read_models import decode_model
from core.services.workbench.facts.run_policy import require_admission, require_run_schema
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository


def recover_unfinished_runs(conn, *, executor_is_active=None, clock=None, run_ref=None):
    """Host evidence returns True/False/None. Foreign-process absence is not assumed.

    The existing scheduler lock proves no local worker is active only while held.
    Missing or inconclusive foreign executor evidence keeps the run unresolved.
    """
    if conn.in_transaction:
        raise RuntimeError("Run recovery must own the outer transaction")
    repo = WorkbenchRunRepository(conn)
    require_run_schema(repo)
    lock = RUN_SCHEDULE_LOCK
    if not lock.acquire(blocking=False):
        return {"recovered": [], "pending": [], "scheduling_busy": True}
    try:
        with TransactionManager(conn).transaction(begin_immediate=True):
            recovered, pending = [], []
            now = (clock or datetime.now)().isoformat(timespec="microseconds")
            for row in repo.unfinished(run_ref):
                require_admission(repo, row)
                reconciled = _reconcile_result(conn, repo, row)
                if reconciled is True:
                    recovered.append(row["run_ref"])
                    continue
                if reconciled is False:
                    pending.append(row["run_ref"])
                    continue
                active = _executor_evidence(row, executor_is_active)
                if active is False and not repo.has_candidates(row["run_ref"]):
                    result = {"state": "interrupted", "result_persisted": False, "candidates": [],
                              "error": {"code": "run_interrupted", "message": "本次排产已中断，未生成候选方案。请重新排产。"}}
                    admission_decision = decode_model(
                        repo.admission_read_model(row["run_ref"], fields=("decision",)), ("decision",),
                    )["decision"]
                    models = build_failure_read_models(row, admission_decision, result)
                    repo.insert_decision_read_models(row["run_ref"], models["run_model"], models["candidate_models"])
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
    result = stored_json(receipt["result_json"])
    if result["state"] != receipt["state"] or not WorkbenchRunResultRepository(conn).consistent(row["run_ref"], result):
        repo.awaiting_reconciliation(row["run_ref"])
        return False
    repo.record_reconciled_finish(row["run_ref"], receipt["state"], receipt["recorded_at"], canonical_json(result.get("error")))
    return True
