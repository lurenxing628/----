"""Projection adaptation never guesses an operation identity or rewrites events."""

from dataclasses import replace

import pytest

from core.infrastructure.errors import AppError
from core.services.scheduler.execution.execution_ledger_guard import ensure_ledger_execution_schedulable
from core.services.scheduler.execution.operation_execution_scope_read import scope_from_plan_row
from core.services.scheduler.execution_fact_provider import ExecutionFactProvider
from tests.workbench.execution_ledger_support import END, START, all_rows
from tests.workbench.scheduler_execution_ledger_support import PLAN_FIELDS, plan_rows, read_facts, read_snapshot
from tests.workbench.scheduler_execution_ledger_support import ledger_case as ledger_fixture


def test_partial_report_is_processing_with_real_remaining_not_legacy_event(ledger_case):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(4))
    before = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    fact = read_facts(case.conn)[case.op_id]
    assert fact.actual_status == "processing" and fact.ledger_execution_state == "partial"
    assert fact.remaining_quantity == 6 and fact.actual_end_time is None
    assert fact.actual_start_time.isoformat() == START
    assert fact.execution_effective_intervals[0][1].isoformat() == END
    assert "execution_ledger_remaining_plan_unavailable" in fact.execution_protection_reasons
    assert ":ledger-v1:" in fact.state_revision
    assert all_rows(case.conn) == before
    assert before["OperationExecutionEvents"] == []


@pytest.mark.parametrize("payload,state,remaining", [
    ({"actual_start": START}, "started", None),
    ({"actual_end": END, "completed_quantity": 3}, "partial", 7),
    ({"effective_processing_hours": 0.5}, "started", None),
])
def test_incomplete_reports_never_become_unstarted_or_zero(ledger_case, payload, state, remaining):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), payload)
    fact = read_facts(case.conn)[case.op_id]
    assert fact.actual_status == "processing" and fact.ledger_execution_state == state
    assert fact.remaining_quantity == remaining
    with pytest.raises(AppError) as error:
        ensure_ledger_execution_schedulable({case.op_id: fact})
    assert error.value.details["reason"] == "execution_ledger_requires_reconciliation"


def test_complete_and_corrected_report_change_flags_and_snapshot(ledger_case):
    case = ledger_case
    case.install()
    saved = case.command("create", case.task(1, case.op_id), case.values(10))["data"]["rows"][0]
    completed = read_facts(case.conn)[case.op_id]
    assert completed.actual_status == "completed" and completed.remaining_quantity == 0
    assert not completed.execution_protection_reasons
    ensure_ledger_execution_schedulable({case.op_id: completed})
    snapshot = read_snapshot(case.conn)
    case.command("correct", saved["report_ref"], {"completed_quantity": 4,
        "original_revision_ref": saved["revision_ref"], "reason": "Verified actual count"})
    partial = read_facts(case.conn)[case.op_id]
    assert partial.actual_status == "processing" and partial.remaining_quantity == 6
    assert partial.state_revision != completed.state_revision
    assert read_snapshot(case.conn).revision != snapshot.revision


@pytest.mark.parametrize("quantity", [None, 0, 10])
def test_old_finish_keeps_exact_legacy_status_revision_and_rows(ledger_case, quantity):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=quantity)
    original = read_facts(case.conn)[case.op_id]
    snapshot = read_snapshot(case.conn)
    case.install()
    before = all_rows(case.conn)
    fact = read_facts(case.conn)[case.op_id]
    assert fact == original and fact.actual_status == "completed"
    assert fact.remaining_quantity is None
    assert read_snapshot(case.conn).revision == snapshot.revision
    assert all_rows(case.conn) == before


