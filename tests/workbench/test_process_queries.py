"""Real SQLite process reads; states, references and unknowns remain distinct."""

import sqlite3
from time import perf_counter

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_query import ProcessPageRequest
from core.services.process.workflow_state import record_confirmation
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_query_support import process_read_database, ref_for, stored


def test_existing_template_values_groups_and_stage_are_truthful_and_readonly(process_read_conn):
    conn = process_read_conn
    before, changes = stored(conn), conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    try:
        reader = WorkbenchProcessQueryService(conn)
        with reader.read_snapshot():
            data = reader.page(ProcessPageRequest())
            entity = reader.detail(ref_for(conn))
        assert data["metrics"]["counts"] == {"total": 5, "route": 3, "source": 2, "hours": 0, "ready": 0}
        assert entity["workflow"]["source"] == {"state": "unconfirmed", "confirmed_at": None, "confirmed_by": None}
        assert not entity["workflow"]["ready"] and entity["write_context"] is None
        assert entity["relationships"]["batch_count"] == 1
        assert entity["operations"][0]["unit_hours"] == .125
        assert entity["operations"][2]["unit_hours"] == 0
        assert any(item["code"] == "zero_unit_hours_review" for item in entity["operations"][2]["issues"])
        assert entity["external_groups"][0]["total_days"] == 6.75
        assert entity["external_groups"][0]["remark"] == "保留合并规则"
        assert entity["operations"][1]["external_group_ref"] == entity["external_groups"][0]["ref"]
        for row in entity["operations"] + entity["external_groups"]:
            assert len(row["ref"]) == 48 and not {"id", "revision", "group_id", "part_no", "op_type_id", "supplier_id"} & row.keys()
    finally:
        conn.execute("PRAGMA query_only=OFF")
    assert stored(conn) == before and conn.total_changes == changes


def test_search_and_sort_before_pagination_with_filtered_counts(process_read_conn):
    conn = process_read_conn
    reader = WorkbenchProcessQueryService(conn)
    with reader.read_snapshot():
        one = reader.page(ProcessPageRequest(size=1, sort="operation_count", direction="desc"))
        assert one["entities"][0]["business_code"] == "PROC-001"
        assert one["page"]["total"] == 5
        stage = reader.page(ProcessPageRequest(stage="source", size=1, number=2))
        assert stage["entities"][0]["business_code"] == "PROC-003"
        assert stage["metrics"]["counts"]["total"] == 2
        assert reader.page(ProcessPageRequest(query="%_"))["page"]["total"] == 1
        assert reader.page(ProcessPageRequest(query="PROC-"))["page"]["total"] == 5
        assert reader.page(ProcessPageRequest(query="热处理"))["page"]["total"] == 1
        assert reader.page(ProcessPageRequest(stage="ready"))["entities"] == []


def test_zero_hour_review_tracks_current_explicit_confirmation(process_read_conn):
    conn = process_read_conn

    def detail():
        reader = WorkbenchProcessQueryService(conn)
        with reader.read_snapshot():
            return reader.detail(ref_for(conn))

    def warning(entity):
        return any(item["code"] == "zero_unit_hours_review" for item in entity["operations"][2]["issues"])

    assert warning(detail())
    with TransactionManager(conn).transaction():
        for stage in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
    before, changes = stored(conn), conn.total_changes
    confirmed = detail()
    assert confirmed["workflow"]["ready"]
    assert confirmed["operations"][2]["unit_hours"] == 0 and not warning(confirmed)
    assert confirmed["operations"][2]["confirmation"]["hours"]["state"] == "confirmed"
    assert stored(conn) == before and conn.total_changes == changes
    conn.execute("UPDATE PartOperations SET setup_hours=1 WHERE part_no='PROC-001' AND seq=30")
    conn.commit()
    changed = detail()
    assert changed["operations"][2]["unit_hours"] == 0 and warning(changed)
    assert changed["operations"][2]["confirmation"]["hours"]["state"] == "unconfirmed"


@pytest.mark.parametrize("patch", [{"query": None}, {"query": "a" * 201}, {"stage": "done"}, {"stage": []},
                                     {"number": True}, {"number": 0}, {"size": 201}, {"size": 1.5}, {"sort": "id"}, {"direction": "DESC"}])
def test_invalid_scope_is_rejected(patch):
    with pytest.raises(WorkbenchCommandRejected) as error:
        ProcessPageRequest(**patch)
    assert error.value.status == 400


@pytest.mark.parametrize("ref", [None, "", "1", "f" * 48, "A" * 48])
def test_wrong_or_missing_references_never_fall_back(process_read_conn, ref):
    reader = WorkbenchProcessQueryService(process_read_conn)
    with reader.read_snapshot(), pytest.raises(WorkbenchCommandRejected) as error:
        reader.detail(ref)
    assert error.value.status == 404


