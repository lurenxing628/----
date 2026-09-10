"""R1-D: strict rejection metadata, optional callbacks, and immutable facts."""

from datetime import timezone

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import factory_time, validate_actual_values
from core.services.workbench.execution_ledger import ExecutionLedgerService
from core.services.workbench.production_report_prepare import ReportBatchRejected, normalize_items
from tests.workbench.test_execution_ledger_support import END, NOW, START, all_rows
from tests.workbench.test_execution_ledger_support import ledger_case as ledger_fixture


@pytest.mark.parametrize("value", [None, "", "2026-02-30T08:00:00", "2026-09-09T08:00:00Z", 0])
def test_invalid_factory_time_never_returns_none(value):
    with pytest.raises(WorkbenchCommandRejected) as error:
        factory_time(value)
    assert error.value.code == "invalid_input"
    assert error.value.status == 422
    assert not error.value.committed


def test_valid_time_and_unknown_hours_are_not_coerced():
    assert factory_time(START).isoformat() == START
    validate_actual_values({"actual_start": START, "actual_end": END, "effective_processing_hours": None}, NOW)
    with pytest.raises(WorkbenchCommandRejected):
        validate_actual_values({"actual_start": END, "actual_end": START}, NOW)
    with pytest.raises(WorkbenchCommandRejected):
        validate_actual_values({"actual_start": START, "actual_end": END, "effective_processing_hours": 2.1}, NOW)


def test_row_rejection_preserves_code_status_cause_and_position():
    valid = {"action": "create", "ref": "a" * 48, "payload": {"actual_start": START}}
    with pytest.raises(ReportBatchRejected) as error:
        normalize_items([valid, dict(valid, ref="not-a-permanent-ref")])
    rejected = error.value
    assert rejected.row_number == 2 and rejected.status == 400
    assert rejected.code == "invalid_input" and rejected.committed is False
    assert rejected.conflicts == []
    assert isinstance(rejected.__cause__, WorkbenchCommandRejected)
    assert str(rejected) == str(rejected.__cause__)


@pytest.mark.parametrize("keyword", ["clock", "context_factory"])
@pytest.mark.parametrize("value", [False, 0, "", object()])
def test_invalid_callback_is_rejected_without_database_access(keyword, value):
    with pytest.raises(TypeError, match="must be callable"):
        ExecutionLedgerService(None, **{keyword: value})


@pytest.mark.parametrize("value", [None, START, NOW.replace(tzinfo=timezone.utc)])
def test_bad_clock_result_is_rejected_without_mutation(ledger_case, value):
    case = ledger_case
    case.install()
    before = all_rows(case.conn)
    ledger = ExecutionLedgerService(case.conn, clock=lambda: value)
    with pytest.raises(ValueError, match="naive factory-local datetime"):
        ledger.get_task(case.task(1, case.op_id))
    assert all_rows(case.conn) == before
    assert not case.conn.in_transaction


def test_falsey_callable_clock_is_not_replaced(ledger_case):
    class Clock:
        calls = 0

        def __bool__(self):
            return False

        def __call__(self):
            self.calls += 1
            return NOW

    case = ledger_case
    case.install()
    clock = Clock()
    ledger = ExecutionLedgerService(case.conn, clock=clock)
    ledger.get_task(case.task(1, case.op_id))
    assert clock.calls == 1


def test_missing_task_report_and_clock_fail_closed(ledger_case):
    case = ledger_case
    case.install()
    before = all_rows(case.conn)
    for read in (case.ledger.get_task, case.ledger.get_report):
        with pytest.raises(WorkbenchCommandRejected) as error:
            read("f" * 48)
        assert error.value.code == "entity_not_found" and error.value.status == 404
    assert all_rows(case.conn) == before
    case.conn.execute("DELETE FROM WorkbenchExecutionLedgerClock")
    case.conn.commit()
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.ledger.repo.clock()
    assert error.value.code == "execution_ledger_unavailable"
    assert all_rows(case.conn) == before


def test_downstream_conflict_keeps_row_details_and_atomic_rollback(ledger_case):
    case = ledger_case
    successor = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, successor], start=END, end="2026-09-09T12:00:00")
    case.install()
    row = case.command("create", case.task(2, case.op_id), case.values(10))["data"]["rows"][0]
    before = all_rows(case.conn)
    with pytest.raises(ReportBatchRejected) as error:
        case.command("correct", row["report_ref"], {"completed_quantity": 5,
            "original_revision_ref": row["revision_ref"], "reason": "Verified counter correction"})
    rejected = error.value
    assert rejected.code == "constraint_conflict" and rejected.status == 409
    assert rejected.row_number == 1 and rejected.committed is False
    assert any(item["code"] == "downstream_requires_completion" for item in rejected.conflicts)
    assert all_rows(case.conn) == before
    assert not case.conn.in_transaction
