"""Copy history and corruption boundaries without mocking the source services."""

import sqlite3

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import restore_snapshot
from core.services.workbench.template_lineage_query import TemplateLineageQuery
from tests.workbench.test_execution_ledger_support import all_rows
from tests.workbench.test_template_lineage_support import (
    calibration,
    completed,
    create,
    edit,
    lineage,
    lineage_case,
    origin,
)
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture

_lineage_fixture = lineage_case


def copy(case, source_id, code):
    case.batch_service.create(code, "P1", 10)
    with TransactionManager(case.conn).transaction():
        return case.lineage_writer.copy_instance(code, source_id)


def test_copy_modified_source_keeps_original_origin_but_cannot_launder_sample(lineage_case):
    case = lineage_case
    root_id = create(case)
    root = origin(case, root_id)
    edit(case, root_id, {"unit_hours": 3})
    copied_id = copy(case, root_id, "DIRTY-001")
    child = origin(case, copied_id)
    assert child["source_lineage_ref"] == root["lineage_ref"]
    assert child["source_eligible"] == 0
    assert child["template_snapshot"] == root["template_snapshot"]
    assert restore_snapshot(child["instance_snapshot"])["unit_hours"] == 3
    assert lineage(case, copied_id)["problems"][child["operation_ref"]][0]["code"] == "template_copy_source_unqualified"
    grandchild_id = copy(case, copied_id, "DIRTY-002")
    assert origin(case, grandchild_id)["source_eligible"] == 0


def test_copy_source_version_is_frozen_before_later_source_edits(lineage_case):
    case = lineage_case
    root_id = create(case)
    copied_id = copy(case, root_id, "CLEAN-001")
    child = origin(case, copied_id)
    edit(case, root_id, {"unit_hours": 3})
    assert lineage(case, copied_id)["problems"][child["operation_ref"]] == []
    assert origin(case, copied_id) == child


def test_quantity_change_and_revert_remain_contaminated(lineage_case):
    case = lineage_case
    op_id = create(case)
    saved = origin(case, op_id)
    with TransactionManager(case.conn).transaction():
        case.batch_service.update("COPY-001", quantity=11)
        case.batch_service.update("COPY-001", quantity=10)
    facts = lineage(case, op_id)
    assert [row["event_type"] for row in facts["events"][saved["operation_ref"]]] == ["created", "batch_changed", "batch_changed"]
    assert facts["problems"][saved["operation_ref"]][0]["code"] == "template_instance_modified"


def test_status_and_resource_assignment_are_versioned_not_template_contamination(lineage_case):
    case = lineage_case
    op_id = create(case)
    saved = origin(case, op_id)
    with TransactionManager(case.conn).transaction():
        case.batch_service.batch_op_repo.update(op_id, {"status": "scheduled", "machine_id": "M1", "operator_id": "O1"})
    facts = lineage(case, op_id)
    assert len(facts["events"][saved["operation_ref"]]) == 2
    assert facts["problems"][saved["operation_ref"]] == []


@pytest.mark.parametrize("table,key", [("WorkbenchTemplateLineageOrigins", "lineage_ref"), ("WorkbenchTemplateLineageEvents", "event_id")])
def test_replace_cannot_overwrite_immutable_evidence(lineage_case, table, key):
    case = lineage_case
    create(case)
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    row = dict(case.conn.execute("SELECT * FROM " + table).fetchone())
    before = all_rows(case.conn)
    sql = "INSERT OR REPLACE INTO " + table + " (" + ",".join(row) + ") VALUES (" + ",".join("?" for _ in row) + ")"
    with pytest.raises(sqlite3.IntegrityError):
        case.conn.execute(sql, tuple(row.values()))
    case.conn.rollback()
    assert all_rows(case.conn) == before
    assert row[key] is not None


@pytest.mark.parametrize("column,value", [("template_snapshot", "[]"), ("instance_fingerprint", "0" * 64), ("source_lineage_ref", "a" * 48)])
def test_corrupt_origin_is_explicit_failure_not_empty_samples(lineage_case, column, value):
    case = lineage_case
    op_id = create(case)
    target = origin(case, op_id)
    if column == "source_lineage_ref":
        op_id = copy(case, op_id, "CHILD-001")
        target = origin(case, op_id)
        value = origin(case, create(case, "UNRELATED-001"))["lineage_ref"]
    ddl = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_lineage_origin_no_update'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_lineage_origin_no_update")
    case.conn.execute("UPDATE WorkbenchTemplateLineageOrigins SET " + column + "=? WHERE lineage_ref=?", (value, target["lineage_ref"]))
    case.conn.execute(ddl)
    case.conn.commit()
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        lineage(case, op_id)
    assert exc.value.code == "template_lineage_corrupt"
    assert all_rows(case.conn) == before


