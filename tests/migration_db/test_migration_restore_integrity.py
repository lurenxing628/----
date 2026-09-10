"""Migration rollback must validate the exact payload before touching the database."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pytest

from core.infrastructure import migration_backup as migration_mod
from core.infrastructure import sqlite_integrity as integrity_mod
from core.infrastructure.backup import BackupIntegrityError


def _make_restore_files(tmp_path):
    db_path = tmp_path / "app.db"
    backup_path = tmp_path / "before.db"
    for path, value in ((db_path, "current"), (backup_path, "before")):
        with closing(sqlite3.connect(str(path))) as conn:
            conn.execute("CREATE TABLE Demo (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO Demo (value) VALUES (?)", (value * 1024,))
            conn.commit()
    for suffix in ("-wal", "-shm", "-journal"):
        db_path.with_name(db_path.name + suffix).write_bytes(suffix.encode("ascii") * 32)
    return db_path, backup_path


def _database_state(db_path):
    state = {}
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = db_path.with_name(db_path.name + suffix)
        st = path.stat()
        state[suffix] = (path.read_bytes(), st.st_ino, st.st_mtime_ns, st.st_size)
    return state


def _invalid_payload(payload, corruption):
    if corruption == "empty":
        return b""
    if corruption == "not_sqlite":
        return b"not a sqlite database" * 256
    if corruption == "short_header":
        return payload[:16]
    if corruption == "header_only":
        return payload[:100]
    if corruption == "truncated_byte":
        return payload[:-1]
    if corruption == "truncated_page":
        return payload[: len(payload) // 2]
    page_size = int.from_bytes(payload[16:18], "big")
    if corruption == "missing_page":
        return payload[:-page_size]
    assert corruption == "broken_btree"
    return payload[:page_size] + b"\xff" + payload[page_size + 1 :]


@pytest.mark.parametrize(
    "corruption",
    ["empty", "not_sqlite", "short_header", "header_only", "truncated_byte", "truncated_page", "missing_page", "broken_btree"],
)
def test_invalid_backup_leaves_database_and_all_sidecars_unchanged(tmp_path, monkeypatch, corruption):
    db_path, backup_path = _make_restore_files(tmp_path)
    backup_path.write_bytes(_invalid_payload(backup_path.read_bytes(), corruption))
    original_state = _database_state(db_path)
    target_stat = Mock(wraps=migration_mod.stat_regular_file)
    cleanup = Mock(wraps=migration_mod.cleanup_sqlite_sidecars)
    monkeypatch.setattr(migration_mod, "stat_regular_file", target_stat)
    monkeypatch.setattr(migration_mod, "cleanup_sqlite_sidecars", cleanup)

    with pytest.raises(BackupIntegrityError):
        migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path), retries=1)

    target_stat.assert_not_called()
    cleanup.assert_not_called()
    assert _database_state(db_path) == original_state
    assert not db_path.with_name(db_path.name + ".rollback_tmp").exists()


def test_checks_payload_returned_by_read_not_the_backup_path(tmp_path, monkeypatch):
    db_path, backup_path = _make_restore_files(tmp_path)
    original_state = _database_state(db_path)
    read_payload = Mock(return_value=_invalid_payload(backup_path.read_bytes(), "broken_btree"))
    monkeypatch.setattr(migration_mod, "read_fixed_bytes", read_payload)

    with pytest.raises(BackupIntegrityError):
        migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path))

    read_payload.assert_called_once_with(str(backup_path))
    assert _database_state(db_path) == original_state


def test_restores_validated_bytes_even_if_backup_changes_after_read(tmp_path, monkeypatch):
    db_path, backup_path = _make_restore_files(tmp_path)
    expected_payload = backup_path.read_bytes()
    real_read = migration_mod.read_fixed_bytes

    def read_then_replace_backup(path):
        payload = real_read(path)
        backup_path.write_bytes(b"changed after read")
        return payload

    read_payload = Mock(side_effect=read_then_replace_backup)
    monkeypatch.setattr(migration_mod, "read_fixed_bytes", read_payload)

    migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path))

    read_payload.assert_called_once_with(str(backup_path))
    assert db_path.read_bytes() == expected_payload
    assert backup_path.read_bytes() == b"changed after read"
    assert not db_path.with_name(db_path.name + ".rollback_tmp").exists()
    for suffix in ("-wal", "-shm", "-journal"):
        assert not db_path.with_name(db_path.name + suffix).exists()
    with closing(sqlite3.connect(str(db_path))) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert conn.execute("SELECT value FROM Demo").fetchone() == ("before" * 1024,)


def test_retry_checks_new_payload_before_second_replace(tmp_path, monkeypatch):
    db_path, backup_path = _make_restore_files(tmp_path)
    original_payload = db_path.read_bytes()
    replace_calls = []
    cleanup = Mock(wraps=migration_mod.cleanup_sqlite_sidecars)
    monkeypatch.setattr(migration_mod, "cleanup_sqlite_sidecars", cleanup)

    def locked_replace(source, destination):
        replace_calls.append((source, destination))
        backup_path.write_bytes(b"corrupted between retries")
        raise PermissionError("database file is in use")

    monkeypatch.setattr(migration_mod.os, "replace", locked_replace)
    sleep = Mock()
    monkeypatch.setattr(migration_mod.time, "sleep", sleep)

    with pytest.raises(BackupIntegrityError):
        migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path), retries=3, base_delay_s=0.01)

    assert len(replace_calls) == 1
    assert cleanup.call_count == 1
    sleep.assert_called_once_with(0.01)
    assert db_path.read_bytes() == original_payload
    assert not db_path.with_name(db_path.name + ".rollback_tmp").exists()


def test_migration_runner_reports_integrity_failure_without_changing_database(tmp_path):
    from core.infrastructure.migration_runner import MigrationRollbackError, _rollback_from_backup

    db_path, backup_path = _make_restore_files(tmp_path)
    backup_path.write_bytes(b"bad migration backup")
    original_state = _database_state(db_path)

    with pytest.raises(MigrationRollbackError) as raised:
        _rollback_from_backup(str(db_path), str(backup_path))

    assert isinstance(raised.value.__cause__, BackupIntegrityError)
    assert _database_state(db_path) == original_state


@pytest.mark.parametrize("failure", ["connect", "execute", "fetch", "not_ok", "empty_result"])
def test_validation_failure_is_visible_and_removes_isolated_files(tmp_path, monkeypatch, failure):
    db_path, backup_path = _make_restore_files(tmp_path)
    original_state = _database_state(db_path)
    scratch = tmp_path / "integrity-scratch"
    scratch.mkdir()
    monkeypatch.setattr(integrity_mod.tempfile, "tempdir", str(scratch))
    real_connect = sqlite3.connect
    logger = Mock()
    sleep = Mock()
    monkeypatch.setattr(migration_mod.time, "sleep", sleep)

    class BrokenCursor:
        def fetchall(self):
            if failure == "fetch":
                raise sqlite3.DatabaseError("injected fetch failure")
            return [] if failure == "empty_result" else [("damaged page",)]

    class BrokenConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "PRAGMA integrity_check":
                if failure == "execute":
                    raise sqlite3.DatabaseError("injected execute failure")
                return BrokenCursor()
            return super().execute(sql, *args, **kwargs)

    def connect(database, **kwargs):
        if failure == "connect":
            raise sqlite3.OperationalError("injected connect failure")
        return real_connect(database, factory=BrokenConnection, **kwargs)

    connect_spy = Mock(side_effect=connect)
    monkeypatch.setattr(integrity_mod.sqlite3, "connect", connect_spy)

    with pytest.raises(BackupIntegrityError) as raised:
        migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path), logger=logger)

    if failure in ("connect", "execute", "fetch"):
        assert isinstance(raised.value.__cause__, sqlite3.Error)
    assert logger.error.called
    sleep.assert_not_called()
    assert connect_spy.call_count == 1
    assert _database_state(db_path) == original_state
    assert list(scratch.iterdir()) == []


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
@pytest.mark.parametrize("page_size", [512, 4096, 65536])
def test_valid_backup_is_checked_readonly_in_isolation(tmp_path, monkeypatch, page_size, journal_mode):
    db_path, backup_path = _make_restore_files(tmp_path)
    backup_path.unlink()
    with closing(sqlite3.connect(str(backup_path))) as conn:
        conn.execute(f"PRAGMA page_size = {page_size}")
        assert conn.execute(f"PRAGMA journal_mode = {journal_mode}").fetchone()[0] == journal_mode.lower()
        conn.execute("CREATE TABLE Saved (value TEXT)")
        conn.execute("INSERT INTO Saved VALUES ('valid backup')")
        conn.commit()
    payload = backup_path.read_bytes()
    original_state = _database_state(db_path)
    scratch = tmp_path / "scratch #?%"
    scratch.mkdir()
    monkeypatch.setattr(integrity_mod.tempfile, "tempdir", str(scratch))
    real_connect = sqlite3.connect
    observed = []

    def inspect_connect(database, **kwargs):
        uri = urlsplit(database)
        staged_path = Path(url2pathname(uri.path))
        assert scratch in staged_path.parents
        assert staged_path.read_bytes() == payload
        assert _database_state(db_path) == original_state
        assert uri.query == "mode=ro"
        assert kwargs["uri"] is True
        observed.append(database)
        conn = real_connect(database, **kwargs)
        try:
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                conn.execute("CREATE TABLE MustNotWrite (id INTEGER)")
        except BaseException:
            conn.close()
            raise
        return conn

    monkeypatch.setattr(integrity_mod.sqlite3, "connect", inspect_connect)
    migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path))

    assert len(observed) == 1
    assert db_path.read_bytes() == payload
    assert backup_path.read_bytes() == payload
    assert list(scratch.iterdir()) == []
