"""Restart, replacement identity, archive preservation and real resource aggregation."""

import importlib

import pytest

from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.plan_read_support import assert_error
from tests.workbench.report_execution_ledger_support import ReportLedgerApi
from tests.workbench.report_execution_ledger_support import report_ledger_api as _fixture


def test_replan_and_fullapp_restart_keep_original_report_refs(report_ledger_api):
    api = report_ledger_api
    first = api.create(api.values(4))
    original = api.read(topic="records")["data"]["rows"][0]
    with api.db() as conn:
        LedgerCase(conn).plan(2, [1])
    current = api.read(topic="records")["data"]["rows"][0]
    assert current["report_ref"] == first["report_ref"] and current["report_no"] == first["report_no"]
    assert current["recorded_against_plan_ref"] == original["recorded_against_plan_ref"]
    assert current["recorded_against_task_ref"] == original["recorded_against_task_ref"]
    assert api.task()["task_ref"] != original["recorded_against_task_ref"]
    restarted = ReportLedgerApi(importlib.import_module("app").create_app(), api.path)
    assert restarted.read(topic="records")["data"]["rows"] == [current]


def test_same_operation_number_replacement_does_not_inherit_old_report(report_ledger_api):
    api = report_ledger_api
    first = api.create(api.values(4))
    old = api.read(topic="records")["data"]["rows"][0]
    with api.db() as conn:
        conn.execute("DELETE FROM Schedule WHERE op_id=1")
        conn.execute("DELETE FROM BatchOperations WHERE id=1")
        conn.execute("INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_id,op_type_name,source) VALUES (1,'OP1','B1',1,'T1','Turning','internal')")
        LedgerCase(conn).plan(2, [1])
    current = api.read()["data"]["rows"][0]
    assert current["operation_ref"] != old["operation_ref"] and current["production_report_count"] == 0
    assert current["execution_state"] == "unreported" and api.read(topic="records")["data"]["rows"] == []
    with api.db() as conn:
        retained = ExecutionLedgerService(conn).get_report(first["report_ref"])
        assert retained.operation_ref == old["operation_ref"] and retained.report_no == old["report_no"]


def test_changed_resources_keep_whole_operation_and_separate_measured_hours(report_ledger_api):
    api = report_ledger_api
    first = api.create(api.values(4, effective_processing_hours=.5))
    with api.db() as conn:
        second_ref = LedgerCase(conn).ref("machine", "M2")
    second = api.create(api.values(6, effective_processing_hours=1.5, actual_machine_ref=second_ref))
    data = api.read(topic="records", resource_type="machine", resource_ref=second_ref)["data"]
    assert len(data["rows"]) == 2 and {row["report_ref"] for row in data["rows"]} == {first["report_ref"], second["report_ref"]}
    resources = data["resources"]["machines"]
    assert sorted(row["effective_processing_hours"] for row in resources) == [.5, 1.5]
    before = api.read()
    with api.db() as conn:
        conn.execute("DELETE FROM Machines WHERE machine_id='M2'")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Replacement','T1')")
        replacement = LedgerCase(conn).ref("machine", "M2")
    assert replacement != second_ref
    assert_error(api.get(snapshot_ref=before["meta"]["snapshot_ref"]), "snapshot_stale")
    historical = api.read(topic="records", resource_type="machine", resource_ref=second_ref)["data"]
    actual = next(row for row in historical["rows"] if row["report_ref"] == second["report_ref"])
    assert actual["machine_ref"] == second_ref and actual["machine_available"] is False
    assert actual["machine_label"] != "Replacement"
    assert api.read(topic="records", resource_type="machine", resource_ref=replacement)["data"]["rows"] == []


def test_legacy_pause_exception_display_never_becomes_processing_hours(report_ledger_api):
    api = report_ledger_api
    with api.db() as conn:
        case = LedgerCase(conn)
        case.event(1, "start")
        case.event(1, "pause", time="2026-09-09T08:10:00")
        case.event(1, "resume", time="2026-09-09T08:30:00")
        case.event(1, "exception", time="2026-09-09T08:40:00")
        case.event(1, "finish", quantity=10)
    row = api.read()["data"]["rows"][0]
    assert row["pause_duration_minutes"] == 20 and row["exception_reason"] == "其他"
    assert row["complete"] and row["effective_processing_hours"] is None


@pytest.mark.parametrize("change", ["changed", "missing"])
def test_legacy_source_change_stales_snapshot_without_overwriting_archive(report_ledger_api, change):
    api = report_ledger_api
    with api.db() as conn:
        case = LedgerCase(conn)
        case.event(1, "start")
        event = case.event(1, "finish", quantity=10)
        archive = [tuple(row) for row in conn.execute("SELECT * FROM WorkbenchExecutionLegacyFacts ORDER BY id")]
    reading = api.read(topic="records")
    records = reading["data"]["rows"]
    with api.db() as conn:
        if change == "changed":
            conn.execute("UPDATE OperationExecutionEvents SET remark='source was edited' WHERE id=?", (event,))
        else:
            conn.execute("DELETE FROM OperationExecutionEvents WHERE id=?", (event,))
    assert_error(api.get(topic="records", snapshot_ref=reading["meta"]["snapshot_ref"]), "snapshot_stale")
    refreshed = api.read(topic="records")
    assert refreshed["data"]["rows"] == records
    current = api.read()["data"]["rows"][0]
    assert current["complete"] and current["known_completed_quantity"] == 10
    gap = next(row for row in current["execution_data_gaps"] if row["code"] == "legacy_source_changed")
    assert gap["change"] == change and gap["message"] in refreshed["data"]["data_gaps"]
    with api.db() as conn:
        assert archive == [tuple(row) for row in conn.execute("SELECT * FROM WorkbenchExecutionLegacyFacts ORDER BY id")]
    if change == "changed":
        with api.db() as conn:
            conn.execute("UPDATE OperationExecutionEvents SET remark='different edit' WHERE id=?", (event,))
        assert_error(api.get(topic="records", snapshot_ref=refreshed["meta"]["snapshot_ref"]), "snapshot_stale")
