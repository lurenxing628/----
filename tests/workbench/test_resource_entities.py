"""Resource CRUD must preserve legacy facts and use explicit, atomic relations."""

from copy import deepcopy
from dataclasses import replace

import pytest

from core.errors import BusinessError, ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.personnel.operator_service import OperatorService
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import business_snapshot, insert_row, table_rows
from tests.workbench.resource_entity_support import (
    ENTITY_TABLES,
    NEW_TABLES,
    create_catalog,
    explicit_operator,
    identity_for,
    invalid_entity_inputs,
    resource_database,
    resource_row,
    resource_service,
    run_resource,
    stored_state,
)


@pytest.mark.parametrize("kind,action,payload", list(invalid_entity_inputs()))
def test_invalid_resource_input_is_rejected_before_io(schema_conn, kind, action, payload):
    before = stored_state(schema_conn), schema_conn.total_changes
    with pytest.raises(ValidationError):
        run_resource(schema_conn, kind, action, payload)
    assert (stored_state(schema_conn), schema_conn.total_changes) == before


@pytest.mark.parametrize("kind", ("op_type", "machine", "operator"))
def test_crud_persists_real_whitelisted_fields_and_retires_identity(resource_conn, kind):
    conn = resource_conn
    fields = {"remark": " first "}
    if kind == "op_type":
        fields["category"] = "external"
    elif kind == "machine":
        fields.update(status="maintain", category=" grinding ")
    else:
        fields["status"] = "active"
    baseline = business_snapshot(conn)
    result = run_resource(conn, kind, "create", {"business_code": " NEW ", "label": " new name ", "fields": fields})
    identity = identity_for(conn, kind, "NEW")
    row = resource_row(conn, kind, "NEW")
    assert result["result"] == "committed" and result["data"] == {"entity_ref": identity.ref, "business_code": "NEW"}
    key = ENTITY_TABLES[kind][1]
    expected = {key: "NEW", "name": "new name", "remark": "first", "created_at": row["created_at"]}
    expected.update({"category": "external", "default_hours": None} if kind == "op_type" else
                    {"team_id": None, "status": "maintain", "category": "grinding", "op_type_id": None}
                    if kind == "machine" else {"team_id": None, "status": "active"})
    if kind != "op_type":
        expected["updated_at"] = row["updated_at"]
    assert row == expected and row["created_at"]
    assert all(not table_rows(conn, name) for name in NEW_TABLES)
    run_resource(conn, kind, "update", {"label": "renamed", "fields": {"remark": None}}, code="NEW")
    updated = resource_row(conn, kind, "NEW")
    expected = {**row, "name": "renamed", "remark": None}
    if kind != "op_type":
        expected["updated_at"] = updated["updated_at"]
    assert updated == expected
    result = run_resource(conn, kind, "delete", {}, code="NEW")
    assert result["result"] == "committed" and resource_row(conn, kind, "NEW") is None
    retired = WorkbenchIdentityRepository(conn).get(identity.ref)
    assert not retired.active and retired.revision > identity.revision
    assert business_snapshot(conn) == baseline
    assert not conn.in_transaction


@pytest.mark.parametrize("kind", ("op_type", "machine", "operator"))
@pytest.mark.parametrize("payload", ({}, {"fields": {}}, {"fields": {"remark": "keep"}}))
def test_no_difference_does_not_touch_revisions_or_hidden_fields(resource_conn, kind, payload):
    table, key, code = ENTITY_TABLES[kind]
    resource_conn.execute(f'UPDATE "{table}" SET remark=? WHERE "{key}"=?', ("keep", code))
    resource_conn.commit()
    identity, before = identity_for(resource_conn, kind), business_snapshot(resource_conn)
    result = run_resource(resource_conn, kind, "update", payload)
    assert result["result"] == "unchanged"
    assert identity_for(resource_conn, kind) == identity
    assert business_snapshot(resource_conn) == before


@pytest.mark.parametrize("kind", ("machine", "operator"))
@pytest.mark.parametrize("raw", (None, " Legacy HOLD ", "inactive"))
def test_omitted_raw_unknown_status_is_not_normalized_or_given_a_reason(resource_conn, kind, raw):
    table, key, code = ENTITY_TABLES[kind]
    resource_conn.execute(f'UPDATE "{table}" SET status=? WHERE "{key}"=?', (raw, code))
    resource_conn.commit()
    before = resource_row(resource_conn, kind)
    run_resource(resource_conn, kind, "update", {"label": "changed"})
    row = resource_row(resource_conn, kind)
    assert row == {**before, "name": "changed", "updated_at": row["updated_at"]}
    assert row["updated_at"] != before["updated_at"]
    snapshot = resource_service(resource_conn, kind).snapshot(identity_for(resource_conn, kind))
    assert snapshot["record"]["status"] == raw and snapshot["profile"] is None


