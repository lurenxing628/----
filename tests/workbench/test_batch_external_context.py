"""Template edits cannot reinterpret frozen batch external work."""

import time

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.batch.service import BatchService
from core.services.process.workflow_state import record_confirmation
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.schedule_service import ScheduleService
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.operations import WorkbenchBatchOperationService
from core.services.workbench.batch.projection import BatchProjection
from core.services.workbench.facts.preflight_checks import PreflightChecks
from core.services.workbench.process.mutations import WorkbenchProcessMutationService
from core.services.workbench.run.input_external import prime_template_cache
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository
from tests.workbench.process_query_support import ref_for, seed_process


@pytest.fixture
def context_conn(schema_conn):
    conn = schema_conn
    seed_process(conn)
    with TransactionManager(conn).transaction():
        for row in conn.execute("SELECT id FROM PartOperations WHERE part_no='PROC-001' ORDER BY seq").fetchall():
            TemplateLineageWriter(conn).copy_template("PROC-B", row["id"])
        for stage in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
    return conn


def inputs(conn, batch="PROC-B"):
    svc = ScheduleService(conn)
    return build_algo_operations(svc, svc.op_repo.list_by_batch(batch), strict_mode=True)


def projection(conn, batch="PROC-B"):
    facts = BatchFacts(conn).load()
    row = next(row for row in facts["Batches"] if row["batch_id"] == batch)
    return BatchProjection(facts).entity(row)


def set_group_days(conn, days):
    repo = WorkbenchProcessQueryRepository(conn)
    rows = repo.template_operations_with_refs("PROC-001")
    payload = {"operations": [{"ref": row["ref"], **(
        {"setup_hours": row["setup_hours"], "unit_hours": row["unit_hours"]} if row["source"] == "internal"
        else {"external_days": row["ext_days"]})} for row in rows if row["status"] == "active"],
        "groups": [{"ref": row["ref"], "total_days": days} for row in repo.template_groups_with_refs("PROC-001")],
        "confirm_zero_unit_hours": True}
    with TransactionManager(conn).transaction():
        identity = WorkbenchIdentityRepository(conn).get(ref_for(conn))
        WorkbenchProcessMutationService(conn).apply("hours_confirm", payload, identity)


def test_template_hours_save_preserves_protected_batch_and_saved_schedule(context_conn):
    conn = context_conn
    op_id = inputs(conn)[1].id
    conn.execute("INSERT INTO Schedule(op_id,start_time,end_time,version) VALUES (?,?,?,1)",
                 (op_id, "2026-10-01 08:00:00", "2026-10-08 02:00:00"))
    conn.commit()
    before = {table: [tuple(row) for row in conn.execute("SELECT * FROM " + table)]
              for table in ("BatchOperations", "Schedule", "BatchExternalContexts")}
    set_group_days(conn, 9)
    result = projection(conn)
    assert result["protected"] and result["relationships"]["plan_reference_count"] == 1
    assert result["operations"][1]["external_group"]["total_days"] == 6.75
    assert inputs(conn)[1].ext_group_total_days == 6.75
    assert before == {table: [tuple(row) for row in conn.execute("SELECT * FROM " + table)] for table in before}


def test_explicit_sync_previews_old_and_new_days_then_replaces_context(context_conn):
    conn = context_conn
    set_group_days(conn, 9)
    service = WorkbenchBatchOperationService(conn)
    batch_ref = ref_for(conn, "batch", "PROC-B")
    preview = service.sync_preview(batch_ref, {})
    assert preview["before"][1]["external_group"]["total_days"] == 6.75
    assert preview["after"][1]["external_group"]["total_days"] == 9
    assert preview["change_counts"]["updated"] == 1
    with TransactionManager(conn).transaction():
        service.sync(batch_ref, {})
    assert inputs(conn)[1].ext_group_total_days == 9


