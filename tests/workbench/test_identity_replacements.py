"""Identity preservation for SQLite conflict policies on the two unique-name tables."""

from __future__ import annotations

from dataclasses import replace

import pytest

from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import (
    RESOURCE_CASES,
    SEED_ROWS,
    business_snapshot,
    identity_database,
    insert_row,
    resource_payload,
    table_rows,
)

pytestmark = [
    pytest.mark.parametrize("kind", ("op_type", "resource_team")),
    pytest.mark.parametrize("recursive", (0, 1)),
]


@pytest.fixture
def replacement_case(identity_conn, kind, recursive):
    conn = identity_conn
    conn.execute(f"PRAGMA recursive_triggers = {recursive}")
    assert conn.execute("PRAGMA recursive_triggers").fetchone()[0] == recursive
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    table, (column,) = RESOURCE_CASES[kind]
    source_key = SEED_ROWS[table][column]
    if kind == "op_type":
        # Isolate conflict semantics without disabling foreign keys on the temporary fixture.
        for dependent in ("Machines", "Suppliers"):
            conn.execute(f'UPDATE "{dependent}" SET op_type_id = NULL WHERE op_type_id = ?', (source_key,))
    payload = resource_payload(kind)
    insert_row(conn, table, payload)
    conn.commit()
    repo = WorkbenchIdentityRepository(conn)
    source = repo.find_active(kind, source_key)
    target = repo.find_active(kind, payload[column])
    assert source is not None and target is not None
    assert source.active and target.active and source.ref != target.ref
    assert source.revision == target.revision == 1
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    return conn, table, column, source, target


def _identity_snapshot(conn):
    repo = WorkbenchIdentityRepository(conn)
    return {row[0]: repo.get(row[0]) for row in conn.execute("SELECT ref FROM WorkbenchEntityRefs")}


def _business_rows(conn, table, column):
    return {row[column]: dict(row) for row in conn.execute(f'SELECT * FROM "{table}"')}


def _conflict_updates(column, target_row, conflict):
    updates = {"remark": "candidate-change"}
    if conflict in ("primary_key", "both"):
        updates[column] = target_row[column]
    if conflict in ("unique_name", "both"):
        updates["name"] = target_row["name"]
    return updates


def _update_row(conn, table, column, key, updates, *, policy):
    assignments = ", ".join(f'"{name}" = ?' for name in updates)
    conn.execute(
        f'UPDATE OR {policy} "{table}" SET {assignments} WHERE "{column}" = ?',
        tuple(updates.values()) + (key,),
    )


def test_insert_or_ignore_unique_name_conflict_does_not_touch_existing_refs(replacement_case):
    conn, table, column, source, _ = replacement_case
    payload = dict(_business_rows(conn, table, column)[source.entity_key])
    payload.update({column: source.entity_key + "-ignored", "remark": "ignored-insert"})
    before = business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), conn.total_changes

    insert_row(conn, table, payload, verb="INSERT OR IGNORE")

    assert (business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), conn.total_changes) == before
    assert WorkbenchIdentityRepository(conn).find_active(source.kind, payload[column]) is None


@pytest.mark.parametrize("conflict", ("primary_key", "unique_name", "both"))
def test_update_or_ignore_conflict_does_not_touch_either_ref(replacement_case, conflict):
    conn, table, column, source, target = replacement_case
    rows = _business_rows(conn, table, column)
    updates = _conflict_updates(column, rows[target.entity_key], conflict)
    before = business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), conn.total_changes

    _update_row(conn, table, column, source.entity_key, updates, policy="IGNORE")

    assert (business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), conn.total_changes) == before
    repo = WorkbenchIdentityRepository(conn)
    assert repo.get(source.ref) == source
    assert repo.get(target.ref) == target


@pytest.mark.parametrize("conflict", ("primary_key", "unique_name", "both"))
def test_update_or_replace_keeps_updating_ref_and_retires_displaced_ref(replacement_case, conflict):
    conn, table, column, source, target = replacement_case
    expected_refs = _identity_snapshot(conn)
    expected_rows = _business_rows(conn, table, column)
    updates = _conflict_updates(column, expected_rows[target.entity_key], conflict)
    source_row = expected_rows.pop(source.entity_key)
    expected_rows.pop(target.entity_key)
    source_row.update(updates)
    expected_rows[source_row[column]] = source_row
    expected_refs[source.ref] = replace(source, entity_key=source_row[column], revision=source.revision + 1)
    expected_refs[target.ref] = replace(target, active=False, revision=target.revision + 1)

    _update_row(conn, table, column, source.entity_key, updates, policy="REPLACE")

    assert _identity_snapshot(conn) == expected_refs
    assert _business_rows(conn, table, column) == expected_rows
    repo = WorkbenchIdentityRepository(conn)
    assert repo.find_active(source.kind, source_row[column]) == expected_refs[source.ref]
    vacated_key = source.entity_key if column in updates else target.entity_key
    assert repo.find_active(source.kind, vacated_key) is None
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_insert_or_replace_colliding_with_two_objects_retires_both_refs(replacement_case):
    conn, table, column, source, target = replacement_case
    expected_refs = _identity_snapshot(conn)
    expected_rows = _business_rows(conn, table, column)
    payload = dict(expected_rows[source.entity_key])
    payload.update(name=expected_rows[target.entity_key]["name"], remark="replacement-instance")
    expected_rows.pop(target.entity_key)
    expected_rows[source.entity_key] = payload
    for old in (source, target):
        expected_refs[old.ref] = replace(old, active=False, revision=old.revision + 1)

    insert_row(conn, table, payload, verb="INSERT OR REPLACE")

    repo = WorkbenchIdentityRepository(conn)
    current = repo.find_active(source.kind, source.entity_key)
    assert current is not None and current.active and current.revision == 1
    assert current.ref not in expected_refs
    expected_refs[current.ref] = current
    assert _identity_snapshot(conn) == expected_refs
    assert _business_rows(conn, table, column) == expected_rows
    assert repo.find_active(source.kind, target.entity_key) is None
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_inserting_old_name_after_rename_does_not_retire_renamed_object(replacement_case):
    conn, table, column, source, target = replacement_case
    expected_refs = _identity_snapshot(conn)
    expected_rows = _business_rows(conn, table, column)
    payload = dict(expected_rows[source.entity_key])
    old_name = payload["name"]
    new_name = old_name + "-renamed"
    payload.update({column: source.entity_key + "-reuse-name", "remark": "new-instance"})
    renamed = replace(source, revision=source.revision + 1)
    expected_refs[source.ref] = renamed
    expected_rows[source.entity_key]["name"] = new_name

    conn.execute(f'UPDATE "{table}" SET name = ? WHERE "{column}" = ?', (new_name, source.entity_key))
    assert _identity_snapshot(conn) == expected_refs
    insert_row(conn, table, payload)

    repo = WorkbenchIdentityRepository(conn)
    current = repo.find_active(source.kind, payload[column])
    assert current is not None and current.active and current.revision == 1
    assert current.ref not in expected_refs
    expected_refs[current.ref] = current
    expected_rows[payload[column]] = payload
    assert _identity_snapshot(conn) == expected_refs
    assert _business_rows(conn, table, column) == expected_rows
    assert repo.find_active(source.kind, source.entity_key) == renamed
    assert repo.get(target.ref) == target
