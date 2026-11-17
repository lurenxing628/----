"""Snapshot source capture preserves exact instance rules and evaluates registered members once."""

from collections import Counter

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.dashboard.external import load_external
from core.services.workbench.dashboard.external_handling import DashboardExternalHandling
from core.services.workbench.dashboard.policy import read_stored
from core.services.workbench.outsourcing.source import WorkbenchOutsourcingSourceService
from data.repositories.workbench_dashboard_repo import WorkbenchDashboardRepository
from tests.workbench.dashboard_external_handling_support import (
    external_handling_case as _handling_case,  # noqa: F401
)
from tests.workbench.dashboard_external_support import (
    external_case as _external_case,  # noqa: F401
)
from tests.workbench.dashboard_support import NOW
from tests.workbench.dashboard_support import (
    dashboard_case as _dashboard_case,  # noqa: F401
)


def _resolved(source, target):
    try:
        return source.load(target)
    except WorkbenchCommandRejected as exc:
        return exc.code, str(exc), exc.status


def _same_sources(source, targets):
    revision = source.repo.plan_identity_revision()
    expected = [
        _resolved(source.capture([target], revision=revision), target)
        for target in targets
    ]
    captured = source.capture(targets, revision=revision)
    assert [_resolved(captured, target) for target in targets] == expected
    return captured


@pytest.mark.parametrize("history", (False, True))
def test_detail_and_history_capture_all_receipt_operations_once(
    external_handling_case, history, monkeypatch
):
    case, conn = external_handling_case, external_handling_case.conn
    ref = case.register(merged=True)
    reader = case.shipments.reader
    load_kwargs = []
    bound = []
    original_load = WorkbenchOutsourcingSourceService.load

    def counted_load(self, target, **kwargs):
        load_kwargs.append(kwargs)
        return original_load(self, target, **kwargs)

    monkeypatch.setattr(WorkbenchOutsourcingSourceService, "load", counted_load)
    queries = []
    with reader.read_snapshot():
        conn.set_trace_callback(queries.append)
        try:
            result = (
                reader.history(ref, as_of=NOW, bind_snapshot=bound.append)
                if history
                else reader.detail(ref, as_of=NOW, bind_snapshot=bound.append)
            )
        finally:
            conn.set_trace_callback(None)
    assert "content" not in result
    assert result["item"]["source_state"] == "current"
    assert len(result["item"]["target"]["operations"]) == 2
    assert "source_resolution" not in result["item"]["target"]
    assert load_kwargs == [{"projection": "identity"}]
    assert len(bound) == 1 and set(bound[0]) == {"revisions", "clock"}
    assert sum("SELECT revision FROM WorkbenchPlanIdentityClock" in sql for sql in queries) == 1, queries
    assert sum("SELECT * FROM WorkbenchPlanSourceRefs" in sql for sql in queries) == 1, queries
    assert sum("JOIN WorkbenchOutsourcingReceipts r" in sql for sql in queries) == 1, queries
    assert not any(
        "WorkbenchOutsourcingOperationOrigins" in sql
        or "WorkbenchOutsourcingSourceConfirmations" in sql
        or "source_facts_json" in sql
        for sql in queries
    )
    assert sum('JOIN "BatchOperations" source' in sql for sql in queries) == 1, queries
    if history:
        assert len(result["history"]["items"]) == 1
    else:
        assert not any("WorkbenchOutsourcingFacts" in sql for sql in queries)


