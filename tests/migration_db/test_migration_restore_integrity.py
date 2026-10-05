"""损坏备份保留原库，恢复使用已读取并验证的数据。"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from unittest.mock import Mock

import pytest

from core.infrastructure import migration_backup as migration_mod
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


@pytest.mark.parametrize('corruption', ["broken_btree"])
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
