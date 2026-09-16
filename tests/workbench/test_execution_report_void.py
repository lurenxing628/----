"""Withdrawal changes effective facts once, while preserving every original row."""

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain, input_fingerprint
from core.services.workbench.production_report import WorkbenchProductionReportService
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository
from tests.workbench.execution_ledger_support import START, all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture
from tests.workbench.scheduler_execution_ledger_support import read_facts


def report(case, values=None):
    return case.command("create", case.task(1, case.op_id), values or case.values(4))["data"]["rows"][0]


def intent(row):
    return {"original_revision_ref": row["revision_ref"], "reason": "误记了其他工序的产出", "declared_operator": "现场班长"}


def test_preview_is_select_only_and_void_preserves_original_history(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    case.command("correct", row["report_ref"], {**intent(row), "completed_quantity": 5})
    original = case.ledger.get_report(row["report_ref"])
    payload = {**intent(row), "original_revision_ref": original.revision_ref}
    before = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    preview = case.writer.preview("report_void", row["report_ref"], payload)
    assert preview["can_confirm"] and preview["before"]["known_completed_quantity"] == 5
    assert preview["after"]["known_completed_quantity"] == 0 and preview["after"]["execution_state"] == "unreported"
    assert all_rows(case.conn) == before
    case.conn.execute("PRAGMA query_only=OFF")
    saved = case.command("report_void", row["report_ref"], payload)
    after = all_rows(case.conn)
    assert saved["data"]["state"] == "voided" and saved["data"]["refresh_required"]
    assert {name for name in before if before[name] != after[name]} == {
        "WorkbenchProductionReportVoids", "WorkbenchExecutionLedgerClock", "WorkbenchCommandReceipts"}
    projected = case.ledger.get_task(case.task(1, case.op_id))
    assert projected.reports == [] and projected.remaining_quantity == 10
    audit = projected.voided_reports[0]
    assert audit["report"]["correction_history"] == original.correction_history
    assert audit["void_fact"]["reason"] == payload["reason"] and audit["void_fact"]["declared_operator"] == "现场班长"
    assert audit["void_fact"]["receipt_ref"] == saved["receipt_ref"]
    assert case.ledger.get_report(row["report_ref"]).revision_ref == original.revision_ref


def test_zero_output_is_real_execution_until_explicitly_voided(ledger_case):
    case = ledger_case
    case.install()
    row = report(case, {"completed_quantity": 0, "effective_processing_hours": 0})
    assert case.ledger.get_task(case.task(1, case.op_id)).execution_state == "started"
    case.command("report_void", row["report_ref"], intent(row))
    assert case.ledger.get_task(case.task(1, case.op_id)).execution_state == "unreported"


def test_void_one_of_many_keeps_other_report_and_scheduler_intervals(ledger_case):
    case = ledger_case
    case.install()
    first = report(case)
    second = report(case, case.values(3, actual_start="2026-09-09T10:00:00", actual_end="2026-09-09T12:00:00"))
    case.command("report_void", first["report_ref"], intent(first))
    p = case.ledger.get_task(case.task(1, case.op_id))
    assert p.known_completed_quantity == 3 and p.remaining_quantity == 7 and p.execution_state == "partial"
    assert [row.report_ref for row in p.reports] == [second["report_ref"]]
    fact = read_facts(case.conn)[case.op_id]
    assert fact.remaining_quantity == 7 and len(fact.execution_effective_intervals) == 1
    assert fact.execution_effective_intervals[0][0].isoformat() == "2026-09-09T10:00:00"


def test_repeat_void_replays_before_actor_token_and_new_key_is_unchanged(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    saved = case.command("report_void", row["report_ref"], intent(row), key="void-original-request-0001")
    def unavailable(*_):
        raise AssertionError("committed replay must not read a new actor or context")
    restarted = WorkbenchProductionReportService(case.conn, actor_provider=unavailable)
    replay = restarted.execute("report_void", row["report_ref"], intent(row), request_key="void-original-request-0001", validate_context=unavailable)
    assert replay == {**saved, "replayed": True}
    again = case.command("report_void", row["report_ref"], intent(row))
    assert again["result"] == "unchanged" and again["data"]["void_fact_ref"] == saved["data"]["void_fact_ref"]
    assert case.conn.execute("SELECT count(*) FROM WorkbenchProductionReportVoids").fetchone()[0] == 1


def test_old_revision_and_stale_operation_snapshot_cannot_void(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    preview = case.writer.preview("report_void", row["report_ref"], intent(row))
    report(case, case.values(1))
    before = all_rows(case.conn)
    def validate(ref, action, snapshot):
        assert ref == row["report_ref"] and action == "report_void"
        if input_fingerprint(snapshot) != input_fingerprint(preview["snapshot"]):
            raise WorkbenchCommandRejected("context_stale", "changed")
    with pytest.raises(WorkbenchCommandRejected, match="changed"):
        case.command("report_void", row["report_ref"], intent(row), validate_context=validate)
    assert all_rows(case.conn) == before
    case.command("correct", row["report_ref"], {**intent(row), "remark": "新记录"})
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("report_void", row["report_ref"], intent(row))
    assert error.value.code == "context_stale"


@pytest.mark.parametrize("quantity", [4, 10])
def test_downstream_started_blocks_even_if_parent_was_only_partial(ledger_case, quantity):
    case = ledger_case
    successor = case.op("NEXT", seq=2)
    case.plan(2, [case.op_id, successor])
    case.install()
    row = case.command("create", case.task(2, case.op_id), case.values(quantity))["data"]["rows"][0]
    case.command("create", case.task(2, successor), {"actual_start": START, "completed_quantity": 0})
    before = all_rows(case.conn)
    preview = case.writer.preview("report_void", row["report_ref"], intent(row))
    assert not preview["can_confirm"] and preview["downstream_impacts"]
    assert all(item["operation_label"].startswith("2 ") for item in preview["downstream_impacts"])
    with pytest.raises(WorkbenchCommandRejected):
        case.command("report_void", row["report_ref"], intent(row))
    assert all_rows(case.conn) == before


def test_new_adopted_plan_protects_its_execution_basis(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    case.plan(2, [case.op_id])
    preview = case.writer.preview("report_void", row["report_ref"], intent(row))
    assert not preview["can_confirm"]
    assert "adopted_execution_basis_changed" in {item["code"] for item in preview["downstream_impacts"]}


def test_old_actual_start_survives_voiding_new_report(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.install()
    row = report(case)
    original = all_rows(case.conn)["OperationExecutionEvents"]
    case.command("report_void", row["report_ref"], intent(row))
    projection = case.ledger.get_task(case.task(1, case.op_id))
    assert projection.execution_state == "started" and projection.first_actual_start == START
    assert all_rows(case.conn)["OperationExecutionEvents"] == original


def test_void_failure_rolls_back_fact_clock_and_receipt(ledger_case, monkeypatch):
    case = ledger_case
    case.install()
    row = report(case)
    original = WorkbenchExecutionReportRepository.append_void
    def fail(self, fact, *, request_key):
        original(self, fact, request_key=request_key)
        raise RuntimeError("injected after append")
    monkeypatch.setattr(WorkbenchExecutionReportRepository, "append_void", fail)
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        case.command("report_void", row["report_ref"], intent(row))
    assert all_rows(case.conn) == before


def test_voided_history_cannot_be_corrected_reimported_or_replaced(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    case.command("report_void", row["report_ref"], intent(row))
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], {**intent(row), "completed_quantity": 2})
    assert error.value.code == "report_voided"
    with pytest.raises(WorkbenchCommandRejected) as error:
        report(case, {**case.values(2), "source": "excel", "report_no": row["report_no"]})
    assert error.value.code == "report_voided"
    for sql in ("DELETE FROM WorkbenchProductionReportVoids", "UPDATE WorkbenchProductionReportVoids SET reason='changed'",
                "INSERT OR REPLACE INTO WorkbenchProductionReportVoids SELECT * FROM WorkbenchProductionReportVoids"):
        with pytest.raises(sqlite3.IntegrityError):
            case.conn.execute(sql)
        case.conn.rollback()
    assert all_rows(case.conn) == before


def test_missing_void_table_never_reactivates_archived_reports(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    case.command("report_void", row["report_ref"], intent(row))
    case.conn.execute("DROP TABLE WorkbenchProductionReportVoids")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.ledger.get_task(case.task(1, case.op_id))
    assert error.value.code == "execution_ledger_unavailable"
