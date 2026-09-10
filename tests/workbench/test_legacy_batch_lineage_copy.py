"""Legacy BatchService.copy_batch: lossless lineage and real atomic rollback."""

import sqlite3

import pytest

from core.infrastructure.errors import AppError, BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import restore_snapshot, state_snapshot
from core.services.workbench.template_lineage_query import TemplateLineageQuery
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.legacy_batch_lineage_copy_support import (
    assert_only_copy_appends,
    assert_raw_copy,
    fail_last_origin,
    legacy_case,
    operations,
    seed_scale,
)
from tests.workbench.process_workflow_support import stored_state
from tests.workbench.test_execution_ledger_support import all_rows
from tests.workbench.test_template_lineage_support import calibration, create, lineage, origin

_legacy_fixture = legacy_case


def test_real_fifty_batches_three_operations_keep_lineage_plans_and_execution(legacy_case):
    case = legacy_case
    sources = seed_scale(case)
    before = stored_state(case.conn)
    source_rows = {code: operations(case, code) for code in sources}
    parents = {row["id"]: origin(case, row["id"]) for rows in source_rows.values() for row in rows}
    facts = TemplateLineageQuery(case.conn).read([saved["operation_ref"] for saved in parents.values()])
    for index, code in enumerate(sources):
        destination = "DST-" + str(index).zfill(3)
        result = case.batch_service.copy_batch(code, destination)
        assert result.batch_id == destination and result.status == "pending"
        copied_rows = operations(case, destination)
        assert len(copied_rows) == 3
        for source, copied in zip(source_rows[code], copied_rows):
            assert_raw_copy(source, copied, destination)
            parent, child = parents[source["id"]], origin(case, copied["id"])
            assert child["operation_ref"] != parent["operation_ref"]
            assert child["source_operation_ref"] == parent["operation_ref"]
            assert child["source_lineage_ref"] == parent["lineage_ref"]
            assert child["source_event_id"] == facts["events"][parent["operation_ref"]][-1]["event_id"]
            assert child["source_eligible"] == 1
            assert child["template_snapshot"] == parent["template_snapshot"]
            assert child["template_revision"] == parent["template_revision"]
        batch = dict(case.conn.execute("SELECT * FROM Batches WHERE batch_id=?", (destination,)).fetchone())
        original = dict(case.conn.execute("SELECT * FROM Batches WHERE batch_id=?", (code,)).fetchone())
        for key in set(original) - {"batch_id", "status", "created_at", "updated_at"}:
            assert batch[key] == original[key], key
    after = stored_state(case.conn)
    assert after[0] == before[0]
    assert_only_copy_appends(before[1], after[1], 50, 150)
    assert not case.conn.in_transaction


@pytest.mark.parametrize("failure", ["last_origin", "caller_cancel"])
def test_fifty_batch_outer_rollback_restores_every_original_row_and_sequence(legacy_case, failure):
    case = legacy_case
    sources = seed_scale(case)
    if failure == "last_origin":
        fail_last_origin(case, "DST-049")
    before = stored_state(case.conn)
    completed = []
    expected_error = sqlite3.IntegrityError if failure == "last_origin" else RuntimeError
    with pytest.raises(expected_error, match="legacy last operation failure|caller cancelled all fifty"):
        with TransactionManager(case.conn).transaction():
            for index, code in enumerate(sources):
                completed.append(case.batch_service.copy_batch(code, "DST-" + str(index).zfill(3)).batch_id)
            assert case.conn.execute("SELECT count(*) FROM BatchOperations WHERE batch_id LIKE 'DST-%'").fetchone()[0] == 150
            raise RuntimeError("caller cancelled all fifty")
    assert len(completed) == (49 if failure == "last_origin" else 50)
    assert stored_state(case.conn) == before
    assert not case.conn.in_transaction


def test_last_operation_failure_rolls_back_legacy_owned_transaction(legacy_case):
    case = legacy_case
    seed_scale(case, count=1)
    fail_last_origin(case, "SINGLE")
    before = stored_state(case.conn)
    with pytest.raises(sqlite3.IntegrityError, match="legacy last operation failure"):
        case.batch_service.copy_batch("SRC-000", "SINGLE")
    assert stored_state(case.conn) == before
    assert not case.conn.in_transaction


