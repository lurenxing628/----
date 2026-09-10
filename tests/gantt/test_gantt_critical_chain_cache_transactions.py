"""Transactional visibility and a single read snapshot for identity/computation."""

from __future__ import annotations

import sqlite3

import pytest

from tests.gantt.gantt_critical_chain_cache_support import SOURCES, CachePlanDB, cache_db, reset_cache


@pytest.mark.parametrize("source", SOURCES)
def test_uncommitted_writes_and_savepoint_rollback_do_not_poison_shared_cache(monkeypatch, tmp_path, source):
    reset_cache(monkeypatch)
    path = tmp_path / "transaction.db"
    with cache_db(source, path) as case:
        observer_conn = sqlite3.connect(str(path))
        observer_conn.row_factory = sqlite3.Row
        try:
            observer = CachePlanDB(observer_conn, source)
            assert case.read()["ids"] == ["A", "B"]
            case.conn.execute("BEGIN")
            case.conn.execute("SAVEPOINT caller_owned")
            case.conn.execute("UPDATE " + case.table + " SET machine_id = 'M2' WHERE op_id = 2")
            assert case.read()["ids"] == ["B"]
            assert case.conn.in_transaction is True
            assert observer.read()["ids"] == ["A", "B"]
            case.conn.execute("ROLLBACK TO caller_owned")
            assert case.read()["ids"] == ["A", "B"]
            case.conn.execute("RELEASE caller_owned")
            assert case.conn.in_transaction is True
            case.conn.execute("UPDATE " + case.table + " SET machine_id = 'M2' WHERE op_id = 2")
            assert case.read()["ids"] == ["B"]
            case.conn.commit()
            assert observer.read()["ids"] == ["B"]
            assert observer_conn.in_transaction is False
        finally:
            observer_conn.close()


@pytest.mark.parametrize("source", SOURCES)
def test_existing_read_transaction_keeps_snapshot_until_rollback(monkeypatch, tmp_path, source):
    reset_cache(monkeypatch)
    path = tmp_path / "wal.db"
    with cache_db(source, path) as case:
        case.conn.execute("PRAGMA journal_mode = WAL")
        writer = sqlite3.connect(str(path))
        try:
            case.conn.execute("BEGIN")
            assert case.read()["ids"] == ["A", "B"]
            writer.execute("UPDATE " + case.table + " SET machine_id = 'M2' WHERE op_id = 2")
            writer.commit()
            # Respect the caller's snapshot; do not force a commit for freshness.
            assert case.read()["ids"] == ["A", "B"]
            assert case.conn.in_transaction is True
            case.conn.rollback()
            current = case.read()
            assert current["ids"] == ["B"]
            assert current["cache_hit"] is False
            assert case.conn.in_transaction is False
        finally:
            writer.close()


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("warm", [False, True])
def test_write_between_fingerprint_and_compute_cannot_mix_snapshots(monkeypatch, tmp_path, source, warm):
    reset_cache(monkeypatch)
    path = tmp_path / "between.db"
    with cache_db(source, path) as case:
        case.conn.execute("PRAGMA journal_mode = WAL")
        writer = sqlite3.connect(str(path))
        original = case.provider._plan_rows_fingerprint
        try:
            if warm:
                case.read()

            def fingerprint_then_write(snapshot):
                fingerprint = original(snapshot)
                writer.execute("UPDATE " + case.table + " SET machine_id = 'M2' WHERE op_id = 2")
                writer.execute("UPDATE BatchOperations SET op_code = 'B-new' WHERE id = 2")
                writer.commit()
                return fingerprint

            monkeypatch.setattr(case.provider, "_plan_rows_fingerprint", fingerprint_then_write)
            old = case.read()
            assert old["ids"] == ["A", "B"]
            assert old["cache_hit"] is warm
            monkeypatch.setattr(case.provider, "_plan_rows_fingerprint", original)
            current = case.read()
            assert current["ids"] == ["B-new"]
            assert current["cache_hit"] is False
            writer.execute("UPDATE " + case.table + " SET machine_id = 'M1' WHERE op_id = 2")
            writer.execute("UPDATE BatchOperations SET op_code = 'B' WHERE id = 2")
            writer.commit()
            assert case.read()["ids"] == ["A", "B"]
        finally:
            writer.close()