def merged_pair(conn):
    conn.execute("UPDATE ExternalGroups SET end_seq=21 WHERE group_id='PROC-G'")
    conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                 "VALUES('PROC-001',21,'PROC-EX','热处理','external','PROC-S',3.25,'PROC-G')")
    conn.commit()
    with TransactionManager(conn).transaction():
        for stage in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
        WorkbenchBatchOperationService(conn).sync(ref_for(conn, "batch", "PROC-B"), {})


def test_sync_preview_explains_split_groups_even_when_each_cycle_is_unchanged(context_conn):
    conn = context_conn
    merged_pair(conn)
    repo = WorkbenchProcessQueryRepository(conn)
    group = repo.template_groups_with_refs("PROC-001")[0]
    members = [row for row in repo.template_operations_with_refs("PROC-001") if row["source"] == "external"]
    payload = {"groups": [{"ref": group["ref"] if index == 0 else None,
                           "operation_refs": [member["ref"]], "supplier_ref": ref_for(conn, "supplier", "PROC-S"),
                           "total_days": 6.75} for index, member in enumerate(members)], "discard_group_refs": []}
    with TransactionManager(conn).transaction():
        identity = WorkbenchIdentityRepository(conn).get(ref_for(conn))
        WorkbenchProcessMutationService(conn).apply("groups_confirm", payload, identity)
        record_confirmation(conn, "PROC-001", "hours")
    service = WorkbenchBatchOperationService(conn)
    preview = service.sync_preview(ref_for(conn, "batch", "PROC-B"), {})
    assert preview["change_counts"] == {"added": 0, "removed": 0, "updated": 2, "unchanged": 2}
    old, new = preview["external_groups"]["before"], preview["external_groups"]["after"]
    assert len(old) == 1 and old[0]["member_sequences"] == [20, 21]
    assert [(group["start_sequence"], group["end_sequence"], group["member_sequences"]) for group in new] == [
        (20, 20, [20]), (21, 21, [21])]
    assert all(group["total_days"] == 6.75 for group in old + new)
    with TransactionManager(conn).transaction():
        service.sync(ref_for(conn, "batch", "PROC-B"), {})
    assert len({row.ext_group_id for row in inputs(conn) if row.source == "external"}) == 2


