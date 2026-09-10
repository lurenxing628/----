"""Additive v23, exact schema parity and preservation across real file upgrade."""

from __future__ import annotations

import sqlite3

import pytest

from core.infrastructure.database import ensure_schema
from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    current_schema_contract_issues,
    get_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS, v23
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_dashboard_external_schema import workbench_dashboard_external_objects
from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.infrastructure.workbench_outsourcing_schema import workbench_outsourcing_objects
from core.infrastructure.workbench_plan_identity_write_guard import plan_identity_write_guard_objects
from core.infrastructure.workbench_process_schema import process_objects
from core.infrastructure.workbench_process_workflow_schema import (
    WORKFLOW_TABLES,
    install_process_workflow,
    workbench_process_workflow_contract_issues,
    workflow_objects,
)
from core.services.process.workflow_state import read_workflow, record_confirmation
from tests.workbench import process_v22_migration_support as v22_support
from tests.workbench.identity_metadata_support import connect_temp, schema_snapshot, table_rows
from tests.workbench.legacy_migration_current_support import V30_TABLES, V31_TABLES
from tests.workbench.process_v22_migration_support import (
    assert_new_metadata,
    assert_old_tables_preserved,
    assert_v22_schema,
    ddl_snapshot,
    seed_v22,
    table_snapshot,
)
from tests.workbench.process_workflow_support import (
    business_rows,
    confirm_all,
    remove_workflow,
    stored_state,
    v22_workflow_database,
    workflow_database,
)


def test_latest_schema_registration_and_additive_objects(schema_conn, db_path):
    assert CURRENT_SCHEMA_VERSION >= 23 and MIGRATIONS[23] is v23.run
    assert workbench_process_workflow_contract_issues(schema_conn) == []
    assert current_schema_contract_issues(schema_conn) == []
    with connect_temp(db_path) as conn:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
        assert current_schema_contract_issues(conn) == []


def test_v22_upgrade_preserves_every_business_row_and_identity_and_adds_no_confirmations(tmp_path, schema_path):
    path, backups = tmp_path / "v22.db", tmp_path / "backups"
    with connect_temp(path) as conn:
        seed_v22(conn)
        before, objects = table_snapshot(conn), ddl_snapshot(conn)
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    files = list(backups.glob("*.db"))
    assert len(files) == 1 and f"before_migrate_v22_to_v{CURRENT_SCHEMA_VERSION}" in files[0].name
    with connect_temp(files[0]) as backup:
        assert_v22_schema(backup)
        assert table_snapshot(backup) == before
        assert ddl_snapshot(backup) == objects
        assert [tuple(row) for row in backup.execute("PRAGMA integrity_check")] == [("ok",)]
        assert not backup.execute("PRAGMA foreign_key_check").fetchall()
    with connect_temp(path) as upgraded:
        assert get_schema_version(upgraded) == CURRENT_SCHEMA_VERSION
        assert current_schema_contract_issues(upgraded) == []
        assert_old_tables_preserved(upgraded, before, objects)
        assert_new_metadata(upgraded, before)
        upgraded_before, upgraded_objects = table_snapshot(upgraded), ddl_snapshot(upgraded)
        assert read_workflow(upgraded, "P1")["origin"] == "legacy"
        assert table_snapshot(upgraded) == upgraded_before
        assert [tuple(row) for row in upgraded.execute("PRAGMA integrity_check")] == [("ok",)]
        assert not upgraded.execute("PRAGMA foreign_key_check").fetchall()
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(backups))
    assert list(backups.glob("*.db")) == files
    with connect_temp(path) as reopened:
        assert table_snapshot(reopened) == upgraded_before
        assert ddl_snapshot(reopened) == upgraded_objects


