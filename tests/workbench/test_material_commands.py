"""Private material commands: strict input, stable identities and atomic receipts."""

from copy import deepcopy
from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from core.errors import AppError, BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.material.material_service import MaterialService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.materials import WorkbenchMaterialService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_query_repo import WorkbenchMaterialQueryRepository
from tests.workbench.identity_metadata_support import business_snapshot
from tests.workbench.material_support import (
    CREATE,
    KEY,
    identity_for,
    invalid_payloads,
    material_database,
    material_row,
    run_material,
    stored_state,
)


@pytest.mark.parametrize("action,payload", list(invalid_payloads()))
def test_strict_json_rejects_invalid_input_without_io(action, payload):
    adapter = WorkbenchMaterialService(None)
    with pytest.raises(ValidationError):
        adapter.normalize_input(action, payload)


@pytest.mark.parametrize("action", (None, [], {}, True, "", "upsert", "UPDATE"))
def test_unknown_action_is_rejected_without_io(action):
    with pytest.raises(ValidationError):
        WorkbenchMaterialService.normalize_input(action, {})


def test_normalization_is_pure_stable_and_preserves_omissions(material_conn):
    adapter = WorkbenchMaterialService(material_conn)
    payload = {"label": " steel ", "fields": {"spec": None, "unit": " \t", "stock_qty": 2}}
    before = deepcopy(payload)
    expected = {"label": "steel", "fields": {"spec": None, "unit": None, "stock_qty": 2.0}}
    changes = material_conn.total_changes
    with patch.object(adapter._materials, "get", side_effect=AssertionError("unexpected read")), \
            patch.object(adapter._identities, "get", side_effect=AssertionError("unexpected read")):
        assert adapter.normalize_input("update", payload) == expected
    assert material_conn.total_changes == changes and not material_conn.in_transaction
    MaterialService(material_conn).update("MAT1", name="changed elsewhere")
    assert adapter.normalize_input("update", payload) == expected
    assert adapter.normalize_input("update", expected) == expected
    assert adapter.normalize_input("update", {}) == {"fields": {}}
    assert adapter.normalize_input("delete", {}) == {}
    assert payload == before


@pytest.mark.parametrize("fields", ({}, {"spec": " D50 ", "unit": " kg ", "stock_qty": 1.25,
                                        "status": "inactive", "remark": " new note "},
                                   {"spec": None, "unit": None, "remark": None, "stock_qty": 0}))
def test_create_uses_domain_service_and_persisted_ref(material_conn, fields):
    before = business_snapshot(material_conn)
    original = MaterialService.create
    calls = []

    def create(service, *args, **kwargs):
        calls.append((args, kwargs))
        assert service.conn.in_transaction
        return original(service, *args, **kwargs)

    with patch.object(MaterialService, "create", create):
        result = run_material(material_conn, "create", {"business_code": " MAT2 ", "label": " new steel ", "fields": fields})
    identity = identity_for(material_conn, "MAT2")
    assert len(calls) == 1 and calls[0][0] == ("MAT2", "new steel")
    assert result["result"] == "committed" and not result["replayed"]
    assert result["data"] == {"entity_ref": identity.ref, "business_code": "MAT2"}
    assert identity.ref != "MAT2" and identity.revision == 1
    row = material_row(material_conn, "MAT2")
    expected = {"material_id": "MAT2", "name": "new steel", "spec": None, "unit": None,
                "stock_qty": 0.0, "status": "active", "remark": None, "created_at": row["created_at"]}
    expected.update(WorkbenchMaterialService.normalize_input("create", {**CREATE, "fields": fields})["fields"])
    assert row == expected and row["created_at"]
    after = business_snapshot(material_conn)
    assert {k: v for k, v in after.items() if k != "Materials"} == {k: v for k, v in before.items() if k != "Materials"}
    assert after["Materials"][1][:-1] == before["Materials"][1]
    assert not material_conn.in_transaction


@pytest.mark.parametrize("payload,changed", [
    ({"label": " renamed "}, {"name": "renamed"}),
    ({"fields": {"stock_qty": 0}}, {"stock_qty": 0.0}),
    ({"fields": {"status": "active"}}, {"status": "active"}),
    ({"fields": {"spec": " D50 ", "unit": " piece ", "remark": " next "}},
     {"spec": "D50", "unit": "piece", "remark": "next"}),
])
def test_update_only_changes_supplied_columns_and_never_batch_facts(material_conn, payload, changed):
    conn = material_conn
    conn.execute("UPDATE Materials SET status = 'Legacy HOLD ' WHERE material_id = 'MAT1'")
    conn.commit()
    identity, before, row = identity_for(conn), business_snapshot(conn), material_row(conn)
    result = run_material(conn, "update", payload, identity=identity)
    assert result["result"] == "committed"
    assert material_row(conn) == {**row, **changed}
    assert identity_for(conn) == replace(identity, revision=identity.revision + 1)
    after = business_snapshot(conn)
    assert {k: v for k, v in after.items() if k != "Materials"} == {k: v for k, v in before.items() if k != "Materials"}
    assert result["data"] == {"entity_ref": identity.ref, "business_code": "MAT1"}


