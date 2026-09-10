"""Material query scope, raw data boundaries and temporary read snapshots."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import pytest
from flask import Flask

import web.public_token_registry as registry
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.material_queries import WorkbenchMaterialQueryService
from web.routes.workbench.read_context import bind_read_snapshot


@pytest.fixture
def materials(schema_conn):
    rows = [("M-3", "B", "round", 30, "active"), ("M-1", "B", "flat", 10, "active"),
            ("M-4", "A", "50%_size", 40, "inactive"), ("M-2", "B", "round", None, None)]
    schema_conn.executemany("INSERT INTO Materials(material_id,name,spec,stock_qty,status,unit,remark) VALUES (?,?,?,?,?,'kg','retained')", rows)
    schema_conn.commit()
    return schema_conn, WorkbenchMaterialQueryService(schema_conn)


def test_filtered_count_sort_and_page_are_from_one_readonly_scope(materials):
    conn, service = materials
    before = list(conn.iterdump()), conn.total_changes
    conn.execute("PRAGMA query_only = ON")
    with service.read_snapshot() as state:
        records, page = service.page(MaterialPageRequest(query="round", size=1, sort="stock_qty", direction="desc"))
        assert [record.entity["business_code"] for record in records] == ["M-3"]
        assert page == {"number": 1, "size": 1, "total": 2, "pages": 2, "sort": [{"field": "stock_qty", "direction": "desc"}]}
        next_records, _ = service.page(MaterialPageRequest(query="round", number=2, size=1, sort="stock_qty", direction="desc"))
        assert next_records[0].entity["business_code"] == "M-2"
        assert service.state_fingerprint() == state
    assert (list(conn.iterdump()), conn.total_changes) == before
    assert not conn.in_transaction


def test_search_is_literal_and_sort_ties_do_not_repeat_pages(materials):
    _, service = materials
    records, page = service.page(MaterialPageRequest(query="%_"))
    assert page["total"] == 1 and records[0].entity["business_code"] == "M-4"
    request = MaterialPageRequest(query="B", sort="label", size=1)
    codes = [service.page(replace(request, number=number))[0][0].entity["business_code"] for number in (1, 2, 3)]
    assert codes == ["M-1", "M-2", "M-3"]
    assert service.page(replace(request, number=4))[0] == []
    assert service.page(MaterialPageRequest(status="inactive"))[1]["total"] == 1


def test_unknown_stock_status_and_threshold_are_not_invented(materials):
    _, service = materials
    record = service.page(MaterialPageRequest(query="M-2"))[0][0]
    entity = service.detail(record.identity.ref).entity
    assert entity["fields"]["stock_qty"] is None and entity["status"] is None
    assert entity["fields"]["unit"] == "kg" and entity["fields"]["remark"] == "retained"
    assert {item["code"] for item in entity["issues"]} == {"stock_unknown", "status_unknown", "stock_level_unknown"}
    assert "revision" not in entity and "created_at" not in entity["fields"]


def test_metrics_use_full_filtered_scope_without_inventing_low_stock(materials):
    conn, service = materials
    before = list(conn.iterdump())
    with service.read_snapshot():
        query = MaterialPageRequest(size=1, number=2)
        assert service.metrics(query)["counts"] == {"total": 4, "active": 2, "inactive": 1, "unknown": 1, "stock_unknown": 1}
        filtered = service.metrics(MaterialPageRequest(query="round", size=1))
        assert filtered["counts"] == {"total": 2, "active": 1, "inactive": 0, "unknown": 1, "stock_unknown": 1}
        assert "low_stock" not in filtered["counts"]
        assert filtered["basis"]["low_stock"]
        assert service.metrics(MaterialPageRequest(query="not present"))["counts"] == dict.fromkeys(filtered["counts"], 0)
    assert list(conn.iterdump()) == before


@pytest.mark.parametrize("stock", (float("inf"), -1, "bad"))
def test_invalid_stored_stock_is_rejected_without_zero_substitution(materials, stock):
    conn, service = materials
    conn.execute("UPDATE Materials SET stock_qty=? WHERE material_id='M-1'", (stock,))
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(WorkbenchCommandRejected) as error:
        service.page(MaterialPageRequest())
    assert error.value.code == "storage_failure" and error.value.status == 500
    assert list(conn.iterdump()) == before


def test_old_ref_is_not_resolved_to_same_code_replacement(materials):
    conn, service = materials
    original = service.page(MaterialPageRequest(query="M-1"))[0][0]
    conn.execute("DELETE FROM Materials WHERE material_id='M-1'")
    conn.execute("INSERT INTO Materials(material_id,name) VALUES ('M-1','new')")
    conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        service.detail(original.identity.ref)
    assert error.value.code == "entity_not_found"
    assert service.page(MaterialPageRequest(query="M-1"))[0][0].identity.ref != original.identity.ref


def test_missing_metadata_fails_visible_instead_of_omitting_or_repairing_row(materials):
    conn, service = materials
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind='material' AND entity_key='M-1'")
    conn.commit()
    before = list(conn.iterdump())
    with pytest.raises(WorkbenchCommandRejected, match="永久引用缺失"):
        service.page(MaterialPageRequest())
    assert list(conn.iterdump()) == before


@pytest.mark.parametrize("patch", ({"query": 0}, {"query": "a" * 201}, {"status": "low_stock"},
                                    {"number": True}, {"number": 0}, {"size": 201}, {"size": 1.2},
                                    {"sort": "ref"}, {"sort": "name; DROP TABLE Materials"}, {"direction": "DESC"}))
def test_scope_rejects_bad_types_or_unregistered_options(patch):
    with pytest.raises(WorkbenchCommandRejected):
        MaterialPageRequest(**patch)


def test_old_read_snapshot_rejects_new_data_filter_and_restart(materials, monkeypatch):
    conn, service = materials
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(registry, "time", SimpleNamespace(time=lambda: clock["now"]))
    scope = MaterialPageRequest(size=1).scope()
    with Flask("read-test").app_context():
        with service.read_snapshot() as state:
            snapshot = bind_read_snapshot(scope, state)
            assert bind_read_snapshot(scope, state, snapshot["snapshot_ref"]) == snapshot
            with pytest.raises(WorkbenchCommandRejected) as error:
                bind_read_snapshot({**scope, "query": "different"}, state, snapshot["snapshot_ref"])
            assert error.value.code == "snapshot_stale"
        conn.execute("UPDATE Materials SET remark='new' WHERE material_id='M-4'")
        conn.commit()
        with pytest.raises(WorkbenchCommandRejected):
            bind_read_snapshot(scope, service.state_fingerprint(), snapshot["snapshot_ref"])
        clock["now"] += 901
        with pytest.raises(WorkbenchCommandRejected):
            bind_read_snapshot(scope, state, snapshot["snapshot_ref"])
    with Flask("restart-test").app_context():
        with pytest.raises(WorkbenchCommandRejected):
            bind_read_snapshot(scope, state, snapshot["snapshot_ref"])


def test_wal_writer_cannot_split_read_count_and_rows(materials, tmp_path):
    conn, _ = materials
    path = tmp_path / "read-snapshot.db"
    target = sqlite3.connect(str(path))
    conn.backup(target)
    target.execute("PRAGMA journal_mode=WAL")
    target.row_factory = sqlite3.Row
    writer = sqlite3.connect(str(path))
    reader = WorkbenchMaterialQueryService(target)
    try:
        with reader.read_snapshot() as state:
            writer.execute("INSERT INTO Materials(material_id,name) VALUES ('new-row','new')")
            writer.commit()
            assert reader.page(MaterialPageRequest())[1]["total"] == 4
            assert reader.state_fingerprint() == state
        assert reader.page(MaterialPageRequest())[1]["total"] == 5
        assert reader.state_fingerprint() != state
    finally:
        writer.close()
        target.close()
