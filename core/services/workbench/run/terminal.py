"""A run's end inside the caller's completion transaction: receipt, terminal state and history entry.

The worker and restart recovery already own the write transaction; everything written here rolls
back with it, so a failed history entry leaves neither a receipt nor a terminal state behind.
"""

from typing import Any, Dict, Mapping

from core.models.workbench_run_receipt import FailedReceipt, RunReceipt
from core.services.workbench.facts.decision_read_model import build_failure_read_models
from core.services.workbench.history_entries.writer import record_run_finished
from data.repositories.workbench_run_repo import WorkbenchRunRepository, encode_result


def record_run_terminal(conn, run_ref: str, encoded: Mapping[str, str], body: RunReceipt,
                        now: str) -> Dict[str, Any]:
    """Store the encoded receipt and terminal state, then catalogue ``body``, the same receipt before encoding."""
    written = WorkbenchRunRepository(conn).finish_prepared(run_ref, encoded, now)
    record_run_finished(conn, run_ref=run_ref, state=written["state"], finished_at=now,
                        receipt_ref=written["receipt_ref"], result=body)
    return written


def record_terminal_without_results(conn, row: Mapping[str, Any], admission: Mapping[str, Any],
                                    result: FailedReceipt, now: str) -> None:
    """A failed or interrupted run: its admission-block read models, then the receipt, terminal state and entry."""
    models = build_failure_read_models(admission, result)
    WorkbenchRunRepository(conn).insert_decision_read_models(row["run_ref"], models["run_model"], models["candidate_models"])
    record_run_terminal(conn, row["run_ref"], encode_result(result.document()), result, now)
