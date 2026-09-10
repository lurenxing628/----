"""The central provider reads 10000 tasks with bounded SQL, never N+1 ledgers."""

import ast
from pathlib import Path

from core.services.execution.ledger_reader import ExecutionLedgerReader
from tests.workbench.scheduler_execution_ledger_support import ledger_case as ledger_fixture
from tests.workbench.scheduler_execution_ledger_support import read_facts


def test_ten_thousand_tasks_use_one_loaded_projection_and_bounded_sql(ledger_case, monkeypatch):
    case = ledger_case
    ids = [case.op_id] + [case.op("BULK-" + str(index), seq=index) for index in range(2, 10001)]
    case.plan(2, ids)
    case.install()
    case.command("create", case.task(2, case.op_id), case.values(4))
    calls, statements, steps = [], [], []
    original = ExecutionLedgerReader.project_loaded

    def counted(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ExecutionLedgerReader, "project_loaded", counted)
    case.conn.execute("PRAGMA query_only=ON")
    case.conn.set_trace_callback(statements.append)
    case.conn.set_progress_handler(lambda: steps.append(1) or 0, 10000)
    try:
        facts = read_facts(case.conn, 2)
    finally:
        case.conn.set_trace_callback(None)
        case.conn.set_progress_handler(None, 0)
    assert len(facts) == 10000 and calls == [1]
    assert facts[case.op_id].ledger_execution_state == "partial"
    assert sum(fact.actual_status == "not_started" for fact in facts.values()) == 9999
    selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
    assert len(selects) < 450, len(selects)
    assert len(steps) * 10000 < 18000000, len(steps) * 10000
    report_reads = [sql for sql in selects if "JOIN WorkbenchProductionReportRevisions v" in sql]
    assert len(report_reads) == 34
    print(f"10000 tasks: projections={len(calls)}, SELECTs={len(selects)}, "
          f"report_reads={len(report_reads)}, VM_steps={len(steps) * 10000}")


def test_adapter_python38_syntax():
    root = Path(__file__).resolve().parents[2]
    paths = list(root.glob("core/services/scheduler/execution/execution_ledger*.py"))
    paths.append(root / "core/services/scheduler/execution/execution_fact_provider.py")
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 8))