@pytest.mark.parametrize("key", ("spec", "unit", "remark"))
@pytest.mark.parametrize("clear", (None, "", " \t"))
def test_clear_translates_null_to_domain_empty_string_and_preserves_omitted_fields(material_conn, key, clear):
    row = material_row(material_conn)
    original, calls = MaterialService.update, []

    def update(service, material_id, **kwargs):
        calls.append(kwargs)
        return original(service, material_id, **kwargs)

    with patch.object(MaterialService, "update", update):
        result = run_material(material_conn, "update", {"fields": {key: clear}})
    assert calls == [{key: ""}] and result["result"] == "committed"
    assert material_row(material_conn) == {**row, key: None}


@pytest.mark.parametrize("payload", ({}, {"fields": {}}, {"label": " steel "},
                                   {"fields": {"stock_qty": 12.375, "spec": "D25", "status": "inactive"}}))
def test_unchanged_skips_domain_update_and_revision_but_has_atomic_receipt(material_conn, payload):
    identity, before = identity_for(material_conn), business_snapshot(material_conn)
    with patch.object(MaterialService, "update", side_effect=AssertionError("no-op must not update")):
        result = run_material(material_conn, "update", payload)
    assert result["result"] == "unchanged"
    assert identity_for(material_conn) == identity
    assert business_snapshot(material_conn) == before
    assert WorkbenchCommandService(material_conn).lookup(KEY) == {**result, "replayed": True}


def test_already_cleared_field_is_unchanged(material_conn):
    run_material(material_conn, "update", {"fields": {"spec": None}})
    identity = identity_for(material_conn)
    result = run_material(material_conn, "update", {"fields": {"spec": ""}}, key=KEY + "-again")
    assert result["result"] == "unchanged" and identity_for(material_conn) == identity


def test_duplicate_code_propagates_domain_rejection_without_overwrite(material_conn):
    before = stored_state(material_conn)
    with pytest.raises(BusinessError) as error:
        run_material(material_conn, "create", {**CREATE, "business_code": " MAT1 "})
    assert error.value.code == ErrorCode.DUPLICATE_ENTRY
    assert stored_state(material_conn) == before and not material_conn.in_transaction


@pytest.mark.parametrize("action", ("create", "update", "delete"))
def test_apply_refuses_to_own_transaction(material_conn, action):
    before = stored_state(material_conn)
    with pytest.raises(RuntimeError, match="外层"):
        WorkbenchMaterialService(material_conn).apply(action, CREATE if action == "create" else {}, identity_for(material_conn))
    assert stored_state(material_conn) == before


@pytest.mark.parametrize("action", ("update", "delete"))
@pytest.mark.parametrize("bad", ("missing", "pk", "dict", "kind", "inactive", "ref", "key", "revision"))
def test_apply_rechecks_identity_type_kind_liveness_and_current_row(material_conn, action, bad):
    identity = identity_for(material_conn)
    invalid = {"missing": None, "pk": "MAT1", "dict": {"ref": identity.ref},
               "kind": replace(identity, kind="machine"), "inactive": replace(identity, active=False),
               "ref": replace(identity, ref="missing-ref"), "key": replace(identity, entity_key="MAT2"),
               "revision": replace(identity, revision=identity.revision + 1)}[bad]
    before = stored_state(material_conn)
    with pytest.raises(WorkbenchCommandRejected):
        with TransactionManager(material_conn).transaction(begin_immediate=True):
            WorkbenchMaterialService(material_conn).apply(action, {}, invalid)
    assert stored_state(material_conn) == before


