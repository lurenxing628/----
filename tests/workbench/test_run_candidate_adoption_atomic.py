"""Actual SQL rollback and COMMIT ACK injection; concurrent intent uses one receipt."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.scheduler import schedule_service
from tests.workbench.run_candidate_adoption_support import (
    INTENT,
    KEY,
    CommitFailureConnection,
    candidate,
    preview,
    service,
    snapshot,
)
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import connect


@pytest.mark.parametrize("table", ["Schedule", "ScheduleHistory", "OperationLogs", "WorkbenchCommandReceipts"])
def test_failure_after_real_writes_rolls_back_every_table(candidate_case, table):
    case = candidate_case
    case.operation(seq=2)
    case.conn.commit()
    # Install fault before admission so it is part of the exact facts schema.
    condition = "NEW.version>0 AND (SELECT COUNT(*) FROM Schedule)>0" if table == "Schedule" else (
        "NEW.action='scheduling.candidate.adopt'" if table == "WorkbenchCommandReceipts" else "1")
    case.conn.execute('CREATE TRIGGER bx_inject BEFORE INSERT ON "' + table + '" WHEN ' + condition
                      + " BEGIN SELECT RAISE(ABORT,'injected storage failure'); END")
    case.conn.commit()
    ref = candidate(case)
    token = preview(case, ref)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).adopt(ref, token, KEY, INTENT)
    assert snapshot(case.conn) == before
    assert not case.conn.in_transaction
    assert service(case.conn).lookup(ref, KEY) is None


@pytest.mark.parametrize("after_commit", [False, True])
def test_commit_failure_lookup_distinguishes_saved_receipt_without_redo(candidate_case, after_commit):
    case = candidate_case
    ref = candidate(case)
    token = preview(case, ref)
    conn = sqlite3.connect(str(case.path), factory=CommitFailureConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    before = snapshot(conn)
    conn.acknowledge_only = after_commit
    # Only outer adoption COMMIT should fail, not read/savepoint release.
    conn.fail_commit = True
    try:
        with pytest.raises(WorkbenchCommandUncertain):
            service(conn).adopt(ref, token, KEY, INTENT)
        receipt = service(case.conn).lookup(ref, KEY)
        assert (receipt is not None) is after_commit
        assert not conn.in_transaction
        if after_commit:
            saved = snapshot(case.conn)
            replay = service(case.conn).adopt(ref, "restart-expired", KEY, INTENT)
            assert replay == receipt and replay["replayed"] is True
            assert snapshot(case.conn) == saved
        else:
            assert snapshot(case.conn) == before
    finally:
        conn.close()


def test_two_connections_concurrently_replay_one_adoption(candidate_case):
    case = candidate_case
    ref = candidate(case)
    token = preview(case, ref)
    barrier = Barrier(2)

    def adopt():
        conn = connect(case.path)
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                return service(conn).adopt(ref, token, KEY, INTENT)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(adopt) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(row["replayed"] for row in results) == [False, True]
    assert len({row["receipt_ref"] for row in results}) == 1
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 1
    assert case.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='adopt_run_candidate'").fetchone()[0] == 1


def test_existing_worker_lock_rejects_without_waiting_or_writing(candidate_case):
    case = candidate_case
    ref = candidate(case)
    token = preview(case, ref)
    before = snapshot(case.conn)
    with schedule_service._RUN_SCHEDULE_LOCK:
        with pytest.raises(WorkbenchCommandRejected) as error:
            service(case.conn).adopt(ref, token, KEY, INTENT)
    assert error.value.code == "scheduling_busy"
    assert snapshot(case.conn) == before


def test_guard_and_mutation_hold_one_sqlite_writer_lock(candidate_case):
    case = candidate_case
    ref = candidate(case)
    token = preview(case, ref)
    observations = []

    def trace(sql):
        if not observations and sql.startswith("SELECT request_key"):
            other = sqlite3.connect(str(case.path), timeout=0.01)
            try:
                other.execute("UPDATE Machines SET name='race'")
            except sqlite3.OperationalError as exc:
                observations.append((case.conn.in_transaction, str(exc)))
            finally:
                other.close()

    case.conn.set_trace_callback(trace)
    try:
        service(case.conn).adopt(ref, token, KEY, INTENT)
    finally:
        case.conn.set_trace_callback(None)
    assert observations == [(True, "database is locked")]
