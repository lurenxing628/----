"""便携运行使用本地目录，移动目录后业务数据仍可读取。"""
from __future__ import annotations

import sqlite3
import sys
from contextlib import closing

import pytest
from flask import Flask

from web.bootstrap import factory, launcher, launcher_paths


@pytest.fixture
def portable_dir(tmp_path, monkeypatch):
    root = tmp_path / "便携 排产系统"
    root.mkdir()
    (root / "aps-portable.txt").write_text("portable\n", encoding="ascii")
    for name in ("APS_SHARED_DATA_ROOT", "APS_DB_PATH", "APS_LOG_DIR", "APS_BACKUP_DIR",
                 "APS_EXCEL_TEMPLATE_DIR", "ProgramData", "LOCALAPPDATA"):
        monkeypatch.setenv(name, str(tmp_path / "old installation" / name))
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    def registry_must_not_be_read():
        pytest.fail("portable launch must not consult the installed SharedDataRoot")

    monkeypatch.setattr(launcher, "read_shared_data_root_from_registry", registry_must_not_be_read)
    monkeypatch.setattr(launcher_paths, "read_shared_data_root_from_registry", registry_must_not_be_read)
    return root


@pytest.mark.parametrize('domain', ["工厂域"])
def test_portable_factory_and_lock_use_local_paths_under_any_account(portable_dir, monkeypatch, domain):
    monkeypatch.setenv("USERNAME", "操作员")
    monkeypatch.setenv("USERDOMAIN", domain)
    app = Flask("portable-path-contract")
    factory._apply_runtime_config(app, base_dir=str(portable_dir))
    data = portable_dir / "user-data"
    assert launcher_paths.resolve_shared_data_root(str(portable_dir)) == str(data)
    assert app.config["DATABASE_PATH"] == str(data / "db" / "aps.db")
    assert launcher_paths.resolve_runtime_db_path(str(portable_dir)) == app.config["DATABASE_PATH"]
    assert app.config["LOG_DIR"] == str(data / "logs")
    assert launcher_paths.resolve_prelaunch_log_dir(str(portable_dir)) == app.config["LOG_DIR"]
    assert app.config["BACKUP_DIR"] == str(data / "backups")
    assert app.config["EXCEL_TEMPLATE_DIR"] == str(data / "templates_excel")
    assert launcher_paths.default_chrome_profile_dir(str(portable_dir)) == str(data / "chrome109_profile")
    assert launcher_paths.runtime_log_mirror_dir(str(portable_dir), app.config["LOG_DIR"]) == ""
    assert not (portable_dir.parent / "old installation").exists()


def test_moving_portable_directory_preserves_data_and_resolves_new_paths(portable_dir):
    original_db = portable_dir / "user-data" / "db" / "aps.db"
    original_db.parent.mkdir(parents=True)
    with closing(sqlite3.connect(str(original_db))) as conn, conn:
        conn.execute("CREATE TABLE preserved (value TEXT)")
        conn.execute("INSERT INTO preserved VALUES (?)", ("原有数据",))
    moved = portable_dir.with_name("移动后 排产系统")
    portable_dir.rename(moved)
    moved_db = launcher_paths.resolve_runtime_db_path(str(moved))
    assert moved_db == str(moved / "user-data" / "db" / "aps.db")
    with closing(sqlite3.connect(moved_db)) as conn:
        assert conn.execute("SELECT value FROM preserved").fetchone() == ("原有数据",)
    assert not portable_dir.exists()