def test_unknown_source_deleted_operation_and_missing_values_are_not_zero(process_read_conn):
    reader = WorkbenchProcessQueryService(process_read_conn)
    with reader.read_snapshot():
        unknown = reader.detail(ref_for(process_read_conn, code="PROC-003"))
        assert unknown["relationships"]["unclassified_count"] == 1
        op = unknown["operations"][0]
        assert op["source"] is None and op["unit_hours"] is None and op["op_type_ref"] is None
        deleted = reader.detail(ref_for(process_read_conn, code="PROC-004"))
        assert deleted["operations"][0]["status"] == "deleted" and deleted["relationships"]["operation_count"] == 0
        assert deleted["workflow"]["stage"] == "route"


@pytest.mark.parametrize("kind", ["part", "template_operation", "template_external_group", "op_type", "supplier"])
def test_missing_identity_is_not_repaired_by_reads(process_read_conn, kind):
    conn = process_read_conn
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind=?", (kind,))
    conn.commit()
    before = stored(conn)
    reader = WorkbenchProcessQueryService(conn)
    with pytest.raises(WorkbenchCommandRejected), reader.read_snapshot():
        if kind == "part":
            reader.page(ProcessPageRequest())
        else:
            reader.detail(ref_for(conn))
    assert stored(conn) == before


def test_delete_recreate_does_not_follow_old_part_or_operation(process_read_conn):
    conn = process_read_conn
    old = ref_for(conn, code="PROC-003")
    op = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='template_operation' AND active=1 AND alternate_key='PROC-003:10'").fetchone()[0]
    conn.execute("DELETE FROM Parts WHERE part_no='PROC-003'")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('PROC-003','新零件')")
    conn.commit()
    assert ref_for(conn, code="PROC-003") != old
    assert conn.execute("SELECT active FROM WorkbenchEntityRefs WHERE ref=?", (op,)).fetchone()[0] == 0
    with pytest.raises(WorkbenchCommandRejected):
        WorkbenchProcessQueryService(conn).detail(old)


def test_ten_thousand_operations_read_in_bounded_queries(process_read_conn, record_property):
    conn = process_read_conn
    conn.executemany("INSERT INTO Parts(part_no,part_name,route_parsed) VALUES (?,?,'yes')", [(f"S-{i:04d}", f"零件{i}") for i in range(1000)])
    results = []
    for start, end in ((0, 2000), (2000, 10000)):
        conn.executemany("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name) VALUES (?,?,'PROC-IN','车削')", [(f"S-{i % 1000:04d}", i // 1000 + 1) for i in range(start, end)])
        conn.commit()
        statements = []
        conn.set_trace_callback(statements.append)
        conn.execute("PRAGMA query_only=ON")
        begin = perf_counter()
        try:
            reader = WorkbenchProcessQueryService(conn)
            with reader.read_snapshot():
                page = reader.page(ProcessPageRequest(query="S-", size=200, number=5, sort="operation_count"))
                assert page["page"]["total"] == 1000 and len(page["entities"]) == 200
                assert all(row["relationships"]["operation_count"] == end // 1000 for row in page["entities"])
        finally:
            seconds = perf_counter() - begin
            conn.execute("PRAGMA query_only=OFF")
            conn.set_trace_callback(None)
        selects = sum(sql.lstrip().upper().startswith("SELECT") for sql in statements)
        results.append({"operations": end, "selects": selects, "seconds": seconds})
    record_property("process_read_scale", results)
    # The workflow and explicit confirmations add eight bulk reads, not per-part queries.
    assert results[0]["selects"] == results[1]["selects"] <= 20


def test_read_snapshot_is_consistent_while_another_connection_changes_template(process_read_conn, tmp_path):
    path = tmp_path / "process-wal.db"
    with sqlite3.connect(str(path)) as copy:
        process_read_conn.backup(copy)
    first = sqlite3.connect(str(path)); first.row_factory = sqlite3.Row
    second = sqlite3.connect(str(path))
    try:
        first.execute("PRAGMA journal_mode=WAL")
        reader = WorkbenchProcessQueryService(first)
        with reader.read_snapshot() as before:
            second.execute("UPDATE PartOperations SET unit_hours=9 WHERE part_no='PROC-001' AND seq=10"); second.commit()
            assert reader.detail(ref_for(first))["operations"][0]["unit_hours"] == .125
        with reader.read_snapshot() as after:
            assert before != after and reader.detail(ref_for(first))["operations"][0]["unit_hours"] == 9
    finally:
        first.close(); second.close()