def test_sync_group_comparison_uses_members_and_range_instead_of_recreated_identity(context_conn):
    conn = context_conn
    merged_pair(conn)
    conn.execute("UPDATE PartOperations SET ext_group_id=NULL WHERE ext_group_id='PROC-G'")
    conn.execute("DELETE FROM ExternalGroups WHERE group_id='PROC-G'")
    conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                 "VALUES('RECREATED','PROC-001',20,21,'merged',6.75,'PROC-S')")
    conn.execute("UPDATE PartOperations SET ext_group_id='RECREATED' WHERE part_no='PROC-001' AND seq IN (20,21)")
    conn.commit()
    with TransactionManager(conn).transaction():
        for stage in ("source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
    preview = WorkbenchBatchOperationService(conn).sync_preview(ref_for(conn, "batch", "PROC-B"), {})
    assert preview["change_counts"] == {"added": 0, "removed": 0, "updated": 0, "unchanged": 4}
    assert preview["external_groups"]["before"] == preview["external_groups"]["after"]


def test_sync_compares_actual_members_even_when_group_boundaries_are_unchanged(context_conn):
    conn = context_conn
    merged_pair(conn)
    conn.execute("UPDATE PartOperations SET ext_group_id=NULL WHERE part_no='PROC-001' AND seq=21")
    conn.commit()
    with TransactionManager(conn).transaction():
        for stage in ("source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
    preview = WorkbenchBatchOperationService(conn).sync_preview(ref_for(conn, "batch", "PROC-B"), {})
    external = [row for row in preview["changes"] if row["sequence"] in (20, 21)]
    assert all(row["change"] == "updated" for row in external)
    old, new = preview["external_groups"]["before"][0], preview["external_groups"]["after"][0]
    assert old["start_sequence"] == new["start_sequence"] == 20
    assert old["end_sequence"] == new["end_sequence"] == 21
    assert old["member_sequences"] == [20, 21] and new["member_sequences"] == [20]


def test_sync_group_members_keep_full_sqlite_sequence_precision(context_conn):
    conn = context_conn
    merged_pair(conn)
    high = (1 << 63) - 1
    conn.execute("UPDATE PartOperations SET seq=? WHERE part_no='PROC-001' AND seq=20", (high - 1,))
    conn.execute("UPDATE PartOperations SET seq=? WHERE part_no='PROC-001' AND seq=21", (high,))
    conn.execute("UPDATE ExternalGroups SET start_seq=?,end_seq=? WHERE group_id='PROC-G'", (high - 1, high))
    conn.commit()
    service = WorkbenchBatchOperationService(conn)
    with TransactionManager(conn).transaction():
        for stage in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
        service.sync(ref_for(conn, "batch", "PROC-B"), {})
    preview = service.sync_preview(ref_for(conn, "batch", "PROC-B"), {})
    assert preview["change_counts"] == {"added": 0, "removed": 0, "updated": 0, "unchanged": 4}
    assert preview["external_groups"]["before"] == preview["external_groups"]["after"]
    group = preview["external_groups"]["after"][0]
    assert group["start_sequence"] == str(high - 1) and group["end_sequence"] == str(high)
    assert group["member_sequences"] == [str(high - 1), str(high)]
    previous = next(row for row in preview["before"] if row["sequence"] == str(high))
    assert previous["external_group"]["start_sequence"] == str(high - 1)
    assert previous["external_group"]["end_sequence"] == str(high)
    frozen = conn.execute("SELECT start_sequence,end_sequence FROM BatchExternalContexts WHERE sequence=?", (high,)).fetchone()
    assert type(frozen[0]) is int and type(frozen[1]) is int


def test_group_deletion_and_template_type_changes_do_not_break_batch_input(context_conn):
    conn = context_conn
    conn.execute("UPDATE PartOperations SET ext_group_id=NULL,source='internal',op_type_id='PROC-IN' WHERE seq=20")
    conn.execute("DELETE FROM ExternalGroups WHERE group_id='PROC-G'")
    conn.commit()
    svc = ScheduleService(conn)
    facts = BatchFacts(conn).load()
    operations = svc.op_repo.list_by_batch("PROC-B")
    prime_template_cache(svc, facts, {"PROC-B": svc.batch_repo.get("PROC-B")}, operations)
    assert build_algo_operations(svc, operations, strict_mode=True)[1].ext_group_total_days == 6.75
    assert projection(conn)["operations"][1]["external_group"]["total_days"] == 6.75


def test_batch_copy_and_piece_copy_inherit_original_not_current_group(context_conn):
    conn = context_conn
    conn.execute("UPDATE BatchOperations SET piece_id='piece-A' WHERE seq=20")
    conn.commit()
    original = inputs(conn)[1]
    set_group_days(conn, 9)
    BatchService(conn).copy_batch("PROC-B", "COPIED")
    copied = inputs(conn, "COPIED")[1]
    assert copied.piece_id == "piece-A"
    assert copied.ext_group_total_days == original.ext_group_total_days == 6.75
    assert copied.ext_group_id == original.ext_group_id


@pytest.mark.parametrize("strict", [False, True])
def test_missing_snapshot_never_falls_back_to_live_template(context_conn, strict):
    conn = context_conn
    conn.execute("DELETE FROM BatchExternalContexts")
    conn.commit()
    svc = ScheduleService(conn)
    with pytest.raises(ValidationError) as error:
        build_algo_operations(svc, svc.op_repo.list_by_batch("PROC-B"), strict_mode=strict)
    assert error.value.field == "external_context"
    row = projection(conn)["operations"][1]
    assert row["external_group"] is None and row["external_days"] is None
    assert any(item["code"] == "external_context_invalid" for item in row["issues"])


def test_reused_group_code_gets_a_distinct_algorithm_identity(context_conn):
    conn = context_conn
    original = inputs(conn)[1].ext_group_id
    conn.execute("UPDATE PartOperations SET ext_group_id=NULL WHERE seq=20")
    conn.execute("DELETE FROM ExternalGroups WHERE group_id='PROC-G'")
    conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days) "
                 "VALUES('PROC-G','PROC-001',20,20,'merged',6.75)")
    conn.execute("UPDATE PartOperations SET ext_group_id='PROC-G' WHERE seq=20")
    conn.commit()
    with TransactionManager(conn).transaction():
        for stage in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
    BatchService(conn).create_batch_from_template("NEW-B", "PROC-001", 1)
    assert inputs(conn, "NEW-B")[1].ext_group_id != original
    assert inputs(conn)[1].ext_group_id == original