@pytest.mark.parametrize("action", ("update", "delete"))
def test_deleted_recreated_same_code_rejects_old_ref(material_conn, action):
    run_material(material_conn, "create", CREATE)
    old = identity_for(material_conn, "MAT2")
    deleted = run_material(material_conn, "delete", {}, identity=old, key=KEY + "-delete")
    assert deleted["data"] == {"entity_ref": old.ref, "business_code": "MAT2"}
    MaterialService(material_conn).create("MAT2", "new instance")
    current = identity_for(material_conn, "MAT2")
    assert current.ref != old.ref and current.revision == 1
    assert not WorkbenchIdentityRepository(material_conn).get(old.ref).active
    before = stored_state(material_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_material(material_conn, action, {"label": "unsafe"} if action == "update" else {},
                     identity=old, key=KEY + "-stale")
    assert error.value.code == "entity_not_found"
    assert stored_state(material_conn) == before


def test_referenced_delete_is_rejected_and_preserves_all_rows_and_refs(material_conn):
    before = stored_state(material_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_material(material_conn, "delete", {})
    assert error.value.code == "constraint_conflict" and error.value.committed is False
    assert isinstance(error.value.__cause__, AppError)
    assert stored_state(material_conn) == before and not material_conn.in_transaction
    assert not material_conn.execute("PRAGMA foreign_key_check").fetchall()


@pytest.mark.parametrize("action", ("create", "update", "delete", "unchanged"))
def test_receipt_failure_rolls_back_material_identity_and_receipt_together(material_conn, monkeypatch, action):
    if action == "delete":
        MaterialService(material_conn).create("MAT2", "delete candidate")
    identity = identity_for(material_conn, "MAT2" if action == "delete" else "MAT1")
    before = stored_state(material_conn)
    command = WorkbenchCommandService(material_conn)
    original = command.repo.insert

    def fail(**kwargs):
        original(**kwargs)
        raise OSError("fixture receipt failure after insert")

    monkeypatch.setattr(command.repo, "insert", fail)
    payload = CREATE if action == "create" else {"label": "changed"} if action == "update" else {}
    with pytest.raises(WorkbenchCommandUncertain):
        run_material(material_conn, "update" if action == "unchanged" else action, payload,
                     identity=None if action == "create" else identity, command=command)
    assert stored_state(material_conn) == before
    assert command.lookup(KEY) is None and not material_conn.in_transaction


@pytest.mark.parametrize("action", ("create", "update", "delete"))
def test_successful_nested_domain_mutation_does_not_commit_outer_transaction(material_conn, action):
    MaterialService(material_conn).create("MAT2", "delete candidate")
    identity = identity_for(material_conn, "MAT2")
    before = stored_state(material_conn)
    payload = {**CREATE, "business_code": "MAT3"} if action == "create" else {"label": "changed"} if action == "update" else {}
    with pytest.raises(RuntimeError, match="fixture outer failure"):
        with TransactionManager(material_conn).transaction(begin_immediate=True):
            result = WorkbenchMaterialService(material_conn).apply(action, payload, None if action == "create" else identity)
            assert result.result == "committed" and material_conn.in_transaction
            raise RuntimeError("fixture outer failure")
    assert stored_state(material_conn) == before


@pytest.mark.parametrize("action", ("create", "update", "delete", "unchanged"))
def test_atomic_receipt_replays_stable_facts_after_entity_changes(material_conn, action):
    MaterialService(material_conn).create("MAT2", "candidate")
    identity = identity_for(material_conn, "MAT2")
    payload = {**CREATE, "business_code": "MAT3"} if action == "create" else {"label": "changed"} if action == "update" else {}
    actual_action = "update" if action == "unchanged" else action
    passed_identity = None if action == "create" else identity
    first = run_material(material_conn, actual_action, payload, identity=passed_identity)
    code = first["data"]["business_code"]
    domain = MaterialService(material_conn)
    domain.delete(code)
    domain.create(code, "recreated after receipt")
    before = stored_state(material_conn)

    def expired():
        pytest.fail("receipt must replay before expired guard")

    second = run_material(material_conn, actual_action, payload, identity=passed_identity, guard=expired)
    assert second == {**first, "replayed": True}
    assert set(second["data"]) == {"entity_ref", "business_code"}
    assert second["data"]["entity_ref"] != identity_for(material_conn, code).ref
    assert stored_state(material_conn) == before
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_material(material_conn, "create", {**CREATE, "label": "different intent"})
    assert error.value.code == "request_key_conflict"


def test_snapshot_returns_all_model_fields_readonly_and_does_not_repair_missing_refs(material_conn):
    adapter = WorkbenchMaterialService(material_conn)
    identity = identity_for(material_conn)
    before, changes = stored_state(material_conn), material_conn.total_changes
    assert adapter.snapshot(identity) == {
        "identity": asdict(identity),
        "material": {**material_row(material_conn), "ref": identity.ref,
                     "revision": identity.revision, "requirement_count": 1},
    }
    assert stored_state(material_conn) == before and material_conn.total_changes == changes
    assert not material_conn.in_transaction
    material_conn.execute("DELETE FROM WorkbenchEntityRefs WHERE ref = ?", (identity.ref,))
    material_conn.commit()
    before, changes = stored_state(material_conn), material_conn.total_changes
    with pytest.raises(WorkbenchCommandRejected, match="引用已失效"):
        adapter.snapshot(identity)
    assert stored_state(material_conn) == before and material_conn.total_changes == changes


@pytest.mark.parametrize("value", (None, "corrupt"))
def test_snapshot_does_not_coerce_raw_stock_or_status(material_conn, value):
    material_conn.execute("UPDATE Materials SET stock_qty = ?, status = NULL WHERE material_id = 'MAT1'", (value,))
    material_conn.commit()
    before, changes = stored_state(material_conn), material_conn.total_changes
    snapshot = WorkbenchMaterialService(material_conn).snapshot(identity_for(material_conn))
    assert snapshot["material"]["stock_qty"] == value and snapshot["material"]["status"] is None
    assert stored_state(material_conn) == before and material_conn.total_changes == changes


@pytest.mark.parametrize("fields", ({"stock_qty": 0}, {"status": "active"},
                                   {"stock_qty": 0, "status": "active"}))
def test_null_to_default_is_a_real_update_and_omitted_null_is_preserved(material_conn, fields):
    material_conn.execute("UPDATE Materials SET stock_qty = NULL, status = NULL WHERE material_id = 'MAT1'")
    material_conn.commit()
    identity, row = identity_for(material_conn), material_row(material_conn)
    result = run_material(material_conn, "update", {"fields": fields})
    assert result["result"] == "committed"
    assert material_row(material_conn) == {**row, **fields}
    assert identity_for(material_conn) == replace(identity, revision=identity.revision + 1)


def test_snapshot_query_failure_propagates_without_writes(material_conn):
    before = stored_state(material_conn)
    error = AppError(ErrorCode.DB_QUERY_ERROR, "fixture storage failure")
    with patch.object(WorkbenchMaterialQueryRepository, "get_by_ref", side_effect=error):
        with pytest.raises(AppError) as raised:
            WorkbenchMaterialService(material_conn).snapshot(identity_for(material_conn))
    assert raised.value is error and stored_state(material_conn) == before


@pytest.mark.parametrize("missing", (True, False))
def test_missing_or_inconsistent_ref_query_cannot_apply(material_conn, missing):
    identity = identity_for(material_conn)
    raw = WorkbenchMaterialQueryRepository(material_conn).get_by_ref(identity.ref)
    raw["material_id"] = "another-code"
    before = stored_state(material_conn)
    with patch.object(WorkbenchMaterialQueryRepository, "get_by_ref", return_value=None if missing else raw):
        with pytest.raises(WorkbenchCommandRejected):
            run_material(material_conn, "update", {"label": "unsafe"})
    assert stored_state(material_conn) == before


@pytest.mark.parametrize("action", ("update", "delete"))
def test_legacy_whitespace_key_never_redirects_to_another_material(material_conn, action):
    material_conn.execute("INSERT INTO Materials (material_id, name) VALUES (' MAT1 ', 'legacy whitespace')")
    material_conn.commit()
    identity = identity_for(material_conn, " MAT1 ")
    before = stored_state(material_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_material(material_conn, action, {"label": "unsafe"} if action == "update" else {}, identity=identity)
    assert error.value.code == "constraint_conflict" and stored_state(material_conn) == before


def test_create_missing_persisted_identity_fails_and_outer_command_rolls_back(material_conn, monkeypatch):
    before = stored_state(material_conn)
    monkeypatch.setattr(WorkbenchIdentityRepository, "find_active", lambda *_args: None)
    with pytest.raises(WorkbenchCommandUncertain) as error:
        run_material(material_conn, "create", CREATE)
    assert isinstance(error.value.__cause__, RuntimeError)
    assert stored_state(material_conn) == before


def test_unexpected_domain_delete_error_is_not_misreported_as_constraint(material_conn):
    error = AppError(ErrorCode.DB_QUERY_ERROR, "fixture storage failure")
    before = stored_state(material_conn)
    with patch.object(MaterialService, "delete", side_effect=error):
        with pytest.raises(AppError) as raised:
            with TransactionManager(material_conn).transaction(begin_immediate=True):
                WorkbenchMaterialService(material_conn).apply("delete", {}, identity_for(material_conn))
    assert raised.value is error and stored_state(material_conn) == before
