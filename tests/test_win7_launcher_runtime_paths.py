from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from flask import Flask


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_launcher():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher", None)
    return importlib.import_module("web.bootstrap.launcher")


def _import_factory():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.factory", None)
    return importlib.import_module("web.bootstrap.factory")


def test_resolve_shared_data_root_prefers_explicit_env(monkeypatch, tmp_path):
    launcher = _import_launcher()
    shared_root = tmp_path / "shared-data"
    monkeypatch.setenv("APS_SHARED_DATA_ROOT", str(shared_root))
    got = launcher.resolve_shared_data_root(str(tmp_path / "runtime"), frozen=False)
    assert got == os.path.abspath(str(shared_root))


def test_resolve_shared_data_root_uses_registry_only_when_frozen(monkeypatch, tmp_path):
    launcher = _import_launcher()
    base_dir = tmp_path / "app"
    registry_root = tmp_path / "registry-shared"
    monkeypatch.delenv("APS_SHARED_DATA_ROOT", raising=False)
    monkeypatch.setattr(launcher, "read_shared_data_root_from_registry", lambda: str(registry_root))
    got_dev = launcher.resolve_shared_data_root(str(base_dir), frozen=False)
    got_frozen = launcher.resolve_shared_data_root(str(base_dir), frozen=True)
    assert got_dev == os.path.abspath(str(base_dir))
    assert got_frozen == os.path.abspath(str(registry_root))


def test_resolve_prelaunch_log_dir_uses_shared_root(monkeypatch, tmp_path):
    launcher = _import_launcher()
    shared_root = tmp_path / "shared"
    monkeypatch.delenv("APS_LOG_DIR", raising=False)
    monkeypatch.setenv("APS_SHARED_DATA_ROOT", str(shared_root))
    got = launcher.resolve_prelaunch_log_dir(str(tmp_path / "runtime"), frozen=True)
    assert got == os.path.abspath(str(shared_root / "logs"))


def test_apply_runtime_config_uses_shared_root_for_all_data_dirs(monkeypatch, tmp_path):
    factory = _import_factory()
    base_dir = tmp_path / "app"
    shared_root = tmp_path / "shared-data"
    monkeypatch.setenv("APS_SHARED_DATA_ROOT", str(shared_root))
    monkeypatch.delenv("APS_DB_PATH", raising=False)
    monkeypatch.delenv("APS_LOG_DIR", raising=False)
    monkeypatch.delenv("APS_BACKUP_DIR", raising=False)
    monkeypatch.delenv("APS_EXCEL_TEMPLATE_DIR", raising=False)
    app = Flask("aps-runtime-config-test")
    factory._apply_runtime_config(app, base_dir=str(base_dir))
    assert app.config["BASE_DIR"] == str(base_dir)
    assert app.config["DATABASE_PATH"] == os.path.join(os.path.abspath(str(shared_root)), "db", "aps.db")
    assert app.config["LOG_DIR"] == os.path.join(os.path.abspath(str(shared_root)), "logs")
    assert app.config["BACKUP_DIR"] == os.path.join(os.path.abspath(str(shared_root)), "backups")
    assert app.config["EXCEL_TEMPLATE_DIR"] == os.path.join(os.path.abspath(str(shared_root)), "templates_excel")


def test_current_runtime_owner_uses_computername_when_userdomain_missing(monkeypatch):
    launcher = _import_launcher()
    monkeypatch.setenv("USERNAME", "alice")
    monkeypatch.delenv("USERDOMAIN", raising=False)
    monkeypatch.setenv("COMPUTERNAME", "LOCALBOX")
    assert launcher.current_runtime_owner() == r"LOCALBOX\alice"


def test_stop_runtime_from_log_dir_returns_busy_when_contract_missing_but_health_ok(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    calls = {}

    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: True)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))
    monkeypatch.setattr(
        launcher,
        "stop_aps_chrome_processes",
        lambda profile_dir, logger=None: calls.setdefault("chrome", profile_dir) or True,
    )

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 1
    assert calls == {}


def test_stop_runtime_from_log_dir_uses_state_dir_and_parent_runtime_dir(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    calls = {}

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)

    def _fake_delete(path: str) -> None:
        calls["delete"] = path

    def _fake_stop(profile_dir: str, logger=None) -> bool:
        calls["chrome"] = profile_dir
        return True

    monkeypatch.setattr(launcher, "delete_runtime_contract_files", _fake_delete)
    monkeypatch.setattr(launcher, "stop_aps_chrome_processes", _fake_stop)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 0
    assert calls["delete"] == os.path.abspath(str(state_dir))
    assert calls["chrome"] == os.path.abspath(str(tmp_path / "shared-data" / "chrome109_profile"))


def test_launcher_bat_contains_json_health_probe_and_owner_fallback():
    text = (Path(_repo_root()) / "assets" / "启动_排产系统_Chrome.bat").read_text(encoding="utf-8")
    assert "ConvertFrom-Json" in text
    assert r"Contains('\"app\":\"aps\"')" not in text
    assert "%COMPUTERNAME%" in text


def test_installer_uninstall_stop_checks_multiple_runtime_roots():
    text = (Path(_repo_root()) / "installer" / "aps_win7.iss").read_text(encoding="utf-8")
    assert "TryStopKnownApsRuntime" in text
    assert "LegacyDataRootPath" in text
    assert "ExpandConstant('{app}')" in text


def test_main_installer_contains_precleanup_and_skip_legacy_migration():
    text = (Path(_repo_root()) / "installer" / "aps_win7.iss").read_text(encoding="utf-8")
    assert "function PrepareToInstall" in text
    assert "RunPreInstallFullWipe(True, Result)" in text
    assert "SkipLegacyMigration" in text
    assert "ResolveStopHelperExe" in text
    assert "RegisteredMainAppDirPath" in text


def test_legacy_installer_uses_runtime_root_stop_contract():
    text = (Path(_repo_root()) / "installer" / "aps_win7_legacy.iss").read_text(encoding="utf-8")
    assert "function PrepareToInstall" in text
    assert "TryStopKnownApsRuntime" in text
    assert "TryStopApsRuntimeAtDir(HelperExePath, SharedDataRootPath" in text
    assert "TryStopApsRuntimeAtDir(HelperExePath, LegacyDataRootPath" in text
    assert "Params := '--runtime-stop \"' + SharedLogDirPath" not in text


def test_chrome_installer_remains_non_target_for_precleanup():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "function PrepareToInstall" not in text
    assert "Chrome109Profile" in text
