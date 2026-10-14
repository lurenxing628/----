"""Real SQLite connections: state, immutable history and receipt commit together."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.dashboard_external_handling_support import external_handling_case as _handling_case  # noqa: F401
from tests.workbench.dashboard_external_handling_support import ledger_counts, production_storage
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401
from tests.workbench.dashboard_support import follow


@pytest.mark.parametrize('table', ['WorkbenchCommandReceipts'])
def test_failure_rolls_back_all_three_writes(external_handling_case, table):
    case = external_handling_case
    case.register()
    item = case.item("external")
    before, counts = production_storage(case.conn), ledger_counts(case.conn)
    case.conn.execute("CREATE TRIGGER dt_injected_abort BEFORE INSERT ON " + table + " BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(WorkbenchCommandUncertain):
        case.command(item, follow(), key="external-handling-rollback-01")
    assert not case.conn.in_transaction and ledger_counts(case.conn) == counts
    assert WorkbenchCommandService(case.conn).lookup("external-handling-rollback-01") is None
    assert production_storage(case.conn) == before


@pytest.mark.parametrize('same_key', [False])
def test_concurrent_writes_have_one_history(external_handling_case, same_key):
    case = external_handling_case
    case.register()
    case.conn.execute("PRAGMA journal_mode=WAL")
    item, barrier = case.item("external"), Barrier(2)

    def write(index):
        conn = get_connection(str(case.path))
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                return case.command(item, follow(), key="external-handling-race-0" + str(0 if same_key else index), conn=conn)
        except WorkbenchCommandRejected as error:
            return error.code
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, range(2)))
    assert len(case.history(item["item_ref"])) == 1
    saved = case.conn.execute("SELECT source_hash,source_facts_json FROM WorkbenchDashboardExternalHistory WHERE item_ref=?",
                              (item["item_ref"],)).fetchone()
    assert saved["source_hash"] is None
    archived = json.loads(saved["source_facts_json"])
    assert archived["facts"]["receipt"]["outsourcing_ref"] == item["source"]["outsourcing_ref"]
    winner = next(row for row in results if isinstance(row, dict))
    key = "external-handling-race-0" + ("0" if same_key or results[0] == winner else "1")
    replay = case.command(item, follow(), key=key)
    assert replay["replayed"] and replay["receipt_ref"] == winner["receipt_ref"]
    assert len(case.history(item["item_ref"])) == 1
    if same_key:
        assert {row["replayed"] for row in results} == {False, True}
        assert len({row["receipt_ref"] for row in results}) == 1
    else:
        assert sum(row == "stale_write" for row in results) == 1