def test_duplicate_copied_operation_code_rolls_back_every_table(legacy_case):
    case = legacy_case
    create(case, "SOURCE")
    create(case, "COLLIDER")
    with TransactionManager(case.conn).transaction():
        case.conn.execute("UPDATE BatchOperations SET op_code='CHILD_02' WHERE batch_id='COLLIDER' AND seq=2")
    before = stored_state(case.conn)
    with pytest.raises(AppError) as error:
        case.batch_service.copy_batch("SOURCE", "CHILD")
    assert error.value.code == ErrorCode.DUPLICATE_ENTRY
    assert error.value.details == {"db_message": "UNIQUE constraint failed: BatchOperations.op_code"}
    assert isinstance(error.value.__cause__, sqlite3.IntegrityError)
    assert str(error.value.__cause__) == "UNIQUE constraint failed: BatchOperations.op_code"
    assert stored_state(case.conn) == before
    assert not case.conn.in_transaction


@pytest.mark.parametrize("bound", [False, True])
@pytest.mark.parametrize("values", [
    {"setup_hours": None, "unit_hours": 0, "ext_days": None, "source": "unknown"},
    {"setup_hours": 0, "unit_hours": None, "ext_days": 0, "source": " EXTERNAL "},
    {"setup_hours": b"\x00\xfflegacy", "unit_hours": "unknown", "ext_days": b"\x80\x00", "source": None},
])
def test_raw_unknown_null_zero_and_blob_values_are_not_model_normalized(legacy_case, bound, values):
    case = legacy_case
    raw = dict(op_type_id="legacy-type", op_type_name=b"\x00\xffraw-name", **values)
    case.batch_service.create("RAW", "P1", 10)
    with TransactionManager(case.conn).transaction():
        if bound:
            case.conn.execute("UPDATE PartOperations SET " + ",".join(key + "=?" for key in raw) + " WHERE id=?",
                              tuple(raw.values()) + (case.template_id,))
            op_id = case.lineage_writer.copy_template("RAW", case.template_id)
        else:
            insert_row(case.conn, "BatchOperations", dict(op_code="RAW_01", batch_id="RAW", seq=1, **raw))
            op_id = operations(case, "RAW")[0]["id"]
        case.conn.execute("UPDATE BatchOperations SET piece_id='piece-01',machine_id='M1',operator_id='O1',supplier_id='S1',status='completed' WHERE id=?", (op_id,))
    before = all_rows(case.conn)
    source = operations(case, "RAW")[0]
    old_ref = case.lineage_repo.instance(op_id)["operation_ref"]
    case.batch_service.copy_batch(" RAW ", " RAW-COPY ")
    copied = operations(case, "RAW-COPY")[0]
    assert_raw_copy(source, copied, "RAW-COPY")
    instance = case.lineage_repo.instance(copied["id"])
    assert instance["operation_ref"] != old_ref
    event = case.lineage_repo.events([instance["operation_ref"]])[instance["operation_ref"]][0]
    assert state_snapshot(event) == state_snapshot(instance)
    if bound:
        saved = origin(case, copied["id"])
        assert saved["source_operation_ref"] == old_ref
        assert restore_snapshot(saved["instance_snapshot"])["op_type_name"] == raw["op_type_name"]
        assert restore_snapshot(saved["template_snapshot"])["setup_hours"] == raw["setup_hours"]
    else:
        assert lineage(case, copied["id"])["origins"] == {}
        assert lineage(case, op_id)["origins"] == {}
    after = all_rows(case.conn)
    assert after["BatchOperations"][:len(before["BatchOperations"])] == before["BatchOperations"]
    assert after["WorkbenchPlanSourceRefs"][:len(before["WorkbenchPlanSourceRefs"])] == before["WorkbenchPlanSourceRefs"]


