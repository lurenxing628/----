"""Loose legacy databases must not attach colliding candidate/scenario identities."""

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.execution_ledger_support import NOW, all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture


@pytest.mark.parametrize("after_install", [False, True])
@pytest.mark.parametrize("scope", [
    {"source": "candidate_rows"}, {"role": "baseline_best"}, {"scenario": "old-scenario"},
    {"source": "adjustment_scenario_rows", "role": "critical_best", "scenario": "old-scenario"},
    {"batch_id": "OTHER-BATCH"},
])
def test_loose_legacy_foreign_scope_never_binds_official(ledger_case, scope, after_install):
    case = ledger_case
    if after_install:
        case.install()
    case.conn.execute("PRAGMA ignore_check_constraints=ON")
    if "batch_id" in scope:
        case.conn.execute("PRAGMA foreign_keys=OFF")
    case.event(case.op_id, "start", **scope)
    case.event(case.op_id, "finish", quantity=10, **scope)
    original = [tuple(row) for row in case.conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
    if not after_install:
        case.install()
    archived = case.conn.execute("SELECT * FROM WorkbenchExecutionLegacyFacts ORDER BY id").fetchall()
    assert len(archived) == 2
    assert all(row["operation_ref"] is None and row["recorded_against_task_ref"] is None and row["recorded_against_plan_ref"] is None for row in archived)
    assert [tuple(row) for row in case.conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")] == original
    projection = case.ledger.get_task(case.task(1, case.op_id))
    assert projection.execution_state != "complete" and projection.known_completed_quantity == 0
    assert projection.data_quality == "invalid"


def test_report_recorded_at_is_server_factory_time_not_sqlite_utc_default(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    saved = case.command("create", task, case.values(1))["data"]["rows"][0]
    report = case.ledger.get_report(saved["report_ref"])
    assert report.recorded_at == NOW.isoformat(timespec="seconds")
    assert report.correction_history[0]["recorded_at"] == report.recorded_at
    stored = case.conn.execute("SELECT recorded_at FROM WorkbenchProductionReports WHERE report_ref=?", (report.report_ref,)).fetchone()[0]
    assert stored == report.recorded_at


def test_legacy_creation_metadata_is_not_relabelled_as_factory_actual_time(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.conn.execute("UPDATE OperationExecutionEvents SET created_at='2026-09-09 00:15:00'")
    case.conn.commit()
    case.install()
    fact = case.ledger.get_task(case.task(1, case.op_id)).legacy_facts[0]
    assert fact["created_at"] == "2026-09-09 00:15:00"
    assert fact["created_at_time_basis"] == "legacy_storage"
    assert fact["created_at_default_basis"] == "utc"
    assert "recorded_at" not in fact


def test_legacy_blob_metadata_remains_stored_but_is_explicitly_unavailable(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    case.conn.execute("UPDATE OperationExecutionEvents SET remark=?,created_at=?", (sqlite3.Binary(b"raw-note"), sqlite3.Binary(b"raw-time")))
    case.conn.commit()
    original = all_rows(case.conn)["OperationExecutionEvents"]
    case.install()
    projection = case.ledger.get_task(case.task(1, case.op_id))
    assert projection.execution_state == "complete"
    assert projection.legacy_facts[0]["remark"] is None and projection.legacy_facts[0]["created_at"] is None
    assert projection.legacy_facts[0]["unavailable_fields"] == [
        {"field": "remark", "storage_type": "bytes"}, {"field": "created_at", "storage_type": "bytes"}]
    assert any(gap["code"] == "legacy_field_not_displayable" for gap in projection.data_gaps)
    assert all_rows(case.conn)["OperationExecutionEvents"] == original
    archived = case.conn.execute("SELECT remark,created_at FROM WorkbenchExecutionLegacyFacts LIMIT 1").fetchone()
    assert tuple(archived) == (b"raw-note", b"raw-time")


def test_completed_report_cannot_be_downgraded_by_sparse_new_report(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    case.command("create", task, case.values(10))
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("create", task, {"actual_start": "2026-09-09T11:00:00"})
    assert error.value.code == "constraint_conflict"
    assert all_rows(case.conn) == before
    assert case.ledger.get_task(task).execution_state == "complete"


def test_ambiguous_legacy_resource_ref_is_null_with_filter_gap(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    resource = dict(case.conn.execute("SELECT * FROM WorkbenchEntityRefs WHERE kind='machine' AND entity_key='M1'").fetchone())
    resource.update(ref="d" * 48, active=0)
    columns = list(resource)
    case.conn.execute("INSERT INTO WorkbenchEntityRefs (" + ",".join(columns) + ") VALUES (" + ",".join("?" for _ in columns) + ")", tuple(resource.values()))
    case.install()
    projection = case.ledger.get_task(case.task(1, case.op_id))
    assert projection.execution_state == "complete"
    assert all(row["actual_machine_ref"] is None for row in projection.legacy_facts)
    gaps = [row for row in projection.data_gaps if row["code"] == "legacy_resource_identity_unresolved"]
    assert len(gaps) == 2 and all(row["fields"] == ["actual_machine_ref"] for row in gaps)
