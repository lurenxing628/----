"""Frozen domain time, explicit limits, and coherent concurrent SQLite snapshots."""

from datetime import datetime

import pytest

from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.workbench.plan_read_support import assert_error
from tests.workbench.report_execution_ledger_support import report_ledger_api as _fixture
from tests.workbench.test_execution_ledger_support import LedgerCase
from web.routes.workbench import read_context


def test_reused_snapshot_freezes_legacy_validity_not_only_due_age(report_ledger_api, monkeypatch):
    api = report_ledger_api
    with api.db() as conn:
        case = LedgerCase(conn)
        case.event(1, "start")
        case.event(1, "finish", quantity=10)

    class Early(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 9, 9, 9)

    class Later(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 9, 9, 12)

    monkeypatch.setattr(read_context, "datetime", Early)
    first = api.read()
    assert first["data"]["rows"][0]["complete"] is False
    monkeypatch.setattr(read_context, "datetime", Later)
    frozen = api.read(snapshot_ref=first["meta"]["snapshot_ref"])
    assert frozen["data"] == first["data"]
    assert api.read()["data"]["rows"][0]["complete"] is True


def test_concurrent_append_never_mixes_plan_ledger_and_snapshot(report_ledger_api, monkeypatch):
    api = report_ledger_api
    with api.db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
    original = ExecutionLedgerService.workspace_projection
    appended = []

    def append_after_read(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if not appended:
            with api.db() as conn:
                case = LedgerCase(conn)
                case.command("create", case.task(1, 1), case.values(4))
            appended.append(True)
        return result

    monkeypatch.setattr(ExecutionLedgerService, "workspace_projection", append_after_read)
    first = api.read()
    assert first["data"]["summary"]["production_reports"] == 0
    assert_error(api.get(snapshot_ref=first["meta"]["snapshot_ref"]), "snapshot_stale")
    assert api.read()["data"]["summary"]["production_reports"] == 1


def test_xlsx_refuses_oversized_history_instead_of_truncating(report_ledger_api):
    api = report_ledger_api
    report = api.create(api.values(4, remark="x" * 2000))
    for index in range(8):
        api.revise(report, remark=str(index) + "x" * 1999)
    first = api.read(topic="records")
    token = first["meta"]["snapshot_ref"]
    assert_error(api.get("/export", topic="records", snapshot_ref=token, format="xlsx"), "export_too_large", 413)
    csv = api.get("/export", topic="records", snapshot_ref=token, format="csv")
    assert csv.status_code == 200 and len(csv.data) > 32767


@pytest.mark.parametrize("damage", ["DROP TABLE WorkbenchExecutionLedgerClock", "DROP INDEX idx_wb_execution_reports_operation"])
def test_missing_or_damaged_ledger_is_not_legacy_fallback(report_ledger_api, damage):
    api = report_ledger_api
    with api.db() as conn:
        conn.execute(damage)
    before = api.state()
    assert_error(api.get(), "execution_ledger_unavailable")
    assert api.state() == before