def test_snapshot_capture_preserves_instance_rules_and_single_registered_evaluation(
    external_handling_case, monkeypatch
):
    case, conn = external_handling_case, external_handling_case.conn
    source = WorkbenchOutsourcingSourceService(conn)
    target = case.shipments.payload(merged=True)["target"]
    with case.shipments.reader.read_snapshot():
        before = _same_sources(source, [target])
        assert "source_resolution" not in before.load(target)["public"]

    ref = case.register(merged=True)
    reader = case.shipments.reader
    with reader.read_snapshot():
        registered = reader.admitted_receipt(ref)[0]["target"]
        captured = _same_sources(source, [registered])
        expected_registered = captured.load(registered)
        assert "source_resolution" not in expected_registered["public"]
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
        targets_data = reader.targets(
            batch_ref=target["batch_ref"], bind_snapshot=lambda _content: None
        )
        conn.set_trace_callback(None)
        assert all("source_resolution" not in item for item in targets_data["items"])
        assert not any(sql.startswith("PRAGMA table_info") for sql in selected_queries)
        assert (
            sum("SELECT revision FROM WorkbenchPlanIdentityClock" in sql for sql in selected_queries)
            == 1
        )

    calls = Counter()
    original_load = WorkbenchOutsourcingSourceService.load

    def counted(self, target, **kwargs):
        calls[tuple(target["operation_refs"])] += 1
        return original_load(self, target, **kwargs)

    monkeypatch.setattr(WorkbenchOutsourcingSourceService, "load", counted)
    with reader.read_snapshot():
        changed = conn.total_changes
        result, receipts = load_external(conn, NOW)
        stored, _ = read_stored(WorkbenchDashboardRepository(conn))
        DashboardExternalHandling(conn).read(result, receipts, stored)
        assert conn.total_changes == changed
        assert calls[tuple(registered["operation_refs"])] == 1
        assert len(calls) == 2  # One merged receipt and one remaining unregistered operation.
        assert result["unregistered_count"] == 1
        assert result["receipt_count"] == result["current_receipt_count"] == 1


def test_targets_page_slices_before_source_projection_and_binds_revisions(
    external_handling_case, monkeypatch
):
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
    target_bound = []
    target_queries = []
    with reader.read_snapshot():
        conn.set_trace_callback(target_queries.append)
        try:
            paged = reader.targets(number=1, size=20, bind_snapshot=target_bound.append)
        finally:
            conn.set_trace_callback(None)
    target_kwargs = list(load_kwargs)
    case.register(merged=True)
    load_kwargs.clear()
    receipt_bound = []
    with reader.read_snapshot():
        listed = reader.receipts(number=1, size=20, as_of=NOW, bind_snapshot=receipt_bound.append)
    receipt_kwargs = list(load_kwargs)
    assert "content" not in paged and "content" not in listed
    assert len(paged["items"]) == 20
    assert paged["page"]["total"] == 53
    assert len(target_kwargs) == 20
    assert len(receipt_kwargs) == 1
    assert all(kw == {"projection": "target_row"} for kw in target_kwargs)
    assert all(kw == {"projection": "identity"} for kw in receipt_kwargs)
    assert all("source_resolution" not in item for item in paged["items"])
    assert sum("WHERE o.id IN (SELECT value FROM json_each(" in sql for sql in target_queries) == 1
    assert len(target_bound) == 1 and set(target_bound[0]) == {"revisions", "clock", "query"}
    assert len(receipt_bound) == 1 and set(receipt_bound[0]) == {"revisions", "clock"}


def test_receipts_list_paginates_in_sql_and_reads_only_current_page_rows(
    external_handling_case, monkeypatch
):
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
    repo_header_decode_calls = []
    orig_repo_header = WorkbenchOutsourcingRepository._header

    def counted_repo_header(row, members):
        repo_header_decode_calls.append(row["outsourcing_ref"])
        return orig_repo_header(row, members)

    monkeypatch.setattr(
        WorkbenchOutsourcingRepository, "_header", staticmethod(counted_repo_header)
    )
    queries = []
    with reader.read_snapshot():
        conn.set_trace_callback(queries.append)
        try:
            unmatched = reader.receipts(
                status="returned", number=1, size=20, as_of=NOW, bind_snapshot=lambda _content: None
            )
        finally:
            conn.set_trace_callback(None)
    assert unmatched["items"] == [] and unmatched["page"]["total"] == 0
    assert repo_header_decode_calls == []
    assert not any("WorkbenchOutsourcingFacts" in sql for sql in queries)
    assert not any("WorkbenchOutsourcingMembers" in sql for sql in queries)
    assert not any("LIMIT " in sql and "WorkbenchOutsourcingReceipts" in sql for sql in queries)

    queries.clear()
    with reader.read_snapshot():
        conn.set_trace_callback(queries.append)
        try:
            empty_page = reader.receipts(
                status="awaiting", number=10, size=2, as_of=NOW, bind_snapshot=lambda _content: None
            )
        finally:
            conn.set_trace_callback(None)
    assert empty_page["items"] == [] and empty_page["page"]["total"] == 10
    assert repo_header_decode_calls == []
    assert not any("WorkbenchOutsourcingFacts" in sql for sql in queries)
    assert not any("WorkbenchOutsourcingMembers" in sql for sql in queries)

    queries.clear()
    with reader.read_snapshot():
        conn.set_trace_callback(queries.append)
        try:
            paged = reader.receipts(
                status="awaiting", number=2, size=2, as_of=NOW, bind_snapshot=lambda _content: None
            )
        finally:
            conn.set_trace_callback(None)
    page_refs = [item["outsourcing_ref"] for item in paged["items"]]
    all_refs = [
        row[0]
        for row in conn.execute(
            "SELECT outsourcing_ref FROM WorkbenchOutsourcingReceipts ORDER BY outsourcing_ref"
        )
    ]
    assert paged["page"]["total"] == 10 and page_refs == all_refs[2:4]
    assert repo_header_decode_calls == page_refs
    assert not any("WorkbenchOutsourcingFacts" in sql for sql in queries)
    assert (
        sum(
            "SELECT * FROM WorkbenchOutsourcingReceipts WHERE returned IS NULL "
            "ORDER BY outsourcing_ref LIMIT 2 OFFSET 2" in sql
            for sql in queries
        )
        == 1
    )
    assert sum("FROM WorkbenchOutsourcingMembers WHERE outsourcing_ref IN" in sql for sql in queries) == 1


