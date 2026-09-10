"""Additive v22 identity contracts; no production database or global registration."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys

import pytest

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migrations import v22
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import entity_key_sql, identity_triggers
from core.infrastructure.workbench_process_schema import (
    PROCESS_ENTITY_TABLES,
    install_process,
    process_objects,
    workbench_process_contract_issues,
)
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import (
    business_snapshot,
    connect_temp,
    copy_to_temp,
    insert_row,
    schema_snapshot,
    table_rows,
)
from tests.workbench.process_identity_support import (
    PROCESS_CASES,
    legacy_process_rows,
    process_database,
    process_row,
    stored_process_state,
)

KINDS = tuple(PROCESS_CASES)
CONFLICTS = [("template_operation", conflict) for conflict in ("key", "unique_position", "both")]
CONFLICTS.append(("template_external_group", "key"))


def test_exports_are_only_six_template_identity_triggers():
    assert PROCESS_ENTITY_TABLES == {
        "template_operation": ("PartOperations", ("id",)),
        "template_external_group": ("ExternalGroups", ("group_id",)),
    }
    assert set(process_objects()) == {"wb_ref_" + kind + "_" + event
                                     for kind in KINDS for event in ("insert", "update", "delete")}
    assert all(sql.startswith("CREATE TRIGGER") for sql in process_objects().values())


def test_v21_rows_hidden_fields_hours_plans_preserved_and_refs_survive_process_restart(mem_conn, tmp_path):
    conn = legacy_process_rows(mem_conn)
    before, refs, objects = business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), schema_snapshot(conn)
    changes = conn.total_changes
    business_tables = set(before) - {"sqlite_sequence"}
    denied = []

    def reject_business_writes(action, table, _column, _db, _source):
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE) and table in business_tables:
            denied.append(table)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(reject_business_writes)
    try:
        assert v22.run(conn) == MigrationOutcome.APPLIED
    finally:
        conn.set_authorizer(lambda *_args: sqlite3.SQLITE_OK)
    assert denied == [] and business_snapshot(conn) == before
    assert set(schema_snapshot(conn)) - set(objects) == set(process_objects())
    assert {name: schema_snapshot(conn)[name] for name in objects} == objects
    after_refs = table_rows(conn, "WorkbenchEntityRefs")
    assert after_refs[:len(refs)] == refs and len(after_refs) == len(refs) + 4
    assert conn.total_changes - changes == 4
    assert workbench_process_contract_issues(conn) == []
    assert all(re.fullmatch(r"[0-9a-f]{48}", row[0]) for row in after_refs)
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    assert table_rows(conn, "WorkbenchCommandReceipts") == []
    path = tmp_path / "process-upgrade.db"
    copy_to_temp(conn, path)
    code = """import json, sqlite3, sys
from core.infrastructure.migrations import v22
conn = sqlite3.connect(sys.argv[1])
v22.run(conn)
v22.run(conn)
print(json.dumps(conn.execute('SELECT * FROM WorkbenchEntityRefs ORDER BY rowid').fetchall()))
conn.close()
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, str(path)], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [list(row) for row in after_refs]
    with connect_temp(path) as reopened:
        assert business_snapshot(reopened) == before
        assert schema_snapshot(reopened) == schema_snapshot(conn)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("change", ("content", "part", "sequence", "primary_key", "no_op"))
