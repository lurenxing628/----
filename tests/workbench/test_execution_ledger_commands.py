"""Atomic receipts, original-intent replay, correction history and dry-run batches."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401


def test_correct_keeps_stable_number_and_every_original_value(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    saved = case.command("create", task, case.values(4, remark="original"))["data"]["rows"][0]
    original = case.ledger.get_report(saved["report_ref"])
    payload = {"completed_quantity": 6, "remark": "corrected", "original_revision_ref": original.revision_ref,
               "reason": "Checked counter", "declared_operator": "declared-foreman"}
    case.command("correct", original.report_ref, payload)
    result = case.ledger.get_report(original.report_ref)
    assert result.report_no == original.report_no and result.report_ref == original.report_ref
    assert result.completed_quantity == 6
    assert result.correction_history[0]["after"]["completed_quantity"] == 4
    assert result.correction_history[1]["before"]["remark"] == "original"
    assert result.correction_history[1]["reason"] == "Checked counter"
    assert result.local_operator == "local-os-user" and result.declared_operator == "declared-foreman"
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", original.report_ref, payload)
    assert error.value.code == "stale_write"


def test_mid_mutation_exception_rolls_back_report_revision_clock_and_receipt(ledger_case, monkeypatch):
    case = ledger_case
    case.install()
    before = all_rows(case.conn)
    original = WorkbenchExecutionReportRepository.append

    def fail(self, row, *, request_key):
        original(self, row, request_key=request_key)
        raise RuntimeError("injected after append")

    monkeypatch.setattr(WorkbenchExecutionReportRepository, "append", fail)
    with pytest.raises(WorkbenchCommandUncertain):
        case.command("create", case.task(1, case.op_id), case.values(1), key="ledger-rollback-000001")
    assert all_rows(case.conn) == before
    assert case.writer.commands.lookup("ledger-rollback-000001") is None
