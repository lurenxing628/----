"""Real creation, synchronization, copies, import and rollback contracts."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
from core.services.scheduler.batch_excel_import import import_batches_from_preview_rows
from core.services.workbench.batch_bulk import WorkbenchBatchBulkService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.template_lineage_query import TemplateLineageQuery
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.template_lineage_support import create, edit, lineage, lineage_case, origin, sync
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture

_lineage_fixture = lineage_case


def test_real_creation_saves_exact_template_ref_revision_and_birth(lineage_case):
    case = lineage_case
    op_id = create(case)
    saved = origin(case, op_id)
    template = case.lineage_repo.template(case.template_id)
    assert saved["template_operation_ref"] == template["template_operation_ref"]
    assert saved["template_revision"] == template["template_revision"]
    assert saved["source_operation_ref"] is None
    assert len(saved["instance_fingerprint"]) == len(saved["template_fingerprint"]) == 64
    assert lineage(case, op_id)["problems"][saved["operation_ref"]] == []


def test_sync_retires_original_and_replay_does_not_create_new_identity(lineage_case):
    case = lineage_case
    old_id = create(case)
    old = origin(case, old_id)
    first = sync(case)
    new_id = case.conn.execute("SELECT id FROM BatchOperations WHERE batch_id='COPY-001'").fetchone()[0]
    new = origin(case, new_id)
    assert new["operation_ref"] != old["operation_ref"]
    assert new["template_operation_ref"] == old["template_operation_ref"]
    before = all_rows(case.conn)
    second = sync(case)
    assert second["replayed"] is True
    assert second["receipt_ref"] == first["receipt_ref"]
    assert all_rows(case.conn) == before
    retired = TemplateLineageQuery(case.conn).read([old["operation_ref"]])
    assert retired["origins"][old["operation_ref"]] == old
    assert retired["problems"][old["operation_ref"]][0]["code"] == "template_instance_retired"


def test_manual_edit_and_revert_are_permanent_contamination_with_same_origin(lineage_case):
    case = lineage_case
    op_id = create(case)
    old = origin(case, op_id)
    edit(case, op_id, {"unit_hours": 4})
    before = all_rows(case.conn)
    edit(case, op_id, {"unit_hours": 4})
    assert all_rows(case.conn) == before
    edit(case, op_id, {"unit_hours": 1}, key="template-edit-request-0002")
    facts = lineage(case, op_id)
    assert facts["origins"][old["operation_ref"]] == old
    assert [event["event_type"] for event in facts["events"][old["operation_ref"]]] == ["created", "updated", "updated"]
    assert facts["problems"][old["operation_ref"]][0]["code"] == "template_instance_modified"


def test_withdrawal_is_idempotent_preserves_evidence_and_cannot_rebind(lineage_case):
    case = lineage_case
    op_id = create(case)
    old = origin(case, op_id)
    with TransactionManager(case.conn).transaction():
        assert case.lineage_writer.withdraw(old["operation_ref"], "wrong source supplied")
        assert not case.lineage_writer.withdraw(old["operation_ref"], "wrong source supplied")
    assert origin(case, op_id) == old
    assert lineage(case, op_id)["problems"][old["operation_ref"]][0]["code"] == "template_lineage_withdrawn"
    with TransactionManager(case.conn).transaction(), pytest.raises(WorkbenchCommandRejected):
        case.lineage_repo.append_origin(case.lineage_repo.instance(op_id), case.lineage_repo.template(case.template_id), old["template_snapshot"])


def test_old_instances_never_receive_template_backfill_or_copy_guess(lineage_case):
    case = lineage_case
    old_instance = case.lineage_repo.instance(case.op_id)
    before = all_rows(case.conn)
    with TransactionManager(case.conn).transaction(), pytest.raises(WorkbenchCommandRejected):
        template = case.lineage_repo.template(case.template_id)
        case.lineage_repo.append_origin(old_instance, template, "{}")
    assert all_rows(case.conn) == before
    case.batch_service.create("OLD-COPY", "P1", 10)
    with TransactionManager(case.conn).transaction():
        new_id = case.lineage_writer.copy_instance("OLD-COPY", case.op_id)
    assert not lineage(case, new_id)["lineages"]
    assert not lineage(case, case.op_id)["lineages"]


def test_bulk_copy_keeps_verified_revision_and_new_execution_ref(lineage_case):
    case = lineage_case
    op_id = create(case)
    old = origin(case, op_id)
    case.conn.execute("UPDATE PartOperations SET unit_hours=5")
    case.conn.commit()
    payload = {"action": "copy", "refs": [case.ref("batch", "COPY-001")]}
    result = WorkbenchCommandService(case.conn).execute(request_key="template-copy-request-0001", action="batch.bulk_confirm",
        context_ref="template-copy-bulk", normalized_input=payload, guard=lambda: None,
        mutate=lambda _: WorkbenchBatchBulkService(case.conn).apply(payload))
    assert result["data"]["count"] == 1
    copied_id = case.conn.execute("SELECT id FROM BatchOperations WHERE batch_id='COPY-002'").fetchone()[0]
    copied = origin(case, copied_id)
    assert copied["source_operation_ref"] == old["operation_ref"]
    assert copied["source_lineage_ref"] == old["lineage_ref"]
    assert copied["template_revision"] == old["template_revision"]
    assert copied["operation_ref"] != old["operation_ref"]
    assert copied["template_snapshot"] == old["template_snapshot"]


def test_op_code_change_and_delete_recreate_do_not_rebind(lineage_case):
    case = lineage_case
    op_id = create(case)
    old = origin(case, op_id)
    case.conn.execute("UPDATE BatchOperations SET op_code='RENAMED' WHERE id=?", (op_id,))
    case.conn.commit()
    assert origin(case, op_id) == old
    assert lineage(case, op_id)["problems"][old["operation_ref"]] == []
    new_id = create(case, rebuild=True)
    assert new_id != op_id and origin(case, new_id)["operation_ref"] != old["operation_ref"]
    assert case.lineage_repo.origins([old["operation_ref"]])[old["operation_ref"]] == old


def test_replace_retires_identity_even_without_recursive_delete_triggers(lineage_case):
    case = lineage_case
    op_id = create(case)
    old = origin(case, op_id)
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    case.conn.execute("INSERT OR REPLACE INTO BatchOperations(id,op_code,batch_id,seq,source,op_type_name) VALUES (?,'COPY-001_01','COPY-001',1,'internal','Replacement')", (op_id,))
    case.conn.commit()
    new = case.lineage_repo.instance(op_id)
    assert new["operation_ref"] != old["operation_ref"]
    assert not lineage(case, op_id)["lineages"]
    assert TemplateLineageQuery(case.conn).read([old["operation_ref"]])["problems"][old["operation_ref"]][0]["code"] == "template_instance_retired"


def test_real_batch_import_uses_atomic_template_write_chain(lineage_case):
    case = lineage_case
    row = ImportPreviewRow(2, RowStatus.NEW, {"批次号": "IMPORT-001", "图号": "P1", "数量": 10,
                                           "优先级": "normal", "齐套": "yes"})
    result = import_batches_from_preview_rows(case.batch_service, preview_rows=[row], mode=ImportMode.APPEND,
        parts_cache={"P1": case.batch_service.part_repo.get("P1")}, auto_generate_ops=True)
    assert result["new_count"] == 1
    op_id = case.conn.execute("SELECT id FROM BatchOperations WHERE batch_id='IMPORT-001'").fetchone()[0]
    assert origin(case, op_id)["template_operation_ref"] == case.lineage_repo.template(case.template_id)["template_operation_ref"]


def test_database_failure_after_instance_insert_rolls_back_whole_batch(lineage_case):
    case = lineage_case
    case.conn.execute("CREATE TRIGGER fail_lineage_test BEFORE INSERT ON WorkbenchTemplateLineageOrigins BEGIN SELECT RAISE(ABORT,'test storage failure'); END")
    case.conn.commit()
    before = all_rows(case.conn)
    with pytest.raises(Exception, match="test storage failure"):
        create(case)
    assert all_rows(case.conn) == before
    assert not case.conn.in_transaction


def test_caller_rollback_preserves_origin_events_and_all_business_rows(lineage_case):
    case = lineage_case
    op_id = create(case)
    before = all_rows(case.conn)
    with pytest.raises(RuntimeError, match="cancel"):
        with TransactionManager(case.conn).transaction():
            case.conn.execute("UPDATE BatchOperations SET unit_hours=3 WHERE id=?", (op_id,))
            create(case, "ROLLBACK-001")
            raise RuntimeError("cancel")
    assert all_rows(case.conn) == before


def test_sync_failure_restores_deleted_instances_and_original_sources(lineage_case):
    from core.models.workbench_command import WorkbenchCommandUncertain

    case = lineage_case
    op_id = create(case)
    old = origin(case, op_id)
    case.conn.execute("CREATE TRIGGER fail_sync_lineage_test BEFORE INSERT ON WorkbenchTemplateLineageOrigins BEGIN SELECT RAISE(ABORT,'test sync storage failure'); END")
    case.conn.commit()
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        sync(case)
    assert all_rows(case.conn) == before
    assert origin(case, op_id) == old
