"""Atomic receipts, original-intent replay, correction history and dry-run batches."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain, input_fingerprint
from core.services.workbench.production_report import WorkbenchProductionReportService
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository
from tests.workbench.test_execution_ledger_support import all_rows
from tests.workbench.test_execution_ledger_support import ledger_case as ledger_fixture


def test_original_request_replays_before_actor_token_or_time_checks(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    payload = case.values(3)
    key = "ledger-original-request-0001"
    saved = case.command("create", task, payload, key=key)

    def unavailable():
        raise AssertionError("replay must not resolve a new actor or validate expired state")

    case.writer.actor_provider = unavailable
    case.writer.ledger.clock = unavailable
    replayed = case.command("create", task, payload, key=key, validate_context=lambda *_: unavailable())
    assert replayed == {**saved, "replayed": True}
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("create", task, case.values(4), key=key)
    assert error.value.code == "request_key_conflict"


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


def test_supplement_cannot_overwrite_known_fields(ledger_case):
    case = ledger_case
    case.install()
    row = case.command("create", case.task(1, case.op_id), case.values(0))["data"]["rows"][0]
    for replacement in (None, 1):
        before = all_rows(case.conn)
        with pytest.raises(WorkbenchCommandRejected):
            case.command("supplement", row["report_ref"], {"completed_quantity": replacement,
                "original_revision_ref": row["revision_ref"], "reason": "not unknown"})
        assert all_rows(case.conn) == before


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


def test_receipt_failure_rolls_back_domain_data(ledger_case):
    case = ledger_case
    case.install()
    case.conn.execute("CREATE TRIGGER fail_ledger_receipt BEFORE INSERT ON WorkbenchCommandReceipts BEGIN SELECT RAISE(ABORT,'receipt failed'); END")
    case.conn.commit()
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        case.command("create", case.task(1, case.op_id), case.values(1))
    assert all_rows(case.conn) == before


def test_write_refuses_callers_uncommitted_outer_transaction(ledger_case):
    case = ledger_case
    case.install()
    before = all_rows(case.conn)
    case.conn.execute("BEGIN")
    with pytest.raises(RuntimeError):
        case.command("create", case.task(1, case.op_id), case.values(1))
    assert case.conn.in_transaction
    case.conn.rollback()
    assert all_rows(case.conn) == before


def test_same_file_preview_accumulates_without_writes_and_confirms_same_snapshot(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    items = [{"action": "create", "ref": task, "payload": case.values(q, source="excel", report_no=f"EX-{q}")} for q in (4, 6)]
    before = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    preview = case.writer.preview_batch(items)
    assert preview["projections"][0]["execution_state"] == "complete"
    assert [row["row_number"] for row in preview["rows"]] == [1, 2]
    assert all_rows(case.conn) == before
    case.conn.execute("PRAGMA query_only=OFF")
    seen = []
    result = case.writer.execute_batch(items, context_ref=case.plan_ref(1), request_key="ledger-batch-00000001",
        validate_context=lambda ref, action, snapshot: seen.append((action, input_fingerprint(snapshot))))
    assert seen == [("batch", input_fingerprint(preview["snapshot"]))]
    assert result["data"]["summary"] == {"total": 2, "changed": 2, "unchanged": 0}
    assert case.ledger.get_task(task).known_completed_quantity == 10


def test_batch_overreport_rejected_with_row_and_zero_writes(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    items = [{"action": "create", "ref": task, "payload": case.values(6)}] * 2
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.writer.preview_batch(items)
    assert error.value.row_number == 2
    assert all_rows(case.conn) == before
    with pytest.raises(WorkbenchCommandRejected):
        case.writer.execute_batch(items, context_ref=case.plan_ref(1), request_key="ledger-batch-invalid1", validate_context=lambda *_: None)
    assert all_rows(case.conn) == before


def test_import_replay_survives_lost_bytes_but_different_preview_conflicts(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    items = [{"action": "create", "ref": task, "payload": case.values(4, source="excel", report_no="FILE1")}]
    preview_ref = "preview_" + "1" * 24
    saved = case.writer.execute_import(preview_ref, request_key="ledger-import-000001", load_items=lambda: items, validate_context=lambda *_: None)

    def lost():
        raise AssertionError("expired preview bytes must not be loaded on replay")

    restarted = WorkbenchProductionReportService(case.conn, actor_provider=lost)
    again = restarted.execute_import(preview_ref, request_key="ledger-import-000001", load_items=lost, validate_context=lambda *_: lost())
    assert again == {**saved, "replayed": True}
    with pytest.raises(WorkbenchCommandRejected) as error:
        restarted.execute_import("preview_" + "2" * 24, request_key="ledger-import-000001", load_items=lost, validate_context=lambda *_: lost())
    assert error.value.code == "request_key_conflict"


def test_excel_same_number_supplements_across_version_without_rebinding(ledger_case):
    case = ledger_case
    case.install()
    old_task = case.task(1, case.op_id)
    base = case.values(4, source="excel", report_no="IMPORT-STABLE", effective_processing_hours=None)
    saved = case.command("create", old_task, base)["data"]["rows"][0]
    case.plan(2, [case.op_id])
    task = case.task(2, case.op_id)
    again = case.command("create", task, base)
    assert again["result"] == "unchanged"
    case.command("create", task, {**base, "effective_processing_hours": 1.5})
    report = case.ledger.find_report("IMPORT-STABLE")
    assert report.report_ref == saved["report_ref"] and report.recorded_against_task_ref == old_task
    assert report.effective_processing_hours == 1.5 and len(report.correction_history) == 2
    with pytest.raises(WorkbenchCommandRejected):
        case.command("create", task, {**base, "completed_quantity": 5})
