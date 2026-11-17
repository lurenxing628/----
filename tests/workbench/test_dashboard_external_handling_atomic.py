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


def test_receipt_write_failure_rolls_back_state_history_and_receipt(external_handling_case):
    case = external_handling_case
    case.register()
    item = case.item("external")
    before, counts = production_storage(case.conn), ledger_counts(case.conn)
    case.conn.execute(
        "CREATE TRIGGER dt_injected_abort BEFORE INSERT ON WorkbenchCommandReceipts"
        " BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    with pytest.raises(WorkbenchCommandUncertain):
        case.command(item, follow(), key="external-handling-rollback-01")
    assert not case.conn.in_transaction and ledger_counts(case.conn) == counts
    assert WorkbenchCommandService(case.conn).lookup("external-handling-rollback-01") is None
    assert production_storage(case.conn) == before


def test_competing_writes_reject_stale_loser_and_replay_winner_receipt(external_handling_case):
    case = external_handling_case
    case.register()
    case.conn.execute("PRAGMA journal_mode=WAL")
    item, barrier = case.item("external"), Barrier(2)

    def write(index):
        conn = get_connection(str(case.path))
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                return case.command(item, follow(), key="external-handling-race-0" + str(index), conn=conn)
        except WorkbenchCommandRejected as error:
            return error.code
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, range(2)))
    assert len(case.history(item["item_ref"])) == 1
    saved = case.conn.execute(
        "SELECT * FROM WorkbenchDashboardHistory WHERE item_ref=?",
        (item["item_ref"],),
    ).fetchone()
    assert "source_facts_json" not in saved.keys()
    archived = json.loads(saved["source_json"])
    assert archived["category"] == "external"
    assert archived["source"]["outsourcing_ref"] == item["source"]["outsourcing_ref"]
    winner = next(row for row in results if isinstance(row, dict))
    key = "external-handling-race-0" + ("0" if results[0] == winner else "1")
    replay = case.command(item, follow(), key=key)
    assert replay["replayed"] and replay["receipt_ref"] == winner["receipt_ref"]
    assert len(case.history(item["item_ref"])) == 1
    assert sum(row == "stale_write" for row in results) == 1


def test_external_write_token_ignores_unrelated_plan_clock_and_rejects_receipt_mutation(external_handling_case):
    case = external_handling_case
    ref = case.register()
    item = case.item("external")

    # Advancing the global plan clock via an unrelated plan publish must not invalidate the external write_token.
    case.plan(2)
    case.conn.commit()
    committed = case.command(item, follow(), key="external-ignore-plan-clock-01")
    assert committed["result"] == "committed"

    # Mutating the receipt's own facts invalidates the external item's source_revision and triggers stale_write.
    refreshed = case.item("external")
    case.returned(ref)
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        case.command(refreshed, follow(remark="After return mutation"), key="external-stale-after-return-01")
    assert rejected.value.code == "stale_write"
