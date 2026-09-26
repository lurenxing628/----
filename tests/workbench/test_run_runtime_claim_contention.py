"""Real DELETE-journal lock failures retry only a proven unstarted claim."""

import sqlite3
import threading
from contextlib import closing
from types import SimpleNamespace

import pytest

from core.infrastructure.transaction import in_transaction_context
from core.services.workbench.run.jobs import WorkbenchRunService
from core.services.workbench.run.worker import WorkbenchRunWorker
from core.services.workbench.run.worker_claim import RunClaimBusy
from tests.workbench.run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.run_runtime_support import install
from tests.workbench.run_runtime_support import owned_case as _owned_case  # noqa: F401
from web.bootstrap import workbench_run_runtime as runtime_module


def _observe_connections(monkeypatch):
    actual = runtime_module.get_connection
    observed = []

    def connect(path):
        conn = actual(path)
        # Test-only timeout: the SQLite lock/rollback itself remains real.
        conn.execute("PRAGMA busy_timeout=40")
        statements = []
        conn.set_trace_callback(statements.append)
        observed.append((conn, statements))
        return conn

    monkeypatch.setattr(runtime_module, "get_connection", connect)
    return observed


def _observe_worker(monkeypatch):
    state = SimpleNamespace(attempts=[], computations=[], busy=[],
                            failed=threading.Event(), release=threading.Event())
    actual_execute, actual_compute = WorkbenchRunWorker.execute, WorkbenchRunWorker._compute

    def execute(worker, ref, **kwargs):
        state.attempts.append((worker.conn, kwargs))
        try:
            return actual_execute(worker, ref, **kwargs)
        except RunClaimBusy as exc:
            state.busy.append((exc, worker.conn.in_transaction, in_transaction_context(worker.conn)))
            state.failed.set()
            assert state.release.wait(10), "test did not release the database lock"
            raise

    def compute(worker, row):
        state.computations.append(row["run_ref"])
        return actual_compute(worker, row)

    monkeypatch.setattr(WorkbenchRunWorker, "execute", execute)
    monkeypatch.setattr(WorkbenchRunWorker, "_compute", compute)
    return state


def _hold_lock(holder, mode):
    assert holder.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    holder.execute("BEGIN" if mode == "read" else "BEGIN IMMEDIATE")
    # BEGIN alone does not acquire a shared read lock. Fetch the actual table.
    holder.execute("SELECT * FROM WorkbenchRunJobs").fetchall()


@pytest.mark.parametrize("mode", ["read", "write"])
def test_real_delete_claim_lock_rolls_back_then_new_connection_computes_once(owned_case, monkeypatch, mode):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    connections = _observe_connections(monkeypatch)
    watch = _observe_worker(monkeypatch)
    with closing(sqlite3.connect(str(case.path))) as holder:
        _hold_lock(holder, mode)
        try:
            runtime(ref)
            assert watch.failed.wait(10), runtime.status
            error, active_transaction, active_context = watch.busy[0]
            assert isinstance(error.__cause__, sqlite3.OperationalError)
            assert str(error.__cause__) == "database is locked"
            assert not active_transaction and not active_context
            assert watch.computations == []
            original = WorkbenchRunService(case.conn).get(ref)
            assert (original["state"], original["stage"]) == ("queued", "queued")
            assert original["started_at"] is None and original["candidates"] == []
        finally:
            holder.rollback()
            watch.release.set()
        assert runtime.wait_idle(timeout=25), runtime.status

    assert runtime.ready, runtime.status
    assert len(watch.attempts) == 2 and len(watch.busy) == 1
    first, second = watch.attempts
    assert first[0] is not second[0] and first[1] == {}
    assert second[1]["retry_original"]["job"]["run_ref"] == ref
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        first[0].execute("SELECT 1")
    assert watch.computations == [ref]
    final = WorkbenchRunService(case.conn).get(ref)
    assert final["state"] == "complete" and final["result_persisted"]
    assert len(final["candidates"]) == 4
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 1
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 4
    assert case.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert case.conn.execute("PRAGMA foreign_key_check").fetchall() == []

    statements = next(trace for conn, trace in connections if conn is first[0])
    claim_begin = statements.index("BEGIN IMMEDIATE")
    updates = [i for i, sql in enumerate(statements) if sql.startswith("UPDATE WorkbenchRunJobs SET state='running'")]
    if mode == "read":
        assert len(updates) == 1 and claim_begin < updates[0]
        claim_commit = statements.index("COMMIT", updates[0])
        assert claim_commit < statements.index("ROLLBACK", claim_commit)
    else:
        assert updates == []  # The other writer prevented BEGIN, before any claim UPDATE.


def test_shutdown_during_claim_backoff_leaves_original_queued(owned_case, monkeypatch):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    _observe_connections(monkeypatch)
    watch = _observe_worker(monkeypatch)
    entered, release_wait = threading.Event(), threading.Event()
    actual_wait = runtime._stop.wait

    def wait(timeout=None):
        entered.set()
        assert release_wait.wait(10), "test did not permit shutdown to finish"
        return actual_wait(timeout)

    monkeypatch.setattr(runtime._stop, "wait", wait)
    with closing(sqlite3.connect(str(case.path))) as holder:
        _hold_lock(holder, "read")
        try:
            runtime(ref)
            assert watch.failed.wait(10), runtime.status
            holder.rollback()
            watch.release.set()
            assert entered.wait(10), "claim did not enter its bounded backoff"
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                watch.attempts[0][0].execute("SELECT 1")
            assert runtime.shutdown(wait=False) is False
        finally:
            holder.rollback()
            watch.release.set()
            release_wait.set()
        assert runtime.shutdown(timeout=10)
    assert len(watch.attempts) == 1 and watch.computations == []
    row = WorkbenchRunService(case.conn).get(ref)
    assert (row["state"], row["stage"]) == ("queued", "queued")
    assert row["started_at"] is None and row["receipt_ref"] is None
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 0


def test_compute_sqlite_busy_is_durable_failure_without_reexecution(owned_case, monkeypatch):
    case = owned_case
    runtime = install(case)
    ref = case.accept()["run_ref"]
    calls = []

    def busy(_worker, row):
        calls.append(row["run_ref"])
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(WorkbenchRunWorker, "_compute", busy)
    runtime(ref)
    assert runtime.wait_idle(timeout=15), runtime.status
    assert calls == [ref] and runtime.ready
    row = WorkbenchRunService(case.conn).get(ref)
    assert row["state"] == "failed" and row["started_at"] is not None
    assert row["error"]["code"] == "candidate_computation_failed"
    assert row["candidates"] == [] and not row["result_persisted"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 1
    runtime(ref)
    assert runtime.wait_idle(timeout=5)
    assert calls == [ref]