def test_update_keeps_row_identity_and_advances_revision_even_when_part_or_sequence_changes(process_conn, kind, change):
    conn = process_conn
    table, column, key = PROCESS_CASES[kind]
    repo = WorkbenchIdentityRepository(conn)
    old = repo.find_active(kind, str(key))
    updates = {
        "content": {"unit_hours": 2.75} if kind == "template_operation" else {"remark": "changed"},
        "part": {"part_no": "P2"},
        "sequence": {"seq": 9} if kind == "template_operation" else {"start_seq": 8, "end_seq": 9},
        "primary_key": {column: 91 if kind == "template_operation" else "renamed"},
        "no_op": {column: key},
    }[change]
    assignments = ",".join('"' + name + '"=?' for name in updates)
    conn.execute(f'UPDATE "{table}" SET {assignments} WHERE "{column}"=?', tuple(updates.values()) + (key,))
    current = repo.find_active(kind, str(updates.get(column, key)))
    assert current.ref == old.ref and current.active and current.revision == old.revision + 1
    assert len([row for row in table_rows(conn, "WorkbenchEntityRefs") if row[1] == kind]) >= 1
    conn.commit()
    before, changes = stored_process_state(conn), conn.total_changes
    assert v22.run(conn) == MigrationOutcome.APPLIED
    assert stored_process_state(conn) == before and conn.total_changes == changes


@pytest.mark.parametrize("kind", KINDS)
def test_delete_reinsert_same_key_never_revives_old_ref(process_conn, kind):
    conn = process_conn
    table, column, key = PROCESS_CASES[kind]
    payload = process_row(conn, kind)
    repo = WorkbenchIdentityRepository(conn)
    old = repo.find_active(kind, str(key))
    conn.execute(f'DELETE FROM "{table}" WHERE "{column}"=?', (key,))
    assert not repo.get(old.ref).active and repo.get(old.ref).revision == old.revision + 1
    insert_row(conn, table, payload)
    current = repo.find_active(kind, str(key))
    assert current.ref != old.ref and current.revision == 1 and not repo.get(old.ref).active


@pytest.mark.parametrize("kind,conflict", CONFLICTS)
@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("verb", ("REPLACE", "INSERT OR REPLACE", "UPDATE OR REPLACE", "INSERT OR IGNORE"))
def test_conflict_policies_track_both_primary_and_unique_position_victims(process_conn, kind, conflict, recursive, verb):
    conn = process_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    table, column, key = PROCESS_CASES[kind]
    repo = WorkbenchIdentityRepository(conn)
    source = repo.find_active(kind, str(key))
    second_key = 71 if kind == "template_operation" else "second"
    second = process_row(conn, kind)
    second.update({column: second_key, "part_no": "P2"})
    if kind == "template_operation":
        second["seq"] = 7
    insert_row(conn, table, second)
    target = repo.find_active(kind, str(second_key))
    payload = process_row(conn, kind)
    if conflict in ("key", "both"):
        payload[column] = second_key
    elif verb != "UPDATE OR REPLACE":
        # Keep the unused id below the existing AUTOINCREMENT high-water mark.
        payload[column] = 61
    if conflict in ("unique_position", "both"):
        payload.update(part_no="P2", seq=7)
    elif kind == "template_operation":
        payload["seq"] = 9
    before, changes = stored_process_state(conn), conn.total_changes
    if verb == "UPDATE OR REPLACE":
        assignments = ",".join('"' + name + '"=?' for name in payload)
        conn.execute(f'{verb} "{table}" SET {assignments} WHERE "{column}"=?', tuple(payload.values()) + (key,))
    else:
        insert_row(conn, table, payload, verb=verb)
    if verb == "INSERT OR IGNORE":
        assert stored_process_state(conn) == before and conn.total_changes == changes
        return
    current = repo.find_active(kind, str(payload[column]))
    assert current.active and not repo.get(target.ref).active
    assert repo.get(target.ref).revision == target.revision + 1
    if verb == "UPDATE OR REPLACE":
        assert current.ref == source.ref and current.revision == source.revision + 1
    else:
        assert current.ref not in (source.ref, target.ref) and current.revision == 1
        assert repo.get(source.ref) == source
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("verb", ("REPLACE", "INSERT OR REPLACE", "UPDATE OR REPLACE"))
def test_replace_displacing_two_rows_retires_both_refs(process_conn, recursive, verb):
    conn = process_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    payload = process_row(conn, "template_operation")
    second = dict(payload, id=81, seq=9)
    insert_row(conn, "PartOperations", second)
    repo = WorkbenchIdentityRepository(conn)
    old = [repo.find_active("template_operation", key) for key in ("21", "81")]
    survivor = None
    if verb == "UPDATE OR REPLACE":
        insert_row(conn, "PartOperations", dict(payload, id=91, seq=11))
        survivor = repo.find_active("template_operation", "91")
        conn.execute("UPDATE OR REPLACE PartOperations SET id=21, seq=9 WHERE id=91")
    else:
        insert_row(conn, "PartOperations", dict(payload, seq=9), verb=verb)
    current = repo.find_active("template_operation", "21")
    assert current.ref not in {identity.ref for identity in old}
    assert all(not repo.get(identity.ref).active and repo.get(identity.ref).revision == identity.revision + 1
               for identity in old)
    if survivor is not None:
        assert current.ref == survivor.ref and current.revision == survivor.revision + 1


