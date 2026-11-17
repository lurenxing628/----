"""Settle unfinished runs from executor evidence; no time-based retry or lease expiry.

A run's candidates, receipt and terminal state commit in one completion transaction (``worker.py``
with ``run/terminal.py``), so an unfinished run never has saved results to settle from.
"""

from datetime import datetime
from typing import Callable

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF
from core.models.workbench_run_receipt import FailedReceipt
from core.services.scheduler.schedule_lock import RUN_SCHEDULE_LOCK
from core.services.workbench.facts.decision_read_models import decode_model
from core.services.workbench.facts.run_policy import require_admission
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .terminal import record_terminal_without_results


def recover_unfinished_runs(conn, *, executor_is_active=None, clock: Callable[[], datetime], run_ref=None):
    """Host evidence returns True/False/None. Foreign-process absence is not assumed.

    The existing scheduler lock proves no local worker is active only while held.
    Missing or inconclusive foreign executor evidence keeps the run unresolved.
    """
    if conn.in_transaction:
        raise RuntimeError("Run recovery must own the outer transaction")
    repo = WorkbenchRunRepository(conn)
    lock = RUN_SCHEDULE_LOCK
    if not lock.acquire(blocking=False):
        return {"recovered": [], "pending": [], "scheduling_busy": True}
    try:
        with TransactionManager(conn).transaction(begin_immediate=True):
            recovered, pending = [], []
            now = clock().isoformat(timespec="microseconds")
            for row in repo.unfinished(run_ref):
                require_admission(repo, row)
                active = _executor_evidence(row, executor_is_active)
                if active is False:
                    result = FailedReceipt(
                        "interrupted", {"code": "run_interrupted", "message": "本次排产已中断，未生成候选方案。请重新排产。"}, None
                    )
                    admission_decision = decode_model(
                        repo.admission_read_model(row["run_ref"], fields=("decision",)), ("decision",),
                    )["decision"]
                    record_terminal_without_results(conn, row, admission_decision, result, now)
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
