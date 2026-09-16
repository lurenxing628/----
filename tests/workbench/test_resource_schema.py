"""v20 -> v21 is additive, atomic, and never guesses legacy resource facts."""

import sqlite3

import pytest

from core.errors import AppError
from core.infrastructure import migration_runner
from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    MigrationContractError,
    current_schema_contract_issues,
    detect_schema_is_current,
    ensure_current_schema_contract,
    ensure_schema_version,
    get_schema_version,
)
from core.infrastructure.migrations import v21
from core.infrastructure.workbench_metadata_schema import RESOURCE_TABLES
from core.infrastructure.workbench_process_workflow_schema import WORKFLOW_TABLES
from core.infrastructure.workbench_resource_schema import resource_objects, workbench_resource_contract_issues
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.execution_ledger_migration_support import V27_TABLES
from tests.workbench.identity_metadata_support import (
    RESOURCE_CASES,
    business_snapshot,
    connect_temp,
    copy_to_temp,
    insert_row,
    remove_resources_for_v20,
    schema_snapshot,
    seed_resources,
    table_rows,
)
from tests.workbench.legacy_migration_current_support import (
    V30_EMPTY_TABLES,
    V30_TABLES,
    V31_TABLES,
    V32_TABLES,
    assert_v30_source_maps_only,
    assert_v31_receipt_maps_only,
)
from tests.workbench.plan_identity_support import IDENTITY_TABLES, LEDGER_TABLES, load_v24_schema, table_snapshot
from tests.workbench.resource_entity_support import (
    ENTITY_TABLES,
    FIXED_FIELDS,
    NEW_TABLES,
    create_catalog,
    identity_for,
    resource_database,
    resource_service,
    run_resource,
    stored_state,
)
from tests.workbench.schema29_regression_support import V29_EMPTY_TABLES, V29_TABLES, assert_v29_source_maps_only


def _assert_v20_upgrade_metadata(conn, before):
    after = business_snapshot(conn)
    assert {name: after[name] for name in before} == before
    empty_tables = set(NEW_TABLES) | set(WORKFLOW_TABLES + LEDGER_TABLES[1:] + RUN_TABLES + V27_TABLES
                                       + V29_EMPTY_TABLES + V30_EMPTY_TABLES)
    added_tables = empty_tables | set(IDENTITY_TABLES + LEDGER_TABLES + V29_TABLES + V30_TABLES + V31_TABLES + V32_TABLES)
    assert set(after) - set(before) == added_tables
    assert all(not table_rows(conn, table) for table in empty_tables)
    assert_v29_source_maps_only(conn)
    assert_v30_source_maps_only(conn)
    assert_v31_receipt_maps_only(conn)