def test_groups_are_explicit_and_never_rewrite_legacy_teams(resource_conn):
    conn = resource_conn
    old = resource_service(conn, "machine").snapshot(identity_for(conn, "machine"))
    assert old["record"]["team_id"] == "T1" and old["group"] is None
    group = create_catalog(conn, "machine_group")
    baseline = resource_row(conn, "machine"), table_rows(conn, "ResourceTeams"), table_rows(conn, "OperatorMachine")
    for ref in (group.ref, None):
        before = identity_for(conn, "machine")
        result = run_resource(conn, "machine", "update", {"relationships": {"group_ref": ref}})
        assert result["result"] == "committed" and identity_for(conn, "machine").revision > before.revision
        snapshot = resource_service(conn, "machine").snapshot(identity_for(conn, "machine"))
        assert (snapshot["group"]["identity"]["ref"] if snapshot["group"] else None) == ref
        assert (resource_row(conn, "machine"), table_rows(conn, "ResourceTeams"), table_rows(conn, "OperatorMachine")) == baseline


def test_skills_preserve_retained_metadata_and_never_derive_machine_authorizations(resource_conn):
    conn = resource_conn
    original = dict(conn.execute("SELECT * FROM OperatorSkill WHERE operator_id='O1'").fetchone())
    permissions = table_rows(conn, "OperatorMachine")
    refs = [identity_for(conn, "op_type", code).ref for code in ("OT1", "OT2")]
    run_resource(conn, "operator", "update", {"relationships": {"skill_refs": refs}})
    assert dict(conn.execute("SELECT * FROM OperatorSkill WHERE id=?", (original["id"],)).fetchone()) == original
    assert table_rows(conn, "OperatorMachine") == permissions
    before = stored_state(conn)
    identity = identity_for(conn, "operator")
    result = run_resource(conn, "operator", "update", {"relationships": {"skill_refs": refs[::-1]}})
    assert result["result"] == "unchanged" and identity_for(conn, "operator") == identity
    assert stored_state(conn)[:3] == before[:3]
    run_resource(conn, "operator", "update", {"relationships": {"skill_refs": [refs[1]]}})
    assert [row["op_type_id"] for row in conn.execute("SELECT * FROM OperatorSkill WHERE operator_id='O1'")] == ["OT2"]
    run_resource(conn, "operator", "update", {"relationships": {"skill_refs": []}})
    assert not conn.execute("SELECT * FROM OperatorSkill WHERE operator_id='O1'").fetchall()
    assert table_rows(conn, "OperatorMachine") == permissions


def test_explicit_empty_skills_are_distinct_from_never_registered(resource_conn):
    conn = resource_conn
    initial = resource_service(conn, "operator").snapshot(identity_for(conn, "operator", "EMPTY"))
    assert initial["skills"] == [] and initial["profile"] is None
    identity = identity_for(conn, "operator", "EMPTY")
    result = run_resource(conn, "operator", "update", {"relationships": {"skill_refs": []}}, code="EMPTY")
    saved = resource_service(conn, "operator").snapshot(identity_for(conn, "operator", "EMPTY"))
    assert result["result"] == "committed" and saved["identity"]["revision"] > identity.revision
    assert saved["skills"] == []
    assert saved["profile"] == {"operator_id": "EMPTY", "skills_declared": 1,
                                "shift_profile_id": None, "inactive_reason": None}
    assert saved["record"] == initial["record"]


@pytest.mark.parametrize("status,reason", (("leave", "leave"), ("inactive", "disabled"), ("active", None)))
def test_status_meaning_is_explicit_and_preserves_shift_skills_and_calendar(resource_conn, status, reason):
    old = explicit_operator(resource_conn)
    calendar = table_rows(resource_conn, "OperatorCalendar")
    run_resource(resource_conn, "operator", "update", {"fields": {"status": status}})
    snapshot = resource_service(resource_conn, "operator").snapshot(identity_for(resource_conn, "operator"))
    assert snapshot["record"]["status"] == ("active" if status == "active" else "inactive")
    assert snapshot["profile"] == {**old["profile"], "inactive_reason": reason}
    for key in ("skills", "machine_authorizations", "shift", "shift_pattern"):
        assert snapshot[key] == old[key]
    assert table_rows(resource_conn, "OperatorCalendar") == calendar


