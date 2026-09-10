"""Real groups, complete shift patterns, and deletion/revision contracts."""

from copy import deepcopy

import pytest

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from tests.workbench.identity_metadata_support import insert_row, table_rows
from tests.workbench.resource_entity_support import (
    FIXED_FIELDS,
    ROTATING_FIELDS,
    create_catalog,
    identity_for,
    resource_database,
    resource_row,
    resource_service,
    run_resource,
    stored_state,
)


@pytest.mark.parametrize("fields", (FIXED_FIELDS, ROTATING_FIELDS))
def test_fixed_and_rotating_patterns_roundtrip_exact_explicit_times(resource_conn, fields):
    conn = resource_conn
    calendars = table_rows(conn, "OperatorCalendar"), table_rows(conn, "WorkCalendar")
    identity = create_catalog(conn, "shift_profile", fields=fields)
    adapter = resource_service(conn, "shift_profile")
    snapshot = adapter.snapshot(identity)
    row = snapshot["record"]
    assert row == {"profile_id": "SHIFT1", "name": "SHIFT1", "status": "active", "remark": None,
                   "anchor_date": fields["anchor_date"], "cycle_days": fields["cycle_days"],
                   "created_at": row["created_at"]}
    expected = [{"profile_id": "SHIFT1", **day, "is_rest": int(day["is_rest"])} for day in fields["pattern"]]
    assert snapshot["pattern"] == expected and snapshot["members"] == []
    run_resource(conn, "operator", "update", {"relationships": {"shift_profile_ref": identity.ref}})
    operator = resource_service(conn, "operator").snapshot(identity_for(conn, "operator"))
    assert operator["shift_pattern"] == expected
    assert (table_rows(conn, "OperatorCalendar"), table_rows(conn, "WorkCalendar")) == calendars
    assert len(table_rows(conn, "WorkbenchShiftProfiles")) == 1


@pytest.mark.parametrize("field", ("anchor_date", "cycle_days", "pattern"))
def test_shift_creation_never_invents_missing_anchor_cycle_or_day_times(resource_conn, field):
    fields = deepcopy(FIXED_FIELDS)
    del fields[field]
    before = stored_state(resource_conn)
    with pytest.raises(ValidationError):
        create_catalog(resource_conn, "shift_profile", fields=fields)
    assert stored_state(resource_conn) == before


@pytest.mark.parametrize("field,values", [
    ("anchor_date", (None, "", "2026-02-29", "2026-9-09", "20260909", "2026-09-09T00:00:00", True, float("nan"))),
    ("cycle_days", (None, "", True, False, 1.0, float("nan"), 0, -1, 367)),
    ("pattern", (None, {}, [], True, float("nan"))),
    ("status", (None, "", True, float("nan"), "unknown")),
    ("unknown", (None,)),
])
def test_invalid_catalog_fields_cannot_write_partial_rows(resource_conn, field, values):
    for value in values:
        fields = {**deepcopy(FIXED_FIELDS), field: value}
        before = stored_state(resource_conn)
        with pytest.raises(ValidationError):
            create_catalog(resource_conn, "shift_profile", fields=fields)
        assert stored_state(resource_conn) == before


@pytest.mark.parametrize("bad", [
    {"day_offset": True}, {"day_offset": 1}, {"day_offset": -1}, {"day_offset": None},
    {"is_rest": 0}, {"is_rest": None}, {"is_rest": "false"}, {"unknown": 0},
    {"shift_start": None}, {"shift_start": ""}, {"shift_start": "7:00"}, {"shift_start": "24:00"},
    {"shift_end": "07:60"}, {"shift_end": "07:00:00"}, {"shift_end": True},
])
def test_pattern_requires_each_day_offset_boolean_and_valid_explicit_times(resource_conn, bad):
    fields = deepcopy(FIXED_FIELDS)
    fields["pattern"][0].update(bad)
    before = stored_state(resource_conn)
    with pytest.raises(ValidationError):
        create_catalog(resource_conn, "shift_profile", fields=fields)
    assert stored_state(resource_conn) == before


@pytest.mark.parametrize("mode", ("missing_time", "duplicate", "gap", "cycle_mismatch", "rest_missing_time"))
def test_incomplete_or_duplicate_pattern_rejects_without_synthetic_shifts(resource_conn, mode):
    fields = deepcopy(ROTATING_FIELDS)
    if mode in ("missing_time", "rest_missing_time"):
        del fields["pattern"][2 if mode == "rest_missing_time" else 0]["shift_start"]
    elif mode == "duplicate":
        fields["pattern"][1]["day_offset"] = 0
    elif mode == "gap":
        fields["pattern"].pop(1)
    else:
        fields["cycle_days"] = 2
    before = stored_state(resource_conn)
    with pytest.raises(ValidationError):
        create_catalog(resource_conn, "shift_profile", fields=fields)
    assert stored_state(resource_conn) == before


@pytest.mark.parametrize("kind", ("machine_group", "shift_profile"))
def test_catalog_no_difference_keeps_revision_and_all_rows(resource_conn, kind):
    identity = create_catalog(resource_conn, kind)
    before = stored_state(resource_conn)
    payload = {"label": identity.entity_key, "fields": deepcopy(FIXED_FIELDS) if kind == "shift_profile" else {}}
    result = run_resource(resource_conn, kind, "update", payload)
    assert result["result"] == "unchanged" and identity_for(resource_conn, kind) == identity
    assert stored_state(resource_conn)[:3] == before[:3]


