"""Batch snapshots bind unified source revisions and material evaluation day."""

import json

from core.models.content import content_text, unpacked
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from core.services.workbench.facts.source_revisions import BATCH_SOURCE_KEYS, read_source_revisions
from tests.workbench.batch_support import batch_database

_batch_fixture = batch_database


def test_batch_snapshot_binds_source_revisions_and_material_day_without_rescanning(batch_client):
    conn = batch_client.batch_conn
    reader = WorkbenchBatchQueryService(conn)
    with reader.detached_read_snapshot() as fingerprint:
        facts = reader.load()
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
            assert reader.fingerprint() == fingerprint
        finally:
            conn.set_trace_callback(None)
        assert trace == []

    expected = read_source_revisions(conn, BATCH_SOURCE_KEYS)
    assert expected["production_input_receipts"] == 1
    assert reader.fingerprint() == content_text(["batch-facts-v3", expected, facts["material_day"]])
    conn.execute(
        "INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_json,outcome_json) "
        "VALUES ('batch-noop-00001',?,'batch.update','ctx','{}','{\"result\":\"unchanged\"}')",
        ("a" * 32,),
    )
    conn.commit()
    assert reader.fingerprint() == fingerprint
    conn.execute(
        "INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_json,outcome_json) "
        "VALUES ('batch-dupkey-0001',?,'batch.update','ctx','{}','{\"result\":\"unchanged\",\"result\":\"committed\"}')",
        ("b" * 32,),
    )
    conn.commit()
    assert read_source_revisions(conn, BATCH_SOURCE_KEYS)["production_input_receipts"] == 2
    assert reader.fingerprint() != fingerprint
    after_receipt = reader.fingerprint()
    conn.execute("UPDATE Batches SET remark='updated' WHERE batch_id='FREE-001'")
    conn.commit()
    assert reader.fingerprint() != after_receipt
