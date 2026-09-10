"""Report lifecycle, strict quantities and caller-owned read snapshots."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.test_execution_ledger_support import END, START, all_rows
from tests.workbench.test_execution_ledger_support import ledger_case as ledger_fixture


def test_partial_end_and_complete_cumulative(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    first = case.command("create", task, case.values(4))["data"]["rows"][0]
    projection = case.ledger.get_task(task)
    assert projection.execution_state == "partial" and projection.confirmed_finish is None
    assert projection.remaining_quantity == 6 and projection.remaining_plan is None
    second = case.command("create", task, case.values(6))["data"]["rows"][0]
    projection = case.ledger.get_task(task)
    assert projection.execution_state == "complete"
    assert projection.completion_basis == "complete_reports"
    assert projection.confirmed_finish == END and projection.quantity_complete
    assert first["report_no"] != second["report_no"]
    assert first["report_ref"] != second["report_ref"]


def test_unknown_zero_hours_and_sparse_supplement(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    row = case.command("create", task, {"actual_start": START})["data"]["rows"][0]
    projection = case.ledger.get_task(task)
    assert projection.unknown_record_count == 1 and projection.remaining_quantity is None
    assert projection.reports[0].effective_processing_hours is None
    patch = case.values(0, effective_processing_hours=0)
    patch.update(original_revision_ref=row["revision_ref"], reason="Fill verified fields")
    case.command("supplement", row["report_ref"], patch)
    report = case.ledger.get_report(row["report_ref"])
    assert report.completed_quantity == 0 and report.effective_processing_hours == 0
    assert len(report.correction_history) == 2
    assert report.correction_history[0]["after"]["completed_quantity"] is None
    assert report.correction_history[1]["before"]["effective_processing_hours"] is None
    assert report.correction_history[1]["receipt_ref"] is not None
    assert report.local_operator == "local-os-user"


@pytest.mark.parametrize("patch", [
    {"completed_quantity": 11}, {"completed_quantity": -1}, {"completed_quantity": 1.5},
    {"completed_quantity": True}, {"effective_processing_hours": -1},
    {"effective_processing_hours": float("nan")}, {"effective_processing_hours": float("inf")},
    {"effective_processing_hours": 2.1}, {"actual_start": "2026-09-11T08:00:00"},
    {"actual_end": "2026-09-11T10:00:00"}, {"actual_start": END, "actual_end": START},
    {"actual_end": "2026-09-09T10:00:00Z"},
])
def test_invalid_reports_write_nothing(ledger_case, patch):
    case = ledger_case
    case.install()
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        case.command("create", case.task(1, case.op_id), case.values(**patch) if "completed_quantity" not in patch else case.values(patch["completed_quantity"]))
    assert all_rows(case.conn) == before


def test_piece_target_is_one_not_batch_quantity(ledger_case):
    case = ledger_case
    piece = case.op("PIECE", seq=1, piece="unit-1")
    case.plan(2, [piece])
    case.install()
    task = case.task(2, piece)
    projection = case.ledger.get_task(task)
    assert projection.target_basis == "piece" and projection.target_quantity == 1
    with pytest.raises(WorkbenchCommandRejected):
        case.command("create", task, case.values(2))
    case.command("create", task, case.values(1))
    assert case.ledger.get_task(task).execution_state == "complete"


def test_cross_plan_refs_and_query_only(ledger_case):
    case = ledger_case
    case.install()
    old_task = case.task(1, case.op_id)
    saved = case.command("create", old_task, case.values(4))["data"]["rows"][0]
    case.plan(2, [case.op_id])
    new_task = case.task(2, case.op_id)
    before = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    projection = case.ledger.get_task(old_task)
    assert projection.current_task_ref == new_task and projection.comparison_task_ref == old_task
    assert projection.known_completed_quantity == 4
    assert projection.reports[0].recorded_against_task_ref == old_task
    assert projection.reports[0].recorded_against_plan_ref == case.plan_ref(1)
    assert case.ledger.get_report(saved["report_ref"]).report_no == saved["report_no"]
    assert all_rows(case.conn) == before
    case.conn.execute("PRAGMA query_only=OFF")
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("create", old_task, case.values(1))
    assert error.value.code == "plan_not_writable"
