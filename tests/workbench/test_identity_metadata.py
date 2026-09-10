"""Permanent references and v20 migration contracts, using only temporary databases."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from dataclasses import asdict

import pytest

from core.infrastructure import migration_runner
from core.infrastructure.database import ensure_schema
from core.infrastructure.errors import AppError
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
from core.infrastructure.migrations import v20
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import (
    RESOURCE_TABLES,
    entity_key,
    metadata_objects,
    workbench_metadata_contract_issues,
)
from core.infrastructure.workbench_resource_schema import RESOURCE_TABLE_NAMES
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.models.workbench_command import WorkbenchCommandOutcome
from core.services.equipment.machine_service import MachineService
from core.services.personnel.operator_service import OperatorService
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.execution_ledger_migration_support import V27_TABLES
from tests.workbench.identity_metadata_support import (
    METADATA_TABLES,
    RESOURCE_CASES,
    SEED_ROWS,
    business_snapshot,
    connect_temp,
    copy_to_temp,
    identity_database,
    insert_row,
    legacy_identity_database,
    remove_metadata_for_v19,
    resource_key,
    resource_payload,
    schema_snapshot,
    seed_resources,
    table_rows,
    where_key,
)
from tests.workbench.legacy_migration_current_support import (
    V30_EMPTY_TABLES,
    V30_TABLES,
    V31_TABLES,
    assert_v30_source_maps_only,
    assert_v31_receipt_maps_only,
)
from tests.workbench.plan_identity_support import IDENTITY_TABLES, LEDGER_TABLES, load_v24_schema, table_snapshot
from tests.workbench.schema29_regression_support import V29_EMPTY_TABLES, V29_TABLES, assert_v29_source_maps_only


def test_full_schema_and_v19_upgrade_have_identical_structure_and_keep_every_field(schema_conn, v19_conn, tmp_path, schema_path):
    assert RESOURCE_TABLES == RESOURCE_CASES
    assert set(METADATA_TABLES) <= metadata_objects().keys()
    assert current_schema_contract_issues(schema_conn) == []
    ensure_schema_version(schema_conn)
    assert get_schema_version(schema_conn) == CURRENT_SCHEMA_VERSION
    schema_conn.commit()
    fresh = schema_snapshot(schema_conn)
    assert all(not table_rows(schema_conn, table) for table in METADATA_TABLES)
    conn = v19_conn
    assert get_schema_version(conn) == 19
    seed_resources(conn, relations=True)
    before = business_snapshot(conn)
    old_schema, backup_before = schema_snapshot(conn), table_snapshot(conn)
    assert not set(LEDGER_TABLES + RUN_TABLES + V27_TABLES) & set(before)
    path = tmp_path / "upgrade.db"
    copy_to_temp(conn, path)

    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))

    with connect_temp(path) as upgraded:
        assert get_schema_version(upgraded) == CURRENT_SCHEMA_VERSION
        assert schema_snapshot(upgraded) == fresh
        actual_business = business_snapshot(upgraded)
        assert {name: actual_business[name] for name in before} == before
        from core.infrastructure.workbench_process_workflow_schema import WORKFLOW_TABLES
        empty_tables = set(RESOURCE_TABLE_NAMES + WORKFLOW_TABLES + LEDGER_TABLES[1:] + RUN_TABLES + V27_TABLES
                           + V29_EMPTY_TABLES + V30_EMPTY_TABLES + V31_TABLES)
        added_tables = empty_tables | set(IDENTITY_TABLES + LEDGER_TABLES + V29_TABLES + V30_TABLES)
        assert set(actual_business) - set(before) == added_tables
        assert all(not table_rows(upgraded, table) for table in empty_tables)
        assert_v29_source_maps_only(upgraded)
        assert_v30_source_maps_only(upgraded)
        assert_v31_receipt_maps_only(upgraded)
        assert [tuple(row) for row in upgraded.execute("SELECT kind,source_key FROM WorkbenchPlanSourceRefs ORDER BY kind")] == [
            ("operation", "31"), ("schedule_row", "41")]
        assert table_rows(upgraded, "WorkbenchTaskRefs") == []
        assert table_rows(upgraded, "WorkbenchPlanIdentityClock") == [(1, 1)]
        assert table_rows(upgraded, "WorkbenchExecutionLedgerClock") == [(1, 1, 1)]
        assert current_schema_contract_issues(upgraded) == []
        assert not upgraded.execute("PRAGMA foreign_key_check").fetchall()
        identities = WorkbenchIdentityRepository(upgraded)
        assert len(table_rows(upgraded, "WorkbenchEntityRefs")) == len(RESOURCE_CASES) + 2
        assert identities.find_active("template_operation", "21") is not None
        assert identities.find_active("template_external_group", "EG1") is not None
        for kind, (table, _) in RESOURCE_CASES.items():
            row = identities.find_active(kind, resource_key(kind, SEED_ROWS[table]))
            assert row is not None and row.active and row.revision == 1
        refs = table_rows(upgraded, "WorkbenchEntityRefs")
        assert v20.run(upgraded) == MigrationOutcome.APPLIED
        assert table_rows(upgraded, "WorkbenchEntityRefs") == refs
        assert business_snapshot(upgraded) == actual_business
    backups = list((tmp_path / "backups").glob(f"*before_migrate_v19_to_v{CURRENT_SCHEMA_VERSION}*.db"))
    assert len(backups) == 1
    with connect_temp(backups[0]) as backup:
        assert get_schema_version(backup) == 19
        assert schema_snapshot(backup) == old_schema
        assert table_snapshot(backup) == backup_before
        assert business_snapshot(backup) == before


@pytest.mark.parametrize("kind", RESOURCE_CASES)
def test_update_rename_delete_and_recreate_keep_instance_identity(identity_conn, kind):
    conn, table = identity_conn, RESOURCE_CASES[kind][0]
    payload = resource_payload(kind)
    insert_row(conn, table, payload)
    repo = WorkbenchIdentityRepository(conn)
    key = resource_key(kind, payload)
    original = repo.find_active(kind, key)
    assert original is not None and original.revision == 1 and original.active
    assert len(original.ref) == 48 and set(original.ref) <= set("0123456789abcdef")
    where, values = where_key(kind, payload)
    display_column = "name" if "name" in payload else "part_name" if "part_name" in payload else "remark"
    conn.execute(f'UPDATE "{table}" SET "{display_column}" = ? WHERE {where}', ("renamed",) + values)
    assert repo.get(original.ref).revision == 2
    conn.execute(f'UPDATE "{table}" SET remark = remark WHERE {where}', values)
    assert repo.get(original.ref).revision == 3
    column = RESOURCE_CASES[kind][1][-1]
    new_value = "2030-01-02" if column == "date" else payload[column] + "-renamed"
    conn.execute(f'UPDATE "{table}" SET "{column}" = ? WHERE {where}', (new_value,) + values)
    payload[column] = new_value
    new_key = resource_key(kind, payload)
    renamed = repo.find_active(kind, new_key)
    assert renamed.ref == original.ref and renamed.revision == 4
    assert repo.find_active(kind, key) is None
    where, values = where_key(kind, payload)
    conn.execute(f'DELETE FROM "{table}" WHERE {where}', values)
    deleted = repo.get(original.ref)
    assert not deleted.active and deleted.revision == 5 and deleted.entity_key == new_key
    assert repo.find_active(kind, new_key) is None
    insert_row(conn, table, payload)
    recreated = repo.find_active(kind, new_key)
    assert recreated.ref != original.ref and recreated.revision == 1
    assert repo.get(original.ref) == deleted


@pytest.mark.parametrize("kind", RESOURCE_CASES)
@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("verb", ("REPLACE", "INSERT OR REPLACE"))
def test_replace_same_business_key_never_reuses_old_ref(identity_conn, kind, recursive, verb):
    conn, table = identity_conn, RESOURCE_CASES[kind][0]
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    payload = resource_payload(kind)
    insert_row(conn, table, payload)
    repo = WorkbenchIdentityRepository(conn)
    key = resource_key(kind, payload)
    old = repo.find_active(kind, key)
    payload["remark"] = "replacement"
    insert_row(conn, table, payload, verb=verb)
    current, retired = repo.find_active(kind, key), repo.get(old.ref)
    assert current.ref != old.ref and current.revision == 1 and current.active
    assert not retired.active and retired.revision == old.revision + 1
    assert repo.active_map(kind, [key]) == {key: current}


@pytest.mark.parametrize("kind", ("op_type", "resource_team"))
@pytest.mark.parametrize("recursive", (0, 1))
def test_replace_unique_name_conflict_retires_displaced_different_key(identity_conn, kind, recursive):
    conn, (table, columns) = identity_conn, RESOURCE_CASES[kind]
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    payload = resource_payload(kind)
    insert_row(conn, table, payload)
    repo = WorkbenchIdentityRepository(conn)
    old_key = resource_key(kind, payload)
    old = repo.find_active(kind, old_key)
    payload[columns[0]] += "-other"
    insert_row(conn, table, payload, verb="INSERT OR REPLACE")
    assert conn.execute(f'SELECT 1 FROM "{table}" WHERE "{columns[0]}" = ?', (old_key,)).fetchone() is None
    retired = repo.get(old.ref)
    assert not retired.active and retired.revision == old.revision + 1
    assert repo.find_active(kind, old_key) is None
    current = repo.find_active(kind, resource_key(kind, payload))
    assert current.ref != old.ref and current.active and current.revision == 1


def test_metadata_queries_are_read_only_and_do_not_fill_missing_refs(identity_conn):
    conn = identity_conn
    repo = WorkbenchIdentityRepository(conn)
    missing = repo.find_active("machine", "M1")
    retained = repo.find_active("operator", "O1")
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE ref = ?", (missing.ref,))
    conn.commit()
    before = business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), conn.total_changes
    conn.execute("PRAGMA query_only = ON")
    try:
        assert repo.get(missing.ref) is None
        assert repo.find_active("machine", "M1") is None
        assert repo.active_map("machine", ["M1", "absent", "M1"]) == {}
        assert repo.active_map("operator", iter(["O1", "absent", "O1"])) == {"O1": retained}
        assert repo.active_map("operator", iter(())) == {}
        assert repo.get("f" * 48) is None
        assert not conn.in_transaction
        assert (business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), conn.total_changes) == before
    finally:
        conn.execute("PRAGMA query_only = OFF")


def test_querying_absent_metadata_table_exposes_error_without_installing_it(v19_conn):
    conn = v19_conn
    seed_resources(conn)
    before = schema_snapshot(conn), business_snapshot(conn), conn.total_changes
    repo = WorkbenchIdentityRepository(conn)
    conn.execute("PRAGMA query_only = ON")
    try:
        for lookup in (lambda: repo.get("f" * 48), lambda: repo.find_active("machine", "M1"),
                       lambda: repo.active_map("machine", ["M1"])):
            with pytest.raises(AppError) as error:
                lookup()
            assert isinstance(error.value.__cause__, sqlite3.OperationalError)
            assert "no such table: WorkbenchEntityRefs" in str(error.value.__cause__)
        assert (schema_snapshot(conn), business_snapshot(conn), conn.total_changes) == before
    finally:
        conn.execute("PRAGMA query_only = OFF")


@pytest.mark.parametrize("operation", ("insert", "update", "rename", "delete", "replace"))
def test_rollback_leaves_no_new_ref_or_early_revision(identity_conn, operation):
    conn = identity_conn
    repo = WorkbenchIdentityRepository(conn)
    old = repo.find_active("machine", "M1")
    before = business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs")
    sql = {
        "insert": "INSERT INTO Machines(machine_id, name) VALUES ('new', 'new')",
        "update": "UPDATE Machines SET name = 'changed' WHERE machine_id = 'M1'",
        "rename": "UPDATE Machines SET machine_id = 'renamed' WHERE machine_id = 'M1'",
        "delete": "DELETE FROM Machines WHERE machine_id = 'M1'",
        "replace": "INSERT OR REPLACE INTO Machines(machine_id, name) VALUES ('M1', 'new')",
    }[operation]
    with pytest.raises(RuntimeError, match="abort identity write"):
        with TransactionManager(conn).transaction():
            conn.execute(sql)
            assert table_rows(conn, "WorkbenchEntityRefs") != before[1]
            raise RuntimeError("abort identity write")
    assert not conn.in_transaction
    assert (business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs")) == before
    assert repo.get(old.ref) == old


@pytest.mark.parametrize("backfill", (False, True))
def test_composite_calendar_keys_with_colons_chinese_and_emoji_do_not_cross_records(schema_conn, mem_conn, backfill):
    conn = load_v24_schema(mem_conn) if backfill else schema_conn
    if backfill:
        remove_metadata_for_v19(conn)
    pairs = [("a:b", "c"), ("a", "b:c"), ("\u4e2d:\U0001f680", "\u6587:\U0001f680"), ("\u4e2d", ":\U0001f680\u6587:\U0001f680")]
    expected = ["a%3Ab:c", "a:b%3Ac", "\u4e2d%3A\U0001f680:\u6587%3A\U0001f680", "\u4e2d:%3A\U0001f680\u6587%3A\U0001f680"]
    for number, (operator, date) in enumerate(pairs):
        conn.execute("INSERT INTO Operators(operator_id, name) VALUES (?, ?)", (operator, operator))
        conn.execute("INSERT INTO OperatorCalendar(operator_id, date, remark) VALUES (?, ?, ?)", (operator, date, str(number)))
    if backfill:
        conn.commit()
        before = business_snapshot(conn)
        assert v20.run(conn) == MigrationOutcome.APPLIED
        assert business_snapshot(conn) == before
    assert [entity_key(*pair) for pair in pairs] == expected
    repo = WorkbenchIdentityRepository(conn)
    before = repo.active_map("operator_calendar", expected)
    assert set(before) == set(expected) and len({row.ref for row in before.values()}) == 4
    conn.execute("UPDATE OperatorCalendar SET remark = 'changed' WHERE operator_id = ? AND date = ?", pairs[0])
    conn.execute("DELETE FROM OperatorCalendar WHERE operator_id = ? AND date = ?", pairs[2])
    assert repo.get(before[expected[0]].ref).revision == 2
    assert not repo.get(before[expected[2]].ref).active
    for position in (1, 3):
        assert repo.get(before[expected[position]].ref) == before[expected[position]]


def test_active_map_chunks_over_500_composite_keys_without_loss(identity_conn, monkeypatch):
    conn = identity_conn
    keys = []
    for number in range(1203):
        operator, date = "\u4e2d:\U0001f680:" + str(number), "2030-01-01"
        conn.execute("INSERT INTO Operators(operator_id, name) VALUES (?, ?)", (operator, operator))
        conn.execute("INSERT INTO OperatorCalendar(operator_id, date) VALUES (?, ?)", (operator, date))
        keys.append(resource_key("operator_calendar", {"operator_id": operator, "date": date}))
    repo = WorkbenchIdentityRepository(conn)
    expected = {key: repo.find_active("operator_calendar", key) for key in keys}
    batches, fetchall = [], repo.fetchall

    def record(sql, params):
        batches.append(len(params) - 1)
        return fetchall(sql, params)

    monkeypatch.setattr(repo, "fetchall", record)
    assert repo.active_map("operator_calendar", iter(keys + keys[:23] + ["missing"])) == expected
    assert batches == [500, 500, 204]
    assert all(row is not None and row.active for row in expected.values())
    assert len({row.ref for row in expected.values()}) == len(keys)


@pytest.mark.parametrize("kind,service_type", [("machine", MachineService), ("operator", OperatorService)])
@pytest.mark.parametrize("pathway", ("legacy", "workbench"))
def test_old_and_new_domain_write_paths_maintain_identity(identity_conn, kind, service_type, pathway):
    conn = identity_conn
    service, repo = service_type(conn), WorkbenchIdentityRepository(conn)

    def invoke(action, callback):
        if pathway == "legacy":
            return callback()

        def mutate(_):
            callback()
            return WorkbenchCommandOutcome("committed", {})

        WorkbenchCommandService(conn).execute(request_key="identity-path-" + action, action=action,
                                              context_ref="identity-test", normalized_input={},
                                              guard=lambda: None, mutate=mutate)

    invoke("create", lambda: service.create("domain-new", "old-name"))
    old = repo.find_active(kind, "domain-new")
    assert old is not None and old.revision == 1
    invoke("update", lambda: service.update("domain-new", name="new-name", remark="retained"))
    assert repo.get(old.ref).revision == 2 and repo.find_active(kind, "domain-new").ref == old.ref
    invoke("delete", lambda: service.delete("domain-new"))
    assert not repo.get(old.ref).active and repo.get(old.ref).revision == 3
    invoke("recreate", lambda: service.create("domain-new", "new-instance"))
    assert repo.find_active(kind, "domain-new").ref != old.ref


def test_refs_and_revisions_survive_a_new_python_process(identity_conn, tmp_path, repo_root):
    conn = identity_conn
    conn.execute("UPDATE Machines SET name = 'renamed' WHERE machine_id = 'M1'")
    conn.execute("DELETE FROM Materials WHERE material_id = 'MAT1'")
    insert_row(conn, "Materials", SEED_ROWS["Materials"])
    conn.commit()
    repo = WorkbenchIdentityRepository(conn)
    expected = [asdict(repo.get(row[0])) for row in conn.execute("SELECT ref FROM WorkbenchEntityRefs ORDER BY ref")]
    path = tmp_path / "restart.db"
    copy_to_temp(conn, path)
    script = """