@pytest.mark.parametrize("status", ("active", "inactive"))
def test_legacy_status_setter_clears_even_same_value_reason_without_erasing_profile(resource_conn, status):
    old = explicit_operator(resource_conn)
    calendar = table_rows(resource_conn, "OperatorCalendar")
    OperatorService(resource_conn).set_status("O1", status)
    snapshot = resource_service(resource_conn, "operator").snapshot(identity_for(resource_conn, "operator"))
    assert snapshot["profile"] == {**old["profile"], "inactive_reason": None}
    assert snapshot["skills"] == old["skills"] and snapshot["shift"] == old["shift"]
    assert snapshot["record"]["status"] == status
    assert table_rows(resource_conn, "OperatorCalendar") == calendar


@pytest.mark.parametrize("kind,relation", (("machine", "op_type_ref"), ("operator", "skill_refs")))
@pytest.mark.parametrize("bad", ("external", "unknown", "wrongkind", "deleted", "whitespace"))
def test_invalid_relation_identity_or_source_cannot_change_any_fact(resource_conn, kind, relation, bad):
    conn = resource_conn
    ref = identity_for(conn, "op_type", "EXT").ref
    if bad == "unknown":
        ref = "f" * 48
    elif bad == "wrongkind":
        ref = identity_for(conn, "machine").ref
    elif bad == "deleted":
        ref = identity_for(conn, "op_type", "OT2").ref
        conn.execute("DELETE FROM OpTypes WHERE op_type_id='OT2'")
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('OT2','recreated')")
    elif bad == "whitespace":
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES (' OT2 ','padded')")
        ref = identity_for(conn, "op_type", " OT2 ").ref
    conn.commit()
    before = stored_state(conn)
    payload = {"label": "must not change", "relationships": {relation: [ref] if relation == "skill_refs" else ref}}
    with pytest.raises(WorkbenchCommandRejected):
        run_resource(conn, kind, "update", payload)
    assert stored_state(conn) == before and not conn.in_transaction


@pytest.mark.parametrize("kind", ("op_type", "machine", "operator"))
@pytest.mark.parametrize("action", ("update", "delete"))
def test_recreated_and_old_whitespace_business_codes_reject_stale_writes(resource_conn, kind, action):
    conn = resource_conn
    run_resource(conn, kind, "create", {"business_code": "SAFE", "label": "safe"})
    old = identity_for(conn, kind, "SAFE")
    run_resource(conn, kind, "delete", {}, identity=old)
    run_resource(conn, kind, "create", {"business_code": "SAFE", "label": "new"})
    table, key, _ = ENTITY_TABLES[kind]
    insert_row(conn, table, {key: " SAFE ", "name": "padded"})
    conn.commit()
    before = stored_state(conn)
    for identity in (old, identity_for(conn, kind, " SAFE ")):
        with pytest.raises(WorkbenchCommandRejected):
            run_resource(conn, kind, action, {} if action == "delete" else {"label": "wrong"}, identity=identity)
    assert stored_state(conn) == before


@pytest.mark.parametrize("kind", ("op_type", "machine", "operator"))
def test_forged_or_stale_current_identity_is_rejected(resource_conn, kind):
    identity = identity_for(resource_conn, kind)
    before = stored_state(resource_conn)
    for bad in (replace(identity, kind="material"), replace(identity, entity_key="other"),
                replace(identity, revision=identity.revision + 1), replace(identity, ref="f" * 48),
                replace(identity, active=False)):
        with pytest.raises(WorkbenchCommandRejected):
            run_resource(resource_conn, kind, "update", {"label": "must not save"}, identity=bad)
    assert stored_state(resource_conn) == before