def test_report_correction_changes_suggestion_without_rewriting_origin(lineage_case):
    case = lineage_case
    ids, reports = completed(case, [1, 2, 3, 4, 5])
    originals = [origin(case, op_id) for op_id in ids]
    first = calibration(case)
    changed = case.command("correct", reports[2]["report_ref"], {"original_revision_ref": reports[2]["revision_ref"],
        "reason": "quantity correction", "completed_quantity": 9})
    assert changed["data"]["rows"][0]["revision_ref"] != reports[2]["revision_ref"]
    second = calibration(case)
    assert second["rows"][0]["sample_count"] == 4 and second["rows"][0]["suggested_unit_hours"] is None
    assert second["fingerprint"] != first["fingerprint"]
    assert [origin(case, op_id) for op_id in ids] == originals


def test_source_read_does_not_assume_current_template_still_exists(lineage_case):
    case = lineage_case
    op_id = create(case)
    child_id = copy(case, op_id, "CHILD-001")
    old = origin(case, child_id)
    case.conn.execute("DELETE FROM PartOperations")
    case.conn.commit()
    facts = TemplateLineageQuery(case.conn).read([old["operation_ref"]])
    assert facts["origins"][old["operation_ref"]] == old
    assert facts["lineages"][old["operation_ref"]].template_operation_ref == old["template_operation_ref"]


def test_corrupt_mutation_flag_is_not_trusted(lineage_case):
    case = lineage_case
    op_id = create(case)
    edit(case, op_id, {"unit_hours": 3})
    ddl = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_lineage_event_no_update'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_lineage_event_no_update")
    case.conn.execute("UPDATE WorkbenchTemplateLineageEvents SET affects_calibration=0 WHERE event_type='updated'")
    case.conn.execute(ddl)
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as exc:
        lineage(case, op_id)
    assert exc.value.code == "template_lineage_corrupt"


def test_oversized_evidence_rejects_copy_without_truncating_source_blob(lineage_case):
    case = lineage_case
    size = 5 * 1024 * 1024
    case.conn.execute("UPDATE PartOperations SET op_type_name=zeroblob(?)", (size,))
    case.conn.commit()
    case.batch_service.create("TOO-LARGE", "P1", 10)
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        with TransactionManager(case.conn).transaction():
            case.lineage_writer.copy_template("TOO-LARGE", case.template_id)
    assert exc.value.code == "query_too_large"
    assert all_rows(case.conn) == before
    row = case.conn.execute("SELECT typeof(op_type_name),length(op_type_name) FROM PartOperations").fetchone()
    assert tuple(row) == ("blob", size)


def test_template_content_change_without_revision_is_not_same_revision_evidence(lineage_case):
    case = lineage_case
    completed(case, [1, 2, 3, 4, 5])
    ddl = case.conn.execute("SELECT sql FROM sqlite_master WHERE name='wb_ref_template_operation_update'").fetchone()[0]
    case.conn.execute("DROP TRIGGER wb_ref_template_operation_update")
    case.conn.execute("UPDATE PartOperations SET setup_hours=9")
    case.conn.execute(ddl)
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as exc:
        calibration(case)
    assert exc.value.code == "template_lineage_corrupt"


def test_delete_changes_only_target_business_rows_refs_and_append_only_event(lineage_case):
    case = lineage_case
    op_id = create(case)
    saved = origin(case, op_id)
    before = all_rows(case.conn)
    case.batch_service.delete("COPY-001")
    after = all_rows(case.conn)
    affected = {"Batches", "BatchOperations", "WorkbenchEntityRefs", "WorkbenchPlanSourceRefs",
                "WorkbenchPlanIdentityClock", "WorkbenchTemplateLineageEvents", "sqlite_sequence"}
    for table in before:
        if table not in affected:
            assert after[table] == before[table], table
    before_seq, after_seq = dict(before["sqlite_sequence"]), dict(after["sqlite_sequence"])
    assert after_seq.pop("WorkbenchTemplateLineageEvents") == before_seq.pop("WorkbenchTemplateLineageEvents") + 1
    assert after_seq == before_seq
    events = case.lineage_repo.events([saved["operation_ref"]])[saved["operation_ref"]]
    assert [row["event_type"] for row in events] == ["created", "retired"]
    assert case.lineage_repo.origins([saved["operation_ref"]])[saved["operation_ref"]] == saved