@pytest.mark.parametrize("removed_issue", (
    *("missing_outsourcing_schema:" + name for name in workbench_outsourcing_objects()),
    *("missing_workbench_plan_write_guard: " + name for name in plan_identity_write_guard_objects()),
    *("missing_dashboard_external_schema:" + name for name in workbench_dashboard_external_objects()),
    None,
))
def test_v22_schema_requires_every_followup_diagnostic_and_rejects_unknowns(mem_conn, monkeypatch, removed_issue):
    seed_v22(mem_conn)
    before, objects = table_snapshot(mem_conn), ddl_snapshot(mem_conn)
    issues = list(current_schema_contract_issues(mem_conn))
    if removed_issue is None:
        issues.append("unexpected_schema_diagnostic")
    else:
        assert removed_issue in issues
        issues.remove(removed_issue)
    monkeypatch.setattr(v22_support, "current_schema_contract_issues", lambda _conn: issues)
    with pytest.raises(AssertionError):
        assert_v22_schema(mem_conn)
    assert table_snapshot(mem_conn) == before and ddl_snapshot(mem_conn) == objects


@pytest.mark.parametrize("damage", (*V30_TABLES, *V31_TABLES, "missing_origin", "guessed_batch", "extra_table"))
def test_v22_metadata_rejects_missing_tables_changed_origins_and_extra_tables(tmp_path, schema_path, damage):
    path = tmp_path / "v22-metadata.db"
    with connect_temp(path) as conn:
        seed_v22(conn)
        before = table_snapshot(conn)
    ensure_schema(str(path), schema_path=schema_path, backup_dir=str(tmp_path / "backups"))
    with connect_temp(path) as conn:
        assert_new_metadata(conn, before)
        if damage in V30_TABLES + V31_TABLES:
            conn.execute('DROP TABLE "' + damage + '"')
        elif damage == "extra_table":
            conn.execute("CREATE TABLE UnexpectedMetadata(value TEXT)")
        else:
            # Damage only this private upgrade to test the assertion, not DDL guards.
            origins = table_rows(conn, "WorkbenchOutsourcingOperationOrigins")
            assert len(origins) == 1 and origins[0][1] is None
            if damage == "missing_origin":
                conn.execute("DROP TRIGGER wb_outsourcing_operationorigins_no_delete")
                conn.execute("DELETE FROM WorkbenchOutsourcingOperationOrigins")
            else:
                conn.execute("DROP TRIGGER wb_outsourcing_operationorigins_no_update")
                conn.execute("UPDATE WorkbenchOutsourcingOperationOrigins SET batch_ref="
                             "(SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='B1' AND active=1)")
        with pytest.raises(AssertionError):
            assert_new_metadata(conn, before)


