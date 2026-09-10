"""Actual file-SQLite concurrency, rollback, lost response and same-key retry."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from tests.workbench.calibration_adoption_support import INTENT, KEY, connect, service, snapshot, token
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


@pytest.mark.parametrize("table", ["PartOperations", "WorkbenchCalibrationAdoptions", "WorkbenchCalibrationQuotaLocks", "WorkbenchCommandReceipts"])
def test_each_write_failure_rolls_back_quota_audit_lock_and_receipt(ready_adoption_case, table):
    case = ready_adoption_case
    write_token = token(case)
    event = "UPDATE" if table == "PartOperations" else "INSERT"
    case.conn.execute("CREATE TRIGGER co_test_failure BEFORE " + event + " ON " + table +
                      " BEGIN SELECT RAISE(ABORT,'CO injected storage failure'); END")
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    conn = connect(case)
    try:
        assert snapshot(conn) == before
        assert service(conn).receipt(case.template_ref, KEY) is None
    finally:
        conn.close()
    assert not case.conn.in_transaction
    case.conn.execute("DROP TRIGGER co_test_failure")
    result = service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    assert result["result"] == "committed" and not result["replayed"]


@pytest.mark.parametrize("same_key", [True, False])
def test_two_connections_adopt_once_and_never_overwrite_lock(ready_adoption_case, same_key):
    case = ready_adoption_case
    write_token = token(case)
    barrier = Barrier(2)

    def worker(index):
        conn = connect(case)
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                try:
                    return service(conn).confirm(case.template_ref, write_token,
                        KEY if same_key or index == 0 else KEY + "-other", INTENT)
                except WorkbenchCommandRejected as error:
                    return {"code": error.code}
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, (0, 1)))
    successes = [row for row in results if row.get("ok")]
    if same_key:
        assert len(successes) == 2
        assert sorted(row["replayed"] for row in successes) == [False, True]
        assert successes[0]["receipt_ref"] == successes[1]["receipt_ref"]
    else:
        assert len(successes) == 1
        assert [row for row in results if not row.get("ok")] == [{"code": "stale_write"}]
    assert case.conn.execute("SELECT count(*) FROM WorkbenchCalibrationAdoptions").fetchone()[0] == 1
    assert case.conn.execute("SELECT count(*) FROM WorkbenchCalibrationQuotaLocks").fetchone()[0] == 1
    assert case.conn.execute("SELECT count(*) FROM WorkbenchCommandReceipts WHERE action='calibration.adopt'").fetchone()[0] == 1


def test_readers_never_observe_partial_uncommitted_adoption(ready_adoption_case, monkeypatch):
    case = ready_adoption_case
    case.conn.execute("PRAGMA journal_mode=WAL")
    write_token = token(case)
    held, release = Event(), Event()

    original = WorkbenchCalibrationAdoptionRepository.append

    def append(repo, *args, **kwargs):
        result = original(repo, *args, **kwargs)
        held.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(WorkbenchCalibrationAdoptionRepository, "append", append)

    def worker():
        conn = connect(case)
        try:
            with case.app.app_context():
                return service(conn).confirm(case.template_ref, write_token, KEY, INTENT)
        finally:
            conn.close()

    before = snapshot(case.conn)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        try:
            assert held.wait(5)
            assert snapshot(case.conn) == before
            assert service(case.conn).receipt(case.template_ref, KEY) is None
        finally:
            release.set()
        assert future.result(timeout=10)["result"] == "committed"
    assert service(case.conn).receipt(case.template_ref, KEY)["result"] == "committed"


def test_busy_failure_retains_original_key_and_can_retry(ready_adoption_case):
    case = ready_adoption_case
    write_token = token(case)
    conn = connect(case, timeout=0.02)
    before = snapshot(case.conn)
    case.conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(WorkbenchCommandUncertain):
            service(conn).confirm(case.template_ref, write_token, KEY, INTENT)
        assert not conn.in_transaction
        assert snapshot(conn) == before
    finally:
        case.conn.rollback()
    try:
        result = service(conn).confirm(case.template_ref, write_token, KEY, INTENT)
        assert result["result"] == "committed"
    finally:
        conn.close()


def test_lost_response_reopen_expired_context_and_intent_conflict(ready_adoption_case):
    case = ready_adoption_case
    result = service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    before = snapshot(case.conn)
    case.app.extensions.clear()  # Simulates a process losing all transient preview tokens.
    conn = connect(case)
    try:
        replay = service(conn, integration_enabled=False).confirm(case.template_ref, "expired", KEY, INTENT)
        assert replay["receipt_ref"] == result["receipt_ref"] and replay["replayed"] is True
        assert service(conn).receipt(case.template_ref, KEY) == replay
        with pytest.raises(WorkbenchCommandRejected) as error:
            service(conn).confirm(case.template_ref, "expired", KEY, {**INTENT, "reason": "different"})
        assert error.value.code == "request_key_conflict"
        with pytest.raises(WorkbenchCommandRejected) as error:
            service(conn).receipt("a" * 48, KEY)
        assert error.value.code == "request_key_conflict"
        assert snapshot(conn) == before
    finally:
        conn.close()


def test_commit_failure_rolls_back_and_same_key_retry_commits_once(ready_adoption_case):
    import sqlite3

    class FailCommitConnection(sqlite3.Connection):
        fail_commit = True

        def commit(self):
            if self.fail_commit:
                self.fail_commit = False
                raise OSError("CO simulated commit IO failure")
            super().commit()

    case = ready_adoption_case
    write_token = token(case)
    before = snapshot(case.conn)
    conn = sqlite3.connect(case.db_path, factory=FailCommitConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with pytest.raises(WorkbenchCommandUncertain):
            service(conn).confirm(case.template_ref, write_token, KEY, INTENT)
        assert not conn.in_transaction
        assert snapshot(case.conn) == before
        assert service(case.conn).receipt(case.template_ref, KEY) is None
        assert service(conn).confirm(case.template_ref, write_token, KEY, INTENT)["result"] == "committed"
    finally:
        conn.close()
