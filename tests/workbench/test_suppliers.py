"""D06 supplier adapter: raw snapshots, explicit relations and atomic commands."""

from copy import deepcopy
from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from core.errors import AppError, BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain, input_fingerprint
from core.services.process.supplier_service import SupplierService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.suppliers import WorkbenchSupplierService
from data.repositories.workbench_supplier_state_repo import WorkbenchSupplierStateRepository
from tests.workbench.supplier_support import (
    CREATE,
    KEY,
    identity_for,
    invalid_payloads,
    relationships,
    run_supplier,
    stored_state,
    supplier_database,
    supplier_row,
)


@pytest.mark.parametrize("action,payload", list(invalid_payloads()))
def test_strict_input_rejected_without_database(action, payload):
    with pytest.raises(ValidationError):
        WorkbenchSupplierService.normalize_input(action, payload)


@pytest.mark.parametrize("action", (None, [], {}, True, "", "upsert", "UPDATE"))
def test_unknown_action_rejected(action):
    with pytest.raises(ValidationError):
        WorkbenchSupplierService.normalize_input(action, {})


def test_normalization_is_pure_idempotent_and_omissions_are_preserved(supplier_conn):
    adapter = WorkbenchSupplierService(supplier_conn)
    payload = {"label": " new label ", "fields": {"remark": None}, "relationships": relationships(supplier_conn, "HEAT", "COAT")}
    before = deepcopy(payload)
    expected = {**payload, "label": "new label", "relationships": {"op_type_refs": sorted(payload["relationships"]["op_type_refs"])}}
    with patch.object(adapter._query, "get_op_type_by_ref", side_effect=AssertionError("no IO")):
        assert adapter.normalize_input("update", payload) == expected
        assert adapter.normalize_input("update", expected) == expected
        assert adapter.normalize_input("update", {}) == {"fields": {}}
        assert adapter.normalize_input("delete", {}) == {}
    assert payload == before


def test_create_reuses_domain_and_stores_one_supplier_with_only_explicit_bindings(supplier_conn):
    conn = supplier_conn
    payload = {**CREATE, "business_code": " SUP2 ", "relationships": relationships(conn, "COAT", "HEAT")}
    original = SupplierService.create
    calls = []

    def create(service, *args, **kwargs):
        assert service.conn.in_transaction
        calls.append(args)
        return original(service, *args, **kwargs)

    with patch.object(SupplierService, "create", create):
        result = run_supplier(conn, "create", payload)
    identity = identity_for(conn, "SUP2")
    assert calls == [("SUP2", "New supplier")]
    assert result["data"] == {"entity_ref": identity.ref, "business_code": "SUP2"}
    assert supplier_row(conn, "SUP2")["op_type_id"] is None
    assert conn.execute("SELECT COUNT(*) FROM Suppliers").fetchone()[0] == 2
    assert [tuple(row) for row in conn.execute("SELECT * FROM WorkbenchSupplierOpTypes ORDER BY op_type_id")] == [("SUP2", "COAT"), ("SUP2", "HEAT")]
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


@pytest.mark.parametrize("status,stored,reason", [("active", "active", None), ("pending_review", "inactive", "pending_review"), ("inactive", "inactive", "disabled")])
def test_explicit_status_mapping_create_update_and_noop(supplier_conn, status, stored, reason):
    conn = supplier_conn
    run_supplier(conn, "create", {**CREATE, "fields": {"default_days": 2, "status": status}})
    assert supplier_row(conn, "SUP2")["status"] == stored
    run_supplier(conn, "update", {"fields": {"status": status}}, key=KEY + "-update")
    adapter = WorkbenchSupplierService(conn)
    snapshot = adapter.snapshot(identity_for(conn))
    assert snapshot["state"] == {"status": status, "inactive_reason": reason}
    assert snapshot["supplier"]["status"] == stored
    identity = identity_for(conn)
    result = run_supplier(conn, "update", {"fields": {"status": status}}, key=KEY + "-noop")
    assert result["result"] == "unchanged" and identity_for(conn) == identity