def test_v23_installer_adds_empty_workflow_without_business_writes(v22_workflow_conn):
    conn = v22_workflow_conn
    conn.execute("""INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,remark)
        VALUES('OLD-B','P1','historical part name',17,'2026-10-01','keep batch')""")
    old_op = conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,setup_hours,unit_hours)
        VALUES('OLD-B:1','OLD-B',1,'historical operation','internal',7.5,0.375)""").lastrowid
    conn.execute("""INSERT INTO Schedule(op_id,start_time,end_time,version,lock_status)
        VALUES(?,'2026-10-01 08:00:00','2026-10-01 12:00:00',7,'locked')""", (old_op,))
    conn.commit()
    before, objects = business_rows(conn), schema_snapshot(conn)
    refs = table_rows(conn, "WorkbenchEntityRefs")
    changes, denied = conn.total_changes, []

    def no_business_writes(action, table, _column, _db, _source):
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and table in before:
            denied.append(table)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(no_business_writes)
    try:
        assert v23.run(conn) == MigrationOutcome.APPLIED
    finally:
        conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
    assert not denied and business_rows(conn) == before and table_rows(conn, "WorkbenchEntityRefs") == refs
    assert conn.total_changes == changes
    assert all(table_rows(conn, table) == [] for table in WORKFLOW_TABLES)
    actual = schema_snapshot(conn)
    optimized = {"wb_ref_template_operation_insert", "wb_ref_template_operation_update"}
    assert {key for key in objects if actual[key] != objects[key]} == optimized
    for name in optimized:
        assert actual[name][:2] == objects[name][:2]
        assert _canonical_sql(actual[name][2]) == _canonical_sql(process_objects()[name])
    assert set(workflow_objects()) <= set(schema_snapshot(conn)) - set(objects)


@pytest.mark.parametrize("outer", (False, True))
def test_failed_v23_rolls_back_ddl_and_never_commits_owner(v22_workflow_conn, outer):
    conn = v22_workflow_conn
    if outer:
        conn.execute("BEGIN")
        conn.execute("UPDATE Parts SET remark='outer-owner'")
    before = stored_state(conn)

    def fail_second_table(action, name, *_):
        return (sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TABLE and name == WORKFLOW_TABLES[1]
                else sqlite3.SQLITE_OK)

    conn.set_authorizer(fail_second_table)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            v23.run(conn)
    finally:
        conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
    assert stored_state(conn) == before and conn.in_transaction is outer
    conn.rollback()


def test_install_is_idempotent_and_obeys_owner_rollback(workflow_conn):
    conn = workflow_conn
    confirm_all(conn)
    before, changes = stored_state(conn), conn.total_changes
    v23.run(conn)
    v23.run(conn)
    assert stored_state(conn) == before and conn.total_changes == changes
    remove_workflow(conn)
    before = stored_state(conn)
    conn.execute("BEGIN")
    v23.run(conn)
    assert conn.in_transaction
    conn.rollback()
    assert stored_state(conn) == before
    with pytest.raises(RuntimeError, match="caller transaction"):
        install_process_workflow(conn)


@pytest.mark.parametrize("name", tuple(workflow_objects()))
@pytest.mark.parametrize("damage", ("missing", "wrong_sql"))
def test_damage_fails_closed_and_get_does_not_repair(workflow_conn, name, damage):
    conn = workflow_conn
    kind = "INDEX" if name.startswith("idx_") else "TABLE"
    conn.execute('DROP ' + kind + ' "' + name + '"')
    if damage == "wrong_sql":
        sql = workflow_objects()[name]
        sql = sql.replace("(operation_ref)", "(stage)") if kind == "INDEX" else sql.replace("signature TEXT", "signature BLOB")
        conn.execute(sql)
    conn.commit()
    before, changes = stored_state(conn), conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    with pytest.raises(RuntimeError, match="workflow"):
        read_workflow(conn, "P1")
    assert workbench_process_workflow_contract_issues(conn)
    conn.execute("PRAGMA query_only=OFF")
    with pytest.raises(RuntimeError, match="workflow"):
        v23.run(conn)
    assert stored_state(conn) == before and conn.total_changes == changes


@pytest.mark.parametrize("signature", (None, "", "bad", "F" * 64, "x" * 64, b"0" * 64))
def test_invalid_confirmation_signature_rejected_by_schema(workflow_conn, signature):
    conn = workflow_conn
    confirm_all(conn)
    with pytest.raises(sqlite3.IntegrityError):
        with TransactionManager(conn).transaction():
            conn.execute("UPDATE WorkbenchProcessOperationConfirmations SET signature=?", (signature,))
    with pytest.raises(sqlite3.IntegrityError):
        with TransactionManager(conn).transaction():
            conn.execute("UPDATE WorkbenchProcessWorkflow SET route_signature=?", (signature,))
    assert read_workflow(conn, "P1")["ready"]


def test_confirmation_storage_failure_keeps_business_and_receipt_atomic(workflow_conn):
    conn = workflow_conn
    with TransactionManager(conn).transaction():
        record_confirmation(conn, "P1", "route")
    before = stored_state(conn)

    def deny_confirmation(action, name, *_):
        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_INSERT and name == WORKFLOW_TABLES[1] else sqlite3.SQLITE_OK

    conn.set_authorizer(deny_confirmation)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            with TransactionManager(conn).transaction():
                conn.execute("UPDATE PartOperations SET setup_hours=3 WHERE seq=1")
                conn.execute("""INSERT INTO WorkbenchCommandReceipts
                    (request_key,receipt_ref,action,context_ref,input_hash,outcome_json) VALUES(?,?,?,?,?,?)""",
                             ("r" * 16, "a" * 32, "source", "context", "a" * 64, "{}"))
                record_confirmation(conn, "P1", "source")
    finally:
        conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
    assert stored_state(conn) == before
