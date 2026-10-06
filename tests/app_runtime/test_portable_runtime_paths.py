"""便携运行使用本地目录，移动目录后业务数据仍可读取。"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest
from flask import Flask

from core.services.workbench.facts.run_data_context import RunDataContext
from core.services.workbench.facts.system_journal import SystemMaintenanceJournal
from tests.workbench.system_maintenance_support import SystemTestAPI
from web.bootstrap import factory, launcher, launcher_paths
from web.bootstrap.workbench_system_restore_recovery import (
    RECOVERY,
    prepare_system_restore_startup,
    system_journal_directory,
)


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


def _portable_system_api(portable_dir):
    data = portable_dir / "user-data"
    data.mkdir()
    api = SystemTestAPI(data)
    database = data / "db" / "aps.db"
    database.parent.mkdir()
    api.database.rename(database)
    api.database = database
    api.journal_dir = Path(system_journal_directory(str(database)))
    api.journal_dir.mkdir()
    api.app.config.update(DATABASE_PATH=str(database), WORKBENCH_SYSTEM_JOURNAL_DIR=str(api.journal_dir))
    return api


@pytest.mark.parametrize("relocation", ["move", "upgrade"])
def test_moving_portable_directory_preserves_data_and_resolves_new_paths(portable_dir, relocation):
    api = _portable_system_api(portable_dir)
    original_db = api.database
    with closing(sqlite3.connect(str(original_db))) as conn, conn:
        conn.execute("CREATE TABLE preserved (value TEXT)")
        conn.execute("INSERT INTO preserved VALUES (?)", ("原有数据",))
    request_key = "portable-backup-before-move"
    created = api.file_action("create", key=request_key)
    assert created.status_code == 200, created.get_json()
    assert created.get_json()["data"]["operation"]["state"] == "succeeded"
    scope = api.journal().database_scope
    saved_history = {path.name: path.read_bytes() for path in api.journal_dir.glob("*.json")}
    with closing(api.connect()) as conn:
        context = RunDataContext(conn, str(api.journal_dir)).ref()
    moved = portable_dir.with_name("移动后 排产系统")
    if relocation == "move":
        portable_dir.rename(moved)
    else:
        moved.mkdir()
        (moved / "aps-portable.txt").write_text("portable\n", encoding="ascii")
        shutil.copytree(portable_dir / "user-data", moved / "user-data")
    moved_db = launcher_paths.resolve_runtime_db_path(str(moved))
    assert moved_db == str(moved / "user-data" / "db" / "aps.db")
    app = Flask("moved-portable-startup")
    factory._apply_runtime_config(app, base_dir=str(moved))
    assert prepare_system_restore_startup(app) is False
    assert RECOVERY not in app.extensions
    with closing(sqlite3.connect(moved_db)) as conn:
        assert conn.execute("SELECT value FROM preserved").fetchone() == ("原有数据",)
    api.database, api.backups = Path(moved_db), moved / "user-data" / "backups"
    api.journal_dir = Path(app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"])
    api.app.config.update(DATABASE_PATH=moved_db, BACKUP_DIR=str(api.backups),
                          WORKBENCH_SYSTEM_JOURNAL_DIR=str(api.journal_dir))
    assert api.journal().database_scope == scope
    assert {path.name: path.read_bytes() for path in api.journal_dir.glob("*.json")} == saved_history
    replay = api.file_action("create", key=request_key).get_json()["data"]["operation"]
    assert replay["replayed"] is True
    assert replay["job_ref"] == created.get_json()["data"]["operation"]["job_ref"]
    after_move = api.file_action("create", key="portable-backup-after-move")
    assert after_move.status_code == 200, after_move.get_json()
    assert after_move.get_json()["data"]["operation"]["state"] == "succeeded"
    assert all(record["database_scope"] == scope for record in api.journal().records())
    with closing(api.connect()) as conn:
        assert RunDataContext(conn, str(api.journal_dir)).ref() == context
    assert portable_dir.exists() is (relocation == "upgrade")
    with pytest.raises(RuntimeError, match="不属于当前数据库"):
        SystemMaintenanceJournal(str(api.journal_dir), str(moved / "another.db")).assert_ready()