def test_legacy_inactive_reason_unknown_is_not_inferred_and_legacy_status_write_clears_reason(supplier_conn):
    conn = supplier_conn
    domain = SupplierService(conn)
    adapter = WorkbenchSupplierService(conn)
    domain.update("SUP1", status="inactive")
    assert adapter.snapshot(identity_for(conn))["state"] == {"status": "inactive", "inactive_reason": "unknown"}
    run_supplier(conn, "update", {"fields": {"status": "pending_review"}})
    domain.update("SUP1", name="legacy rename")
    assert adapter.snapshot(identity_for(conn))["state"]["status"] == "pending_review"
    domain.update("SUP1", status="active")
    assert adapter.snapshot(identity_for(conn))["supplier"]["profile"]["inactive_reason"] is None
    domain.update("SUP1", status="inactive")
    assert adapter.snapshot(identity_for(conn))["state"]["inactive_reason"] == "unknown"


@pytest.mark.parametrize("clear", (None, "", " \t"))
def test_update_omission_preserves_fields_and_explicit_null_clears_remark(supplier_conn, clear):
    before = supplier_row(supplier_conn)
    run_supplier(supplier_conn, "update", {"fields": {"remark": clear}})
    assert supplier_row(supplier_conn) == {**before, "remark": None}
    identity = identity_for(supplier_conn)
    assert run_supplier(supplier_conn, "update", {"fields": {"remark": clear}}, key=KEY + "-again")["result"] == "unchanged"
    assert identity_for(supplier_conn) == identity


def test_no_difference_in_effective_relationships_does_not_migrate_legacy_or_touch_revision(supplier_conn):
    identity = identity_for(supplier_conn)
    before = WorkbenchSupplierService(supplier_conn).snapshot(identity)
    with patch.object(SupplierService, "update", side_effect=AssertionError("no update")):
        result = run_supplier(supplier_conn, "update", {"label": "Legacy supplier", "relationships": relationships(supplier_conn, "HEAT")})
    assert result["result"] == "unchanged"
    assert WorkbenchSupplierService(supplier_conn).snapshot(identity) == before
    assert supplier_conn.execute("SELECT COUNT(*) FROM WorkbenchSupplierOpTypes").fetchone()[0] == 0


def test_relationship_replacement_retains_or_explicitly_clears_legacy_primary(supplier_conn):
    conn = supplier_conn
    run_supplier(conn, "update", {"relationships": relationships(conn, "COAT", "HEAT")})
    assert supplier_row(conn)["op_type_id"] == "HEAT"
    assert [row[0] for row in conn.execute("SELECT op_type_id FROM WorkbenchSupplierOpTypes")] == ["COAT"]
    original, calls = SupplierService.update, []

    def update(service, code, **kwargs):
        calls.append(kwargs)
        return original(service, code, **kwargs)

    with patch.object(SupplierService, "update", update):
        run_supplier(conn, "update", {"relationships": relationships(conn, "COAT")}, key=KEY + "-replace")
    assert calls == [{"op_type_value": ""}]
    assert supplier_row(conn)["op_type_id"] is None
    run_supplier(conn, "update", {"relationships": relationships(conn)}, key=KEY + "-empty")
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchSupplierOpTypes").fetchone()[0] == 0
    assert supplier_row(conn)["op_type_id"] is None


@pytest.mark.parametrize("bad", ("unknown", "kind", "internal", "retired"))
@pytest.mark.parametrize("action", ("create", "update"))
def test_relation_refs_are_checked_under_outer_tx(supplier_conn, bad, action):
    conn = supplier_conn
    ref = "f" * 48
    if bad == "kind":
        ref = identity_for(conn).ref
    elif bad == "internal":
        ref = identity_for(conn, "MILL", "op_type").ref
    elif bad == "retired":
        ref = identity_for(conn, "COAT", "op_type").ref
        conn.execute("DELETE FROM OpTypes WHERE op_type_id = 'COAT'")
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('COAT','replacement','external')")
        conn.commit()
        assert identity_for(conn, "COAT", "op_type").ref != ref
    before = stored_state(conn)
    with pytest.raises((WorkbenchCommandRejected, ValidationError)):
        run_supplier(conn, action, {**(CREATE if action == "create" else {}), "relationships": {"op_type_refs": [ref]}})
    assert stored_state(conn) == before


@pytest.mark.parametrize("action", ("create", "update", "delete"))
def test_apply_requires_outer_transaction(supplier_conn, action):
    with pytest.raises(RuntimeError, match="外层"):
        WorkbenchSupplierService(supplier_conn).apply(action, CREATE if action == "create" else {})


