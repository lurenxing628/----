"""Frozen v12/v13/v16 catalogs and lossless historical migration fixtures."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

# Each schema.sql is byte-for-byte Git content. The matching migration_state.py
# declares this version at line 8; schema.sql itself uses the new-file marker 0.
FROZEN_SCHEMAS = {
    12: ("b83407fe4c4ae87e1b87c6c23cef84680d23b101",
         "362193fa1d1b4f39851ebd4f75286378bd3787b9e097562e7260e5abbd0104a6"),
    13: ("92e8317761752922cf33faa33f527590f523094c",
         "e1ae4d6b94f43cdab394f08dc0531b83c23e5e75f013e76946b5dfb3b7c34f6f"),
    16: ("a0cfa3e758b8bfdaacf27202aa2e3f9b49eacc30",
         "da5f16211003bb8d27a53db5e63611a034b6e108c2eba529b898f2863ad0a66d"),
}
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_SQL_SPACING = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\s+")


def _quoted(name):
    return '"' + name.replace('"', '""') + '"'


def schema_catalog(conn):
    """Compare complete SQLite objects, columns and foreign keys, not a version label."""
    objects = conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()
    tables = [row[1] for row in objects if row[0] == "table"]
    # Ignore layout differences from the existing scenario reconstruction, not literals.
    normalized = lambda sql: _SQL_SPACING.sub(
        lambda match: " " if match.group(0).isspace() else match.group(0), sql.strip()
    ) if sql is not None else None
    return {
        "objects": tuple((kind, name, table, normalized(sql)) for kind, name, table, sql in objects),
        "columns": {name: tuple(tuple(row) for row in conn.execute("PRAGMA table_info(" + _quoted(name) + ")"))
                    for name in tables},
        "foreign_keys": {name: tuple(tuple(row) for row in conn.execute("PRAGMA foreign_key_list(" + _quoted(name) + ")"))
                         for name in tables},
    }


def _frozen_sql(version):
    if type(version) is not int or version not in FROZEN_SCHEMAS:
        raise AssertionError("Unsupported frozen fixture version")
    raw = (_FIXTURES / ("schema_v" + str(version) + ".sql")).read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_SCHEMAS[version][1]:
        raise AssertionError("Frozen historical DDL hash mismatch: v" + str(version))
    return raw.decode("utf-8")


@contextmanager
def _frozen_database(version):
    with closing(sqlite3.connect(":memory:")) as legacy:
        legacy.executescript(_frozen_sql(version))
        assert legacy.execute("SELECT id, version FROM SchemaVersion").fetchall() == [(1, 0)]
        legacy.execute("UPDATE SchemaVersion SET version = ? WHERE id = 1", (version,))
        legacy.commit()
        yield legacy


def assert_frozen_catalog(conn, *, version):
    with _frozen_database(version) as legacy:
        assert schema_catalog(conn) == schema_catalog(legacy), f"Not the frozen v{version} catalog"
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()[0] == version
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def load_frozen_schema(conn, *, version):
    """Initialize only a genuinely empty fixture connection with historical DDL."""
    if conn.in_transaction or conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
        raise AssertionError("Historical fixture initialization requires an empty database")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise AssertionError("Historical fixture requires foreign_keys=ON")
    with _frozen_database(version) as legacy:
        legacy.backup(conn)
    assert_frozen_catalog(conn, version=version)


def _initial_rows(conn):
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    return {name: [tuple(row) for row in conn.execute(
        # Only this fresh-file timestamp varies; all business rows and clock seeds are exact.
        "SELECT id, version FROM SchemaVersion" if name == "SchemaVersion" else "SELECT * FROM " + _quoted(name)
    )] for name in tables}


def strip_later_schema(conn, *, version: int) -> None:
    """Replace only the callers' pristine bootstrap fixture; never strip a damaged DB."""
    if version not in (13, 16) or conn.in_transaction:
        raise AssertionError("Expected an unseeded v13/v16 fixture setup")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise AssertionError("Historical fixture requires foreign_keys=ON")
    with closing(sqlite3.connect(":memory:")) as pristine:
        # Current DDL is only an admission guard for the existing caller, never history.
        pristine.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
        if schema_catalog(conn) != schema_catalog(pristine) or _initial_rows(conn) != _initial_rows(pristine):
            raise AssertionError("Refuse non-pristine current fixture: catalog or rows differ")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise AssertionError("Refuse foreign-key-invalid fixture")
    with _frozen_database(version) as legacy:
        legacy.backup(conn)
    assert_frozen_catalog(conn, version=version)