@pytest.mark.parametrize("verb", ("REPLACE", "INSERT OR REPLACE"))
def test_replace_without_explicit_id_retires_unique_position_victim(process_conn, verb):
    conn = process_conn
    assert conn.execute("PRAGMA recursive_triggers").fetchone()[0] == 0
    repo = WorkbenchIdentityRepository(conn)
    old = repo.find_active("template_operation", "21")
    conn.execute(f"{verb} INTO PartOperations(part_no,seq,op_type_name) VALUES ('P1',1,'replacement')")
    key = conn.execute("SELECT id FROM PartOperations WHERE part_no='P1' AND seq=1").fetchone()[0]
    current = repo.find_active("template_operation", str(key))
    assert key != 21 and current.ref != old.ref and current.active and current.revision == 1
    assert not repo.get(old.ref).active and repo.get(old.ref).revision == old.revision + 1


@pytest.mark.parametrize("outer", (False, True))
@pytest.mark.parametrize("phase", ("ddl", "backfill"))
def test_v22_failure_rolls_back_schema_and_refs_without_committing_outer_owner(mem_conn, outer, phase):
    conn = legacy_process_rows(mem_conn)
    if outer:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO SystemConfig(config_key, config_value) VALUES ('owner', 'pending')")
    before, attempts, denied = stored_process_state(conn), [], []

    def reject_late_write(action, name, _column, _db, _source):
        if action == sqlite3.SQLITE_INSERT and name == "WorkbenchEntityRefs":
            attempts.append(name)
        if (phase == "ddl" and action == sqlite3.SQLITE_CREATE_TRIGGER and name == "wb_ref_template_external_group_insert"
                or phase == "backfill" and action == sqlite3.SQLITE_INSERT and name == "WorkbenchEntityRefs" and len(attempts) == 2):
            denied.append(name)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(reject_late_write)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            v22.run(conn)
    finally:
        conn.set_authorizer(lambda *_args: sqlite3.SQLITE_OK)
    assert len(denied) == 1 and stored_process_state(conn) == before
    assert conn.in_transaction is outer
    conn.rollback()


def test_success_respects_outer_rollback(mem_conn):
    conn = legacy_process_rows(mem_conn)
    before = stored_process_state(conn)
    conn.execute("BEGIN IMMEDIATE")
    assert v22.run(conn) == MigrationOutcome.APPLIED and conn.in_transaction
    assert workbench_process_contract_issues(conn) == []
    conn.rollback()
    assert stored_process_state(conn) == before


@pytest.mark.parametrize("name", tuple(process_objects()))
@pytest.mark.parametrize("damage", ("missing", "legal_wrong_sql"))
def test_contract_check_is_readonly_and_legally_damaged_trigger_is_not_repaired(process_conn, name, damage):
    conn = process_conn
    conn.execute(f'DROP TRIGGER "{name}"')
    if damage == "legal_wrong_sql":
        sql = process_objects()[name]
        assert "revision + 1" in sql
        conn.execute(sql.replace("revision + 1", "revision + 0"))
    conn.commit()
    before, changes = stored_process_state(conn), conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    try:
        prefix = "missing" if damage == "missing" else "bad"
        assert prefix + "_workbench_process: " + name in workbench_process_contract_issues(conn)
    finally:
        conn.execute("PRAGMA query_only=OFF")
    assert stored_process_state(conn) == before and conn.total_changes == changes
    if damage == "legal_wrong_sql":
        with pytest.raises(RuntimeError, match="bad_workbench_process: " + name):
            v22.run(conn)
        assert stored_process_state(conn) == before