def test_dashboard_deferred_scoped_projection_skips_unretained_returned_receipts_without_extra_sql(
    external_handling_case, monkeypatch
):
    from core.services.workbench.outsourcing.source import AdmittedReceiptSource
    from core.shared.strict_json import canonical_json
    from tests.workbench.dashboard_support import follow

    case, conn = external_handling_case, external_handling_case.conn
    long_remark = "备" * 5000
    conn.executemany(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
        "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)",
        [("XO4", 4), ("XO5", 5)],
    )
    conn.execute("UPDATE Batches SET remark=? WHERE batch_id='XB1'", (long_remark,))
    conn.execute("UPDATE Suppliers SET remark=? WHERE supplier_id='XS1'", (long_remark,))
    conn.commit()

    # Register XO4 first, record a dashboard handling transition on it, then mark it returned:
    # it stays retained on the dashboard via saved handling state.
    ref_handled_returned = case.register(index=4)
    handled_item = next(
        row
        for row in case.read()[0]["items"]
        if row["category"] == "external"
        and row["source"]["outsourcing_ref"] == ref_handled_returned
    )
    case.command(handled_item, follow(), key="deferred-scoped-handled-returned")
    case.returned(ref_handled_returned)

    # Register two returned receipts without handling (unretained) and one awaiting receipt (retained); XO5 stays unregistered.
    ref_returned_1 = case.register(index=1)
    case.returned(ref_returned_1)
    ref_returned_2 = case.register(index=2)
    case.returned(ref_returned_2)
    ref_awaiting = case.register(index=3)

    load_modes = {}
    load_counts = Counter()
    scoped_targets = []
    post_capture_sql = []
    orig_load = WorkbenchOutsourcingSourceService.load
    orig_to_scoped = AdmittedReceiptSource.to_scoped_source

    def tracked_load(self, target, **kwargs):
        key = tuple(target["operation_refs"])
        load_counts[key] += 1
        load_modes[key] = kwargs
        conn.set_trace_callback(post_capture_sql.append)
        try:
            return orig_load(self, target, **kwargs)
        finally:
            conn.set_trace_callback(None)

    def tracked_to_scoped(self):
        scoped_targets.append(tuple(op["identity"]["ref"] for op in self.operations))
        conn.set_trace_callback(post_capture_sql.append)
        try:
            return orig_to_scoped(self)
        finally:
            conn.set_trace_callback(None)

    monkeypatch.setattr(WorkbenchOutsourcingSourceService, "load", tracked_load)
    monkeypatch.setattr(AdmittedReceiptSource, "to_scoped_source", tracked_to_scoped)

    dashboard_queries = []
    with case.shipments.reader.read_snapshot():
        conn.set_trace_callback(dashboard_queries.append)
        try:
            summary, receipts = load_external(conn, NOW)
            stored, _ = read_stored(WorkbenchDashboardRepository(conn))
            observations, _ = DashboardExternalHandling(conn).read(summary, receipts, stored)
        finally:
            conn.set_trace_callback(None)

    assert not any("WorkbenchOutsourcingFacts" in sql for sql in dashboard_queries)

    op_ref = case.shipments.operation_ref
    assert dict(load_counts) == {
        (op_ref("XO1"),): 1,
        (op_ref("XO2"),): 1,
        (op_ref("XO3"),): 1,
        (op_ref("XO4"),): 1,
        (op_ref("XO5"),): 1,
    }
    for code in ("XO1", "XO2", "XO3", "XO4"):
        assert load_modes[(op_ref(code),)] == {"projection": "deferred_scoped"}
    assert load_modes[(op_ref("XO5"),)] == {"projection": "target_row"}

    assert set(scoped_targets) == {(op_ref("XO3"),), (op_ref("XO4"),)}
    assert len(scoped_targets) == 2
    assert post_capture_sql == []
    assert {item["anchor_ref"] for item, _, _ in observations} == {
        ref_awaiting,
        ref_handled_returned,
    }
    for item, _, _ in observations:
        assert "_facts" not in item and "source_revision" in item["_guard"]
        revision = item["_guard"]["source_revision"]
        assert set(revision) == {"latest_fact_ref", "identity", "revisions"}
        assert set(revision["revisions"]) == {"batch", "part", "supplier", "operations"}
        serialized = canonical_json(revision)
        assert long_remark not in serialized and "备" * 10 not in serialized
        assert len(serialized.encode("utf-8")) < 2048

    # Mutating Batches.remark advances entity revision and invalidates the compact external write_token.
    awaiting_item = next(
        row
        for row in case.read()[0]["items"]
        if row["category"] == "external"
        and row["source"]["outsourcing_ref"] == ref_awaiting
    )
    conn.execute("UPDATE Batches SET remark='updated short remark' WHERE batch_id='XB1'")
    conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as stale_exc:
        case.command(awaiting_item, follow(), key="deferred-scoped-stale-after-batch-remark")
    assert stale_exc.value.code == "stale_write"


