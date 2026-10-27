"""Compact batch snapshots preserve the complete read/write dependency value."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime

from core.models.content import content_text, unpacked
from core.models.workbench_execution import ProductionReport
from core.services.workbench.batch.execution import execution_content
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from core.services.workbench.batch.snapshot_content import record_content, shared_content
from data.repositories.workbench_batch_facts_repo import BATCH_FACT_TABLES
from tests.workbench.batch_support import batch_database

_batch_fixture = batch_database


def restored_records(value):
    return [dict(zip(value["columns"], row)) for row in value["values"]]


def restored_execution(value):
    encoded = value["projections"]
    rows = restored_records(encoded["records"])
    for row in rows:
        for name, catalog in encoded["shared"].items():
            row[name] = unpacked(json.loads(catalog[row[name]]))
    return dict(value, projections=dict(zip(encoded["refs"], rows)))


def restored_facts(text):
    version, facts = unpacked(json.loads(text))
    assert version == "batch-facts-v2"
    for name in BATCH_FACT_TABLES:
        facts[name] = restored_records(facts[name])
    # JSON object keys are text; these two pre-existing indexes use operation
    # integer IDs, whose original numeric sort order is part of content_text.
    for name in ("operation_refs", "plan_reference_counts"):
        facts[name] = {int(key): value for key, value in facts[name].items()}
    facts["execution"] = restored_execution(facts["execution"])
    return facts


def test_record_matrix_preserves_columns_types_and_original_order():
    rows = [{"id": 1, "raw": value} for value in (
        None, True, 1, 1.0, b"\x00\xff", date(2026, 10, 18), datetime(2026, 10, 18, 8, 30),
        {"$sqlite_blob": "literal"}, {"storage_type": "date", "iso": "literal"},
    )]
    original = content_text(rows)
    packed = record_content(rows)
    assert packed["columns"] == ["id", "raw"]
    assert content_text(restored_records(unpacked(json.loads(content_text(packed))))) == original
    assert content_text(rows) == original
    assert content_text(record_content(list(reversed(rows)))) != content_text(packed)
    assert content_text(record_content([{"a": 1, "b": 2}])) == content_text(record_content([{"b": 2, "a": 1}]))
    for field in rows[0]:
        changed = deepcopy(rows)
        changed[0][field] = "changed"
        assert content_text(record_content(changed)) != content_text(packed)


def test_shared_catalog_is_allocation_independent_and_keeps_every_value_type():
    values = [None, True, 1, 1.0, {"a": [1, True]}, {"a": [1, True]}, {"a": [1, 1]}]
    rows = [{"value": value} for value in values]
    catalog = shared_content(rows, ("value",))
    assert len(catalog["value"]) == 6
    assert rows[4]["value"] == rows[5]["value"]
    assert content_text(values) == content_text([unpacked(json.loads(catalog["value"][row["value"]])) for row in rows])
    alias = {"a": [1, True]}
    reused = [{"value": alias}, {"value": alias}]
    separate = [{"value": deepcopy(alias)}, {"value": deepcopy(alias)}]
    assert (shared_content(reused, ("value",)), reused) == (shared_content(separate, ("value",)), separate)


def test_compact_snapshot_restores_complete_facts_and_execution_histories(batch_client):
    reader = WorkbenchBatchQueryService(batch_client.batch_conn)
    with reader.detached_read_snapshot():
        facts = reader.load()
        first_ref = next(iter(facts["execution"]["projections"]))
        first = facts["execution"]["projections"][first_ref]
        report = ProductionReport(report_ref="r" * 48, report_no="R1", operation_ref=first_ref,
            recorded_against_task_ref="t" * 48, recorded_against_plan_ref="p" * 48, source="manual",
            actual_start="2026-10-18T08:00:00", actual_end=None, completed_quantity=1,
            effective_processing_hours=1.0, actual_machine_ref=None, actual_operator_ref=None, remark="history",
            recorded_at="2026-10-18T08:01:00", revision_ref="v" * 48,
            correction_history=[{"before": {"completed_quantity": None}, "after": {"completed_quantity": 1},
                                 "reason": "corrected", "kept": {"$sqlite_blob": "literal"}}],
            write_context={"writable": False, "reason": "read-only"})
        enriched = replace(first, reports=[report], plan_identity={"plan_ref": "a" * 48, "version": 1},
            data_gaps=[{"code": "kept", "details": [None, True, 1.0]}],
            voided_reports=[{"report": report.to_dict(), "void_fact": {"reason": "voided", "revision": 2}}])
        other = replace(first, plan_identity={"plan_ref": "b" * 48, "version": 2})
        # Differing plan identities and dictionary insertion orders must survive.
        projections = {"z" * 48: enriched, "a" * 48: other, **facts["execution"]["projections"]}
        facts["execution"]["projections"] = projections
        original = dict(facts, execution=dict(facts["execution"], projections={ref: row.to_dict() for ref, row in projections.items()}))
        expected = content_text(original)
        fingerprint = reader.fingerprint()
        assert content_text(restored_facts(fingerprint)) == expected
        assert content_text(dict(facts, execution=dict(facts["execution"], projections={ref: row.to_dict() for ref, row in projections.items()}))) == expected
        facts["execution"]["projections"] = dict(reversed(list(projections.items())))
        assert reader.fingerprint() == fingerprint
        assert len(content_text(execution_content(facts["execution"]))) < len(content_text(original["execution"]))
        facts["execution"]["projections"][first_ref] = replace(first, target_quantity=999)
        assert reader.fingerprint() != fingerprint
        facts["execution"]["projections"] = projections
        facts["workflow"]["private-extra-field"] = {"kept": [None, 1, True]}
        assert reader.fingerprint() != fingerprint
