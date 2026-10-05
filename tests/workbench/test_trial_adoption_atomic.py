"""Real SQLite fault injection, writer races, COMMIT ACK and original scheduler lock."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from tests.workbench.trial_adoption_support import INTENT, KEY, full_plan, preview, saved_scenario, service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import connect, snapshot


@pytest.mark.parametrize("table", ["WorkbenchCommandReceipts"])
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


@pytest.mark.parametrize("same_key", [True])
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
