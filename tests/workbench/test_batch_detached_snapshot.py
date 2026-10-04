"""Captured batch queries release DELETE-journal locks before projection."""

import re
import sqlite3

import pytest

from core.models.workbench_batch_query import batch_scope
from core.services.personnel.operator_qualification import OperatorQualificationService
from core.services.workbench.batch import facts as facts_module
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from core.services.workbench.process.queries import plain_fingerprint
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


def test_operation_choices_keep_qualification_reads_in_the_batch_snapshot(batch_client, monkeypatch):
    batch_ref = ref_for(batch_client)
    detail = batch_client.get(BASE + "/" + batch_ref).get_json()["data"]
    operation_ref = detail["operations"][0]["ref"]
    original = OperatorQualificationService.load
    captured = []

    def inspect(service, *args, **kwargs):
        assert batch_client.batch_conn.in_transaction
        captured.append(True)
        return original(service, *args, **kwargs)

    monkeypatch.setattr(OperatorQualificationService, "load", inspect)
    response = batch_client.get(BASE + "/choices", query_string={
        "batch_ref": batch_ref, "operation_ref": operation_ref})
    assert response.status_code == 200, response.get_json()
    assert captured
    assert all("eligible" in row for row in response.get_json()["data"]["operators"])
    assert not batch_client.batch_conn.in_transaction


def test_fingerprint_covers_execution_projections_without_a_second_hash(batch_client, monkeypatch):
    reader = WorkbenchBatchQueryService(batch_client.batch_conn)
    facts = reader.load()
    assert facts["execution"]["available"] and facts["execution"]["projections"]
    assert "projection_hash" not in facts["execution"]["snapshot_facts"]
    first = reader.fingerprint()
    assert re.fullmatch(r"[0-9a-f]{64}", first) and first == reader.fingerprint() == plain_fingerprint(facts)
    original = facts_module.project_execution_snapshot

    def changed(raw):
        result = original(raw)
        ref = sorted(result["projections"])[0]
        result["projections"][ref]["data_gaps"].append({"code": "probe", "message": "只改执行投影"})
        return result

    monkeypatch.setattr(facts_module, "project_execution_snapshot", changed)
    assert reader.fingerprint() != first
    monkeypatch.setattr(facts_module, "project_execution_snapshot", original)
    batch_client.batch_conn.execute("UPDATE Batches SET due_date='2031-02-03' WHERE batch_id='FREE-001'")
    assert reader.fingerprint() not in (first, None)
    batch_client.batch_conn.rollback()
