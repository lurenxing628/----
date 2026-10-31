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
        assert sum(sql.startswith('PRAGMA table_info("Batches")') for sql in selected_queries) == 1
        assert sum("SELECT revision FROM WorkbenchPlanIdentityClock" in sql for sql in selected_queries) == 1

    calls = Counter()
    original_load = WorkbenchOutsourcingSourceService.load

    def counted(self, target, **kwargs):
        calls[tuple(target["operation_refs"])] += 1
        return original_load(self, target, **kwargs)

    monkeypatch.setattr(WorkbenchOutsourcingSourceService, "load", counted)
    with reader.read_snapshot():
        changed = conn.total_changes
        result, receipts = load_external(conn, NOW)
        DashboardExternalHandling(conn).read(result, receipts)
        assert conn.total_changes == changed
        assert calls[tuple(registered["operation_refs"])] == 1
        assert len(calls) == 2  # One merged receipt and one remaining unregistered operation.
        assert result["unregistered_count"] == 1
        assert result["receipt_count"] == result["current_receipt_count"] == 1


def test_targets_page_slices_before_source_projection_and_binds_revisions(external_handling_case, monkeypatch):
    case, conn = external_handling_case, external_handling_case.conn
    conn.executemany(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
        "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)",
        [(f"OP-PAGE-{idx:03d}", 100 + idx) for idx in range(50)],
    )
    conn.commit()
    reader = case.shipments.reader
    load_calls = []
    load_kwargs = []
    original_load = WorkbenchOutsourcingSourceService.load

    def counted_load(self, target, **kwargs):
        load_calls.append(target["operation_refs"])
        load_kwargs.append(kwargs)
        return original_load(self, target, **kwargs)

    monkeypatch.setattr(WorkbenchOutsourcingSourceService, "load", counted_load)
    with reader.read_snapshot():
        paged = reader.targets(number=1, size=20)
    target_kwargs = list(load_kwargs)
    case.register(merged=True)
    load_kwargs.clear()
    with reader.read_snapshot():
        listed = reader.receipts(number=1, size=20)
    receipt_kwargs = list(load_kwargs)
    assert len(paged["items"]) == 20
    assert paged["page"]["total"] >= 50
    assert len(target_kwargs) == 20
    assert len(receipt_kwargs) == 1
    assert all(
        kw == {"include_snapshot_facts": False, "include_identity": False, "include_public_operations": False}
        for kw in target_kwargs
    )
    assert all(
        kw == {"include_snapshot_facts": False, "include_public": False}
        for kw in receipt_kwargs
    )
    assert set(paged["content"]) == {"revisions", "clock", "query"}
    assert set(listed["content"]) == {"revisions", "clock"}


def test_receipts_list_filters_and_slices_on_lightweight_facts_before_header_decode(external_handling_case, monkeypatch):
    from core.services.workbench.outsourcing.service import WorkbenchOutsourcingService
    from data.repositories.workbench_outsourcing_repo import WorkbenchOutsourcingRepository

    case, conn = external_handling_case, external_handling_case.conn
    conn.executemany(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
        "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)",
        [(f"XO{idx}", idx) for idx in range(4, 11)],
    )
    conn.commit()
    for idx in range(1, 11):
        case.register(index=idx)
    reader = case.shipments.reader
    header_calls = []
    repo_headers_calls = []
    repo_header_decode_calls = []
    orig_header_from_row = WorkbenchOutsourcingService.header_from_row
    orig_repo_headers = WorkbenchOutsourcingRepository.headers
    orig_repo_header = WorkbenchOutsourcingRepository._header

    def counted_header_from_row(header):
        header_calls.append(header["outsourcing_ref"] if header is not None else None)
        return orig_header_from_row(header)

    def counted_repo_headers(self, refs):
        refs_list = list(refs)
        repo_headers_calls.append(refs_list)
        return orig_repo_headers(self, refs_list)

    def counted_repo_header(row, members):
        repo_header_decode_calls.append(row["outsourcing_ref"])
        return orig_repo_header(row, members)

    monkeypatch.setattr(WorkbenchOutsourcingService, "header_from_row", staticmethod(counted_header_from_row))
    monkeypatch.setattr(WorkbenchOutsourcingRepository, "headers", counted_repo_headers)
    monkeypatch.setattr(WorkbenchOutsourcingRepository, "_header", staticmethod(counted_repo_header))
    queries = []
    with reader.read_snapshot():
        conn.set_trace_callback(queries.append)
        try:
            unmatched = reader.receipts(status="returned", number=1, size=20)
        finally:
            conn.set_trace_callback(None)
    assert unmatched["items"] == [] and unmatched["page"]["total"] == 0
    assert repo_headers_calls == []
    assert repo_header_decode_calls == []
    assert header_calls == []
    assert not any("before_json" in sql or "source_facts_json" in sql for sql in queries)
    assert not any("SELECT * FROM WorkbenchOutsourcingFacts" in sql or "SELECT f.* FROM WorkbenchOutsourcingFacts" in sql for sql in queries)
    assert not any("SELECT * FROM WorkbenchOutsourcingReceipts WHERE outsourcing_ref IN" in sql for sql in queries)
    assert not any("FROM WorkbenchOutsourcingMembers WHERE outsourcing_ref IN" in sql for sql in queries)

    queries.clear()
    with reader.read_snapshot():
        conn.set_trace_callback(queries.append)
        try:
            paged = reader.receipts(status="awaiting", number=2, size=2)
        finally:
            conn.set_trace_callback(None)
    page_refs = [item["outsourcing_ref"] for item in paged["items"]]
    assert paged["page"]["total"] == 10 and len(page_refs) == 2
    assert len(repo_headers_calls) == 1
    assert len(repo_headers_calls[0]) == 2 and set(repo_headers_calls[0]) == set(page_refs)
    assert len(repo_header_decode_calls) == 2 and set(repo_header_decode_calls) == set(page_refs)
    assert header_calls == page_refs
    assert not any("before_json" in sql or "source_facts_json" in sql for sql in queries)
    assert not any("SELECT * FROM WorkbenchOutsourcingFacts" in sql or "SELECT f.* FROM WorkbenchOutsourcingFacts" in sql for sql in queries)
    assert sum("SELECT * FROM WorkbenchOutsourcingReceipts WHERE outsourcing_ref IN" in sql for sql in queries) == 1

    # Corrupt receipt without a latest fact row is still detected even when filtered out by status.
    conn.execute(
        "INSERT INTO WorkbenchOutsourcingReceipts(outsourcing_ref,target_kind,batch_ref,supplier_ref,origin_json,identity_json,created_at) "
        "SELECT ?,target_kind,batch_ref,supplier_ref,origin_json,identity_json,created_at FROM WorkbenchOutsourcingReceipts LIMIT 1",
        ("f" * 48,),
    )
    conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as exc_info:
        with reader.read_snapshot():
            reader.receipts(status="returned", number=1, size=20)
    assert exc_info.value.code == "outsourcing_unavailable"