def test_real_v20_upgrade_is_additive_preserves_refs_and_matches_fresh_ddl(schema_conn, mem_conn, tmp_path, schema_path):
    ensure_schema_version(schema_conn)
    schema_conn.commit()
    fresh = schema_snapshot(schema_conn)
    conn = load_v24_schema(mem_conn)
    remove_resources_for_v20(conn)
    assert RESOURCE_TABLES == RESOURCE_CASES and len(RESOURCE_TABLES) == 10
    assert get_schema_version(conn) == 20
    assert not set(NEW_TABLES) & set(schema_snapshot(conn))
    seed_resources(conn, relations=True)
    conn.execute("UPDATE Operators SET status='inactive'")
    conn.execute("UPDATE Machines SET status=' Legacy HOLD '")
    conn.commit()
    before, refs = business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs")
    old_schema, backup_before = schema_snapshot(conn), table_snapshot(conn)
    assert not set(LEDGER_TABLES + RUN_TABLES + V27_TABLES) & set(before)
    assert len(refs) == 10
    path = tmp_path / "real-v20.db"
    copy_to_temp(conn, path)
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))
    with connect_temp(path) as upgraded:
        assert get_schema_version(upgraded) == CURRENT_SCHEMA_VERSION
        _assert_v20_upgrade_metadata(upgraded, before)
        assert [tuple(row) for row in upgraded.execute("SELECT kind,source_key FROM WorkbenchPlanSourceRefs ORDER BY kind")] == [
            ("operation", "31"), ("schedule_row", "41")]
        assert table_rows(upgraded, "WorkbenchTaskRefs") == []
        assert table_rows(upgraded, "WorkbenchPlanIdentityClock") == [(1, 1)]
        assert table_rows(upgraded, "WorkbenchExecutionLedgerClock") == [(1, 1, 1)]
        current_refs = table_rows(upgraded, "WorkbenchEntityRefs")
        assert [row for row in current_refs if row[1] in RESOURCE_CASES] == refs
        assert {row[1] for row in current_refs if row[1] not in RESOURCE_CASES} == {"template_operation", "template_external_group"}
        assert len(current_refs) == len(refs) + 2
        assert schema_snapshot(upgraded) == fresh
        assert current_schema_contract_issues(upgraded) == []
        assert not upgraded.execute("PRAGMA foreign_key_check").fetchall()
        unchanged = stored_state(upgraded)
        assert v21.run(upgraded) == MigrationOutcome.APPLIED
        assert stored_state(upgraded) == unchanged
    backups = list((tmp_path / "backups").glob(f"*before_migrate_v20_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(backups) == 1
    with connect_temp(backups[0]) as backup:
        assert get_schema_version(backup) == 20
        assert schema_snapshot(backup) == old_schema
        assert table_snapshot(backup) == backup_before
        assert business_snapshot(backup) == before
        assert table_rows(backup, "WorkbenchEntityRefs") == refs


@pytest.mark.parametrize("damage", (*V30_TABLES, *V31_TABLES, "missing_origin", "guessed_batch",
                                   "invented_receipt", "old_value", "old_type", "extra_table"))
def test_v20_upgrade_metadata_rejects_followup_damage_and_old_row_changes(mem_conn, tmp_path, schema_path, damage):
    conn = load_v24_schema(mem_conn)
    remove_resources_for_v20(conn)
    seed_resources(conn, relations=True)
    conn.commit()
    before = business_snapshot(conn)
    path = tmp_path / "v20-metadata.db"
    copy_to_temp(conn, path)
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))
    with connect_temp(path) as upgraded:
        _assert_v20_upgrade_metadata(upgraded, before)
        if damage in V30_TABLES + V31_TABLES:
            upgraded.execute('DROP TABLE "' + damage + '"')
        elif damage == "extra_table":
            upgraded.execute("CREATE TABLE UnexpectedMetadata(value TEXT)")
        elif damage == "old_value":
            upgraded.execute("UPDATE Parts SET remark='changed historical value' WHERE part_no='P1'")
        elif damage == "old_type":
            upgraded.execute("UPDATE Parts SET remark=CAST(remark AS BLOB) WHERE part_no='P1'")
        elif damage == "invented_receipt":
            refs = dict(upgraded.execute("SELECT kind,ref FROM WorkbenchEntityRefs "
                                         "WHERE kind IN ('batch','supplier') AND active=1"))
            insert_row(upgraded, "WorkbenchOutsourcingReceipts", dict(
                outsourcing_ref="f" * 48, target_kind="single", batch_ref=refs["batch"],
                supplier_ref=refs["supplier"], origin_json="{}", identity_json="{}", created_at="2026-09-10"))
        else:
            # Damage only this private upgrade so the snapshot checker must reject it.
            origins = table_rows(upgraded, "WorkbenchOutsourcingOperationOrigins")
            assert len(origins) == 1 and origins[0][1] is None
            if damage == "missing_origin":
                upgraded.execute("DROP TRIGGER wb_outsourcing_operationorigins_no_delete")
                upgraded.execute("DELETE FROM WorkbenchOutsourcingOperationOrigins")
            else:
                upgraded.execute("DROP TRIGGER wb_outsourcing_operationorigins_no_update")
                upgraded.execute("UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref="
                                 "(SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='B1' AND active=1)")
        with pytest.raises(AssertionError):
            _assert_v20_upgrade_metadata(upgraded, before)