def test_legacy_null_group_key_rejects_without_guessing_or_partial_install(mem_conn):
    conn = legacy_process_rows(mem_conn)
    insert_row(conn, "ExternalGroups", {"group_id": None, "part_no": "P1", "start_seq": 5, "end_seq": 6})
    conn.commit()
    before = stored_process_state(conn)
    with pytest.raises(RuntimeError, match="ExternalGroups has a missing primary key"):
        v22.run(conn)
    assert stored_process_state(conn) == before


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("damage", ("missing_column", "missing_primary_key"))
def test_source_primary_key_contract_rejects_legal_but_wrong_tables(schema_conn, kind, damage):
    conn = schema_conn
    for name in process_objects():
        conn.execute(f'DROP TRIGGER IF EXISTS "{name}"')
    table, column, _ = PROCESS_CASES[kind]
    conn.execute(f'DROP TABLE "{table}"')
    key_column = "wrong_key" if damage == "missing_column" else column
    conn.execute(f'CREATE TABLE "{table}" ("{key_column}" TEXT, part_no TEXT, seq INTEGER)')
    conn.commit()
    before = stored_process_state(conn)
    assert "bad_workbench_process_primary_key: " + table in workbench_process_contract_issues(conn)
    with pytest.raises(RuntimeError, match="workbench_process"):
        v22.run(conn)
    assert stored_process_state(conn) == before


@pytest.mark.parametrize("kind", KINDS)
def test_missing_identity_read_never_repairs_and_install_only_backfills_missing_ref(process_conn, kind):
    conn = process_conn
    _, _, key = PROCESS_CASES[kind]
    repo = WorkbenchIdentityRepository(conn)
    old = repo.find_active(kind, str(key))
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE ref=?", (old.ref,))
    conn.commit()
    before, changes = stored_process_state(conn), conn.total_changes
    conn.execute("PRAGMA query_only=ON")
    try:
        assert repo.find_active(kind, str(key)) is None
        assert workbench_process_contract_issues(conn) == []
    finally:
        conn.execute("PRAGMA query_only=OFF")
    assert stored_process_state(conn) == before and conn.total_changes == changes
    with TransactionManager(conn).transaction():
        install_process(conn)
    assert repo.find_active(kind, str(key)).ref != old.ref
    assert conn.total_changes == changes + 1 and business_snapshot(conn) == before[1]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("recursive", (0, 1))
@pytest.mark.parametrize("verb", ("REPLACE", "INSERT OR REPLACE", "UPDATE OR REPLACE"))
def test_failed_sql_replace_retains_original_business_rows_and_identity_evidence(process_conn, kind, recursive, verb):
    conn = process_conn
    conn.execute(f"PRAGMA recursive_triggers={recursive}")
    table, column, key = PROCESS_CASES[kind]
    payload = process_row(conn, kind)
    payload["supplier_id"] = "nonexistent-supplier"
    before = stored_process_state(conn)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        with TransactionManager(conn).transaction():
            if verb == "UPDATE OR REPLACE":
                conn.execute(f'{verb} "{table}" SET supplier_id=? WHERE "{column}"=?', (payload["supplier_id"], key))
            else:
                insert_row(conn, table, payload, verb=verb)
    assert stored_process_state(conn) == before and not conn.in_transaction