@pytest.mark.parametrize("bad", ("missing", "pk", "kind", "inactive", "ref", "key", "revision"))
def test_identity_must_be_current_checked_supplier(supplier_conn, bad):
    identity = identity_for(supplier_conn)
    wrong = {"missing": None, "pk": "SUP1", "kind": replace(identity, kind="op_type"),
             "inactive": replace(identity, active=False), "ref": replace(identity, ref="f" * 48),
             "key": replace(identity, entity_key="SUP2"), "revision": replace(identity, revision=identity.revision + 1)}[bad]
    before = stored_state(supplier_conn)
    with pytest.raises(WorkbenchCommandRejected):
        with TransactionManager(supplier_conn).transaction(begin_immediate=True):
            WorkbenchSupplierService(supplier_conn).apply("update", {"label": "unsafe"}, wrong)
    assert stored_state(supplier_conn) == before


def test_deleted_rebuilt_supplier_never_accepts_old_ref_and_receipt_replays(supplier_conn):
    conn = supplier_conn
    old = identity_for(conn)
    first = run_supplier(conn, "delete", {})
    SupplierService(conn).create("SUP1", "Replacement", default_days=2)
    assert identity_for(conn).ref != old.ref
    assert run_supplier(conn, "delete", {}, identity=old, guard=lambda: pytest.fail("must replay")) == {**first, "replayed": True}
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected, match="引用已失效"):
        run_supplier(conn, "update", {"label": "unsafe"}, identity=old, key=KEY + "-stale")
    assert stored_state(conn) == before


@pytest.mark.parametrize("action", ("update", "delete"))
def test_legacy_whitespace_key_never_redirects(supplier_conn, action):
    conn = supplier_conn
    conn.execute("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES (' SUP1 ','Whitespace',2)")
    conn.commit()
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected, match="空白"):
        run_supplier(conn, action, {}, identity=identity_for(conn, " SUP1 "))
    assert stored_state(conn) == before


def test_new_trimmed_duplicate_never_overwrites(supplier_conn):
    before = stored_state(supplier_conn)
    with pytest.raises(BusinessError) as error:
        run_supplier(supplier_conn, "create", {**CREATE, "business_code": " SUP1 "})
    assert error.value.code == ErrorCode.DUPLICATE_ENTRY and stored_state(supplier_conn) == before


@pytest.mark.parametrize("action", ("create", "update", "delete"))
def test_receipt_failure_rolls_back_supplier_relationships_profiles_and_refs(supplier_conn, monkeypatch, action):
    conn = supplier_conn
    before = stored_state(conn)
    command = WorkbenchCommandService(conn)
    original = command.repo.insert

    def fail(**kwargs):
        original(**kwargs)
        raise OSError("receipt failure")

    monkeypatch.setattr(command.repo, "insert", fail)
    payload = {} if action == "delete" else {**(CREATE if action == "create" else {}),
        "fields": {"default_days": 5, "status": "pending_review"}, "relationships": relationships(conn, "COAT")}
    with pytest.raises(WorkbenchCommandUncertain):
        run_supplier(conn, action, payload, command=command)
    assert stored_state(conn) == before and not conn.in_transaction


def test_snapshot_is_raw_full_readonly_and_related_changes_invalidate_guard(supplier_conn):
    conn = supplier_conn
    run_supplier(conn, "update", {"relationships": relationships(conn, "HEAT", "COAT")})
    conn.execute("UPDATE Suppliers SET default_days = NULL, status = NULL WHERE supplier_id = 'SUP1'")
    conn.commit()
    adapter, identity = WorkbenchSupplierService(conn), identity_for(conn)
    before, changes = stored_state(conn), conn.total_changes
    snapshot = adapter.snapshot(identity)
    assert snapshot["identity"] == asdict(identity)
    assert all(snapshot["supplier"][key] == value for key, value in supplier_row(conn).items())
    assert snapshot["supplier"]["default_days"] is None and snapshot["supplier"]["status"] is None
    assert [row["op_type_id"] for row in snapshot["supplier"]["op_types"]] == ["COAT", "HEAT"]
    assert all(row["ref"] and row["revision"] for row in snapshot["supplier"]["op_types"])
    assert stored_state(conn) == before and conn.total_changes == changes
    conn.execute("UPDATE OpTypes SET remark = 'changed relation' WHERE op_type_id = 'COAT'")
    conn.commit()
    assert identity_for(conn) == identity
    assert input_fingerprint(adapter.snapshot(identity)) != input_fingerprint(snapshot)
    conn.execute("DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id = 'SUP1'")
    conn.commit()
    assert identity_for(conn).revision > identity.revision
    with pytest.raises(WorkbenchCommandRejected) as error:
        adapter.snapshot(identity)
    assert error.value.code == "stale_write"