def test_sql_pagination_filters_and_member_batch_drift_without_legacy_tables(
    external_handling_case,
):
    case, conn = external_handling_case, external_handling_case.conn
    conn.execute(
        "INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_date,ready_status) "
        "VALUES ('xb1','XP1','Part',5,'2026-09-11','2026-09-01','yes')"
    )
    conn.execute(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
        "VALUES ('XO-LOWER','xb1',1,'XT1','Special Nitriding','external','XS1',2)"
    )
    conn.commit()

    ref_overdue = case.register(index=1)
    ref_returned = case.register(index=2)
    case.returned(ref_returned)
    ref_future = case.register(index=3, planned="2026-09-12T12:00:00")
    reader = case.shipments.reader
    xb1_upper_ref = case.shipments.entity_ref("batch", "XB1")

    with reader.read_snapshot():
        # Exact batch_ref filter uses index range + binary equality without mixing 'xb1' into 'XB1'.
        xb1_targets = reader.targets(
            batch_ref=xb1_upper_ref, bind_snapshot=lambda _content: None
        )
        assert [row["business_code"] for row in xb1_targets["items"]] == ["XO1", "XO2", "XO3"]
        searched = reader.targets(query="nitriding", bind_snapshot=lambda _content: None)
        assert [row["business_code"] for row in searched["items"]] == ["XO-LOWER"]
        empty_targets = reader.targets(query="nonexistent-op", bind_snapshot=lambda _content: None)
        assert empty_targets["items"] == [] and empty_targets["page"]["total"] == 0

        overdue_page = reader.receipts(status="overdue", as_of=NOW, bind_snapshot=lambda _content: None)
        returned_page = reader.receipts(status="returned", as_of=NOW, bind_snapshot=lambda _content: None)
        awaiting_page = reader.receipts(status="awaiting", as_of=NOW, bind_snapshot=lambda _content: None)
        assert [row["outsourcing_ref"] for row in overdue_page["items"]] == [ref_overdue]
        assert [row["outsourcing_ref"] for row in returned_page["items"]] == [ref_returned]
        assert {row["outsourcing_ref"] for row in awaiting_page["items"]} == {
            ref_overdue,
            ref_future,
        }

    # Reassigning a registered member operation to another batch instance triggers identity_drift via Members JOIN Receipts.
    conn.execute("UPDATE BatchOperations SET batch_id='xb1' WHERE op_code='XO1'")
    conn.commit()
    with reader.read_snapshot():
        drifted_detail = reader.detail(ref_overdue, as_of=NOW, bind_snapshot=lambda _content: None)["item"]
        assert drifted_detail["source_state"] == "source_unavailable"
        assert drifted_detail["issues"][0]["code"] == "identity_drift"
        assert "工序所属批次实例已变化" in drifted_detail["issues"][0]["message"]
