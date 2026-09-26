"""An unstarted claim can retry only with positive fresh ownership evidence."""

import json
import sqlite3

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF
from core.services.workbench.run.jobs import WorkbenchRunService
from core.services.workbench.run.worker import WorkbenchRunWorker
from core.services.workbench.run.worker_claim import RunClaimBusy, _is_sqlite_lock, claim_run
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_runtime_support import install
from tests.workbench.run_runtime_support import owned_case as _owned_case  # noqa: F401
from web.bootstrap import workbench_run_runtime as host


class ClaimCommitFault:
    def __init__(self, conn, events, *, fail_count=1, committed=False, rollback_failure=False):
        self.conn, self.events = conn, events
        self.fail_count, self.committed = fail_count, committed
        self.rollback_failure, self.failed = rollback_failure, False

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def commit(self):
        claiming = self.conn.execute("SELECT 1 FROM WorkbenchRunJobs WHERE state='running'").fetchone()
        if claiming and len(self.events) < self.fail_count:
            self.events.append("claim_commit")
            self.failed = True
            if self.committed:
                self.conn.commit()
            raise sqlite3.OperationalError("database is locked")
        self.conn.commit()

    def rollback(self):
        if self.failed and self.rollback_failure:
            raise sqlite3.OperationalError("rollback could not release database")
        return self.conn.rollback()


def fault_claim_connections(monkeypatch, events, **kwargs):
    actual = host.get_connection
    monkeypatch.setattr(host, "get_connection", lambda path: ClaimCommitFault(actual(path), events, **kwargs))


def record_forbidden_compute(monkeypatch):
    computed = []

    def forbidden(_worker, row):
        computed.append(row["run_ref"])
        raise AssertionError("this claim must never reach computation")

    monkeypatch.setattr(WorkbenchRunWorker, "_compute", forbidden)
    return computed


@pytest.mark.parametrize("message,expected", [
    ("database is locked", True), ("database table is locked", True),
    ("disk I/O error", False), ("database disk image is malformed", False),
    ("database lock unknown", False), ("database is locked: uncertain commit", False),
])
def test_python38_sqlite_error_text_classification_is_narrow(message, expected):
    assert _is_sqlite_lock(sqlite3.OperationalError(message)) is expected


@pytest.mark.parametrize("code,expected", [(5, True), (6, True), (261, True), (10, False)])
def test_available_sqlite_error_codes_override_text(code, expected):
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = code
    assert _is_sqlite_lock(exc) is expected


@pytest.mark.parametrize("failure", ["lost_ack", "rollback_failure", "exhausted"])
def test_uncertain_or_exhausted_claim_never_computes_and_retains_recovery(owned_case, monkeypatch, failure):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    events = []
    computed = record_forbidden_compute(monkeypatch)
    fault_claim_connections(monkeypatch, events, committed=failure == "lost_ack",
                            rollback_failure=failure == "rollback_failure", fail_count=3 if failure == "exhausted" else 1)
    runtime(ref)
    assert runtime.wait_idle(timeout=15)
    state = WorkbenchRunService(case.conn).get(ref)
    assert state["state"] == "interrupted" and state["candidates"] == []
    assert state["result_persisted"] is False and computed == []
    assert len(events) == (3 if failure == "exhausted" else 1)
    assert not runtime.ready
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 1


def test_active_transaction_after_fault_is_not_classified_retryable(owned_case):
    case = owned_case
    ref = case.accept()["run_ref"]
    events = []
    conn = ClaimCommitFault(case.conn, events)
    conn.rollback = lambda: None
    try:
        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            claim_run(conn, ref, lambda: "2026-09-26T12:00:00")
        assert case.conn.in_transaction and events == ["claim_commit"]
    finally:
        case.conn.rollback()
    assert WorkbenchRunService(case.conn).get(ref)["state"] == "queued"


