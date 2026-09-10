"""Real separate SQLite connections, rollback, receipt uncertainty and reference drift."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from flask import Flask

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.dashboard_support import connect, follow, source_rows  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_commands_one_history(dashboard_case, same_key):
    case = dashboard_case
    case.conn.execute("PRAGMA journal_mode=WAL")
    item, barrier = case.item(), Barrier(2)

    def write(index):
        conn = connect(case.path)
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                return case.command(item, follow(), key=f"dashboard-concurrent-{0 if same_key else index:02d}", conn=conn)
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


@pytest.mark.parametrize("table", ["WorkbenchDashboardHistory", "WorkbenchCommandReceipts"])
def test_failure_rolls_back_disposition_history_receipt(dashboard_case, table):
    case = dashboard_case
    item = case.item()
    before = source_rows(case.conn)
    case.conn.execute("CREATE TRIGGER dashboard_test_abort BEFORE INSERT ON " + table + " BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    with pytest.raises(WorkbenchCommandUncertain):
        case.command(item, follow(), key="dashboard-rollback-0001")
    assert not case.conn.in_transaction
    assert not case.history(item["item_ref"])
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchDashboardStates").fetchone()[0] == 0
    assert WorkbenchCommandService(case.conn).lookup("dashboard-rollback-0001") is None
    assert source_rows(case.conn) == before


def test_commit_reply_lost_lookup_survives_new_connection(dashboard_case, monkeypatch):
    from core.services.workbench.commands import WorkbenchCommandService as Commands

    case = dashboard_case
    item, original = case.item(), Commands.execute

    def lost(self, **kwargs):
        original(self, **kwargs)
        raise WorkbenchCommandUncertain(kwargs["request_key"])

    monkeypatch.setattr(Commands, "execute", lost)
    with pytest.raises(WorkbenchCommandUncertain):
        case.command(item, follow(), key="dashboard-lost-reply-01")
    conn = connect(case.path)
    try:
        receipt = WorkbenchCommandService(conn).lookup("dashboard-lost-reply-01")
        assert receipt["result"] == "committed" and receipt["replayed"]
    finally:
        conn.close()
    assert len(case.history(item["item_ref"])) == 1


def test_replaced_batch_never_inherits_handling(dashboard_case):
    case = dashboard_case
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,ready_status) VALUES ('REPLACE','DP1','Original',1,'no')")
    case.conn.commit()
    old = next(row for row in case.read()[0]["items"] if row["category"] == "material" and row["source"]["batch_id"] == "REPLACE")
    case.command(old, follow())
    case.conn.execute("INSERT OR REPLACE INTO Batches(batch_id,part_no,part_name,quantity,ready_status) VALUES ('REPLACE','DP1','Replacement',1,'no')")
    case.conn.commit()
    selected = [row for row in case.read()[0]["items"] if row["category"] == "material" and row["source"]["batch_id"] == "REPLACE"]
    assert len(selected) == 2
    assert len({row["source"]["batch_ref"] for row in selected}) == 2
    assert next(row for row in selected if row["item_ref"] == old["item_ref"])["risk"]["active"] is None
    assert next(row for row in selected if row["item_ref"] != old["item_ref"])["handling"]["status"] == "new"


def test_downtime_reference_changes_on_same_integer_replacement(dashboard_case):
    case = dashboard_case
    old = case.item("downtime")
    old_ref = old["source"]["downtimes"][0]["downtime_ref"]
    case.conn.execute("INSERT OR REPLACE INTO MachineDowntimes(id,machine_id,start_time,end_time) "
                     "VALUES (1,'DM1','2026-09-09T09:00:00','2026-09-09T11:00:00')")
    case.conn.commit()
    current = case.item("downtime")
    assert old_ref != current["source"]["downtimes"][0]["downtime_ref"]
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command(old, follow())
    assert error.value.code == "stale_write"


def test_raw_types_persist_and_type_only_drift_rejects(dashboard_case):
    case = dashboard_case
    case.conn.execute("UPDATE Batches SET remark=?", (b"same-text",))
    case.conn.commit()
    before = source_rows(case.conn)
    item = case.item()
    case.command(item, follow())
    encoded = json.loads(case.conn.execute("SELECT source_facts_json FROM WorkbenchDashboardHistory").fetchone()[0])
    assert encoded["facts"]["batch"]["remark"] == {"storage_type": "blob", "hex": b"same-text".hex()}
    assert source_rows(case.conn) == before
    fresh = case.item()
    case.conn.execute("UPDATE Batches SET remark='same-text'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command(fresh, follow(remark="New verification"))
    assert error.value.code == "stale_write"


def test_history_sql_update_delete_rejected(dashboard_case):
    case = dashboard_case
    case.command(case.item(), follow())
    for sql in ("UPDATE WorkbenchDashboardHistory SET reason='erase'", "DELETE FROM WorkbenchDashboardHistory",
                "DELETE FROM WorkbenchDashboardStates", "DELETE FROM WorkbenchDashboardItems"):
        with pytest.raises(sqlite3.IntegrityError):
            case.conn.execute(sql)
        case.conn.rollback()


def test_inconsistent_current_state_is_not_silently_displayed(dashboard_case):
    case = dashboard_case
    case.command(case.item(), follow())
    case.conn.execute("UPDATE WorkbenchDashboardStates SET revision=revision+1")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.read()
    assert error.value.code == "dashboard_storage_invalid"


def test_restart_keeps_receipt_and_refs_but_invalidates_old_write_token(dashboard_case):
    case = dashboard_case
    item = case.item()
    first = case.command(item, follow(), key="dashboard-before-restart-01")
    refreshed = case.item()
    with Flask("dashboard-restarted-process").app_context():
        replay = case.command(item, follow(), key="dashboard-before-restart-01")
        assert replay["receipt_ref"] == first["receipt_ref"] and replay["replayed"]
        with pytest.raises(WorkbenchCommandRejected) as error:
            case.command(refreshed, follow(remark="New intent after restart"))
        assert error.value.code == "stale_write"
        assert case.item()["item_ref"] == item["item_ref"]


@pytest.mark.parametrize("table", ["WorkbenchDashboardItems", "WorkbenchDashboardStates", "WorkbenchDashboardHistory", "WorkbenchDashboardDowntimeRefs"])
def test_replace_cannot_bypass_permanent_evidence_with_recursive_triggers_off(dashboard_case, table):
    case = dashboard_case
    case.command(case.item(), follow())
    before = list(case.conn.execute("SELECT * FROM " + table))
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    with pytest.raises(sqlite3.IntegrityError, match="cannot be replaced"):
        case.conn.execute("INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table + " LIMIT 1")
    case.conn.rollback()
    assert list(case.conn.execute("SELECT * FROM " + table)) == before
