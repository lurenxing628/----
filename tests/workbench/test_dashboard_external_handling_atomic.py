"""Real SQLite connections: state, immutable history and receipt commit together."""

import sqlite3
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


@pytest.mark.parametrize("table", ["WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory", "WorkbenchCommandReceipts"])
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


@pytest.mark.parametrize("same_key", [False, True])
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
    if same_key:
        assert {row["replayed"] for row in results} == {False, True}
        assert len({row["receipt_ref"] for row in results}) == 1
    else:
        assert sum(row == "stale_write" for row in results) == 1


def test_committed_reply_loss_lookup_on_new_connection(external_handling_case, monkeypatch):
    case = external_handling_case
    case.register()
    item, execute = case.item("external"), WorkbenchCommandService.execute

    def lost(self, **kwargs):
        execute(self, **kwargs)
        raise WorkbenchCommandUncertain(kwargs["request_key"])

    monkeypatch.setattr(WorkbenchCommandService, "execute", lost)
    with pytest.raises(WorkbenchCommandUncertain):
        case.command(item, follow(), key="external-handling-lost-reply-01")
    conn = get_connection(str(case.path))
    try:
        receipt = WorkbenchCommandService(conn).lookup("external-handling-lost-reply-01")
        assert receipt["result"] == "committed" and receipt["data"]["item_ref"] == item["item_ref"]
    finally:
        conn.close()
    assert len(case.history(item["item_ref"])) == 1


@pytest.mark.parametrize("suffix", ["Items", "States", "History"])
def test_evidence_cannot_be_deleted_or_replaced(external_handling_case, suffix):
    case = external_handling_case
    case.register()
    case.command(case.item("external"), follow())
    table = "WorkbenchDashboardExternal" + suffix
    before = [tuple(row) for row in case.conn.execute("SELECT * FROM " + table)]
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    for sql in ("DELETE FROM " + table, "INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table + " LIMIT 1"):
        with pytest.raises(sqlite3.IntegrityError):
            case.conn.execute(sql)
        case.conn.rollback()
        assert [tuple(row) for row in case.conn.execute("SELECT * FROM " + table)] == before


def test_corrupt_state_is_not_presented_as_valid(external_handling_case):
    case = external_handling_case
    case.register()
    case.command(case.item("external"), follow())
    case.conn.execute("UPDATE WorkbenchDashboardExternalStates SET revision=revision+1")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.read()
    assert error.value.code == "dashboard_storage_invalid"
