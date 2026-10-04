"""Full registered Flask app: new production reports reach every report read."""

import pytest

from core.services.workbench.execution.ledger import ExecutionLedgerService
from tests.workbench.execution_ledger_support import LedgerCase
from tests.workbench.plan_read_support import assert_error
from tests.workbench.report_execution_ledger_support import report_ledger_api as _fixture


def test_fullapp_null_zero_partial_complete_and_immutable_sources(report_ledger_api):
    api = report_ledger_api
    before = api.state()
    assert api.read()["data"]["rows"][0]["execution_state"] == "unreported"
    assert api.state() == before
    report = api.create({"actual_start": "2026-09-09T08:00:00"})
    row = api.read()["data"]["rows"][0]
    assert row["known_completed_quantity"] == 0 and row["unknown_record_count"] == 1
    assert row["remaining_quantity"] is None and row["effective_processing_hours"] is None
    api.revise(report, "supplement", **api.values(0, effective_processing_hours=0))
    record = api.read(topic="records")["data"]["rows"][0]
    assert record["quantity_done"] == 0 and record["effective_processing_hours"] == 0
    assert len(record["correction_history"]) == 2
    api.create(api.values(4, actual_start="2026-09-09T10:00:00", actual_end="2026-09-09T11:00:00", effective_processing_hours=.5))
    partial = api.read()["data"]["rows"][0]
    assert partial["execution_state"] == "partial" and partial["remaining_quantity"] == 6
    assert partial["confirmed_finish"] is None and partial["complete"] is False
    saved = api.create(api.values(6, actual_start="2026-09-09T11:00:00", actual_end="2026-09-09T12:00:00", effective_processing_hours=.75))
    data = api.read()["data"]
    row = data["rows"][0]
    assert {"event_count", "record_count", "production_report_count"}.issubset({column["key"] for column in data["columns"]})
    assert row["complete"] and row["known_completed_quantity"] == 10 and row["remaining_quantity"] == 0
    assert row["confirmed_finish"] == "2026-09-09T12:00:00" and row["effective_processing_hours"] == 1.25
    assert data["summary"]["events"] == 0 and data["summary"]["production_reports"] == 3
    assert api.read(topic="machines")["data"]["rows"][0]["effective_processing_hours"] == 1.25
    frozen = api.read()
    api.revise(saved, effective_processing_hours=1)
    assert_error(api.get(snapshot_ref=frozen["meta"]["snapshot_ref"]), "snapshot_stale")
    assert api.read()["data"]["rows"][0]["effective_processing_hours"] == 1.5
    with api.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM OperationExecutionEvents").fetchone()[0] == 0
    assert not any(sql.lstrip().split()[0].upper() in ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE") for sql in api.statements)


def test_read_invokes_one_authoritative_projection_at_frozen_clock(report_ledger_api, monkeypatch):
    api = report_ledger_api
    api.create(api.values(4))
    calls = []
    original = ExecutionLedgerService.workspace_projection

    def counted(self, *args, **kwargs):
        calls.append(self.clock().isoformat(timespec="seconds"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ExecutionLedgerService, "workspace_projection", counted)
    first = api.read()
    assert calls == [first["meta"]["as_of"]]
    again = api.read(snapshot_ref=first["meta"]["snapshot_ref"])
    assert calls == [first["meta"]["as_of"]] * 2 and first["data"] == again["data"]


@pytest.mark.parametrize("quantity", [None, 0, 10])
def test_legacy_complete_is_not_redefined_by_quantity_or_quality(report_ledger_api, quantity):
    api = report_ledger_api
    with api.db() as conn:
        case = LedgerCase(conn)
        case.event(1, "start")
        case.event(1, "finish", quantity=quantity)
        old = [tuple(row) for row in conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]
    data = api.read()["data"]
    row = data["rows"][0]
    assert row["complete"] and row["completion_basis"] == "legacy_finish_event"
    assert row["known_completed_quantity"] == (quantity or 0)
    assert row["data_quality"] == ("invalid" if quantity == 0 else "legacy_incomplete")
    assert data["summary"]["production_reports"] == 0
    records = api.read(topic="records")["data"]["rows"]
    assert all(row["recorded_at_time_basis"] == "legacy_storage" for row in records)
    assert all(row["report_ref"] is None and row["effective_processing_hours"] is None for row in records)
    with api.db() as conn:
        assert old == [tuple(row) for row in conn.execute("SELECT * FROM OperationExecutionEvents ORDER BY id")]


def test_external_reports_no_internal_resource_inference(report_ledger_api):
    api = report_ledger_api
    with api.db() as conn:
        conn.execute("UPDATE BatchOperations SET source='external' WHERE id=1")
    api.create(api.values(10, actual_machine_ref=None, actual_operator_ref=None))
    row = api.read()["data"]["rows"][0]
    assert row["complete"] and row["records_complete"] and row["data_quality"] == "complete"
    records = api.read(topic="records")["data"]["rows"]
    assert records[0]["machine_ref"] is None and records[0]["operator_ref"] is None


def test_resource_hours_count_internal_work_and_external_is_not_unassigned(report_ledger_api):
    api = report_ledger_api
    with api.db() as conn:
        second = LedgerCase(conn).op("OP2", seq=2)
        conn.execute("UPDATE BatchOperations SET source='external' WHERE id=1")
        conn.execute("UPDATE Schedule SET machine_id=NULL,operator_id=NULL WHERE op_id=1")
        conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (1,?,'M1','O1',?,?)",
                     (second, "2026-09-09T10:00:00", "2026-09-09T11:00:00"))
    api.create(api.values(10, actual_machine_ref=None, actual_operator_ref=None, effective_processing_hours=None))
    api.create(api.values(10, actual_start="2026-09-09T10:00:00", actual_end="2026-09-09T11:00:00",
                          actual_machine_ref=None, effective_processing_hours=.5), op=second)
    # 外协不占本厂设备和人员：资源工时只统计自制；「未填写」只剩漏填设备的自制报工，下钻结果与之一致。
    machines = api.read(topic="machines")["data"]["rows"]
    assert [(row["resource_label"], row["production_reports"], row["effective_processing_hours"]) for row in machines] == [("未填写", 1, .5)]
    assert [(row["resource_label"], row["production_reports"]) for row in api.read(topic="people")["data"]["rows"]] == [("Operator", 1)]
    drilled = api.read(topic="records", resource_type="machine", resource_ref="unassigned")["data"]["rows"]
    assert [row["operation_ref"] for row in drilled] == [api.task(second)["operation_ref"]]
    assert len(api.read(topic="records")["data"]["rows"]) == 2


def test_old_external_record_with_machine_is_neither_summed_nor_drilled_by_that_machine(report_ledger_api, monkeypatch):
    from core.services.workbench.execution import production_report_validation

    api = report_ledger_api
    with api.db() as conn:
        conn.execute("UPDATE BatchOperations SET source='external' WHERE id=1")
        conn.execute("UPDATE Schedule SET machine_id=NULL,operator_id=NULL WHERE op_id=1")
    # 修复前写入的旧外协报工带了本厂设备：资源工时汇总不算它，按这台设备下钻也不该出现。
    monkeypatch.setattr(production_report_validation, "_reject_external_resources", lambda operation, values: None)
    api.create(api.values(10, effective_processing_hours=.5))
    monkeypatch.undo()
    assert api.read(topic="machines")["data"]["rows"] == []
    machine_ref = api.read(topic="records")["data"]["rows"][0]["machine_ref"]
    assert machine_ref is not None
    for kind, ref in (("machine", machine_ref), ("machine", "unassigned")):
        assert api.read(topic="records", resource_type=kind, resource_ref=ref)["data"]["rows"] == []
