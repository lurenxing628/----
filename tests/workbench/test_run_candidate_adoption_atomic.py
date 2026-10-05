"""Actual SQL rollback and COMMIT ACK injection; concurrent intent uses one receipt."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandUncertain
from tests.workbench.run_candidate_adoption_support import INTENT, KEY, candidate, preview, service, snapshot
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import connect


@pytest.mark.parametrize("table", ["WorkbenchCommandReceipts"])
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
