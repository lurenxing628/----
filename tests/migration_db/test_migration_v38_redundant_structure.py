"""v38 removes actual duplicate indexes while preserving history and unknown values."""

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.migration_operation_execution_contract import operation_execution_event_contract_issues
from core.infrastructure.migration_state import current_schema_contract_issues
from core.infrastructure.migrations import v38
from core.infrastructure.migrations.v19 import _EVENT_INDEX_SQL, _EVENT_TABLE_SQL

_SCHEMA = Path(__file__).resolve().parents[2] / "schema.sql"


def _old_current_database():
    conn = sqlite3.connect(":memory:")
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    for name, table, columns, unique in v38._DUPLICATE_INDEXES:
        conn.execute("CREATE " + ("UNIQUE " if unique else "") + "INDEX " + name +
                     " ON " + table + "(" + ",".join(columns) + ")")
    conn.execute("UPDATE SchemaVersion SET version=37")
    conn.executemany("INSERT INTO Operators(operator_id,name,status) VALUES(?,?,?)", (
        ("trimmed", "Trimmed", " inactive "), ("unknown", "Unknown", " Legacy HOLD "),
        ("unchanged", "Unchanged", "inactive")))
    conn.executemany("INSERT INTO WorkbenchOperatorProfiles(operator_id,inactive_reason) VALUES(?,?)", (
        ("trimmed", "leave"), ("unknown", "disabled"), ("unchanged", "leave")))
    conn.commit()
    return conn


def test_v38_preserves_reasons_unknown_values_and_unique_keys_without_noop_data_writes():
    conn = _old_current_database()
    try:
        untouched = conn.execute("SELECT ref,revision FROM WorkbenchEntityRefs WHERE kind='operator' AND entity_key='unchanged'").fetchone()
        v38.run(conn)
        assert conn.execute("SELECT operator_id,status FROM Operators ORDER BY operator_id").fetchall() == [
            ("trimmed", "inactive"), ("unchanged", "inactive"), ("unknown", " Legacy HOLD ")]
        assert conn.execute("SELECT operator_id,inactive_reason FROM WorkbenchOperatorProfiles ORDER BY operator_id").fetchall() == [
            ("trimmed", "leave"), ("unchanged", "leave"), ("unknown", "disabled")]
        assert conn.execute("SELECT ref,revision FROM WorkbenchEntityRefs WHERE kind='operator' AND entity_key='unchanged'").fetchone() == untouched
        assert not current_schema_contract_issues(conn)
        for name, table, columns, _unique in v38._DUPLICATE_INDEXES:
            assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone()
            assert any(row[2] and not row[4] and tuple(col[2] for col in conn.execute('PRAGMA index_info("' + row[1] + '")')) == columns
                       for row in conn.execute('PRAGMA index_list("' + table + '")'))
        conn.execute("INSERT INTO OperatorCalendar(operator_id,date) VALUES('trimmed','2026-10-05')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO OperatorCalendar(operator_id,date) VALUES('trimmed','2026-10-05')")
        conn.commit()
        before = list(conn.iterdump())
        changes = conn.total_changes
        v38.run(conn)
        assert conn.total_changes == changes
        assert list(conn.iterdump()) == before
    finally:
        conn.close()


def test_v38_failure_rolls_back_indexes_data_reasons_and_version(monkeypatch):
    conn = _old_current_database()
    try:
        before = list(conn.iterdump())
        repair = v38._repair_whitespace
        def fail_after_cleanup(current):
            repair(current)
            raise RuntimeError("injected after cleanup")
        monkeypatch.setattr(v38, "_repair_whitespace", fail_after_cleanup)
        with pytest.raises(RuntimeError, match="injected"):
            v38.run(conn)
        assert list(conn.iterdump()) == before
        assert conn.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 37
    finally:
        conn.close()


def test_v38_rejects_an_index_with_changed_collation_without_dropping_it():
    conn = _old_current_database()
    try:
        conn.execute("DROP INDEX idx_operator_calendar_operator_date")
        conn.execute("CREATE INDEX idx_operator_calendar_operator_date ON OperatorCalendar(operator_id COLLATE NOCASE,date)")
        conn.commit()
        before = list(conn.iterdump())
        with pytest.raises(RuntimeError, match="different key semantics"):
            v38.run(conn)
        assert list(conn.iterdump()) == before
    finally:
        conn.close()


def test_current_contract_requires_real_revision_uniqueness_and_shares_structure():
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        traced = []
        conn.set_trace_callback(traced.append)
        assert not current_schema_contract_issues(conn)
        conn.set_trace_callback(None)
        normalized = [" ".join(sql.lower().split()) for sql in traced]
        assert normalized.count("select type, name, tbl_name, sql from sqlite_master") == 1
        assert sum(sql.startswith('pragma table_info') and 'operationexecutionevents' in sql for sql in normalized) == 1
        assert sum(sql.startswith('pragma foreign_key_list') and 'operationexecutionevents' in sql for sql in normalized) == 1
        conn.execute("DROP TABLE OperationExecutionEvents")
        conn.execute(_EVENT_TABLE_SQL.replace(
            "UNIQUE(schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role, previous_state_revision),", ""))
        for sql in _EVENT_INDEX_SQL:
            if "idx_operation_execution_events_op_revision_unique" not in sql:
                conn.execute(sql)
        assert any("revision identity must be unique" in issue for issue in operation_execution_event_contract_issues(conn))
    finally:
        conn.close()