@pytest.mark.parametrize("change", ["revision", "deleted", "recreated"])
def test_exact_parent_event_version_survives_template_change_and_later_source_edit(legacy_case, change):
    case = legacy_case
    op_id = create(case, "SOURCE")
    saved = origin(case, op_id)
    with TransactionManager(case.conn).transaction():
        case.conn.execute("UPDATE BatchOperations SET op_code='RENAMED',status='scheduled',machine_id='M1' WHERE id=?", (op_id,))
        if change == "revision":
            case.conn.execute("UPDATE PartOperations SET unit_hours=9 WHERE id=?", (case.template_id,))
        else:
            case.conn.execute("DELETE FROM PartOperations WHERE id=?", (case.template_id,))
            if change == "recreated":
                insert_row(case.conn, "PartOperations", dict(part_no="P1", seq=1, op_type_id="T1", op_type_name="Turning",
                                                            source="internal", setup_hours=0, unit_hours=1))
    source_event = lineage(case, op_id)["events"][saved["operation_ref"]][-1]["event_id"]
    case.batch_service.copy_batch("SOURCE", "CHILD")
    child_id = operations(case, "CHILD")[0]["id"]
    child = origin(case, child_id)
    assert child["template_operation_ref"] == saved["template_operation_ref"]
    assert child["template_revision"] == saved["template_revision"]
    assert child["template_snapshot"] == saved["template_snapshot"]
    assert child["source_event_id"] == source_event and child["source_eligible"] == 1
    with TransactionManager(case.conn).transaction():
        case.conn.execute("UPDATE BatchOperations SET unit_hours=7 WHERE id=?", (op_id,))
    assert lineage(case, child_id)["problems"][child["operation_ref"]] == []
    assert origin(case, child_id) == child
    assert origin(case, op_id) == saved
    case.batch_service.copy_batch("CHILD", "GRANDCHILD")
    descendant = origin(case, operations(case, "GRANDCHILD")[0]["id"])
    assert descendant["source_lineage_ref"] == child["lineage_ref"]
    assert descendant["source_operation_ref"] == child["operation_ref"]
    assert descendant["source_eligible"] == 1


@pytest.mark.parametrize("contamination", ["modified", "withdrawn"])
def test_five_completed_copies_of_polluted_or_withdrawn_source_are_not_samples(legacy_case, contamination):
    case = legacy_case
    op_id = create(case, "SOURCE")
    saved = origin(case, op_id)
    with TransactionManager(case.conn).transaction():
        if contamination == "modified":
            case.conn.execute("UPDATE BatchOperations SET unit_hours=3 WHERE id=?", (op_id,))
            case.conn.execute("UPDATE BatchOperations SET unit_hours=1 WHERE id=?", (op_id,))
        else:
            case.lineage_writer.withdraw(saved["operation_ref"], "source withdrawn")
    source_event = lineage(case, op_id)["events"][saved["operation_ref"]][-1]["event_id"]
    ids = []
    for index in range(5):
        code = "DIRTY-" + str(index)
        case.batch_service.copy_batch("SOURCE", code)
        ids.append(operations(case, code)[0]["id"])
        child = origin(case, ids[-1])
        assert child["source_lineage_ref"] == saved["lineage_ref"] and child["source_eligible"] == 0
        assert child["source_event_id"] == source_event
    case.plan(1, ids)
    for child_id in ids:
        case.command("create", case.task(1, child_id), case.values(10))
    before = stored_state(case.conn)
    facts = calibration(case)
    samples = {row["sample_ref"]: row for row in facts["samples_by_template"][saved["template_operation_ref"]]}
    for child_id in ids:
        sample = samples[origin(case, child_id)["operation_ref"]]
        assert not sample["eligible"]
        assert {row["code"] for row in sample["exclusion_reasons"]} == {"template_copy_source_unqualified"}
    assert facts["rows"][0]["sample_count"] == 0 and facts["rows"][0]["suggested_unit_hours"] is None
    assert stored_state(case.conn) == before
    case.batch_service.copy_batch("DIRTY-0", "DIRTY-GRANDCHILD")
    assert origin(case, operations(case, "DIRTY-GRANDCHILD")[0]["id"])["source_eligible"] == 0


