"""Real SQLite fault injection, writer races, COMMIT ACK and original scheduler lock."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.scheduler import schedule_service
from tests.workbench.trial_adoption_support import INTENT, KEY, full_plan, preview, saved_scenario, service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import CommitFailureConnection, connect, snapshot


@pytest.mark.parametrize("table", ["Schedule", "ScheduleHistory", "ScheduleVersionSeq", "WorkbenchPlanSourceRefs",
                                 "WorkbenchTaskRefs", "OperationLogs", "WorkbenchCommandReceipts"])
def test_real_insert_failure_rolls_back_entire_adoption(trial_case, table):
    case = trial_case
    value, _ = full_plan(case)
    conditions = {"Schedule": "NEW.version>1 AND (SELECT COUNT(*) FROM Schedule WHERE version>1)>0",
                  "ScheduleHistory": "NEW.version>1", "WorkbenchTaskRefs": "1",
                  "ScheduleVersionSeq": "1", "WorkbenchPlanSourceRefs": "NEW.kind='official' AND NEW.version>1",
                  "OperationLogs": "NEW.action='adopt_trial_scenario'",
                  "WorkbenchCommandReceipts": "NEW.action='trial.scenario.adopt'"}
    case.conn.execute('CREATE TRIGGER cq_failure BEFORE INSERT ON "' + table + '" WHEN ' + conditions[table]
                      + " BEGIN SELECT RAISE(ABORT,'injected CQ failure'); END")
    case.conn.commit()
    saved = saved_scenario(case, value, changed=False)
    token = preview(case, saved)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
    assert not case.conn.in_transaction and snapshot(case.conn) == before
    assert service(case.conn).lookup(saved["scenario_ref"], KEY) is None


@pytest.mark.parametrize("acknowledge_only", [False, True])
def test_commit_failure_uses_original_receipt_without_redo(trial_case, acknowledge_only):
    case = trial_case
    saved = saved_scenario(case)
    token = preview(case, saved)
    before = snapshot(case.conn)
    conn = connect(case.path, CommitFailureConnection)
    conn.fail_commit, conn.acknowledge_only = True, acknowledge_only
    try:
        with pytest.raises(WorkbenchCommandUncertain):
            service(conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
        assert not conn.in_transaction
    finally:
        conn.close()
    with connect(case.path) as reopened:
        receipt = service(reopened).lookup(saved["scenario_ref"], KEY)
        assert (receipt is not None) is acknowledge_only
        if acknowledge_only:
            committed = snapshot(reopened)
            replay = service(reopened).adopt(saved["scenario_ref"], "expired", KEY, INTENT)
            assert replay == receipt and snapshot(reopened) == committed
        else:
            assert snapshot(reopened) == before


@pytest.mark.parametrize("same_key", [True, False])
def test_two_connections_commit_once_under_race(trial_case, same_key):
    case = trial_case
    saved = saved_scenario(case)
    token = preview(case, saved)
    barrier = Barrier(2)

    def adopt(index):
        conn = connect(case.path)
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                try:
                    return service(conn).adopt(saved["scenario_ref"], token, KEY if same_key else KEY + str(index), INTENT)
                except WorkbenchCommandRejected as exc:
                    return exc.code
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(adopt, index) for index in range(2)]
        results = [future.result(timeout=15) for future in futures]
    if same_key:
        assert sorted(item["replayed"] for item in results) == [False, True]
        assert len({item["receipt_ref"] for item in results}) == 1
    else:
        assert sum(isinstance(item, dict) for item in results) == 1 and "snapshot_stale" in results
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 2
    assert case.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='adopt_trial_scenario'").fetchone()[0] == 1


def test_global_run_lock_and_sqlite_immediate_lock_both_apply(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    token = preview(case, saved)
    before = snapshot(case.conn)
    with schedule_service._RUN_SCHEDULE_LOCK:
        with pytest.raises(WorkbenchCommandRejected) as error:
            service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
    assert error.value.code == "scheduling_busy" and snapshot(case.conn) == before
    observations = []

    def trace(sql):
        if not observations and sql.startswith("SELECT request_key"):
            conn = sqlite3.connect(str(case.path), timeout=0.01)
            try:
                conn.execute("UPDATE Machines SET name='drift'")
            except sqlite3.OperationalError as exc:
                observations.append((case.conn.in_transaction, str(exc)))
            finally:
                conn.close()

    case.conn.set_trace_callback(trace)
    try:
        service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
    finally:
        case.conn.set_trace_callback(None)
    assert observations == [(True, "database is locked")]
