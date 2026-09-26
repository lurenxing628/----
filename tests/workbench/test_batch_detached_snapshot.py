"""Captured batch queries release DELETE-journal locks before projection."""

import sqlite3

import pytest

from core.models.workbench_batch_query import batch_scope
from core.services.workbench.batch import facts as facts_module
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from tests.workbench.batch_support import BASE, batch_database, ref_for

_batch_fixture = batch_database


def _queries(reader, ref):
    scopes = [batch_scope({}), batch_scope({"focus": "gaps", "size": 1}),
              batch_scope({"sort": "quantity", "direction": "desc"}),
              batch_scope({"column_filters": {"part_no": ["P1"]}, "status": "pending"})]
    return {"pages": [reader.page(scope) for scope in scopes],
            "selection": [reader.selection(scope) for scope in scopes],
            "detail": reader.detail(ref), "choices": reader.choices()}


def test_captured_queries_release_real_delete_lock_and_keep_one_snapshot(batch_client, tmp_path, monkeypatch):
    path = str(tmp_path / "batch-snapshot.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    batch_client.batch_conn.backup(conn)
    writer = sqlite3.connect(path, timeout=0.05)
    ref = ref_for(batch_client)
    reader = WorkbenchBatchQueryService(conn)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        with reader.read_snapshot() as expected_fingerprint:
            expected = _queries(reader, ref)
        original_workflow = facts_module.project_workflow_snapshot
        original_execution = facts_module.project_execution_snapshot
        projected = []

        def workflow(raw):
            assert not conn.in_transaction
            # A real second connection must commit while the first request projects.
            writer.execute("UPDATE Batches SET quantity=777 WHERE batch_id='FREE-001'")
            writer.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE ref=?", (ref,))
            writer.commit()
            conn.set_authorizer(lambda *_args: sqlite3.SQLITE_DENY)
            projected.append("workflow")
            return original_workflow(raw)

        def execution(raw):
            assert not conn.in_transaction
            projected.append("execution")
            return original_execution(raw)

        monkeypatch.setattr(facts_module, "project_workflow_snapshot", workflow)
        monkeypatch.setattr(facts_module, "project_execution_snapshot", execution)
        with reader.detached_read_snapshot() as actual_fingerprint:
            assert not conn.in_transaction
            assert reader.resolve(ref).active
            assert actual_fingerprint == expected_fingerprint
            assert _queries(reader, ref) == expected
        assert projected == ["workflow", "execution"]
        assert reader._facts is None
        assert writer.execute("SELECT quantity FROM Batches WHERE batch_id='FREE-001'").fetchone()[0] == 777
    finally:
        conn.set_authorizer(None)
        writer.close()
        conn.close()


def test_detached_snapshot_preserves_caller_transaction_and_restores_nested_state(batch_client):
    conn = batch_client.batch_conn
    reader = WorkbenchBatchQueryService(conn)
    conn.execute("BEGIN")
    try:
        conn.execute("UPDATE Batches SET remark='uncommitted' WHERE batch_id='FREE-001'")
        with reader.detached_read_snapshot() as fingerprint:
            captured = reader._facts
            assert conn.in_transaction
            with pytest.raises(RuntimeError, match="projection failed"):
                with reader.detached_read_snapshot() as nested:
                    assert nested == fingerprint
                    raise RuntimeError("projection failed")
            assert reader._facts is captured
        assert reader._facts is None and conn.in_transaction
        conn.rollback()
        assert conn.execute("SELECT remark FROM Batches WHERE batch_id='FREE-001'").fetchone()[0] == "keep-hidden"
    finally:
        conn.rollback()


@pytest.mark.parametrize("query_method,path", [("page", ""), ("detail", "/{ref}"), ("choices", "/choices")])
def test_read_routes_project_after_releasing_owned_transaction(batch_client, monkeypatch, query_method, path):
    original = getattr(WorkbenchBatchQueryService, query_method)
    called = []

    def inspect(reader, *args, **kwargs):
        assert not reader.conn.in_transaction
        called.append(query_method)
        return original(reader, *args, **kwargs)

    monkeypatch.setattr(WorkbenchBatchQueryService, query_method, inspect)
    response = batch_client.get(BASE + path.format(ref=ref_for(batch_client)))
    assert response.status_code == 200, response.get_json()
    assert called == [query_method]
