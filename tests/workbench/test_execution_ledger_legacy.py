"""Legacy evidence remains immutable and cannot migrate to a replacement instance."""

import sqlite3

import pytest

from core.infrastructure.workbench_execution_ledger_schema import (
    LEGACY_COLUMNS,
    execution_ledger_contract_issues,
    install_execution_ledger,
)
from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.execution_ledger_support import END, all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture


@pytest.mark.parametrize("quantity", [None, 0, 10])
def test_legal_old_finish_remains_complete_without_fabricated_report(ledger_case, quantity):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=quantity)
    before = all_rows(case.conn)
    case.install()
    after = all_rows(case.conn)
    assert all(after[table] == rows for table, rows in before.items())
    assert not execution_ledger_contract_issues(case.conn)
    projection = case.ledger.get_task(case.task(1, case.op_id))
    assert projection.execution_state == "complete" and projection.completion_basis == "legacy_finish_event"
    assert projection.confirmed_finish == END and projection.reports == []
    assert projection.data_quality == ("invalid" if quantity == 0 else "legacy_incomplete")
    assert len(projection.legacy_facts) == 2
    assert all(row["effective_processing_hours"] is None for row in projection.legacy_facts)
    if quantity is None:
        assert projection.remaining_quantity is None and projection.unknown_record_count == 1
    source = [tuple(row) for row in case.conn.execute("SELECT " + ",".join(LEGACY_COLUMNS) + " FROM OperationExecutionEvents ORDER BY id")]
    archive = [tuple(row) for row in case.conn.execute("SELECT " + ",".join(LEGACY_COLUMNS) + " FROM WorkbenchExecutionLegacyFacts ORDER BY id")]
    assert source == archive


def test_future_old_events_capture_and_cross_version_cumulative_dedup(ledger_case):
    case = ledger_case
    case.install()
    for version in (1, 2):
        if version == 2:
            case.plan(2, [case.op_id])
        case.event(case.op_id, "start", version=version)
        case.event(case.op_id, "finish", version=version, quantity=10)
    projection = case.ledger.get_task(case.task(2, case.op_id))
    assert projection.known_completed_quantity == 10
    assert projection.execution_state == "complete"
    assert len(projection.legacy_facts) == 4


def test_explicit_legacy_supplement_deduplicates_and_keeps_original(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    case.install()
    task = case.task(1, case.op_id)
    old = [tuple(row) for row in case.conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
    fact = case.ledger.get_task(task).legacy_facts[-1]["legacy_fact_ref"]
    case.command("create", task, case.values(10, legacy_fact_ref=fact, reason="Verified source", declared_operator="written-by-foreman"))
    projection = case.ledger.get_task(task)
    assert projection.known_completed_quantity == 10 and projection.completion_basis == "legacy_finish_event"
    assert len(projection.reports) == 1 and projection.reports[0].declared_operator == "written-by-foreman"
    assert projection.reports[0].local_operator == "local-os-user"
    with pytest.raises(WorkbenchCommandRejected):
        case.command("create", task, case.values(10, legacy_fact_ref=fact, reason="Verified source"))
    assert [tuple(row) for row in case.conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")] == old


def test_unknown_legacy_quantity_contradiction_preserves_finish_invalid(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    case.install()
    task = case.task(1, case.op_id)
    fact = case.ledger.get_task(task).legacy_facts[-1]["legacy_fact_ref"]
    case.command("create", task, case.values(5, legacy_fact_ref=fact, reason="Verified source"))
    projection = case.ledger.get_task(task)
    assert projection.execution_state == "complete" and projection.data_quality == "invalid"
    assert projection.remaining_quantity is None


def test_report_old_instance_not_rebound_after_same_id_number_rebuild(ledger_case):
    case = ledger_case
    case.install()
    old_task = case.task(1, case.op_id)
    row = case.command("create", old_task, case.values(3))["data"]["rows"][0]
    old_ref = case.ledger.get_task(old_task).operation_ref
    case.conn.execute("DELETE FROM BatchOperations WHERE id=?", (case.op_id,))
    case.conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source) VALUES (?,'OP1','B1',1,'T1','Turning','internal')", (case.op_id,))
    case.plan(2, [case.op_id])
    new_task = case.task(2, case.op_id)
    projection = case.ledger.get_task(new_task)
    assert projection.operation_ref != old_ref and projection.reports == []
    assert projection.execution_state == "unreported"
    assert case.ledger.get_report(row["report_ref"]).operation_ref == old_ref
    with pytest.raises(WorkbenchCommandRejected):
        case.command("supplement", row["report_ref"], {"remark": "not a replacement", "original_revision_ref": row["revision_ref"], "reason": "test"})


def test_ambiguous_legacy_identity_is_retained_unbound(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    original = dict(case.conn.execute("SELECT * FROM WorkbenchPlanSourceRefs WHERE kind='schedule_row'").fetchone())
    original.update(ref="e" * 48, active=0)
    columns = list(original)
    case.conn.execute("INSERT INTO WorkbenchPlanSourceRefs (" + ",".join(columns) + ") VALUES (" + ",".join("?" for _ in columns) + ")", tuple(original.values()))
    case.install()
    assert case.conn.execute("SELECT count(*) FROM WorkbenchExecutionLegacyFacts WHERE operation_ref IS NULL").fetchone()[0] == 2
    projection = case.ledger.get_task(case.task(1, case.op_id))
    assert projection.data_quality == "invalid" and projection.legacy_facts == []
    with pytest.raises(WorkbenchCommandRejected):
        case.command("create", case.task(1, case.op_id), case.values(1))


def test_schema_install_is_explicit_transactional_and_not_repaired(ledger_case):
    case = ledger_case
    with pytest.raises(RuntimeError):
        install_execution_ledger(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.ledger.get_task(case.task(1, case.op_id))
    assert error.value.code == "execution_ledger_unavailable"
    before = all_rows(case.conn)
    case.conn.execute("BEGIN")
    install_execution_ledger(case.conn)
    case.conn.rollback()
    assert all_rows(case.conn) == before
    case.install()
    case.conn.execute("DROP INDEX idx_wb_execution_reports_operation")
    case.conn.commit()
    with pytest.raises(RuntimeError):
        case.install()
    case.conn.rollback()


def test_report_and_revision_reject_update_delete(ledger_case):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(1))
    for table in ("WorkbenchProductionReports", "WorkbenchProductionReportRevisions"):
        for statement in ("DELETE FROM " + table, "UPDATE " + table + " SET report_ref=report_ref"):
            with pytest.raises(sqlite3.IntegrityError):
                case.conn.execute(statement)
            case.conn.rollback()