@pytest.mark.parametrize("outer", (False, True))
def test_v21_ddl_failure_rolls_back_new_objects_preserves_outer_transaction(mem_conn, outer):
    conn = load_v24_schema(mem_conn)
    remove_resources_for_v20(conn)
    seed_resources(conn, relations=True)
    if outer:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('owner','uncommitted')")
    before = stored_state(conn)
    denied = []

    def deny_late_trigger(action, name, _arg2, _db, _source):
        if action == sqlite3.SQLITE_CREATE_TRIGGER and name == "wb_ref_shift_profile_insert":
            denied.append(name)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(deny_late_trigger)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            v21.run(conn)
    finally:
        conn.set_authorizer(lambda *_args: sqlite3.SQLITE_OK)
    assert denied == ["wb_ref_shift_profile_insert"]
    assert stored_state(conn) == before and get_schema_version(conn) == 20
    assert conn.in_transaction is outer
    conn.rollback()


def test_v21_success_does_not_commit_outer_owner(mem_conn):
    schema_conn = load_v24_schema(mem_conn)
    remove_resources_for_v20(schema_conn)
    seed_resources(schema_conn, relations=True)
    before = stored_state(schema_conn)
    schema_conn.execute("BEGIN IMMEDIATE")
    assert v21.run(schema_conn) == MigrationOutcome.APPLIED
    assert workbench_resource_contract_issues(schema_conn) == [] and schema_conn.in_transaction
    schema_conn.rollback()
    assert stored_state(schema_conn) == before and get_schema_version(schema_conn) == 20


def test_migration_runner_final_contract_failure_restores_real_v20(mem_conn, tmp_path, monkeypatch):
    conn = load_v24_schema(mem_conn)
    remove_resources_for_v20(conn)
    seed_resources(conn, relations=True)
    before = stored_state(conn)
    path = tmp_path / "runner-v20.db"
    copy_to_temp(conn, path)
    original = migration_runner.ensure_current_schema_contract

    def reject_final(connection, *, schema_version=None):
        original(connection, schema_version=schema_version)
        if schema_version == CURRENT_SCHEMA_VERSION:
            assert connection.in_transaction
            assert workbench_resource_contract_issues(connection) == []
            raise RuntimeError("reject final current contract")

    def connect(filename):
        assert filename == str(path)
        connection = sqlite3.connect(filename)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    monkeypatch.setattr(migration_runner, "ensure_current_schema_contract", reject_final)
    with pytest.raises(RuntimeError, match="reject final current contract"):
        migration_runner._apply_migrations(str(path), to_version=CURRENT_SCHEMA_VERSION, schema_sql=None, connection_factory=connect)
    with connect_temp(path) as reopened:
        assert stored_state(reopened) == before and get_schema_version(reopened) == 20


@pytest.mark.parametrize("name", tuple(resource_objects()))
def test_every_missing_resource_table_trigger_index_rejects_current_contract(schema_conn, name):
    ensure_schema_version(schema_conn)
    object_type = schema_snapshot(schema_conn)[name][0]
    schema_conn.execute(f'DROP {object_type.upper()} "{name}"')
    schema_conn.commit()
    before = stored_state(schema_conn)
    assert "missing_workbench_resource: " + name in current_schema_contract_issues(schema_conn)
    assert not detect_schema_is_current(schema_conn)
    with pytest.raises(MigrationContractError, match="workbench_resource"):
        ensure_current_schema_contract(schema_conn)
    # Other current-contract checks use rolled-back constraint probes.
    assert stored_state(schema_conn) == before and not schema_conn.in_transaction