def test_source_switch_captures_once_and_out_of_order_template_is_explicit(context_conn):
    conn = context_conn
    conn.execute("UPDATE BatchOperations SET source='external',supplier_id='PROC-S',ext_days=2 WHERE seq=10")
    conn.commit()
    before = dict(conn.execute("SELECT * FROM BatchExternalContexts WHERE sequence=10").fetchone())
    assert before["group_id"] is None
    conn.execute("UPDATE PartOperations SET ext_group_id='PROC-G' WHERE seq=10")
    conn.commit()
    assert dict(conn.execute("SELECT * FROM BatchExternalContexts WHERE sequence=10").fetchone()) == before
    conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,ext_days) VALUES('OUT-OF-ORDER','PROC-B',40,'Late','external',2)")
    conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source) VALUES('PROC-001',40,'Late','external')")
    conn.commit()
    svc = ScheduleService(conn)
    with pytest.raises(ValidationError, match="没有有效的模板工序"):
        build_algo_operations(svc, svc.op_repo.list_by_batch("PROC-B"), strict_mode=True)


def second_supplier(conn):
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,status) VALUES('NEW-S','第二家热处理厂','PROC-EX','active')")
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES('NEW-S','PROC-EX')")
    conn.commit()
    return ref_for(conn, "supplier", "NEW-S")


def test_merged_supplier_cannot_be_changed_through_batch_editor(context_conn):
    conn = context_conn
    supplier_ref = second_supplier(conn)
    before = [tuple(row) for row in conn.execute("SELECT * FROM BatchOperations")]
    row = projection(conn)["operations"][1]
    with pytest.raises(WorkbenchCommandRejected, match="不能单独更换供应商"):
        with TransactionManager(conn).transaction():
            WorkbenchBatchOperationService(conn).update(ref_for(conn, "batch", "PROC-B"), {
                "operation_ref": row["ref"], "fields": {"supplier_ref": supplier_ref}})
    assert before == [tuple(row) for row in conn.execute("SELECT * FROM BatchOperations")]


@pytest.mark.parametrize("group_supplier", ["PROC-S", None])
def test_existing_mixed_suppliers_block_scheduling_and_remain_diagnosable_after_copy(context_conn, group_supplier):
    conn = context_conn
    second_supplier(conn)
    conn.execute("UPDATE ExternalGroups SET end_seq=21,supplier_id=? WHERE group_id='PROC-G'", (group_supplier,))
    conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                 "VALUES('PROC-001',21,'PROC-EX','热处理','external','PROC-S',3.25,'PROC-G')")
    conn.commit()
    with TransactionManager(conn).transaction():
        for stage in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
        WorkbenchBatchOperationService(conn).sync(ref_for(conn, "batch", "PROC-B"), {})
    frozen = [tuple(row) for row in conn.execute("SELECT * FROM BatchExternalContexts")]
    # An independent legacy-data path must fail even when it bypasses the UI/service guard.
    conn.execute("UPDATE BatchOperations SET supplier_id='NEW-S' WHERE seq=20")
    conn.commit()
    for strict in (False, True):
        svc = ScheduleService(conn)
        with pytest.raises(ValidationError, match="供应商"):
            build_algo_operations(svc, svc.op_repo.list_by_batch("PROC-B"), strict_mode=strict)
    facts = BatchFacts(conn).load()
    checks = PreflightChecks(facts)
    batch = next(row for row in facts["Batches"] if row["batch_id"] == "PROC-B")
    for op in [row for row in facts["BatchOperations"] if row["seq"] in (20, 21)]:
        assert any(item["code"] == "external_context_invalid" for item in checks.fields(batch, op))
    BatchService(conn).copy_batch("PROC-B", "BAD-COPY")
    with pytest.raises(ValidationError, match="供应商"):
        inputs(conn, "BAD-COPY")
    assert frozen == [tuple(row) for row in conn.execute("SELECT c.* FROM BatchExternalContexts c "
        "JOIN BatchOperations o ON o.id=c.operation_id WHERE o.batch_id='PROC-B'")]


