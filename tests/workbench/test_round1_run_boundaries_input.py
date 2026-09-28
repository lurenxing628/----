"""R1-I: strict persisted DTOs and raw runtime validation remain unchanged."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.facts.run_input_codec import restore_execution_projections, validate_projection_dto
from core.services.workbench.run.input_external import prime_template_cache
from core.services.workbench.run.input_runtime import _validate_stored_runtime
from tests.schedule.service.external_context_support import merged_snapshot, snapshot
from tests.workbench.run_compute_support import run_case as _run_case


@pytest.mark.parametrize("field,value", [
    ("operation_ref", "bad"), ("target_quantity", False), ("target_quantity", -1),
    ("known_completed_quantity", None), ("unknown_record_count", 0.5),
    ("remaining_quantity", float("inf")), ("quantity_complete", 0), ("records_complete", "true"),
    ("execution_state", "unknown"), ("data_quality", None), ("target_basis", "unknown"),
    ("completion_basis", "unknown"), ("reports", [{}]), ("legacy_facts", [None]),
    ("data_gaps", ()), ("plan_identity", []), ("remaining_plan", False), ("write_context", ""),
    ("first_actual_start", "invalid"), ("confirmed_finish", "2026-09-10T08:00:00+08:00"),
])
def test_projection_bad_types_never_default_or_coerce(run_case, field, value):
    projection = replace(run_case.projections()[0], **{field: value})
    with pytest.raises(CandidateRunInputError) as error:
        validate_projection_dto(projection)
    assert error.value.reason == "execution_projection_type"


def test_projection_full_roundtrip_preserves_null_zero_and_all_dto_fields(run_case):
    projection = replace(run_case.projections()[0], target_quantity=None, remaining_quantity=None,
                         legacy_facts=[{"nested": {"zero": 0, "unknown": None}}],
                         write_context={"raw": [None, False, 0]})
    validate_projection_dto(projection)
    restored, = restore_execution_projections([projection.to_dict()])
    assert restored == projection and restored.to_dict() == projection.to_dict()
    assert restored.known_completed_quantity == 0
    assert restored.target_quantity is None and restored.remaining_quantity is None


@pytest.mark.parametrize("damage", ["missing", "extra", "duplicate", "reports_not_list"])
def test_projection_restore_retains_exact_schema_and_reference_checks(run_case, damage):
    row = run_case.projections()[0].to_dict()
    payload = [row]
    if damage == "missing":
        row.pop("remaining_quantity")
    elif damage == "extra":
        row["unexpected"] = None
    elif damage == "duplicate":
        payload.append(dict(row))
    else:
        row["reports"] = None
    with pytest.raises(CandidateRunInputError) as error:
        restore_execution_projections(payload)
    assert error.value.reason == "execution_snapshot_invalid"


@pytest.fixture
def runtime_conn(mem_conn):
    for table in ("WorkCalendar", "OperatorCalendar"):
        mem_conn.execute("CREATE TABLE " + table + " (date,shift_hours,efficiency,day_type,"
                         "allow_normal,allow_urgent,shift_start,shift_end)")
        mem_conn.execute("INSERT INTO " + table + " VALUES (?,?,?,?,?,?,?,?)",
                         ("2026-09-10", 0, 1, "workday", "yes", "no", "08:00", None))
    mem_conn.execute("CREATE TABLE MachineDowntimes(status,start_time,end_time)")
    yield mem_conn


@pytest.mark.parametrize("table", ["WorkCalendar", "OperatorCalendar"])
@pytest.mark.parametrize("field,value,reason", [
    ("date", "2026-02-30", "invalid_calendar_date"),
    ("shift_hours", None, "invalid_calendar_number"),
    ("efficiency", 0, "invalid_calendar_number"),
    ("day_type", "unknown", "invalid_calendar_state"),
    ("allow_normal", None, "invalid_calendar_state"),
    ("allow_urgent", "unknown", "invalid_calendar_state"),
    ("shift_start", None, "invalid_calendar_shift"),
    ("shift_start", "8:00", "invalid_calendar_shift"),
    ("shift_end", "24:00", "invalid_calendar_shift"),
])
def test_each_calendar_rejects_unknown_values_in_private_legacy_db(runtime_conn, table, field, value, reason):
    runtime_conn.execute("UPDATE " + table + " SET " + field + "=?", (value,))
    before = runtime_conn.total_changes
    with pytest.raises(CandidateRunInputError) as error:
        _validate_stored_runtime(runtime_conn)
    assert error.value.reason == reason
    assert error.value.issues[0]["table"] == table
    assert runtime_conn.total_changes == before


@pytest.mark.parametrize("status,start,end,reason", [
    ("unknown", None, None, "invalid_downtime_state"),
    ("active", None, "2026-09-10T09:00:00", "invalid_downtime_interval"),
    ("active", "2026-09-10T08:00:00", "2026-09-10T08:00:00", "invalid_downtime_interval"),
    ("active", "2026-09-10T09:00:00", "2026-09-10T08:00:00", "invalid_downtime_interval"),
    ("active", "2026-09-10T08:00:00+08:00", "2026-09-10T09:00:00", "invalid_downtime_interval"),
    ("cancelled", None, None, None),
    ("active", "2026-09-10T08:00:00", "2026-09-10T09:00:00", None),
])
def test_downtime_retains_cancelled_and_positive_local_interval_cases(runtime_conn, status, start, end, reason):
    runtime_conn.execute("INSERT INTO MachineDowntimes VALUES (?,?,?)", (status, start, end))
    if reason is None:
        _validate_stored_runtime(runtime_conn)
    else:
        with pytest.raises(CandidateRunInputError) as error:
            _validate_stored_runtime(runtime_conn)
        assert error.value.reason == reason


def _external_scope(mode="merged"):
    operations, contexts = [], []
    for operation_id in (1, 2):
        operations.append(SimpleNamespace(id=operation_id, source="external", batch_id="B1", seq=operation_id,
                          op_type_id="EXT", supplier_id="S1", piece_id=None, setup_hours=0, unit_hours=0, ext_days=.25))
        fields = dict(operation_id=operation_id, part_no="P1", sequence=operation_id)
        if mode is None:
            contexts.append(snapshot(**fields))
        else:
            contexts.append(merged_snapshot(**fields, group_part_no="P1", group_id="G" + str(operation_id),
                            group_ref=str(operation_id) * 48, start_sequence=1, end_sequence=2,
                            merge_mode=mode, total_days=2 if mode == "merged" else None, supplier_id="S1"))
    tables = {"BatchExternalContexts": contexts, "BatchOperations": [vars(op).copy() for op in operations]}
    return tables, {"B1": SimpleNamespace(part_no="P1")}, operations


@pytest.mark.parametrize("patch,diagnostic", [
    ({"template_status": "deleted"}, "没有有效的模板工序"),
    ({"template_operation_id": None}, "没有有效的模板工序"),
    ({"template_operation_ref": "broken"}, "缺少模板工序来源编号"),
    ({"part_no": "OTHER"}, "零件或工序号不一致"),
    ({"group_part_no": "OTHER"}, "分组关系不完整"),
    ({"merge_mode": "unknown"}, "分组关系不完整"),
    ({"start_sequence": 0}, "分组范围与本工序不一致"),
    ({"end_sequence": 1}, "分组范围与本工序不一致"),
    ({"total_days": 0}, "整组外协周期未填写或无效"),
    ({"group_ref": None}, "分组缺少来源编号"),
    ({"supplier_id": "OTHER"}, "供应商与保存的规则不一致"),
])
def test_context_failures_do_not_publish_partial_cache(patch, diagnostic):
    tables, batches, operations = _external_scope()
    svc = SimpleNamespace()
    prime_template_cache(svc, tables, batches, operations)
    previous, before = svc._aps_schedule_input_cache, deepcopy(svc._aps_schedule_input_cache)
    damaged = deepcopy(tables)
    damaged["BatchExternalContexts"][1].update(patch)
    with pytest.raises(CandidateRunInputError) as error:
        prime_template_cache(svc, damaged, batches, operations)
    assert error.value.reason == "external_context_invalid"
    assert diagnostic in str(error.value)
    # The first operation is valid; failure must identify the second without replacing any cache.
    assert error.value.issues[0]["op_id"] == 2
    assert svc._aps_schedule_input_cache is previous and previous == before


@pytest.mark.parametrize("mode", [None, "separate", "merged"])
def test_context_cache_keeps_every_frozen_field_and_current_zero_hours(mode):
    tables, batches, operations = _external_scope(mode)
    original = deepcopy(tables)
    # Obsolete live template data cannot override a complete frozen context.
    tables.update(PartOperations=[{"status": "deleted", "source": "internal", "unit_hours": None}],
                  ExternalGroups=[{"total_days": 99}])
    svc = SimpleNamespace()
    prime_template_cache(svc, tables, batches, operations)
    cache = svc._aps_schedule_input_cache
    assert cache["batch"] == batches
    assert cache["external_contexts"] == {row["operation_id"]: row for row in original["BatchExternalContexts"]}
    assert cache["external_contexts_bound"] is True
    assert [vars(op) for op in operations] == original["BatchOperations"]
    assert all(op.setup_hours == op.unit_hours == 0 for op in operations)
    assert "tmpl" not in cache and "grp" not in cache


@pytest.mark.parametrize("missing", ["table", "contexts", "second_context", "members"])
def test_absent_context_or_members_are_rejected_before_cache_publication(missing):
    tables, batches, operations = _external_scope()
    if missing == "table":
        tables.pop("BatchExternalContexts")
    elif missing == "contexts":
        tables["BatchExternalContexts"] = []
    elif missing == "second_context":
        tables["BatchExternalContexts"].pop()
    else:
        tables["BatchOperations"] = []
    svc = SimpleNamespace()
    with pytest.raises(CandidateRunInputError) as error:
        prime_template_cache(svc, tables, batches, operations)
    assert error.value.reason == "external_context_invalid"
    assert ("完整成员资料" if missing == "members" else "周期记录缺失") in str(error.value)
    assert error.value.issues[0]["op_id"] == (2 if missing == "second_context" else 1)
    assert not hasattr(svc, "_aps_schedule_input_cache")
