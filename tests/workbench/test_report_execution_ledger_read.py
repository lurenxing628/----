"""Full registered Flask app: new production reports reach every report read."""

import pytest

from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.workbench.plan_read_support import assert_error
from tests.workbench.report_execution_ledger_support import report_ledger_api as _fixture
from tests.workbench.test_execution_ledger_support import LedgerCase


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
