"""Actual SQLite rollback and competing adoption transactions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from tests.workbench.calibration_adoption_support import INTENT, KEY, connect, service, snapshot, token
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


@pytest.mark.parametrize('table', ['WorkbenchCommandReceipts'])
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


@pytest.mark.parametrize('same_key', [False])
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