def seed_legacy_scenario(conn, *, version: int) -> None:
    """Seed old columns directly, without calling services that require the new schema."""
    assert_frozen_catalog(conn, version=version)
    conn.executescript(
        """
        INSERT INTO ScheduleAdjustmentDraft(draft_id, base_version, base_plan_role, status, created_by, change_count)
        VALUES ('legacy-draft', 5, 'adopted', 'saved_scenario', 'legacy-planner', 1);
        INSERT INTO ScheduleAdjustmentChange(
            draft_id, schedule_id, op_id, change_type, from_start, from_end, to_start, to_end, validation_status
        ) VALUES (
            'legacy-draft', 90, 30, 'move_time', '2026-05-04 08:00:00', '2026-05-04 09:00:00',
            '2026-05-04 11:00:00', '2026-05-04 12:00:00', 'valid'
        );
        INSERT INTO ScheduleAdjustmentScenario(
            scenario_id, source_draft_id, base_version, base_plan_role, base_source_table,
            scenario_name, validation_status, issues_json, row_count, created_by
        ) VALUES (
            'legacy-scenario', 'legacy-draft', 5, 'adopted', 'schedule',
            'retained simulation', 'valid', '[]', 3, 'legacy-planner'
        );
        INSERT INTO ScheduleAdjustmentScenarioRow(
            scenario_id, source_table, source_row_id, op_id, machine_id, operator_id,
            start_time, end_time, lock_status, is_changed
        ) SELECT 'legacy-scenario', 'schedule', id, op_id, machine_id, operator_id,
                 CASE WHEN op_id = 30 THEN '2026-05-04 11:00:00' ELSE start_time END,
                 CASE WHEN op_id = 30 THEN '2026-05-04 12:00:00' ELSE end_time END,
                 lock_status, CASE WHEN op_id = 30 THEN 'yes' ELSE 'no' END
          FROM Schedule WHERE version = 5;
        """
    )
    if version == 16:
        conn.executescript(
            """
            INSERT INTO ScheduleVersionSeq(version) VALUES (6);
            INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (6, 'manual', 2, 3, 'success', '{"source":"gantt_scenario_publish"}', 'legacy-publisher');
            INSERT INTO Schedule(op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            SELECT op_id, machine_id, operator_id, start_time, end_time, lock_status, 6
            FROM ScheduleAdjustmentScenarioRow WHERE scenario_id = 'legacy-scenario';
            UPDATE ScheduleAdjustmentScenario
            SET status = 'published', published_version = 6, published_by = 'legacy-publisher',
                published_reason = 'retained approval', published_at = '2026-05-04 12:30:00';
            UPDATE ScheduleAdjustmentDraft SET status = 'published', reason = 'retained approval';
            INSERT INTO OperationExecutionEvents(
                id, schedule_version, schedule_id, op_id, batch_id, event_type, reported_status, event_time,
                actual_machine_id, actual_operator_id, quantity_done, created_by,
                idempotency_key, request_fingerprint, previous_state_revision
            ) VALUES (
                7, 5, 70, 10, 'B1', 'start', 'processing', '2026-05-04 08:30:00',
                'M1', 'O1', 0, 'legacy-operator', 'legacy-start', 'legacy-fingerprint', '10:0:0'
            );
            """
        )
    assert conn.execute("SELECT COUNT(*) FROM ScheduleAdjustmentScenarioRow").fetchone()[0] == 3
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.commit()


def snapshot_legacy_business_data(conn) -> dict:
    version = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()[0]
    assert_frozen_catalog(conn, version=version)
    tables = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name != 'SchemaVersion'"
    )]
    return {
        table: {
            "columns": tuple(row[1] for row in conn.execute('PRAGMA table_info("' + table + '")')),
            "rows": [tuple(row) for row in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')],
        }
        for table in tables
    }


def assert_legacy_business_data_preserved(conn, before: dict) -> None:
    for table, snapshot in before.items():
        columns = ", ".join('"' + column + '"' for column in snapshot["columns"])
        rows = [tuple(row) for row in conn.execute('SELECT ' + columns + ' FROM "' + table + '" ORDER BY rowid')]
        assert rows == snapshot["rows"], table
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