def test_legacy_finish_quantity_contradiction_blocks_but_does_not_become_partial(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    case.install()
    task = case.task(1, case.op_id)
    old = all_rows(case.conn)["OperationExecutionEvents"]
    ref = case.ledger.get_task(task).legacy_facts[-1]["legacy_fact_ref"]
    case.command("create", task, case.values(5, legacy_fact_ref=ref, reason="Verified count"))
    fact = read_facts(case.conn)[case.op_id]
    assert fact.actual_status == "completed" and fact.remaining_quantity is None
    assert "legacy_target_conflict" in fact.execution_protection_reasons
    with pytest.raises(AppError):
        ensure_ledger_execution_schedulable({case.op_id: fact})
    assert all_rows(case.conn)["OperationExecutionEvents"] == old


@pytest.mark.parametrize("quantity", [4, 10])
def test_new_current_scope_keeps_report_recorded_against_old_task(ledger_case, quantity):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    saved = case.command("create", task, case.values(quantity))["data"]["rows"][0]
    other = case.op("SAME-SEQ", seq=1)
    case.plan(2, [other, case.op_id])
    before = all_rows(case.conn)
    facts = read_facts(case.conn, 2)
    assert facts[case.op_id].ledger_execution_state == ("partial" if quantity == 4 else "complete")
    assert facts[case.op_id].schedule_version == 2
    assert facts[other].actual_status == "not_started"
    report = case.ledger.get_report(saved["report_ref"])
    assert report.recorded_against_task_ref == task
    assert report.recorded_against_plan_ref == case.plan_ref(1)
    assert facts[case.op_id].ledger_operation_ref == report.operation_ref
    assert all_rows(case.conn) == before


def test_cross_version_old_finish_still_protects_completed(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    case.install()
    case.plan(2, [case.op_id])
    fact = read_facts(case.conn, 2)[case.op_id]
    assert fact.actual_status == "completed" and fact.remaining_quantity is None
    assert not fact.execution_protection_reasons


def test_scope_mapping_rejects_wrong_batch_version_and_nonmatching_row(ledger_case):
    case = ledger_case
    case.install()
    scope = scope_from_plan_row(plan_rows(case.conn, 1)[0], PLAN_FIELDS)
    for invalid in (replace(scope, batch_id="B-OTHER"), replace(scope, schedule_version=2),
                    replace(scope, schedule_id=9000), replace(scope, op_id=9999)):
        with pytest.raises(AppError) as error:
            ExecutionFactProvider(case.conn).facts_by_scope([invalid])
        assert error.value.details["reason"] == "execution_ledger_scope_missing"
    foreign = replace(scope, source_table="candidate_rows", effective_plan_role="baseline_best")
    assert ExecutionFactProvider(case.conn).facts_by_scope([foreign])[foreign].actual_status == "not_started"


def test_same_number_replacement_cannot_inherit_old_report(ledger_case):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(4))
    original = read_facts(case.conn)[case.op_id].ledger_operation_ref
    case.conn.execute("DELETE FROM BatchOperations WHERE id=?", (case.op_id,))
    case.conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,source,op_type_name) VALUES (?,'NEW','B1',1,'internal','Turning')", (case.op_id,))
    case.plan(2, [case.op_id])
    fact = read_facts(case.conn, 2)[case.op_id]
    assert fact.actual_status == "not_started" and fact.ledger_operation_ref != original


@pytest.mark.parametrize("damage", [
    "DROP INDEX idx_wb_execution_reports_operation",
    "DROP TRIGGER wb_execution_revisions_clock",
    "DELETE FROM WorkbenchExecutionLedgerClock",
    "DROP TABLE WorkbenchProductionReportRevisions",
])
def test_damaged_v25_ledger_is_not_treated_as_no_reports(ledger_case, damage):
    case = ledger_case
    case.install()
    case.conn.execute("UPDATE SchemaVersion SET version=25 WHERE id=1")
    case.conn.execute(damage)
    case.conn.commit()
    with pytest.raises(AppError) as error:
        read_facts(case.conn)
    assert error.value.details["reason"] == "execution_ledger_unavailable"


def test_pre_v25_without_ledger_is_explicit_legacy_but_v25_missing_is_blocked(ledger_case):
    case = ledger_case
    case.conn.execute("UPDATE SchemaVersion SET version=24 WHERE id=1")
    case.conn.commit()
    assert read_facts(case.conn)[case.op_id].actual_status == "not_started"
    case.conn.execute("UPDATE SchemaVersion SET version=25 WHERE id=1")
    case.conn.commit()
    with pytest.raises(AppError) as error:
        read_facts(case.conn)
    assert error.value.details["reason"] == "execution_ledger_unavailable"


@pytest.mark.parametrize("patch", [
    {"ledger_execution_state": None}, {"actual_status": "not_started"},
    {"execution_effective_intervals": ()}, {"actual_start_time": None}, {"actual_end_time": None},
])
def test_missing_or_inconsistent_ledger_protection_flags_fail_closed(ledger_case, patch):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(10))
    fact = replace(read_facts(case.conn)[case.op_id], **patch)
    with pytest.raises(AppError) as error:
        ensure_ledger_execution_schedulable({case.op_id: fact})
    assert error.value.details["reason"] == "execution_ledger_requires_reconciliation"
    assert error.value.details["data_gaps"]


@pytest.mark.parametrize("second_start,safe", [(END, True), ("2026-09-09T11:00:00", False)])
def test_only_contiguous_real_intervals_can_form_a_complete_seed(ledger_case, second_start, safe):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    case.command("create", task, case.values(4))
    case.command("create", task, case.values(6, actual_start=second_start,
        actual_end="2026-09-09T12:00:00", effective_processing_hours=1))
    fact = read_facts(case.conn)[case.op_id]
    assert fact.actual_status == "completed" and len(fact.execution_effective_intervals) == 2
    if safe:
        ensure_ledger_execution_schedulable({case.op_id: fact})
    else:
        with pytest.raises(AppError) as error:
            ensure_ledger_execution_schedulable({case.op_id: fact})
        assert "execution_ledger_intervals_not_representable" in error.value.details["data_gaps"]


def test_report_with_lost_schedule_scope_is_not_silently_ignored(ledger_case):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(4))
    case.conn.execute("DELETE FROM Schedule WHERE op_id=?", (case.op_id,))
    case.conn.commit()
    assert plan_rows(case.conn, 1) == []
    with pytest.raises(AppError) as error:
        read_facts(case.conn)
    assert error.value.details["reason"] == "execution_ledger_report_scope_missing"