def test_unbound_identical_instances_remain_unbound_after_five_complete_legacy_copies(legacy_case):
    case = legacy_case
    case.batch_service.create("UNBOUND", "P1", 10)
    with TransactionManager(case.conn).transaction():
        insert_row(case.conn, "BatchOperations", dict(op_code="UNBOUND_01", batch_id="UNBOUND", seq=1,
            op_type_id="T1", op_type_name="Turning", source="internal", setup_hours=0, unit_hours=1))
    ids = []
    for index in range(5):
        code = "UNBOUND-" + str(index)
        case.batch_service.copy_batch("UNBOUND", code)
        ids.append(operations(case, code)[0]["id"])
    case.plan(1, ids)
    for op_id in ids:
        case.command("create", case.task(1, op_id), case.values(10))
    before = stored_state(case.conn)
    facts = calibration(case)
    assert case.conn.execute("SELECT count(*) FROM WorkbenchTemplateLineageOrigins").fetchone()[0] == 0
    assert facts["rows"][0]["candidate_count"] == 6
    assert facts["rows"][0]["sample_count"] == facts["rows"][0]["eligible_sample_count"] == 0
    assert facts["rows"][0]["suggested_unit_hours"] is None
    assert all(sample["template_operation_ref"] is None for sample in facts["samples_by_part"]["P1"])
    assert stored_state(case.conn) == before


def test_mixed_bound_and_unbound_pieces_do_not_share_origin(legacy_case):
    case = legacy_case
    create(case, "MIXED")
    with TransactionManager(case.conn).transaction():
        insert_row(case.conn, "BatchOperations", dict(op_code="MIXED_01_piece", batch_id="MIXED", seq=1,
            piece_id="piece", op_type_id="T1", op_type_name="Turning", source="internal", setup_hours=0, unit_hours=1))
    source_rows = operations(case, "MIXED")
    before = all_rows(case.conn)
    case.batch_service.copy_batch("MIXED", "MIXED-COPY")
    copied_rows = operations(case, "MIXED-COPY")
    assert len(copied_rows) == len(source_rows) == 4
    for source, copied in zip(source_rows, copied_rows):
        assert_raw_copy(source, copied, "MIXED-COPY")
        if source["piece_id"] is not None:
            assert not lineage(case, source["id"])["origins"]
            assert not lineage(case, copied["id"])["origins"]
        else:
            assert origin(case, copied["id"])["source_lineage_ref"] == origin(case, source["id"])["lineage_ref"]
    assert all_rows(case.conn)["WorkbenchTemplateLineageOrigins"][:len(before["WorkbenchTemplateLineageOrigins"])] == before["WorkbenchTemplateLineageOrigins"]


def test_empty_batch_copy_keeps_legacy_signature_and_business_fields(legacy_case):
    case = legacy_case
    case.batch_service.create("EMPTY", "P1", 7, remark="no operations")
    before = all_rows(case.conn)
    result = case.batch_service.copy_batch(source_batch_id=" EMPTY ", new_batch_id=" EMPTY-COPY ")
    assert result.batch_id == "EMPTY-COPY" and result.quantity == 7 and result.remark == "no operations"
    assert result.status == "pending" and operations(case, "EMPTY-COPY") == []
    after = all_rows(case.conn)
    assert_only_copy_appends(before, after, 1, 0)


def test_damaged_lineage_schema_does_not_fall_back_to_model_copy(legacy_case):
    case = legacy_case
    create(case, "SOURCE")
    case.conn.execute("DROP INDEX idx_wb_lineage_template_revision")
    case.conn.commit()
    before = stored_state(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        case.batch_service.copy_batch("SOURCE", "BLOCKED")
    assert stored_state(case.conn) == before
    assert not case.conn.in_transaction


@pytest.mark.parametrize("source,destination,error", [
    ("", "COPY", ValidationError), ("SOURCE", "", ValidationError), ("SOURCE", "SOURCE", ValidationError),
    ("MISSING", "COPY", BusinessError), ("SOURCE", "EXISTS", BusinessError),
])
def test_legacy_input_validation_has_no_side_effect(legacy_case, source, destination, error):
    case = legacy_case
    create(case, "SOURCE")
    case.batch_service.create("EXISTS", "P1", 10)
    before = stored_state(case.conn)
    with pytest.raises(error):
        case.batch_service.copy_batch(source, destination)
    assert stored_state(case.conn) == before