import json, sqlite3, sys
from dataclasses import asdict
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
conn = sqlite3.connect(sys.argv[1], uri=True)
conn.row_factory = sqlite3.Row
repo = WorkbenchIdentityRepository(conn)
print(json.dumps([asdict(repo.get(row[0])) for row in conn.execute('SELECT ref FROM WorkbenchEntityRefs ORDER BY ref')]))
conn.close()
"""
    for _ in range(2):
        result = subprocess.run([sys.executable, "-c", script, path.as_uri() + "?mode=ro"], cwd=str(repo_root),
                                check=True, capture_output=True, text=True, timeout=30)
        assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("name", tuple(metadata_objects()))
def test_missing_metadata_object_cannot_claim_current_schema(schema_conn, name):
    ensure_schema_version(schema_conn)
    object_type = schema_snapshot(schema_conn)[name][0]
    schema_conn.execute(f'DROP {object_type.upper()} "{name}"')
    before = schema_snapshot(schema_conn)
    assert "missing_workbench_metadata: " + name in workbench_metadata_contract_issues(schema_conn)
    assert not detect_schema_is_current(schema_conn)
    with pytest.raises(MigrationContractError, match="workbench_metadata"):
        ensure_current_schema_contract(schema_conn)
    assert schema_snapshot(schema_conn) == before


@pytest.mark.parametrize("name,old,new", [
    ("wb_ref_machine_insert", "randomblob(24)", "randomblob(16)"),
    ("wb_ref_machine_update", "revision + 1", "revision + 0"),
    ("wb_ref_machine_delete", "active = 0", "active = 1"),
    ("idx_workbench_refs_active_key", "UNIQUE INDEX", "INDEX"),
    ("idx_workbench_refs_kind", "(kind, active)", "(active, kind)"),
    ("WorkbenchEntityRefs", "revision > 0", "revision >= 0"),
    ("WorkbenchCommandReceipts", "request_key TEXT PRIMARY KEY NOT NULL", "request_key TEXT NOT NULL"),
])
def test_damaged_metadata_ddl_blocks_real_startup_without_repair(schema_conn, tmp_path, schema_path, name, old, new):
    ensure_schema_version(schema_conn)
    object_type = schema_snapshot(schema_conn)[name][0]
    sql = metadata_objects()[name]
    assert old in sql
    schema_conn.execute(f'DROP {object_type.upper()} "{name}"')
    schema_conn.execute(sql.replace(old, new))
    schema_conn.commit()
    assert "bad_workbench_metadata: " + name in workbench_metadata_contract_issues(schema_conn)
    assert not detect_schema_is_current(schema_conn)
    before = schema_snapshot(schema_conn)
    path = tmp_path / "damaged.db"
    copy_to_temp(schema_conn, path)
    with pytest.raises(MigrationContractError, match="bad_workbench_metadata: " + name):
        ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))
    with connect_temp(path) as reopened:
        assert schema_snapshot(reopened) == before
        assert get_schema_version(reopened) == CURRENT_SCHEMA_VERSION


@pytest.mark.parametrize("kind", [kind for kind, (_, columns) in RESOURCE_CASES.items() if len(columns) == 1])
@pytest.mark.parametrize("outer", (False, True))
def test_null_legacy_business_key_fails_explicitly_and_rolls_back_all_v20_ddl(v19_conn, kind, outer):
    conn = v19_conn
    seed_resources(conn, relations=True)
    table, columns = RESOURCE_CASES[kind]
    payload = resource_payload(kind)
    payload[columns[0]] = None
    insert_row(conn, table, payload)
    conn.commit()
    if outer:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO SystemConfig(config_key, config_value) VALUES ('outer-owner', 'uncommitted')")
    before = schema_snapshot(conn), business_snapshot(conn)
    with pytest.raises(RuntimeError, match=table + ".*\u7f3a\u5931.*\u672a\u4fee\u6b63\u539f\u6570\u636e"):
        v20.run(conn)
    assert (schema_snapshot(conn), business_snapshot(conn)) == before
    assert not set(metadata_objects()).intersection(schema_snapshot(conn))
    assert get_schema_version(conn) == 19
    assert conn.in_transaction is outer
    conn.rollback()
    assert conn.execute("SELECT 1 FROM SystemConfig WHERE config_key = 'outer-owner'").fetchone() is None


def test_successful_v20_run_does_not_commit_an_external_transaction(v19_conn):
    conn = v19_conn
    seed_resources(conn, relations=True)
    before = schema_snapshot(conn), business_snapshot(conn)
    conn.execute("BEGIN IMMEDIATE")
    assert v20.run(conn) == MigrationOutcome.APPLIED
    assert conn.in_transaction
    assert workbench_metadata_contract_issues(conn) == []
    assert table_rows(conn, "WorkbenchEntityRefs")
    conn.rollback()
    assert (schema_snapshot(conn), business_snapshot(conn)) == before
    assert get_schema_version(conn) == 19


def test_migration_runner_retains_outer_rollback_ownership(v19_conn, tmp_path, monkeypatch):
    seed_resources(v19_conn, relations=True)
    before = schema_snapshot(v19_conn), business_snapshot(v19_conn)
    path = tmp_path / "runner.db"
    copy_to_temp(v19_conn, path)
    real_contract_check = migration_runner.ensure_current_schema_contract

    def reject_after_current(conn, *, schema_version=None):
        real_contract_check(conn, schema_version=schema_version)
        if schema_version == CURRENT_SCHEMA_VERSION:
            assert conn.in_transaction
            assert table_rows(conn, "WorkbenchEntityRefs")
            raise RuntimeError("reject final current contract")

    def connect(path_string):
        assert path_string == str(path)
        conn = sqlite3.connect(path_string)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr(migration_runner, "ensure_current_schema_contract", reject_after_current)
    with pytest.raises(RuntimeError, match="reject final current contract"):
        migration_runner._apply_migrations(str(path), to_version=CURRENT_SCHEMA_VERSION, schema_sql=None, connection_factory=connect)
    with connect_temp(path) as reopened:
        assert (schema_snapshot(reopened), business_snapshot(reopened)) == before
        assert get_schema_version(reopened) == 19
