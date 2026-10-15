"""数据库路径只准备一次，正常连接和首次入口拒绝行为保持一致。"""

from __future__ import annotations

import datetime
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest

from core.infrastructure import database
from core.infrastructure.safe_files import UnsafeFixedFileError


@contextmanager
def _count_path_preparation(monkeypatch, target: Path):
    counts = {"parent_lstat": 0, "target_lstat": 0, "other_lstat": 0, "makedirs": 0}
    original_lstat = os.lstat
    original_makedirs = os.makedirs

    def counted_lstat(path, *args, **kwargs):
        actual = os.path.abspath(os.fspath(path))
        if actual == str(target.parent):
            key = "parent_lstat"
        elif actual == str(target):
            key = "target_lstat"
        else:
            key = "other_lstat"
        counts[key] += 1
        return original_lstat(path, *args, **kwargs)

    def counted_makedirs(path, *args, **kwargs):
        counts["makedirs"] += 1
        return original_makedirs(path, *args, **kwargs)

    with monkeypatch.context() as scope:
        scope.setattr(os, "lstat", counted_lstat)
        scope.setattr(os, "makedirs", counted_makedirs)
        yield counts


def test_existing_database_prepared_once_preserves_connection_behavior(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "existing.db"
    original = sqlite3.connect(str(target))
    try:
        original.executescript(
            "CREATE TABLE Dates (day DATE);"
            "INSERT INTO Dates VALUES ('2026-10-14'), ('2026-02-30');"
        )
    finally:
        original.close()

    with _count_path_preparation(monkeypatch, target) as counts:
        conn = database.get_connection(str(target))
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            rows = conn.execute("SELECT day FROM Dates ORDER BY rowid").fetchall()
            assert isinstance(rows[0], sqlite3.Row)
            assert rows[0]["day"] == datetime.date(2026, 10, 14)
            assert rows[1]["day"] == "2026-02-30"
        finally:
            conn.close()
    assert counts == {"parent_lstat": 1, "target_lstat": 1, "other_lstat": 0, "makedirs": 0}


def test_fresh_relative_and_memory_database_connections(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    nested = tmp_path / "fresh" / "nested" / "app.db"
    for target in (str(nested), "relative.db", ":memory:"):
        conn = database.get_connection(target)
        try:
            conn.execute("CREATE TABLE ValuesForConnection (value TEXT)")
            conn.execute("INSERT INTO ValuesForConnection VALUES ('stored')")
            conn.commit()
            assert conn.execute("SELECT value FROM ValuesForConnection").fetchone()["value"] == "stored"
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()
    assert nested.is_file()
    reopened = database.get_connection("relative.db")
    try:
        assert reopened.execute("SELECT value FROM ValuesForConnection").fetchone()["value"] == "stored"
    finally:
        reopened.close()


def test_sqlite_connect_error_is_preserved_without_rechecking_path(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "existing.db"
    target.touch()
    failure = sqlite3.OperationalError("unable to open database file")

    def fail_connect(*args, **kwargs):
        assert kwargs["uri"] is True
        assert args[0].endswith("?mode=rw")
        raise failure

    monkeypatch.setattr(database.sqlite3, "connect", fail_connect)
    with _count_path_preparation(monkeypatch, target) as counts:
        with pytest.raises(sqlite3.OperationalError) as caught:
            database.get_connection(str(target))
    assert caught.value is failure
    assert counts == {"parent_lstat": 1, "target_lstat": 1, "other_lstat": 0, "makedirs": 0}


def test_database_first_entry_rejects_symlink_and_nonregular_targets(tmp_path: Path) -> None:
    regular = tmp_path / "regular.db"
    regular.touch()
    alias = tmp_path / "alias.db"
    if os.name != "nt":
        alias.symlink_to(regular)
        with pytest.raises(UnsafeFixedFileError, match="软链接固定文件"):
            database.get_connection(str(alias))
    occupied = tmp_path / "directory.db"
    occupied.mkdir()
    with pytest.raises(UnsafeFixedFileError, match="非普通固定文件"):
        database.get_connection(str(occupied))
