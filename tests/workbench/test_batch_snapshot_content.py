"""Batch snapshots bind unified source revisions and material evaluation day."""

import json

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text, unpacked
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from core.services.workbench.batch.scope import BatchFactScope
from core.services.workbench.facts.source_revisions import BATCH_SOURCE_KEYS, read_source_revisions
from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.part_operation_repo import PartOperationRepository
from data.repositories.workbench_batch_facts_repo import WorkbenchBatchFactsRepository
from tests.workbench.batch_support import batch_database, ref_for

_batch_fixture = batch_database


def test_batch_snapshot_binds_source_revisions_and_material_day_without_rescanning(batch_client):
    conn = batch_client.batch_conn
    reader = WorkbenchBatchQueryService(conn)
    with reader.facts.detached_read_snapshot() as scope:
        fingerprint = scope.fingerprint()
        facts = scope.load()
        restored = unpacked(json.loads(fingerprint))
        assert isinstance(restored, list) and len(restored) == 3
        version, revisions, material_day = restored
        assert version == "batch-facts-v3"
        assert set(revisions) == set(BATCH_SOURCE_KEYS)
        assert revisions == facts["revisions"]
        assert material_day == facts["material_day"]
        trace = []
        conn.set_trace_callback(trace.append)
        try:
            assert scope.fingerprint() == fingerprint
        finally:
            conn.set_trace_callback(None)
        assert trace == []

    expected = read_source_revisions(conn, BATCH_SOURCE_KEYS)
    assert expected["production_input_receipts"] == 1
    assert BatchFactScope(reader.facts).fingerprint() == content_text(["batch-facts-v3", expected, facts["material_day"]])
    conn.execute(
        "INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_json,outcome_json) "
        "VALUES ('batch-noop-00001',?,'batch.update','ctx','{}','{\"result\":\"unchanged\"}')",
        ("a" * 32,),
    )
    conn.commit()
    assert BatchFactScope(reader.facts).fingerprint() == fingerprint
    conn.execute(
        "INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_json,outcome_json) "
        "VALUES ('batch-dupkey-0001',?,'batch.update','ctx','{}','{\"result\":\"unchanged\",\"result\":\"committed\"}')",
        ("b" * 32,),
    )
    conn.commit()
    assert read_source_revisions(conn, BATCH_SOURCE_KEYS)["production_input_receipts"] == 2
    assert BatchFactScope(reader.facts).fingerprint() != fingerprint
    after_receipt = BatchFactScope(reader.facts).fingerprint()
    conn.execute("UPDATE Batches SET remark='updated' WHERE batch_id='FREE-001'")
    conn.commit()
    assert BatchFactScope(reader.facts).fingerprint() != after_receipt


def test_single_batch_template_detail_scales_past_sqlite_variable_limit_and_retains_history(batch_client):
    conn = batch_client.batch_conn
    op_repo = PartOperationRepository(conn)
    group_repo = ExternalGroupRepository(conn)
    deleted_count = 34000

    with TransactionManager(conn).transaction():
        group_repo.create(
            {
                "group_id": "EG-HIST",
                "part_no": "P1",
                "start_seq": 2,
                "end_seq": 2,
                "merge_mode": "separate",
                "total_days": 1.0,
                "supplier_id": "S1",
                "remark": None,
            }
        )
        group_repo.delete_for_part("P1", "EG-HIST")
        group_repo.create(
            {
                "group_id": "EG-HIST",
                "part_no": "P1",
                "start_seq": deleted_count + 2,
                "end_seq": deleted_count + 2,
                "merge_mode": "separate",
                "total_days": 2.0,
                "supplier_id": "S1",
                "remark": None,
            }
        )
        for seq in range(2, deleted_count + 2):
            op_repo.insert_route_operation(
                part_no="P1",
                seq=seq,
                op_type_name="turning",
                source="internal",
                op_type_id="OT1",
                supplier_id=None,
                ext_days=None,
            )
        historical_ids = [
            row["id"]
            for row in op_repo.fetchall(
                "SELECT id FROM PartOperations WHERE part_no='P1' AND seq BETWEEN 2 AND ? ORDER BY id",
                (deleted_count + 1,),
            )
        ]
        for op_id in historical_ids:
            op_repo.mark_deleted_by_id(op_id)
        op_repo.insert_route_operation(
            part_no="P1",
            seq=deleted_count + 2,
            op_type_name="turning",
            source="external",
            op_type_id="OT1",
            supplier_id="S1",
            ext_days=2.0,
        )
        active_op_id = op_repo.fetchvalue(
            "SELECT id FROM PartOperations WHERE part_no='P1' AND seq=?",
            (deleted_count + 2,),
        )
        op_repo.update_fields_by_id(active_op_id, {"ext_group_id": "EG-HIST"})

    batch_ref = ref_for(batch_client)
    query_service = WorkbenchBatchQueryService(conn)
    with query_service.facts.detached_read_snapshot(mode="single_template", target_ref=batch_ref) as detail_scope:
        detail_entity = query_service.detail(detail_scope, batch_ref)
    assert detail_entity["business_code"] == "FREE-001"
    assert detail_entity["template"]["operation_count"] == 2

    facts_repo = WorkbenchBatchFactsRepository(conn)
    batch_row = facts_repo.batch_row("FREE-001")
    assert batch_row is not None
    tables = facts_repo.single_batch_tables(batch_row, batch_ref, include_template=True)

    expected_op_ids = [
        row[0] for row in conn.execute("SELECT id FROM PartOperations WHERE part_no='P1' ORDER BY rowid")
    ]
    assert len(expected_op_ids) == deleted_count + 2
    assert [row["id"] for row in tables["PartOperations"]] == expected_op_ids
    assert sum(row["status"] == "deleted" for row in tables["PartOperations"]) == deleted_count
    assert sum(row["status"] == "active" for row in tables["PartOperations"]) == 2

    expected_refs = [
        row[0]
        for row in conn.execute(
            """SELECT ref FROM WorkbenchEntityRefs
            WHERE kind IN ('part', 'machine', 'operator', 'supplier', 'op_type', 'material')
               OR (kind='batch' AND entity_key='FREE-001')
               OR (kind='template_operation' AND entity_key IN (SELECT CAST(id AS TEXT) FROM PartOperations WHERE part_no='P1'))
               OR (kind='template_external_group' AND entity_key IN ('EG1', 'EG-HIST'))
            ORDER BY rowid"""
        )
    ]
    assert [row["ref"] for row in tables["WorkbenchEntityRefs"]] == expected_refs
    group_ref_states = [
        row["active"]
        for row in tables["WorkbenchEntityRefs"]
        if row["kind"] == "template_external_group" and row["entity_key"] == "EG-HIST"
    ]
    assert group_ref_states == [0, 1]

    assert facts_repo.plan_reference_counts([31, *range(100000, 134000)]) == {31: 1}
