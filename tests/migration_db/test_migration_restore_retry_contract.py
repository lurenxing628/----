"""Keep migration rollback's existing bounded Windows file-lock retry contract."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from unittest.mock import Mock, call

import pytest

from core.infrastructure import migration_backup as migration_mod


@pytest.fixture
def restore_files(tmp_path):
    db_path = tmp_path / "app.db"
    backup_path = tmp_path / "backup.db"
    for path, value in ((db_path, "current"), (backup_path, "before")):
        with closing(sqlite3.connect(str(path))) as conn:
            conn.execute("CREATE TABLE Demo (value TEXT)")
            conn.execute("INSERT INTO Demo VALUES (?)", (value,))
            conn.commit()
    return db_path, backup_path


@pytest.mark.parametrize("stage", ["read", "write", "replace", "sidecars"])
@pytest.mark.parametrize("winerror", [None, 5, 32, 33])
def test_temporary_file_lock_retries_and_restores(restore_files, monkeypatch, stage, winerror):
    db_path, backup_path = restore_files
    payload = backup_path.read_bytes()
    error = PermissionError("in use") if winerror is None else OSError("Windows file lock")
    if winerror is not None:
        error.winerror = winerror
    owner, name = {
        "read": (migration_mod, "read_fixed_bytes"),
        "write": (migration_mod, "write_fixed_bytes"),
        "replace": (migration_mod.os, "replace"),
        "sidecars": (migration_mod, "cleanup_sqlite_sidecars"),
    }[stage]
    real_operation = getattr(owner, name)
    attempts = []

    def locked_twice(*args, **kwargs):
        attempts.append(args)
        if len(attempts) < 3:
            raise error
        return real_operation(*args, **kwargs)

    monkeypatch.setattr(owner, name, locked_twice)
    sleep = Mock()
    logger = Mock()
    monkeypatch.setattr(migration_mod.time, "sleep", sleep)

    migration_mod.restore_db_file_from_backup(
        str(backup_path), str(db_path), retries=3, base_delay_s=0.01, logger=logger,
    )

    assert len(attempts) == (4 if stage == "sidecars" else 3)
    assert sleep.call_args_list == [call(0.01), call(0.02)]
    assert logger.warning.call_count == 1
    assert db_path.read_bytes() == payload
    assert not db_path.with_name(db_path.name + ".rollback_tmp").exists()


@pytest.mark.parametrize("retries, expected_attempts", [(None, 1), (0, 1), (-2, 1), (3, 3)])
def test_exhausted_lock_retries_raise_original_error(restore_files, monkeypatch, retries, expected_attempts):
    db_path, backup_path = restore_files
    original_payload = db_path.read_bytes()
    error = PermissionError("still in use")
    replace = Mock(side_effect=error)
    sleep = Mock()
    monkeypatch.setattr(migration_mod.os, "replace", replace)
    monkeypatch.setattr(migration_mod.time, "sleep", sleep)

    with pytest.raises(PermissionError) as raised:
        migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path), retries=retries, base_delay_s=0.01)

    assert raised.value is error
    assert replace.call_count == expected_attempts
    assert sleep.call_args_list == [call(0.01 * n) for n in range(1, expected_attempts)]
    assert db_path.read_bytes() == original_payload
    assert not db_path.with_name(db_path.name + ".rollback_tmp").exists()


def test_default_retry_count_is_six(restore_files, monkeypatch):
    db_path, backup_path = restore_files
    read = Mock(side_effect=PermissionError("backup file is in use"))
    sleep = Mock()
    monkeypatch.setattr(migration_mod, "read_fixed_bytes", read)
    monkeypatch.setattr(migration_mod.time, "sleep", sleep)

    with pytest.raises(PermissionError):
        migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path))

    assert read.call_count == 6
    assert sleep.call_args_list == [call(0.2 * n) for n in range(1, 6)]


def test_non_lock_error_is_not_retried(restore_files, monkeypatch):
    db_path, backup_path = restore_files
    original_payload = db_path.read_bytes()
    error = OSError("disk I/O error")
    replace = Mock(side_effect=error)
    sleep = Mock()
    monkeypatch.setattr(migration_mod.os, "replace", replace)
    monkeypatch.setattr(migration_mod.time, "sleep", sleep)

    with pytest.raises(OSError) as raised:
        migration_mod.restore_db_file_from_backup(str(backup_path), str(db_path))

    assert raised.value is error
    assert replace.call_count == 1
    sleep.assert_not_called()
    assert db_path.read_bytes() == original_payload
    assert not db_path.with_name(db_path.name + ".rollback_tmp").exists()