@pytest.mark.parametrize("name,old,new", [
    ("WorkbenchMachineGroups", "name TEXT NOT NULL UNIQUE", "name TEXT NOT NULL"),
    ("WorkbenchMachineGroupMembers", "machine_id TEXT PRIMARY KEY NOT NULL", "machine_id TEXT PRIMARY KEY"),
    ("WorkbenchShiftProfiles", "BETWEEN 1 AND 366", "BETWEEN 0 AND 366"),
    ("WorkbenchShiftPatternDays", "PRIMARY KEY(profile_id, day_offset)", "UNIQUE(profile_id, day_offset)"),
    ("WorkbenchOperatorProfiles", "skills_declared INTEGER NOT NULL DEFAULT 0", "skills_declared INTEGER NOT NULL DEFAULT 1"),
    ("WorkbenchSupplierOpTypes", "PRIMARY KEY(supplier_id, op_type_id)", "UNIQUE(supplier_id, op_type_id)"),
    ("WorkbenchSupplierProfiles", "'pending_review', 'disabled'", "'pending_review', 'leave'"),
    ("WorkbenchOpTypePolicies", "'separate', 'merged'", "'separate', 'automatic'"),
    ("idx_wb_machine_members_group", "(group_id)", "(machine_id)"),
    ("idx_wb_operator_profiles_shift", "(shift_profile_id)", "(operator_id)"),
    ("idx_wb_supplier_op_types_op", "(op_type_id)", "(supplier_id)"),
    ("idx_wb_operator_skill_op", "(op_type_id)", "(operator_id)"),
    ("wb_ref_machine_group_insert", "randomblob(24)", "randomblob(16)"),
    ("wb_ref_shift_profile_update", "revision + 1", "revision + 0"),
    ("wb_resource_touch_operatorskill_insert", "revision + 1", "revision + 0"),
    ("wb_resource_operator_status_reason", "inactive_reason = NULL", "inactive_reason = inactive_reason"),
])
def test_damaged_new_objects_block_startup_without_repair(schema_conn, tmp_path, schema_path, name, old, new):
    ensure_schema_version(schema_conn)
    sql = resource_objects()[name]
    assert old in sql
    object_type = schema_snapshot(schema_conn)[name][0]
    schema_conn.execute(f'DROP {object_type.upper()} "{name}"')
    schema_conn.execute(sql.replace(old, new))
    schema_conn.commit()
    assert "bad_workbench_resource: " + name in current_schema_contract_issues(schema_conn)
    path = tmp_path / "damaged-v21.db"
    before = stored_state(schema_conn)
    copy_to_temp(schema_conn, path)
    with pytest.raises(MigrationContractError, match="bad_workbench_resource: " + name):
        ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))
    with connect_temp(path) as reopened:
        assert stored_state(reopened) == before and get_schema_version(reopened) == CURRENT_SCHEMA_VERSION


@pytest.mark.parametrize("kind,table", (("operator", "WorkbenchOperatorProfiles"), ("machine", "WorkbenchMachineGroupMembers"),
                                       ("op_type", "WorkbenchOpTypePolicies")))
def test_missing_profile_table_snapshot_fails_readonly_never_installs(resource_conn, kind, table):
    conn = resource_conn
    conn.execute(f'DROP TABLE "{table}"')
    conn.commit()
    before, changes = stored_state(conn), conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    try:
        with pytest.raises(AppError) as error:
            resource_service(conn, kind).snapshot(identity_for(conn, kind))
        assert isinstance(error.value.__cause__, sqlite3.OperationalError)
        assert "no such table" in str(error.value.__cause__)
    finally:
        conn.execute("PRAGMA query_only=OFF")
    assert stored_state(conn) == before and conn.total_changes == changes


