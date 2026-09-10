"""R1-I: strict persisted DTOs and raw runtime validation remain unchanged."""

from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from core.models.external_group import ExternalGroup
from core.models.part_operation import PartOperation
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.run_input_external import prime_template_cache
from core.services.workbench.run_input_projection_codec import restore_execution_projections, validate_projection_dto
from core.services.workbench.run_input_runtime import _validate_stored_runtime
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


@pytest.mark.parametrize("target,patch,reason", [
    ("template", {"status": "deleted"}, "external_template_missing"),
    ("template", {"source": "internal"}, "external_template_missing"),
    ("template", {"op_type_id": "OTHER"}, "external_template_mismatch"),
    ("template", {"unit_hours": None}, "external_template_invalid"),
    ("group", {"part_no": "OTHER"}, "external_group_invalid"),
    ("group", {"merge_mode": "unknown"}, "external_group_invalid"),
    ("group", {"start_seq": 0}, "external_group_range_invalid"),
    ("group", {"end_seq": 0}, "external_group_range_invalid"),
    ("group", {"total_days": 0}, "external_group_days_invalid"),
])
def test_template_failures_do_not_publish_partial_cache(target, patch, reason):
    template = asdict(PartOperation(1, "P1", 1, op_type_id="EXT", source="external", ext_group_id="G1"))
    group = asdict(ExternalGroup("G1", "P1", 1, 2, merge_mode="merged", total_days=2))
    (template if target == "template" else group).update(patch)
    previous = object()
    svc = SimpleNamespace(_aps_schedule_input_cache=previous)
    op = SimpleNamespace(id=1, source="external", batch_id="B1", seq=1, op_type_id="EXT")
    with pytest.raises(CandidateRunInputError) as error:
        prime_template_cache(svc, {"PartOperations": [template], "ExternalGroups": [group]},
                             {"B1": SimpleNamespace(part_no="P1")}, [op])
    assert error.value.reason == reason
    assert svc._aps_schedule_input_cache is previous


@pytest.mark.parametrize("grouped", [False, True])
def test_template_cache_keeps_every_dataclass_field_and_zero_hours(grouped):
    template = PartOperation(1, "P1", 1, op_type_id="EXT", source="external",
                             ext_group_id="G1" if grouped else None, setup_hours=0, unit_hours=0)
    group = ExternalGroup("G1", "P1", 1, 2, total_days=None, remark="retained")
    svc = SimpleNamespace()
    op = SimpleNamespace(id=1, source="external", batch_id="B1", seq=1, op_type_id="EXT")
    batches = {"B1": SimpleNamespace(part_no="P1")}
    prime_template_cache(svc, {"PartOperations": [asdict(template)], "ExternalGroups": [asdict(group)]}, batches, [op])
    cache = svc._aps_schedule_input_cache
    assert cache["batch"] == batches and cache["tmpl"] == {("P1", 1): template}
    assert cache["grp"] == ({"G1": group} if grouped else {})


@pytest.mark.parametrize("missing,reason", [
    ("PartOperations", "external_template_missing"), ("ExternalGroups", "external_group_invalid"),
])
def test_absent_template_or_group_is_rejected_before_cache_publication(missing, reason):
    template = PartOperation(1, "P1", 1, op_type_id="EXT", source="external", ext_group_id="G1")
    group = ExternalGroup("G1", "P1", 1, 2)
    tables = {"PartOperations": [asdict(template)], "ExternalGroups": [asdict(group)]}
    tables[missing] = []
    svc = SimpleNamespace()
    op = SimpleNamespace(id=1, source="external", batch_id="B1", seq=1, op_type_id="EXT")
    with pytest.raises(CandidateRunInputError) as error:
        prime_template_cache(svc, tables, {"B1": SimpleNamespace(part_no="P1")}, [op])
    assert error.value.reason == reason
    assert not hasattr(svc, "_aps_schedule_input_cache")
