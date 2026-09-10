"""Restart verification depends on durable result and positive executor evidence, not time."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF, new_run_ref
from core.services.workbench.run_worker import WorkbenchRunWorker
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.run_jobs_support import connection, service  # noqa: F401
from tests.workbench.run_jobs_support import job_case as _job_case


def test_restart_keeps_committed_results_and_never_recomputes(job_case):
    case = job_case
    ref = case.accept()["run_ref"]
    result = WorkbenchRunWorker(case.conn).execute(ref)
    changes = case.conn.total_changes
    with connection(case.path) as restarted:
        recovery = service(restarted).recover_unfinished_runs()
        assert recovery == {"recovered": [], "pending": [], "scheduling_busy": False}
        assert WorkbenchRunWorker(restarted).execute(ref) == result
    assert case.conn.total_changes == changes


@pytest.mark.parametrize("evidence", [None, True, False])
def test_foreign_executor_requires_positive_liveness_evidence(job_case, evidence):
    case = job_case
    ref = case.accept()["run_ref"]
    foreign = new_run_ref()
    assert foreign != PROCESS_EXECUTOR_REF
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        assert WorkbenchRunRepository(case.conn).claim(ref, foreign, "2000-01-01T00:00:00")
    with connection(case.path) as restarted:
        result = service(restarted).recover_unfinished_runs(executor_is_active=lambda owner: evidence)
        state = service(restarted).get(ref)
        if evidence is False:
            assert result["recovered"] == [ref] and state["state"] == "interrupted"
        else:
            assert result["pending"] == [ref] and state["state"] == "running"
            assert state["recovery_required"] is (evidence is None)
        assert state["candidates"] == [] and state["progress"] is None


def test_recovery_probe_errors_are_not_swallowed(job_case):
    case = job_case
    ref = case.accept()["run_ref"]
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        WorkbenchRunRepository(case.conn).claim(ref, new_run_ref(), "2000-01-01T00:00:00")

    def failed_probe(owner):
        raise OSError("host process inventory failed")

    with pytest.raises(OSError, match="inventory"):
        service(case.conn).recover_unfinished_runs(executor_is_active=failed_probe)
    assert service(case.conn).get(ref)["state"] == "running"


def test_unknown_recovery_never_allows_browser_retry_to_start_worker(job_case):
    case = job_case
    ref = case.accept()["run_ref"]
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        WorkbenchRunRepository(case.conn).claim(ref, new_run_ref(), "2000-01-01T00:00:00")
    assert service(case.conn).recover_unfinished_runs()["pending"] == [ref]
    for _ in range(5):
        result = WorkbenchRunWorker(case.conn).execute(ref)
        assert result["state"] == "running" and result["recovery_required"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 0


def test_receipt_with_missing_candidates_is_not_reported_success(job_case):
    case = job_case
    ref = case.accept()["run_ref"]
    WorkbenchRunWorker(case.conn).execute(ref)
    # Simulate a damaged restore while preserving the exact expected schema afterward.
    trigger = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_runcandidatetasks_no_delete'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_runcandidatetasks_no_delete")
    case.conn.execute("DELETE FROM WorkbenchRunCandidateTasks WHERE rowid=(SELECT min(rowid) FROM WorkbenchRunCandidateTasks)")
    case.conn.execute(trigger)
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).get(ref)
    assert error.value.code == "run_result_inconsistent"


def test_committed_candidate_receipt_restores_unfinished_state_without_reexecution(job_case):
    case = job_case
    ref = case.accept()["run_ref"]
    original = WorkbenchRunWorker(case.conn).execute(ref)
    trigger = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_run_state_transition'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_run_state_transition")
    case.conn.execute("UPDATE WorkbenchRunJobs SET state='running',stage='computing',finished_at=NULL WHERE run_ref=?", (ref,))
    case.conn.execute(trigger)
    case.conn.commit()
    result = service(case.conn).recover_unfinished_runs()
    assert result["recovered"] == [ref]
    assert service(case.conn).get(ref) == original
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 4


def test_queued_but_awaiting_reconciliation_cannot_be_claimed(job_case):
    case = job_case
    ref = case.accept()["run_ref"]
    repo = WorkbenchRunRepository(case.conn)
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        repo.awaiting_reconciliation(ref)
        assert repo.claim(ref, PROCESS_EXECUTOR_REF, "2026-09-10T12:00:00") is False
    result = WorkbenchRunWorker(case.conn).execute(ref)
    assert result["state"] == "queued" and result["recovery_required"]
    assert result["result_persisted"] is False and result["started_at"] is None