@pytest.mark.parametrize("kind", ("machine_group", "shift_profile"))
@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("verb", ("REPLACE", "INSERT OR REPLACE"))
@pytest.mark.parametrize("conflict", ("key", "unique_name"))
def test_catalog_replace_never_reuses_displaced_identity(resource_conn, kind, recursive, verb, conflict):
    conn = resource_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    old = create_catalog(conn, kind)
    table, key, code = ENTITY_TABLES[kind]
    payload = {key: code if conflict == "key" else code + "-new", "name": code, "remark": "replacement"}
    if kind == "shift_profile":
        payload.update(anchor_date=FIXED_FIELDS["anchor_date"], cycle_days=1)
    insert_row(conn, table, payload, verb=verb)
    conn.commit()
    repo = WorkbenchIdentityRepository(conn)
    current, retired = identity_for(conn, kind, payload[key]), repo.get(old.ref)
    assert current.ref != old.ref and current.active and current.revision == 1
    assert not retired.active and retired.revision > old.revision
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_resource(conn, kind, "update", {"label": "unsafe"}, identity=old)
    assert error.value.code == "entity_not_found" and stored_state(conn) == before


@pytest.mark.parametrize("kind,owner,relation", (
    ("machine_group", "machine", "group_ref"), ("shift_profile", "operator", "shift_profile_ref"),
))
def test_membership_insert_move_delete_advances_both_endpoint_revisions(resource_conn, kind, owner, relation):
    conn = resource_conn
    first, second = create_catalog(conn, kind), create_catalog(conn, kind, code="SECOND")
    for ref, codes in ((first.ref, [first.entity_key]), (second.ref, [first.entity_key, second.entity_key]),
                       (None, [second.entity_key])):
        before = [identity_for(conn, kind, code) for code in codes] + [identity_for(conn, owner)]
        run_resource(conn, owner, "update", {"relationships": {relation: ref}})
        repo = WorkbenchIdentityRepository(conn)
        assert all(repo.get(identity.ref).revision > identity.revision for identity in before), [
            (identity.kind, identity.revision, repo.get(identity.ref).revision) for identity in before]


@pytest.mark.parametrize("table", NEW_TABLES)
def test_resource_foreign_keys_use_no_action_for_business_code_changes(schema_conn, table):
    assert all(row[5] == "NO ACTION" for row in schema_conn.execute(f'PRAGMA foreign_key_list("{table}")'))


@pytest.mark.parametrize("kind", ("machine_group", "shift_profile"))
@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("operation", ("rename", "replace_key", "replace_name", "replace_both"))
def test_unreferenced_catalog_rename_keeps_survivor_ref_and_retires_replaced_ref(schema_conn, kind, recursive, operation):
    conn = schema_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    table, key, _ = ENTITY_TABLES[kind]
    for code in ("A", "B"):
        payload = {key: code, "name": "name-" + code}
        if kind == "shift_profile":
            payload.update(anchor_date="2026-09-09", cycle_days=1)
        insert_row(conn, table, payload)
    conn.commit()
    old, displaced = identity_for(conn, kind, "A"), identity_for(conn, kind, "B")
    target_code = "B" if operation in ("replace_key", "replace_both") else "RENAMED"
    target_name = "name-B" if operation in ("replace_name", "replace_both") else "name-A"
    verb = "UPDATE" if operation == "rename" else "UPDATE OR REPLACE"
    conn.execute("BEGIN IMMEDIATE")
    updates = {key: target_code}
    if operation in ("replace_name", "replace_both"):
        updates["name"] = target_name
    assignments = ",".join(f'"{column}"=?' for column in updates)
    conn.execute(f'{verb} "{table}" SET {assignments} WHERE "{key}"=?', tuple(updates.values()) + ("A",))
    conn.commit()
    repo = WorkbenchIdentityRepository(conn)
    survivor = identity_for(conn, kind, target_code)
    assert survivor.ref == old.ref and survivor.revision == old.revision + 1
    assert identity_for(conn, kind, "A") is None
    if operation == "rename":
        assert repo.get(displaced.ref) == displaced
    else:
        retired = repo.get(displaced.ref)
        assert not retired.active and retired.revision == displaced.revision + 1
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


