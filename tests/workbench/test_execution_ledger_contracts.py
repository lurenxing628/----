"""API-facing shapes, write context bindings, and unsupported facts are explicit."""

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.workbench.execution_ledger_support import NOW, START, all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture


def test_target_unknown_and_zero_remain_distinct(ledger_case):
    case = ledger_case
    case.conn.execute("UPDATE Batches SET quantity='unknown' WHERE batch_id='B1'")
    case.conn.commit()
    case.install()
    task = case.task(1, case.op_id)
    projection = case.ledger.get_task(task)
    assert projection.target_quantity is None and projection.remaining_quantity is None
    case.command("create", task, {"actual_start": START})
    with pytest.raises(WorkbenchCommandRejected):
        case.command("create", task, case.values(1))
    case.conn.execute("UPDATE Batches SET quantity=0 WHERE batch_id='B1'")
    case.conn.commit()
    projection = case.ledger.get_task(task)
    assert projection.target_quantity == 0 and projection.remaining_quantity is None
    assert projection.unknown_record_count == 1


def test_unknown_actual_hours_never_inferred_and_not_completed(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    case.command("create", task, case.values(10, effective_processing_hours=None))
    projection = case.ledger.get_task(task)
    assert projection.quantity_complete and not projection.records_complete
    assert projection.execution_state == "partial" and projection.confirmed_finish is None
    assert projection.reports[0].effective_processing_hours is None


def test_legacy_start_is_not_an_extra_unknown_production_report(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.install()
    task = case.task(1, case.op_id)
    assert case.ledger.get_task(task).remaining_quantity is None
    case.command("create", task, case.values(4))
    case.command("create", task, case.values(6))
    projection = case.ledger.get_task(task)
    assert projection.execution_state == "complete"
    assert projection.completion_basis == "complete_reports"
    assert projection.unknown_record_count == 0 and projection.records_complete
    assert len(projection.legacy_facts) == 1 and len(projection.reports) == 2


def test_legacy_create_needs_link_and_reason(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    case.install()
    task = case.task(1, case.op_id)
    fact = case.ledger.get_task(task).legacy_facts[-1]["legacy_fact_ref"]
    before = all_rows(case.conn)
    for payload in (case.values(1), case.values(1, legacy_fact_ref=fact)):
        with pytest.raises(WorkbenchCommandRejected):
            case.command("create", task, payload)
    assert all_rows(case.conn) == before
    case.command("create", task, case.values(10, legacy_fact_ref=fact, reason="Original counter verified"))
    assert case.ledger.get_task(task).reports[0].correction_history[0]["reason"] == "Original counter verified"


def test_same_report_number_across_operations_is_rejected(ledger_case):
    case = ledger_case
    other = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, other])
    case.install()
    values = case.values(1, source="excel", report_no="SAME-NO")
    case.command("create", case.task(2, case.op_id), values)
    with pytest.raises(WorkbenchCommandRejected):
        case.command("create", case.task(2, other), values)


def test_context_factory_and_snapshot_match_guard_without_plain_type_collisions(ledger_case):
    case = ledger_case
    case.conn.execute("UPDATE BatchOperations SET created_at=? WHERE id=?", (sqlite3.Binary(b"raw-date"), case.op_id))
    case.conn.commit()
    case.install()
    captured = {}

    def issue(ref, actions, snapshot):
        captured[ref] = snapshot
        return {"write_token": "fixture-context", "expires_at": None, "capabilities": actions, "blocked_reasons": []}

    ledger = ExecutionLedgerService(case.conn, clock=lambda: NOW, context_factory=issue)
    task = case.task(1, case.op_id)
    projection = ledger.get_task(task)
    assert projection.write_context["capabilities"] == ["create"]
    before = input_fingerprint(captured[task])
    seen = []
    case.command("create", task, case.values(1), validate_context=lambda ref, action, snapshot: seen.append(input_fingerprint(snapshot)))
    assert seen == [before]


def test_workspace_keeps_comparison_refs_resources_and_stable_fact_fingerprint(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    case.install()
    task = case.task(1, case.op_id)
    op_ref = case.ledger.get_task(task).operation_ref
    case.plan(2, [case.op_id])
    tasks = [{"task_ref": task, "operation_ref": op_ref, "plan_ref": case.plan_ref(1)}]
    with case.ledger.read_snapshot():
        first = case.ledger.workspace_projection(case.plan_ref(1), tasks)
        assert case.conn.in_transaction
        second = case.ledger.workspace_projection(case.plan_ref(1), tasks)
    assert first["available"] is True and first["time_basis"] == "factory_local"
    assert first["snapshot_facts"] == second["snapshot_facts"]
    assert first["projections"][0]["comparison_task_ref"] == task
    assert first["projections"][0]["current_task_ref"] == case.task(2, case.op_id)
    assert first["resources"]["machines"][0]["ref"] == case.ref("machine", "M1")
    assert first["resources"]["operators"][0]["label"] == "Operator"
    legacy = first["projections"][0]["legacy_facts"][0]
    assert legacy["operation_ref"] == op_ref and legacy["recorded_against_task_ref"] == task
    assert "report_ref" not in legacy and "report_no" not in legacy


def test_deleted_same_version_task_is_not_resolved_to_replacement(ledger_case):
    case = ledger_case
    case.install()
    old_task = case.task(1, case.op_id)
    row = dict(case.conn.execute("SELECT * FROM Schedule WHERE version=1").fetchone())
    case.conn.execute("DELETE FROM Schedule WHERE id=?", (row["id"],))
    columns = list(row)
    case.conn.execute("INSERT INTO Schedule (" + ",".join(columns) + ") VALUES (" + ",".join("?" for _ in columns) + ")", tuple(row.values()))
    case.conn.commit()
    new_task = case.task(1, case.op_id)
    assert new_task != old_task
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.ledger.get_task(old_task)
    assert error.value.code == "entity_not_found"
    assert case.ledger.get_task(new_task).current_task_ref == new_task