@pytest.mark.parametrize("backfill", (False, True))
def test_nul_and_escaped_part_numbers_keep_distinct_alternates_through_replace(schema_conn, backfill):
    conn = schema_conn
    assert conn.execute("PRAGMA recursive_triggers").fetchone()[0] == 0
    for name in process_objects():
        conn.execute(f'DROP TRIGGER IF EXISTS "{name}"')
    if not backfill:
        v22.run(conn)
    parts = ("same\0first:%", "same\0second:%", "%3A:%25", "\u4e2d:\0%")
    for number, part in enumerate(parts, 101):
        insert_row(conn, "Parts", {"part_no": part, "part_name": "nul-key"})
        insert_row(conn, "PartOperations", {"id": number, "part_no": part, "seq": 3, "op_type_name": "operation"})
    conn.commit()
    if backfill:
        v22.run(conn)
    repo = WorkbenchIdentityRepository(conn)
    originals = [repo.find_active("template_operation", str(number)) for number in range(101, 105)]
    for number, part in enumerate(parts, 101):
        alternate = conn.execute("SELECT alternate_key FROM WorkbenchEntityRefs WHERE ref=?",
                                 (originals[number - 101].ref,)).fetchone()[0]
        assert alternate == part.replace("%", "%25").replace(":", "%3A") + ":3"
        insert_row(conn, "PartOperations", {"id": number + 100, "part_no": part, "seq": 3,
                   "op_type_name": "replacement"}, verb="REPLACE")
        assert not repo.get(originals[number - 101].ref).active
        assert all(repo.get(old.ref).active for old in originals[number - 100:])


def test_nullable_composite_sql_preserves_null_without_inventing_a_conflict(schema_conn):
    conn = schema_conn
    conn.execute("CREATE TABLE NullableProbe(id INTEGER PRIMARY KEY, part_no TEXT, seq INTEGER, UNIQUE(part_no, seq))")
    for sql in identity_triggers("nullable_probe", "NullableProbe", ("id",), alternate_columns=("part_no", "seq")).values():
        conn.execute(sql)
    values = ((None, 1), ("P", None), (None, None))
    expression = entity_key_sql(("part_no", "seq"), "source")
    repo = WorkbenchIdentityRepository(conn)
    for number, pair in enumerate(values, 1):
        conn.execute("INSERT INTO NullableProbe VALUES (?,?,?)", (number,) + pair)
        old = repo.find_active("nullable_probe", str(number))
        assert conn.execute(f"SELECT {expression} FROM NullableProbe AS source WHERE id=?", (number,)).fetchone()[0] is None
        assert conn.execute("SELECT alternate_key FROM WorkbenchEntityRefs WHERE ref=?", (old.ref,)).fetchone()[0] is None
        conn.execute("REPLACE INTO NullableProbe VALUES (?,?,?)", (number + 10,) + pair)
        assert repo.get(old.ref) == old
        conn.execute("REPLACE INTO NullableProbe VALUES (?,?,?)", (number,) + pair)
        assert not repo.get(old.ref).active and repo.find_active("nullable_probe", str(number)).ref != old.ref


@pytest.mark.parametrize("verb", ("INSERT", "REPLACE", "INSERT OR REPLACE", "UPDATE OR REPLACE"))
def test_new_null_group_primary_key_fails_atomically_after_install(process_conn, verb):
    conn = process_conn
    before = stored_process_state(conn)
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed: WorkbenchEntityRefs.entity_key"):
        with TransactionManager(conn).transaction():
            if verb == "UPDATE OR REPLACE":
                conn.execute("UPDATE OR REPLACE ExternalGroups SET group_id=NULL WHERE group_id='EG1'")
            else:
                insert_row(conn, "ExternalGroups", dict(process_row(conn, "template_external_group"), group_id=None), verb=verb)
    assert stored_process_state(conn) == before


def test_alternate_arguments_are_mutually_exclusive():
    with pytest.raises(ValueError):
        identity_triggers("probe", "PartOperations", ("id",), "part_no", alternate_columns=("part_no", "seq"))
