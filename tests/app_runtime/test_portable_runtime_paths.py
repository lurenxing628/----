"""Portable paths stay with the directory despite old installations and accounts."""
from __future__ import annotations

import os
import sqlite3
import sys
from types import SimpleNamespace

import pytest
from flask import Flask

from web.bootstrap import factory, launcher, launcher_paths
from web.bootstrap.launcher_contracts import _runtime_contract_payload


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


@pytest.mark.parametrize("domain", ["LOCALBOX", "工厂域"])
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
    with sqlite3.connect(str(original_db)) as conn:
        conn.execute("CREATE TABLE preserved (value TEXT)")
        conn.execute("INSERT INTO preserved VALUES (?)", ("原有数据",))
    moved = portable_dir.with_name("移动后 排产系统")
    portable_dir.rename(moved)
    moved_db = launcher_paths.resolve_runtime_db_path(str(moved))
    assert moved_db == str(moved / "user-data" / "db" / "aps.db")
    with sqlite3.connect(moved_db) as conn:
        assert conn.execute("SELECT value FROM preserved").fetchone() == ("原有数据",)
    assert not portable_dir.exists()


def test_portable_stop_contract_uses_the_same_browser_profile(portable_dir):
    data = portable_dir / "user-data"
    payload = _runtime_contract_payload(
        str(portable_dir), "127.0.0.1", 51399,
        db_path=str(data / "db" / "aps.db"), shutdown_token="test-only",
        ui_mode="default", log_dir=str(data / "logs"), backup_dir=str(data / "backups"),
        excel_template_dir=str(data / "templates_excel"),
    )
    assert payload["chrome_profile_dir"] == str(data / "chrome109_profile")


def test_portable_runtime_read_and_stop_resolve_root_and_logs_identically(portable_dir):
    log_dir = portable_dir / "user-data" / "logs"
    root_paths = launcher_paths.resolve_runtime_state_paths(str(portable_dir))
    log_paths = launcher_paths.resolve_runtime_state_paths(str(log_dir))
    assert root_paths == log_paths
    assert root_paths["runtime_dir"] == str(portable_dir)
    assert root_paths["state_dir"] == str(log_dir)
    assert root_paths["contract_path"] == str(log_dir / "aps_runtime.json")
    assert launcher_paths.resolve_runtime_stop_context(str(portable_dir)) == (str(portable_dir), str(log_dir))
    assert launcher_paths.resolve_runtime_stop_context(str(log_dir)) == (str(portable_dir), str(log_dir))


def test_exe_validator_uses_portable_logs_and_rejects_a_different_database(portable_dir, monkeypatch, capsys):
    import validate_dist_exe as validator

    exe = portable_dir / "排产系统.exe"
    exe.write_bytes(b"synthetic")
    other_db = portable_dir.parent / "wrong.db"
    other_db.write_bytes(b"synthetic")
    monkeypatch.setattr(sys, "argv", ["validate_dist_exe.py", str(exe)])
    monkeypatch.setattr(validator, "_assert_networkx_bundled", lambda _path: None)
    monkeypatch.setattr(validator, "_assert_static_bundled", lambda _path: None)
    cleared = []
    monkeypatch.setattr(validator, "_clear_runtime_contract_files", cleared.append)
    process = SimpleNamespace(terminate=lambda: None, wait=lambda timeout: None)
    monkeypatch.setattr(validator.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(validator, "_wait_for_runtime_contract",
                        lambda *args, **kwargs: ("127.0.0.1", 51399, str(other_db)))
    assert validator.main() == 5
    assert cleared == [str(portable_dir / "user-data" / "logs")]
    assert "数据库偏离交付目录配置" in capsys.readouterr().out


def test_invalid_portable_data_directory_fails_without_external_fallback(portable_dir):
    (portable_dir / "user-data").write_text("not a directory", encoding="ascii")
    app = Flask("portable-unwritable-path")
    factory._apply_runtime_config(app, base_dir=str(portable_dir))
    with pytest.raises(OSError):
        factory._ensure_runtime_dirs(app)
    assert app.config["LOG_DIR"] == os.path.join(str(portable_dir), "user-data", "logs")
    assert not (portable_dir.parent / "old installation").exists()