def test_separate_period_still_allows_one_operation_supplier_change(context_conn):
    conn = context_conn
    supplier_ref = second_supplier(conn)
    conn.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'")
    conn.commit()
    with TransactionManager(conn).transaction():
        for stage in ("route", "source", "hours"):
            record_confirmation(conn, "PROC-001", stage)
        service = WorkbenchBatchOperationService(conn)
        service.sync(ref_for(conn, "batch", "PROC-B"), {})
        op = projection(conn)["operations"][1]
        result = service.update(ref_for(conn, "batch", "PROC-B"),
            {"operation_ref": op["ref"], "fields": {"supplier_ref": supplier_ref}})
    assert result.result == "committed"
    assert inputs(conn)[1].supplier_id == "NEW-S" and inputs(conn)[1].ext_days == 3.25


@pytest.mark.parametrize("count", [200, 1000])
def test_large_merged_group_has_linear_storage_and_one_supplier_check(schema_conn, monkeypatch, count):
    from core.services.scheduler.contracts import external_context
    from data.repositories.batch_external_context_repo import BatchExternalContextRepository

    conn = schema_conn
    baseline_bytes = conn.execute("PRAGMA page_count").fetchone()[0] * conn.execute("PRAGMA page_size").fetchone()[0]
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES('P','Large external route')")
    conn.execute("INSERT INTO Suppliers(supplier_id,name) VALUES('S','Supplier')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES('B','P',1)")
    conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                 "VALUES('G','P',1,?,'merged',3,'S')", (count,))
    conn.executemany("INSERT INTO PartOperations(part_no,seq,op_type_name,source,ext_group_id,supplier_id) "
                     "VALUES('P',?,'External','external','G','S')", [(n,) for n in range(1, count + 1)])
    conn.executemany("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,supplier_id) "
                     "VALUES(?,'B',?,'External','external','S')", [(str(n), n) for n in range(1, count + 1)])
    conn.commit()
    counts = {"members_read": 0, "context_checks": 0}
    original_read, original_check = BatchExternalContextRepository.group_members, external_context.context_problem

    def read(*args):
        counts["members_read"] += 1
        return original_read(*args)

    def check(*args, **kwargs):
        counts["context_checks"] += 1
        return original_check(*args, **kwargs)

    monkeypatch.setattr(BatchExternalContextRepository, "group_members", read)
    monkeypatch.setattr(external_context, "context_problem", check)
    begin = time.monotonic()
    result = inputs(conn, "B")
    elapsed = time.monotonic() - begin
    stored_bytes = conn.execute("PRAGMA page_count").fetchone()[0] * conn.execute("PRAGMA page_size").fetchone()[0]
    assert len(result) == count and len({op.ext_group_id for op in result}) == 1
    assert counts["members_read"] <= 1
    assert counts["context_checks"] <= 3 * count
    assert stored_bytes - baseline_bytes < 4096 * count
    assert elapsed < 10, "A single group must not run cubic member validation"
    print("MERGED_CONTEXT_BUDGET", count, "seconds", round(elapsed, 4), "database_growth_bytes", stored_bytes - baseline_bytes)