@pytest.mark.parametrize("kind,owner,relation", (
    ("machine_group", "machine", "group_ref"), ("shift_profile", "operator", "shift_profile_ref"),
))
def test_used_catalog_deletion_rejected_then_explicit_unlink_allows_delete(resource_conn, kind, owner, relation):
    catalog = create_catalog(resource_conn, kind)
    run_resource(resource_conn, owner, "update", {"relationships": {relation: catalog.ref}})
    before = stored_state(resource_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_resource(resource_conn, kind, "delete", {})
    assert error.value.code == "constraint_conflict" and stored_state(resource_conn) == before
    run_resource(resource_conn, owner, "update", {"relationships": {relation: None}})
    run_resource(resource_conn, kind, "delete", {})
    assert identity_for(resource_conn, kind) is None and resource_row(resource_conn, kind) is None


@pytest.mark.parametrize("kind,owner,relation", (
    ("machine_group", "machine", "group_ref"), ("shift_profile", "operator", "shift_profile_ref"),
))
@pytest.mark.parametrize("bad", ("inactive", "team", "unknown", "deleted"))
def test_catalog_relations_reject_inactive_wrong_kind_unknown_and_retired_refs(resource_conn, kind, owner, relation, bad):
    conn = resource_conn
    catalog = create_catalog(conn, kind)
    ref = catalog.ref
    if bad == "inactive":
        run_resource(conn, kind, "update", {"fields": {"status": "inactive"}})
    elif bad == "team":
        ref = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='resource_team' AND active=1").fetchone()[0]
    elif bad == "unknown":
        ref = "f" * 48
    else:
        run_resource(conn, kind, "delete", {})
        create_catalog(conn, kind)
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected):
        run_resource(conn, owner, "update", {"relationships": {relation: ref}})
    assert stored_state(conn) == before


@pytest.mark.parametrize("dependency", ("machines", "skills", "supplier_capabilities", "part_operations", "batch_operations", "legacy_suppliers"))
@pytest.mark.parametrize("action", ("delete", "change_category"))
def test_op_type_dependencies_block_deletion_and_source_change(resource_conn, dependency, action):
    conn = resource_conn
    seeds = {
        "machines": ("Machines", {"machine_id": "DEP", "name": "dependency", "op_type_id": "OT2"}),
        "skills": ("OperatorSkill", {"operator_id": "EMPTY", "op_type_id": "OT2"}),
        "supplier_capabilities": ("WorkbenchSupplierOpTypes", {"supplier_id": "S1", "op_type_id": "OT2"}),
        "part_operations": ("PartOperations", {"part_no": "P1", "seq": 2, "op_type_id": "OT2", "op_type_name": "OT2", "source": "internal"}),
        "batch_operations": ("BatchOperations", {"op_code": "B1:2", "batch_id": "B1", "seq": 2, "op_type_id": "OT2", "op_type_name": "OT2"}),
        "legacy_suppliers": ("Suppliers", {"supplier_id": "DEP", "name": "dependency", "op_type_id": "OT2"}),
    }
    insert_row(conn, *seeds[dependency])
    conn.commit()
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_resource(conn, "op_type", "delete" if action == "delete" else "update",
                     {} if action == "delete" else {"fields": {"category": "external"}}, code="OT2")
    assert error.value.code == "constraint_conflict" and stored_state(conn) == before


def test_external_policy_is_explicit_and_clear_preserves_other_op_type_fields(resource_conn):
    conn = resource_conn
    before = resource_row(conn, "op_type", "EXT")
    for mode in ("merged", "separate", None):
        result = run_resource(conn, "op_type", "update", {"fields": {"default_merge_mode": mode}}, code="EXT")
        assert result["result"] == "committed"
        snapshot = resource_service(conn, "op_type").snapshot(identity_for(conn, "op_type", "EXT"))
        assert snapshot["profile"] == ({"op_type_id": "EXT", "default_merge_mode": mode} if mode else None)
        assert resource_row(conn, "op_type", "EXT") == before
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected):
        run_resource(conn, "op_type", "update", {"fields": {"default_merge_mode": "merged"}})
    assert stored_state(conn) == before


@pytest.mark.parametrize("failure", ("pattern", "cancel"))
def test_partial_shift_pattern_update_rolls_back_header_days_and_refs(resource_conn, monkeypatch, failure):
    conn = resource_conn
    create_catalog(conn, "shift_profile", fields=ROTATING_FIELDS)
    adapter = resource_service(conn, "shift_profile")
    before = stored_state(conn)
    seen = []

    def fail(*_args):
        seen.append(True)
        assert stored_state(conn) != before and conn.in_transaction
        raise RuntimeError("abort partial shift save")

    callback = fail if failure == "cancel" else None
    if failure == "pattern":
        original = adapter.repo.execute

        def execute(sql, params=()):
            result = original(sql, params)
            if "INSERT INTO WorkbenchShiftPatternDays" in sql:
                fail()
            return result

        monkeypatch.setattr(adapter.repo, "execute", execute)
    with pytest.raises(WorkbenchCommandUncertain):
        run_resource(conn, "shift_profile", "update", {"label": "changed", "fields": deepcopy(FIXED_FIELDS)},
                     adapter=adapter, after_apply=callback)
    assert seen == [True] and stored_state(conn) == before and not conn.in_transaction
