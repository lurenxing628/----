"""Snapshot source capture preserves exact instance rules and evaluates registered members once."""

from collections import Counter

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.dashboard.external import load_external
from core.services.workbench.dashboard.external_handling import DashboardExternalHandling
from core.services.workbench.outsourcing.source import WorkbenchOutsourcingSourceService
from tests.workbench.dashboard_external_handling_support import external_handling_case as _handling_case  # noqa: F401
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_support import NOW
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401


def _resolved(source, target):
    try:
        return source.load(target)
    except WorkbenchCommandRejected as exc:
        return exc.code, str(exc), exc.status


def _same_sources(source, targets):
    expected = [_resolved(source.capture([target]), target) for target in targets]
    captured = source.capture(targets)
    assert [_resolved(captured, target) for target in targets] == expected
    return captured


@pytest.mark.parametrize("history", (False, True))
def test_detail_and_history_capture_all_receipt_operations_once(external_handling_case, history):
    case, conn = external_handling_case, external_handling_case.conn
    ref = case.register(merged=True)
    reader = case.shipments.reader
    queries = []
    with reader.read_snapshot():
        conn.set_trace_callback(queries.append)
        try:
            result = reader.history(ref) if history else reader.detail(ref)
        finally:
            conn.set_trace_callback(None)
    assert result["item"]["source_state"] == "current"
    source = result["content"]["source"]
    assert len(source["public"]["operations"]) == 2
    for table in ("WorkbenchPlanSourceRefs", "WorkbenchOutsourcingOperationOrigins", "WorkbenchOutsourcingSourceConfirmations"):
        assert sum("SELECT * FROM " + table in sql for sql in queries) == 1, queries
    assert sum('JOIN "BatchOperations" source' in sql for sql in queries) == 1, queries
    if history:
        assert len(result["history"]["items"]) == 1


def test_snapshot_capture_preserves_instance_rules_and_single_registered_evaluation(external_handling_case, monkeypatch):
    case, conn = external_handling_case, external_handling_case.conn
    source = WorkbenchOutsourcingSourceService(conn)
    target = case.shipments.payload(merged=True)["target"]
    with case.shipments.reader.read_snapshot():
        before = _same_sources(source, [target])
        assert before.load(target)["public"]["source_resolution"]["basis"] == "birth_record"

    ref = case.register(merged=True)
    reader = case.shipments.reader
    with reader.read_snapshot():
        registered = reader.header(ref)["target"]
        captured = _same_sources(source, [registered])
        assert captured.load(registered)["public"]["source_resolution"]["basis"] == "birth_record"
        expected_registered = captured.load(registered)
        # The captured projection may execute no SQL and may not fill misses from the live repository.
        captured_queries = []
        conn.set_trace_callback(captured_queries.append)
        try:
            assert _resolved(captured, registered) == expected_registered
            assert captured.repo.source_row("operation", "not-a-captured-key") is None
        finally:
            conn.set_trace_callback(None)
        assert captured_queries == []
        selected_queries = []
        conn.set_trace_callback(selected_queries.append)
        reader.targets(batch_ref=target["batch_ref"])
        conn.set_trace_callback(None)
        assert sum(sql.startswith('PRAGMA table_info("Batches")') for sql in selected_queries) == 0
        assert sum("SELECT revision FROM WorkbenchPlanIdentityClock" in sql for sql in selected_queries) == 1

    calls = Counter()
    original_load = WorkbenchOutsourcingSourceService.load

    def counted(self, target, **kwargs):
        calls[tuple(target["operation_refs"])] += 1
        return original_load(self, target, **kwargs)

    monkeypatch.setattr(WorkbenchOutsourcingSourceService, "load", counted)
    with reader.read_snapshot():
        changed = conn.total_changes
        result, contents, receipts = load_external(conn, NOW)
        DashboardExternalHandling(conn).read(result, receipts)
        assert conn.total_changes == changed
        assert calls[tuple(registered["operation_refs"])] == 1
        assert len(calls) == 2  # One merged receipt and one remaining unregistered operation.
        assert len(contents["targets"]["targets"]) == result["unregistered_count"] == 1
        assert result["receipt_count"] == result["current_receipt_count"] == 1
