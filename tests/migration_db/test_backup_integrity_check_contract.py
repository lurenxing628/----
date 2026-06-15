"""回归测试：BackupManager.backup() 完整性校验的 loud 契约（R32/O27 收口）——integrity_check 执行本身抛异常（连校验都跑不起来的库不算可信备份）必须 raise RuntimeError 且不升正式备份、不残留 .tmp；fetchall 抛异常同语义；校验跑通但结果≠ok 仍 raise（既有行为回归，防 else 分支被改弱）；校验通过的 happy path 照常生成备份（防误伤）。绝不允许改回「warning 后照样 os.replace 升正式」的静默放行。"""

from __future__ import annotations

import os
import sqlite3
from urllib.parse import unquote

import core.infrastructure.backup as backup_mod
from core.infrastructure.backup import BackupManager


class _ExecuteBoomConnection(sqlite3.Connection):
    """integrity_check 执行即抛错的连接：模拟「校验跑不起来」（如 disk image malformed）。"""

    def execute(self, sql, *args, **kwargs):  # type: ignore[override]
        if "integrity_check" in str(sql).lower():
            raise sqlite3.OperationalError("database disk image malformed")
        return super().execute(sql, *args, **kwargs)


class _FetchBoomCursor:
    def fetchall(self):
        raise sqlite3.OperationalError("fetchall boom")


class _FetchBoomConnection(sqlite3.Connection):
    """integrity_check 的 fetchall 阶段抛错。"""

    def execute(self, sql, *args, **kwargs):  # type: ignore[override]
        if "integrity_check" in str(sql).lower():
            return _FetchBoomCursor()
        return super().execute(sql, *args, **kwargs)


class _CorruptedRowsCursor:
    def fetchall(self):
        return [("corrupted page 1",)]


class _NotOkConnection(sqlite3.Connection):
    """integrity_check 跑通但结果≠ok：触发 else 分支既有 raise。"""

    def execute(self, sql, *args, **kwargs):  # type: ignore[override]
        if "integrity_check" in str(sql).lower():
            return _CorruptedRowsCursor()
        return super().execute(sql, *args, **kwargs)


def _make_manager(tmp_path):
    tmpdir = str(tmp_path)
    db_path = os.path.join(tmpdir, "aps_test.db")
    backup_dir = os.path.join(tmpdir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE Demo (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO Demo (name) VALUES (?)", ("seed",))
        conn.commit()
    finally:
        conn.close()
    return BackupManager(db_path=db_path, backup_dir=backup_dir, keep_days=7, logger=None), backup_dir


def _sqlite_uri_database_path(database) -> str:
    text = os.fspath(database)
    if not text.startswith("file:"):
        return text
    return unquote(text[5:].split("?", 1)[0])


def _patch_dest_factory(monkeypatch, factory):
    """只对 .tmp 目标连接（备份校验侧）注入工厂，源库与维护窗连接保持原生。"""
    real_connect = sqlite3.connect

    def fake_connect(path, *args, **kwargs):
        if _sqlite_uri_database_path(path).endswith(".tmp"):
            kwargs.setdefault("factory", factory)
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(backup_mod.sqlite3, "connect", fake_connect)


def _assert_no_artifacts(backup_dir: str) -> None:
    leftovers = sorted(os.listdir(backup_dir))
    assert leftovers == [], f"raise 后不得残留正式备份或 .tmp 半成品：{leftovers!r}"


def test_backup_raises_when_integrity_check_execution_fails(tmp_path, monkeypatch) -> None:
    manager, backup_dir = _make_manager(tmp_path)
    _patch_dest_factory(monkeypatch, _ExecuteBoomConnection)
    try:
        manager.backup(suffix="manual")
    except RuntimeError as exc:
        assert "完整性检查执行失败" in str(exc), f"报错文案应指明校验执行失败：{exc}"
    else:
        raise AssertionError("integrity_check 执行抛错时 backup() 必须 raise，不得静默升正式备份")
    _assert_no_artifacts(backup_dir)


def test_backup_raises_when_integrity_fetchall_fails(tmp_path, monkeypatch) -> None:
    manager, backup_dir = _make_manager(tmp_path)
    _patch_dest_factory(monkeypatch, _FetchBoomConnection)
    try:
        manager.backup(suffix="manual")
    except RuntimeError as exc:
        assert "完整性检查执行失败" in str(exc), f"报错文案应指明校验执行失败：{exc}"
    else:
        raise AssertionError("fetchall 抛错同属校验跑不起来，backup() 必须 raise")
    _assert_no_artifacts(backup_dir)


def test_backup_raises_when_integrity_result_not_ok(tmp_path, monkeypatch) -> None:
    manager, backup_dir = _make_manager(tmp_path)
    _patch_dest_factory(monkeypatch, _NotOkConnection)
    try:
        manager.backup(suffix="manual")
    except RuntimeError as exc:
        assert "完整性检查" in str(exc), f"≠ok 既有 raise 行为不得改弱：{exc}"
    else:
        raise AssertionError("integrity_check 结果≠ok 时 backup() 必须 raise（既有行为回归）")
    _assert_no_artifacts(backup_dir)


def test_backup_happy_path_still_produces_backup(tmp_path) -> None:
    manager, backup_dir = _make_manager(tmp_path)
    backup_path = manager.backup(suffix="manual")
    assert os.path.exists(backup_path), f"校验通过时应正常生成备份：{backup_path}"
    assert not os.path.exists(backup_path + ".tmp"), "正式备份生成后不得残留 .tmp"
    assert os.path.dirname(backup_path) == backup_dir
