"""Original-source updates invalidate snapshots, never overwrite archived completion."""

import sqlite3

import pytest

from core.infrastructure.database import get_connection
from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.workbench.test_execution_ledger_support import NOW, all_rows
from tests.workbench.test_execution_ledger_support import ledger_case as ledger_fixture


def _workspace(case):
    task = case.task(1, case.op_id)
    op = case.ledger.get_task(task).operation_ref
    return case.ledger.workspace_projection(case.plan_ref(1), [
        {"task_ref": task, "operation_ref": op, "plan_ref": case.plan_ref(1)}])


def _legacy_case(case):
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    case.install()


@pytest.mark.parametrize("change", ["UPDATE OperationExecutionEvents SET quantity_done=1 WHERE event_type='finish'",
                                    "DELETE FROM OperationExecutionEvents WHERE event_type='finish'"])
def test_original_source_change_keeps_archived_finish_and_invalidates_snapshot(ledger_case, change):
    case = ledger_case
    _legacy_case(case)
    before = _workspace(case)
    archived = all_rows(case.conn)["WorkbenchExecutionLegacyFacts"]
    case.conn.execute(change)
    case.conn.commit()
    stored = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    after = _workspace(case)
    assert after["snapshot_facts"]["legacy_source_hash"] != before["snapshot_facts"]["legacy_source_hash"]
    projection = after["projections"][0]
    assert projection["execution_state"] == "complete" and projection["completion_basis"] == "legacy_finish_event"
    assert projection["known_completed_quantity"] == 10
    gap = next(row for row in projection["data_gaps"] if row["code"] == "legacy_source_changed")
    assert gap["change"] == ("missing" if change.startswith("DELETE") else "changed")
    assert all_rows(case.conn) == stored
    assert all_rows(case.conn)["WorkbenchExecutionLegacyFacts"] == archived


def test_already_diverged_source_is_still_type_sensitive_in_snapshot(ledger_case):
    case = ledger_case
    _legacy_case(case)
    case.conn.execute("UPDATE OperationExecutionEvents SET remark='same-value' WHERE event_type='finish'")
    case.conn.commit()
    first = _workspace(case)
    case.conn.execute("UPDATE OperationExecutionEvents SET remark=? WHERE event_type='finish'", (sqlite3.Binary(b"same-value"),))
    case.conn.commit()
    second = _workspace(case)
    assert first["projections"] == second["projections"]
    assert first["snapshot_facts"]["legacy_source_hash"] != second["snapshot_facts"]["legacy_source_hash"]
    op = second["projections"][0]["operation_ref"]
    before = case.ledger.snapshot(op)["legacy_source_hash"]
    case.conn.execute("UPDATE OperationExecutionEvents SET remark='third-value' WHERE event_type='finish'")
    case.conn.commit()
    assert case.ledger.snapshot(op)["legacy_source_hash"] != before


def test_production_connection_date_converters_do_not_fake_source_changes(ledger_case):
    case = ledger_case
    _legacy_case(case)
    path = case.conn.execute("PRAGMA database_list").fetchone()[2]
    other = get_connection(path)
    try:
        ledger = ExecutionLedgerService(other, clock=lambda: NOW)
        projection = ledger.get_task(case.task(1, case.op_id))
        assert not any(row["code"] == "legacy_source_changed" for row in projection.data_gaps)
    finally:
        other.close()