@pytest.mark.parametrize("mode", ("profile_failure", "receipt_failure", "cancel"))
@pytest.mark.parametrize("clear", (False, True))
def test_profile_save_and_clear_failure_rolls_back_every_table(resource_conn, monkeypatch, mode, clear):
    conn = resource_conn
    old = explicit_operator(conn)
    command, adapter = WorkbenchCommandService(conn), resource_service(conn, "operator")
    before = stored_state(conn)
    calls = []

    def fail_after_write(original):
        def fail(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(result)
            assert conn.in_transaction and stored_state(conn) != before
            raise RuntimeError("injected failure after actual write")
        return fail

    callback = None
    if mode == "profile_failure":
        monkeypatch.setattr(adapter.repo, "set_operator_profile", fail_after_write(adapter.repo.set_operator_profile))
    elif mode == "receipt_failure":
        monkeypatch.setattr(command.repo, "insert", fail_after_write(command.repo.insert))
    else:
        callback = fail_after_write(lambda outcome: outcome)
    payload = {"label": "temporary", "fields": {"status": "active" if clear else "inactive"},
               "relationships": {"shift_profile_ref": None if clear else old["shift"]["identity"]["ref"],
                                 "skill_refs": [] if clear else [identity_for(conn, "op_type", "OT2").ref]}}
    with pytest.raises(WorkbenchCommandUncertain):
        run_resource(conn, "operator", "update", payload, command=command, adapter=adapter, after_apply=callback)
    assert len(calls) == 1 and stored_state(conn) == before and not conn.in_transaction


@pytest.mark.parametrize("kind", ("op_type", "machine", "operator"))
def test_snapshot_is_readonly_normalization_is_pure_and_apply_requires_outer_transaction(resource_conn, kind):
    adapter = resource_service(resource_conn, kind)
    identity = identity_for(resource_conn, kind)
    payload = {"label": " changed ", "fields": {"remark": " \t"}}
    original = deepcopy(payload)
    before, changes = stored_state(resource_conn), resource_conn.total_changes
    resource_conn.execute("PRAGMA query_only=ON")
    try:
        assert adapter.normalize_input("update", payload) == {
            "label": "changed", "fields": {"remark": None}, "relationships": {}}
        assert adapter.snapshot(identity)["record"] == resource_row(resource_conn, kind)
        with pytest.raises(RuntimeError, match="\u5916\u5c42"):
            adapter.apply("update", {}, identity)
    finally:
        resource_conn.execute("PRAGMA query_only=OFF")
    assert stored_state(resource_conn) == before and resource_conn.total_changes == changes and payload == original


def test_command_owns_begin_immediate_and_duplicate_create_does_not_overwrite(resource_conn):
    statements = []
    resource_conn.set_trace_callback(statements.append)
    try:
        run_resource(resource_conn, "machine", "update", {"label": "real update"})
    finally:
        resource_conn.set_trace_callback(None)
    assert "BEGIN IMMEDIATE" in statements and "COMMIT" in statements
    before = stored_state(resource_conn)
    with pytest.raises(BusinessError):
        run_resource(resource_conn, "machine", "create", {"business_code": "M1", "label": "overwrite"})
    assert stored_state(resource_conn) == before


def test_machine_op_type_switch_and_clear_update_real_column_only(resource_conn):
    conn = resource_conn
    for ref, code in ((identity_for(conn, "op_type", "OT2").ref, "OT2"), (None, None)):
        old = resource_row(conn, "machine")
        permissions = table_rows(conn, "OperatorMachine")
        result = run_resource(conn, "machine", "update", {"relationships": {"op_type_ref": ref}})
        row = resource_row(conn, "machine")
        assert result["result"] == "committed"
        assert row == {**old, "op_type_id": code, "updated_at": row["updated_at"]}
        assert table_rows(conn, "OperatorMachine") == permissions
        before = stored_state(conn)
        result = run_resource(conn, "machine", "update", {"relationships": {"op_type_ref": ref}})
        assert result["result"] == "unchanged" and stored_state(conn)[:3] == before[:3]


@pytest.mark.parametrize("kind", ("op_type", "machine", "operator"))
@pytest.mark.parametrize("clear", (None, "", " \t"))
def test_remark_clear_preserves_omitted_business_fields(resource_conn, kind, clear):
    old = resource_row(resource_conn, kind)
    run_resource(resource_conn, kind, "update", {"fields": {"remark": clear}})
    row = resource_row(resource_conn, kind)
    expected = {**old, "remark": None}
    if kind != "op_type":
        expected["updated_at"] = row["updated_at"]
    assert row == expected


def test_normalizing_cancelled_profile_edit_does_not_write_any_facts(resource_conn):
    explicit_operator(resource_conn)
    adapter = resource_service(resource_conn, "operator")
    before = stored_state(resource_conn), resource_conn.total_changes
    for _ in range(2):
        adapter.snapshot(identity_for(resource_conn, "operator"))
        assert adapter.normalize_input("update", {"fields": {"status": "active"},
                                                  "relationships": {"skill_refs": [], "shift_profile_ref": None}}) == {
            "fields": {"status": "active"}, "relationships": {"skill_refs": [], "shift_profile_ref": None}}
    assert (stored_state(resource_conn), resource_conn.total_changes) == before


def test_missing_related_ref_snapshot_fails_without_repair(resource_conn):
    conn = resource_conn
    target = identity_for(conn, "op_type")
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE ref=?", (target.ref,))
    conn.commit()
    before, changes = stored_state(conn), conn.total_changes
    for kind in ("machine", "operator"):
        with pytest.raises(WorkbenchCommandRejected) as error:
            resource_service(conn, kind).snapshot(identity_for(conn, kind))
        assert error.value.code == "storage_failure"
    assert stored_state(conn) == before and conn.total_changes == changes
