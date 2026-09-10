"""Real SQLite row/statement/VM bounds, not mocked repository counts."""

import ast
from pathlib import Path

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture


def test_five_thousand_rows_preview_is_read_only_bounded_and_complete(ledger_case):
    case = ledger_case
    case.conn.execute("UPDATE Batches SET quantity=5000 WHERE batch_id='B1'")
    case.conn.commit()
    case.install()
    task = case.task(1, case.op_id)
    items = [{"action": "create", "ref": task, "payload": case.values(1, source="excel", report_no=f"SCALE-{i:04d}")} for i in range(5000)]
    statements, steps = [], []
    before = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    case.conn.set_trace_callback(statements.append)
    case.conn.set_progress_handler(lambda: steps.append(1) or 0, 1000)
    preview = case.writer.preview_batch(items)
    case.conn.set_trace_callback(None)
    case.conn.set_progress_handler(None, 0)
    case.conn.execute("PRAGMA query_only=OFF")
    selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
    assert len(selects) < 120
    assert len(steps) * 1000 < 500000
    assert preview["summary"] == {"total": 5000, "changed": 5000, "unchanged": 0}
    assert preview["projections"][0]["execution_state"] == "complete"
    assert all_rows(case.conn) == before
    result = case.writer.execute_batch(items, context_ref=case.plan_ref(1), request_key="ledger-five-thousand", validate_context=lambda *_: None)
    assert result["data"]["summary"]["changed"] == 5000
    assert case.ledger.get_task(task).known_completed_quantity == 5000
    second = case.writer.preview_batch(items)
    assert second["summary"]["unchanged"] == 5000


def test_ten_thousand_operation_projection_uses_chunked_sql(ledger_case):
    case = ledger_case
    ids = [case.op_id]
    for i in range(2, 10001):
        ids.append(case.op(f"BULK-{i}", seq=i))
    case.plan(2, ids)
    case.install()
    refs = [row[0] for row in case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")]
    statements, steps = [], []
    case.conn.execute("PRAGMA query_only=ON")
    case.conn.set_trace_callback(statements.append)
    case.conn.set_progress_handler(lambda: steps.append(1) or 0, 10000)
    result = case.ledger.project_operations(refs)
    case.conn.set_trace_callback(None)
    case.conn.set_progress_handler(None, 0)
    assert len(result) == 10000
    assert all(row.execution_state == "unreported" and row.known_completed_quantity == 0 for row in result)
    selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
    assert len(selects) < 260
    assert len(steps) * 10000 < 15000000
    joins = [sql for sql in selects if "bo.*, b.quantity" in sql]
    assert joins
    assert all("SCAN bo" not in str(tuple(row)) for sql in joins[:1] for row in case.conn.execute("EXPLAIN QUERY PLAN " + sql))
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.ledger.project_operations(refs + ["f" * 48])
    assert error.value.code == "query_too_large"


def test_new_runtime_sources_parse_as_python38():
    root = Path(__file__).resolve().parents[2]
    files = list(root.glob("core/models/workbench_execution*.py"))
    files += list(root.glob("core/services/workbench/execution_ledger*.py"))
    files += list(root.glob("core/services/workbench/production_report*.py"))
    files += list(root.glob("data/repositories/workbench_execution*.py"))
    files += [root / "core/infrastructure/workbench_execution_ledger_schema.py"]
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 8))