def test_missing_metadata_and_query_failure_never_repaired(supplier_conn):
    conn = supplier_conn
    identity = identity_for(conn)
    error = AppError(ErrorCode.DB_QUERY_ERROR, "fixture query error")
    before = stored_state(conn)
    with patch.object(WorkbenchSupplierStateRepository, "get_by_ref", side_effect=error):
        with pytest.raises(AppError) as raised:
            WorkbenchSupplierService(conn).snapshot(identity)
    assert raised.value is error and stored_state(conn) == before
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE ref = ?", (identity.ref,))
    conn.commit()
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected):
        WorkbenchSupplierService(conn).snapshot(identity)
    assert stored_state(conn) == before


def test_delete_cascades_only_owned_supplements_and_retires_supplier_identity(supplier_conn):
    conn = supplier_conn
    run_supplier(conn, "create", {**CREATE, "fields": {"default_days": 2, "status": "pending_review"},
                 "relationships": relationships(conn, "HEAT", "COAT")})
    identity = identity_for(conn, "SUP2")
    existing = supplier_row(conn)
    result = run_supplier(conn, "delete", {}, identity=identity, key=KEY + "-delete")
    assert result["data"] == {"entity_ref": identity.ref, "business_code": "SUP2"}
    assert supplier_row(conn, "SUP2") is None and supplier_row(conn) == existing
    assert not conn.execute("SELECT * FROM WorkbenchSupplierOpTypes WHERE supplier_id = 'SUP2'").fetchall()
    assert not conn.execute("SELECT * FROM WorkbenchSupplierProfiles WHERE supplier_id = 'SUP2'").fetchall()
    assert conn.execute("SELECT active FROM WorkbenchEntityRefs WHERE ref = ?", (identity.ref,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM OpTypes").fetchone()[0] == 3
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_reordered_explicit_selection_and_omitted_raw_nulls_do_not_touch_revisions(supplier_conn):
    conn = supplier_conn
    run_supplier(conn, "update", {"relationships": relationships(conn, "HEAT", "COAT")})
    conn.execute("UPDATE Suppliers SET default_days = NULL, status = NULL WHERE supplier_id = 'SUP1'")
    conn.commit()
    identity = identity_for(conn)
    before = WorkbenchSupplierService(conn).snapshot(identity)
    with patch.object(SupplierService, "update", side_effect=AssertionError("must not coerce raw nulls")):
        result = run_supplier(conn, "update", {"relationships": relationships(conn, "COAT", "HEAT")}, key=KEY + "-noop")
    assert result["result"] == "unchanged" and identity_for(conn) == identity
    assert WorkbenchSupplierService(conn).snapshot(identity) == before


def test_complete_snapshot_guard_rejects_related_change_even_when_supplier_revision_is_unchanged(supplier_conn):
    conn = supplier_conn
    adapter, identity = WorkbenchSupplierService(conn), identity_for(conn)
    fingerprint = input_fingerprint(adapter.snapshot(identity))
    conn.execute("UPDATE OpTypes SET name = 'Heat renamed' WHERE op_type_id = 'HEAT'")
    conn.commit()
    assert identity_for(conn) == identity

    def guard():
        if input_fingerprint(adapter.snapshot(identity)) != fingerprint:
            raise WorkbenchCommandRejected("stale_write", "related op type changed")
        return identity

    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_supplier(conn, "update", {"label": "unsafe"}, guard=guard)
    assert error.value.code == "stale_write" and stored_state(conn) == before


@pytest.mark.parametrize("missing", (True, False))
def test_missing_or_mismatched_raw_identity_cannot_write(supplier_conn, missing):
    conn = supplier_conn
    row = WorkbenchSupplierStateRepository(conn).get_by_ref(identity_for(conn).ref)
    row["supplier_id"] = "wrong key"
    before = stored_state(conn)
    with patch.object(WorkbenchSupplierStateRepository, "get_by_ref", return_value=None if missing else row):
        with pytest.raises(WorkbenchCommandRejected):
            run_supplier(conn, "update", {"label": "unsafe"})
    assert stored_state(conn) == before
