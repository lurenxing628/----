"""Bounded SQL and snapshot preservation at the admitted full operation count."""

from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests.workbench.report_execution_ledger_support import report_ledger_api as _fixture
from tests.workbench.test_execution_ledger_support import LedgerCase


def test_ten_thousand_operations_one_projection_no_n_plus_one(report_ledger_api, monkeypatch):
    api = report_ledger_api
    with api.db() as conn:
        case = LedgerCase(conn)
        ids = [1] + [case.op("BULK-" + str(index), seq=index) for index in range(2, 10001)]
        case.plan(2, ids)
        case.command("create", case.task(2, 1), case.values(4))
    calls = []
    original = ExecutionLedgerService.project_loaded

    def counted(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ExecutionLedgerService, "project_loaded", counted)
    api.statements.clear()
    first = api.read(size=50)
    assert first["data"]["summary"]["operations"] == 10000 and len(first["data"]["rows"]) == 50
    assert first["data"]["summary"]["production_reports"] == 1 and calls == [1]
    selects = [sql for sql in api.statements if sql.lstrip().upper().startswith("SELECT")]
    report_reads = [sql for sql in selects if "JOIN WorkbenchProductionReportRevisions v" in sql]
    assert len(report_reads) == 34 and len(selects) < 550, len(selects)
    print(f"10000 report operations: projections={len(calls):d} SELECTs={len(selects):d} report_reads={len(report_reads):d}")