@pytest.mark.parametrize("parent,child", (
    ("machine", "WorkbenchMachineGroupMembers"), ("machine_group", "WorkbenchMachineGroupMembers"),
    ("shift_profile", "WorkbenchShiftPatternDays"), ("operator", "WorkbenchOperatorProfiles"),
    ("shift_profile", "WorkbenchOperatorProfiles"), ("supplier", "WorkbenchSupplierOpTypes"),
    ("op_type", "WorkbenchSupplierOpTypes"), ("supplier", "WorkbenchSupplierProfiles"),
    ("op_type", "WorkbenchOpTypePolicies"),
))
@pytest.mark.parametrize("verb", ("UPDATE", "UPDATE OR REPLACE"))
def test_referenced_business_code_rename_fails_without_changing_any_rows(schema_conn, parent, child, verb):
    conn = schema_conn
    parents = {
        "machine": ("Machines", "machine_id"), "machine_group": ("WorkbenchMachineGroups", "group_id"),
        "operator": ("Operators", "operator_id"), "shift_profile": ("WorkbenchShiftProfiles", "profile_id"),
        "supplier": ("Suppliers", "supplier_id"), "op_type": ("OpTypes", "op_type_id"),
    }
    for kind, (table, key) in parents.items():
        for code in ("A", "B"):
            payload = {key: code, "name": "name-" + code}
            if kind == "shift_profile":
                payload.update(anchor_date="2026-09-09", cycle_days=1)
            insert_row(conn, table, payload)
    children = {
        "WorkbenchMachineGroupMembers": {"machine_id": "A", "group_id": "A"},
        "WorkbenchShiftPatternDays": {"profile_id": "A", "day_offset": 0, "is_rest": 0,
                                      "shift_start": "07:15", "shift_end": "15:45"},
        "WorkbenchOperatorProfiles": {"operator_id": "A", "shift_profile_id": "A"},
        "WorkbenchSupplierOpTypes": {"supplier_id": "A", "op_type_id": "A"},
        "WorkbenchSupplierProfiles": {"supplier_id": "A", "inactive_reason": "disabled"},
        "WorkbenchOpTypePolicies": {"op_type_id": "A", "default_merge_mode": "merged"},
    }
    insert_row(conn, child, children[child])
    conn.commit()
    before = stored_state(conn)
    table, key = parents[parent]
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(f'{verb} "{table}" SET "{key}"=? WHERE "{key}"=?',
                         ("B" if verb == "UPDATE OR REPLACE" else "RENAMED", "A"))
    assert stored_state(conn) == before and not conn.in_transaction


def test_direct_skill_relation_mutations_advance_old_new_operator_and_op_type_refs(resource_conn):
    conn = resource_conn
    tracked = [("operator", "O1"), ("operator", "EMPTY"), ("op_type", "OT1"), ("op_type", "OT2")]
    before = {pair: identity_for(conn, *pair) for pair in tracked}
    conn.execute("UPDATE OperatorSkill SET operator_id='EMPTY',op_type_id='OT2' WHERE operator_id='O1' AND op_type_id='OT1'")
    conn.commit()
    assert all(identity_for(conn, *pair).revision > old.revision for pair, old in before.items())
    permissions = table_rows(conn, "OperatorMachine")
    for sql in ("DELETE FROM OperatorSkill WHERE operator_id='EMPTY' AND op_type_id='OT2'",
                "INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('EMPTY','OT2')"):
        before = {pair: identity_for(conn, *pair) for pair in (("operator", "EMPTY"), ("op_type", "OT2"))}
        conn.execute(sql)
        conn.commit()
        assert all(identity_for(conn, *pair).revision > old.revision for pair, old in before.items())
        assert table_rows(conn, "OperatorMachine") == permissions