@pytest.mark.parametrize("change", ["claimed", "candidate"])
def test_changed_evidence_after_fresh_read_is_rechecked_inside_claim(owned_case, monkeypatch, change):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    events, retry_calls = [], []
    computed = record_forbidden_compute(monkeypatch)
    actual_get, actual_execute = host.get_connection, WorkbenchRunWorker.execute
    fault_claim_connections(monkeypatch, events)

    def execute(worker, run_ref, **kwargs):
        if kwargs.get("retry_original") is not None:
            retry_calls.append(run_ref)
            conn = actual_get(str(case.path))
            try:
                with TransactionManager(conn).transaction(begin_immediate=True):
                    if change == "claimed":
                        WorkbenchRunRepository(conn).claim(run_ref, PROCESS_EXECUTOR_REF, "2026-09-26T12:00:00")
                    else:
                        conn.execute("""INSERT INTO WorkbenchRunCandidates VALUES (?,?,?,?,'completed',0,'{}')""",
                                     ("a" * 48, run_ref, "unexpected", 0))
            finally:
                conn.close()
        return actual_execute(worker, run_ref, **kwargs)

    monkeypatch.setattr(WorkbenchRunWorker, "execute", execute)
    runtime(ref)
    assert runtime.wait_idle(timeout=15)
    assert retry_calls == [ref] and computed == [] and events == ["claim_commit"]
    assert not runtime.ready
    row = WorkbenchRunRepository(case.conn).get(ref)
    assert row["state"] == ("interrupted" if change == "claimed" else "queued")
    assert row["stage"] == ("finished" if change == "claimed" else "awaiting_reconciliation")


def test_lock_loss_before_retry_prevents_another_worker_attempt(owned_case, monkeypatch):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    events = []
    computed = record_forbidden_compute(monkeypatch)
    actual_verify = runtime._verify
    fault_claim_connections(monkeypatch, events)

    def verify():
        if events:
            raise host.RunRuntimeOwnershipError("test runtime ownership lost")
        actual_verify()

    monkeypatch.setattr(runtime, "_verify", verify)
    runtime(ref)
    assert runtime.wait_idle(timeout=15)
    assert events == ["claim_commit"] and computed == [] and not runtime.ready
    assert WorkbenchRunService(case.conn).get(ref)["state"] == "queued"


def test_worker_marks_only_clean_claim_lock_failures(owned_case):
    case = owned_case
    ref = case.accept()["run_ref"]
    conn = ClaimCommitFault(case.conn, [])
    with pytest.raises(RunClaimBusy) as caught:
        WorkbenchRunWorker(conn).execute(ref)
    assert isinstance(caught.value.__cause__, sqlite3.OperationalError)
    assert not case.conn.in_transaction
    assert WorkbenchRunService(case.conn).get(ref)["started_at"] is None


@pytest.mark.parametrize("change", ["input_hash", "outcome", "warnings", "receipt_ref"])
def test_corrupt_or_replaced_admission_stops_claim_retry(owned_case, monkeypatch, change):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    events = []
    computed = record_forbidden_compute(monkeypatch)
    fault_claim_connections(monkeypatch, events)
    actual = WorkbenchCommandRepository.get

    def changed(repo, key):
        receipt = actual(repo, key)
        if events and receipt is not None:
            receipt = dict(receipt)
            if change == "input_hash":
                receipt["input_hash"] = "0" * 64
            elif change == "receipt_ref":
                receipt["receipt_ref"] = "0" * 32
            else:
                outcome = json.loads(receipt["outcome_json"])
                outcome["result" if change == "outcome" else "warnings"] = "partial" if change == "outcome" else {}
                receipt["outcome_json"] = json.dumps(outcome)
        return receipt

    monkeypatch.setattr(WorkbenchCommandRepository, "get", changed)
    runtime(ref)
    assert runtime.wait_idle(timeout=15)
    assert events == ["claim_commit"] and computed == [] and not runtime.ready
    assert WorkbenchRunService(case.conn).get(ref)["state"] == "interrupted"


@pytest.mark.parametrize("committed", [False, True])
def test_result_commit_busy_is_reconciled_without_recompute(owned_case, monkeypatch, committed):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    failures, computations = [], []
    actual_get, actual_compute = host.get_connection, WorkbenchRunWorker._compute

    class ResultFault:
        def __init__(self, conn):
            self.conn = conn

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def commit(self):
            result_exists = self.conn.execute("SELECT 1 FROM WorkbenchRunReceipts").fetchone()
            if result_exists and not failures:
                failures.append(ref)
                if committed:
                    self.conn.commit()
                raise sqlite3.OperationalError("database is locked")
            self.conn.commit()

    def compute(worker, row):
        computations.append(row["run_ref"])
        return actual_compute(worker, row)

    monkeypatch.setattr(host, "get_connection", lambda path: ResultFault(actual_get(path)))
    monkeypatch.setattr(WorkbenchRunWorker, "_compute", compute)
    runtime(ref)
    assert runtime.wait_idle(timeout=20)
    assert failures == computations == [ref]
    final = WorkbenchRunService(case.conn).get(ref)
    assert final["state"] == ("complete" if committed else "interrupted")
    assert final["result_persisted"] is committed
    assert len(final["candidates"]) == (4 if committed else 0)
    assert runtime.ready is committed
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 1
