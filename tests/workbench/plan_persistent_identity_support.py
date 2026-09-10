"""CP-owned history and exact write assertions for test_plan_persistent_identity."""

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from core.infrastructure.migration_state import get_schema_version, set_schema_version
from core.infrastructure.workbench_plan_identity_schema import contract_issues
from core.models.workbench_template_lineage import OPERATION_COLUMNS
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.plan_identity_support import all_refs, seed_plans, table_snapshot

_V26_SHA256 = "3b1565dffc6f35c6e929d0d96a9df27377865b885132ad57ffeb05e435bc2a6c"
_EVENTS = "WorkbenchTemplateLineageEvents"
_NOW = "SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')"


def _schema_snapshot(conn):
    return [tuple(row) for row in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name,type")]


@pytest.fixture(name="v26_identity_case")
def v26_identity_fixture(mem_conn):
    """Damage a real pre-lineage database, with foreign keys still enforced."""
    conn = mem_conn
    assert not _schema_snapshot(conn)
    source = (Path(__file__).parent / "fixtures" / "schema-v26.sql").read_bytes()
    assert hashlib.sha256(source).hexdigest() == _V26_SHA256
    conn.executescript(source.decode("utf-8"))
    set_schema_version(conn, 26)
    ddl = _schema_snapshot(conn)
    assert not conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'WorkbenchTemplateLineage%' "
                            "OR name LIKE 'WorkbenchTrial%'").fetchall()
    ids = seed_plans(conn)
    assert _schema_snapshot(conn) == ddl
    assert get_schema_version(conn) == 26 and not contract_issues(conn)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    return conn, WorkbenchPlanIdentityRepository(conn), ids


def _assert_exact_tables(actual, expected):
    assert actual == expected
    # SQLite INTEGER 1 and REAL 1.0 compare equal in Python; storage types must not drift.
    assert {name: [tuple(type(value) for value in row) for row in rows] for name, rows in actual.items()} == {
        name: [tuple(type(value) for value in row) for row in rows] for name, rows in expected.items()}


def assert_ignored_operation_conflicts(conn, repo, ids):
    before, ddl, refs = table_snapshot(conn), _schema_snapshot(conn), all_refs(conn)
    operation = dict(conn.execute("SELECT * FROM BatchOperations WHERE id=?", (ids[0],)).fetchone())
    batch = conn.execute("SELECT part_no,quantity FROM Batches WHERE batch_id=?", (operation["batch_id"],)).fetchone()
    sequences = dict(before["sqlite_sequence"])
    event_id = sequences[_EVENTS] + 1
    expected_event = {name: operation[name] for name in OPERATION_COLUMNS}
    for kind, key in (("batch", operation["batch_id"]), ("part", batch["part_no"])):
        expected_event[kind + "_ref"] = conn.execute(
            "SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, key)).fetchone()[0]
    expected_event.update(event_id=event_id, operation_ref=repo.get_operation_refs([ids[0]])[ids[0]],
                          event_type="updated", affects_calibration=0, reason=None, id=ids[1], quantity=batch["quantity"])

    conn.execute("INSERT OR IGNORE INTO BatchOperations(id, op_code, batch_id, seq, op_type_name) "
                 "VALUES (?, 'ignored', 'CAT-B', 999, 'ignored')", (ids[0],))
    # This explicit id is below the existing sequence, so even sqlite_sequence stays exact.
    _assert_exact_tables(table_snapshot(conn), before)
    started = conn.execute(_NOW).fetchone()[0]
    conn.execute("UPDATE OR IGNORE BatchOperations SET id = ? WHERE id = ?", (ids[1], ids[0]))
    finished = conn.execute(_NOW).fetchone()[0]

    # Frozen v27 records the attempted NEW state in BEFORE UPDATE, even if the row is ignored.
    events = conn.execute("SELECT * FROM WorkbenchTemplateLineageEvents WHERE event_id>=? ORDER BY event_id", (event_id,)).fetchall()
    assert len(events) == 1
    event = dict(events[0])
    stamp = event["recorded_at_utc"]
    datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    assert started <= stamp <= finished
    expected_event["recorded_at_utc"] = stamp
    assert set(event) == set(expected_event)
    expected = {name: list(rows) for name, rows in before.items()}
    expected[_EVENTS] = sorted(before[_EVENTS] + [tuple(expected_event[name] for name in events[0].keys())], key=repr)
    sequences[_EVENTS] = event_id
    expected["sqlite_sequence"] = sorted(sequences.items(), key=repr)
    _assert_exact_tables(table_snapshot(conn), expected)
    assert _schema_snapshot(conn) == ddl and all_refs(conn) == refs
    conn.rollback()
    _assert_exact_tables(table_snapshot(conn), before)
    assert _schema_snapshot(conn) == ddl and all_refs(conn) == refs