class _ReadHookConnection(sqlite3.Connection):
    after_first_row = None

    def execute(self, sql, parameters=()):
        cursor = super().execute(sql, parameters)
        if self.after_first_row is None or "LEFT JOIN BatchOperations" not in sql:
            return cursor
        hook = self.after_first_row
        self.after_first_row = None

        class Cursor:
            def fetchall(self):
                first = cursor.fetchone()
                hook()
                return ([first] if first is not None else []) + cursor.fetchall()

        return Cursor()


@pytest.mark.parametrize("source", SOURCES)
def test_writer_commit_during_fetch_keeps_joined_rows_consistent(monkeypatch, tmp_path, source):
    reset_cache(monkeypatch)
    path = tmp_path / "fetch.db"
    with cache_db(source, path) as case:
        case.conn.execute("PRAGMA journal_mode = WAL")
        reader_conn = sqlite3.connect(str(path), factory=_ReadHookConnection)
        reader_conn.row_factory = sqlite3.Row
        try:
            reader = CachePlanDB(reader_conn, source)

            def write():
                case.conn.execute("UPDATE " + case.table + " SET machine_id = 'M2' WHERE op_id = 2")
                case.conn.execute("UPDATE BatchOperations SET op_code = 'B-new' WHERE id = 2")
                case.conn.commit()

            reader_conn.after_first_row = write
            assert reader.read()["ids"] == ["A", "B"]
            current = reader.read()
            assert current["cache_hit"] is False
            assert current["ids"] == ["B-new"]
        finally:
            reader_conn.close()


@pytest.mark.parametrize("source", SOURCES)
def test_restore_reopen_same_file_path_does_not_reuse_old_content(monkeypatch, tmp_path, source):
    reset_cache(monkeypatch)
    path = tmp_path / "restored.db"
    with cache_db(source, path, seed=False) as case:
        snapshot = sqlite3.connect(":memory:")
        restored_conn = None
        try:
            case.conn.backup(snapshot)
            case.seed_rows()
            assert case.read()["ids"] == ["A", "B"]
            before = case.old_aggregate()
            scope = case.provider._database_scope()
            case.conn.close()
            restored_conn = sqlite3.connect(str(path))
            restored_conn.row_factory = sqlite3.Row
            snapshot.backup(restored_conn)
            restored = CachePlanDB(restored_conn, source)
            restored.seed_rows(machine_b="M2")
            assert restored.provider._database_scope() == scope
            assert restored.old_aggregate() == before
            result = restored.read()
            assert result["cache_hit"] is False
            assert result["ids"] == ["B"]
        finally:
            if restored_conn is not None:
                restored_conn.close()
            snapshot.close()


@pytest.mark.parametrize("source", SOURCES)
def test_read_failure_leaves_callers_pending_changes_and_savepoint_intact(monkeypatch, source):
    reset_cache(monkeypatch)
    with cache_db(source) as case:
        case.conn.execute("BEGIN")
        case.conn.execute("UPDATE " + case.table + " SET machine_id = 'M2' WHERE op_id = 2")
        case.conn.execute("SAVEPOINT caller_owned")
        case.conn.execute("ALTER TABLE BatchOperations RENAME TO HiddenOperations")
        assert case.read()["available"] is False
        assert case.conn.in_transaction is True
        case.conn.execute("ROLLBACK TO caller_owned")
        assert case.read()["ids"] == ["B"]
        case.conn.rollback()
        assert case.read()["ids"] == ["A", "B"]
