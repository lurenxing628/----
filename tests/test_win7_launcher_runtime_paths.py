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


def test_default_chrome_profile_dir_prefers_localappdata_profile_name(monkeypatch, tmp_path):
    launcher = _import_launcher()
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\alice\AppData\Local")
    got = launcher.default_chrome_profile_dir(str(tmp_path))
    assert got == os.path.abspath(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile")


def test_resolve_runtime_state_paths_returns_runtime_dir_for_runtime_and_log_dir(tmp_path):
    launcher = _import_launcher()
    runtime_dir = tmp_path / "runtime-root"
    state_dir = runtime_dir / "logs"
    state_dir.mkdir(parents=True)

    runtime_paths = launcher.resolve_runtime_state_paths(str(runtime_dir))
    log_paths = launcher.resolve_runtime_state_paths(str(state_dir))

    assert runtime_paths["runtime_dir"] == os.path.abspath(str(runtime_dir))
    assert log_paths["runtime_dir"] == os.path.abspath(str(runtime_dir))
    assert runtime_paths["state_dir"] == os.path.abspath(str(state_dir))
    assert log_paths["state_dir"] == os.path.abspath(str(state_dir))
    assert runtime_paths["contract_path"].endswith(os.path.join("logs", "aps_runtime.json"))
    assert log_paths["lock_path"].endswith(os.path.join("logs", "aps_runtime.lock"))



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


def test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")
    calls = {}

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))

    def _fake_stop(profile_dir: str, logger=None) -> bool:
        calls["chrome"] = profile_dir
        return False

    monkeypatch.setattr(launcher, "stop_aps_chrome_processes", _fake_stop)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 1
    assert calls["delete"] == os.path.abspath(str(state_dir))
    assert calls["chrome"] == os.path.abspath(str(tmp_path / "shared-data" / "chrome109_profile"))


def test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable(monkeypatch):
    launcher = _import_launcher()
    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: None)
    assert launcher.stop_aps_chrome_processes(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile") is False


def test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process():
    text = (Path(_repo_root()) / "assets" / "启动_排产系统_Chrome.bat").read_text(encoding="utf-8")
    assert "--user-data-dir" in text
    assert "CHROME_PROFILE_DIR" in text
    assert "Get-CimInstance Win32_Process" in text or "Get-WmiObject Win32_Process" in text
    assert 'tasklist /FI "IMAGENAME eq chrome.exe" /NH /FO CSV' not in text
    assert 'findstr /I /C:"\\"chrome.exe\\""' not in text


def test_launcher_bat_contains_json_health_probe_and_owner_fallback():
    text = (Path(_repo_root()) / "assets" / "启动_排产系统_Chrome.bat").read_text(encoding="utf-8")
    assert "chcp 65001 >nul 2>&1" in text
    assert "ConvertFrom-Json" in text
    assert r"Contains('\"app\":\"aps\"')" not in text
    assert "%COMPUTERNAME%" in text
    assert "LOCK_ACTIVE=UNKNOWN" in text
    assert "BLOCKED_BY_UNCERTAIN" in text
    assert "RUNTIME_CONTRACT_FILE" in text
    assert "port_file_invalid" in text
    assert 'set "HOST=!FILE_HOST!"' in text
    assert 'set "PORT=!FILE_PORT!"' in text
    assert 'call :log launch_error="!LAUNCH_ERROR!"' in text
    assert 'set "CONTRACT_OWNER=!CONTRACT_OWNER:\\=\\!"' in text
    assert 'tasklist /FI "PID eq !LOCK_PID!" /NH /FO CSV' in text
    assert "where wmic" not in text
    assert "wmic process where" not in text
    assert "contract_owner_normalized" in text
    assert "app_spawn_probe" in text
    assert "chrome_profile_probe" in text
    assert "chrome_alive_probe" in text


def test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup():
    text = (Path(_repo_root()) / "web" / "bootstrap" / "launcher.py").read_text(encoding="utf-8")
    assert "_run_powershell_text" in text
    assert "Get-Process -Id $pid0" in text
    assert "Get-CimInstance Win32_Process" in text
    assert "if pids is None:" in text
    assert "_stop_aps_chrome_if_requested" in text
    assert '["wmic"' not in text


def test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths():
    text = (Path(_repo_root()) / ".limcode" / "skills" / "aps-package-win7" / "scripts" / "package_win7.ps1").read_text(encoding="utf-8")
    assert "Invoke-ChromeRuntimeSmoke" in text
    assert "BROWSER SMOKE OK" in text
    assert "--app=$url" in text
    assert 'Invoke-ChromeRuntimeSmoke (Join-Path $payloadDir "chrome.exe") "chrome runtime payload"' in text
    assert 'Invoke-ChromeRuntimeSmoke (Join-Path $distDir "tools\\chrome109\\chrome.exe") "legacy dist chrome runtime"' in text


def test_package_script_exposes_explicit_best_effort_cleanup_wrapper():
    text = (Path(_repo_root()) / ".limcode" / "skills" / "aps-package-win7" / "scripts" / "package_win7.ps1").read_text(encoding="utf-8")
    assert "function Stop-ProcessTreeByIdsBestEffort" in text
    assert "Stop-ProcessTreeByIdsBestEffort $cleanupChromeIds" in text
    assert "Stop-ProcessTreeByIds $cleanupChromeIds" not in text


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
    assert "TryMigrateLegacyDataBeforeInstall" in text
    assert "CleanupMigrationPartialData" in text
    assert "MigrateLegacyDataIfNeeded" not in text


def test_legacy_installer_uses_runtime_root_stop_contract():
    text = (Path(_repo_root()) / "installer" / "aps_win7_legacy.iss").read_text(encoding="utf-8")
    assert "function PrepareToInstall" in text
    assert "TryStopKnownApsRuntime" in text
    assert "TryStopApsRuntimeAtDir(HelperExePath, SharedDataRootPath" in text
    assert "TryStopApsRuntimeAtDir(HelperExePath, LegacyDataRootPath" in text
    assert "Params := '--runtime-stop \"' + SharedLogDirPath" not in text
    assert "TryMigrateLegacyDataBeforeInstall" in text
    assert "CleanupMigrationPartialData" in text
    assert "MigrateLegacyDataIfNeeded" not in text


def test_installers_fail_closed_on_silent_uninstall_and_retry_delete():
    repo_root = Path(_repo_root())
    main_text = (repo_root / "installer" / "aps_win7.iss").read_text(encoding="utf-8")
    legacy_text = (repo_root / "installer" / "aps_win7_legacy.iss").read_text(encoding="utf-8")
    chrome_text = (repo_root / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")

    assert "silent uninstall: failed to stop APS runtime before uninstall" in main_text
    assert "silent uninstall: failed to stop APS runtime or bundled Chrome before uninstall" in legacy_text
    assert "silent uninstall: failed to stop APS Chrome processes before uninstall" in chrome_text
    assert "Sleep(1000)" in main_text
    assert "Sleep(1000)" in legacy_text
    assert "powershell.exe" in chrome_text
    assert "Get-CimInstance Win32_Process" in chrome_text
    assert "Get-WmiObject Win32_Process" in chrome_text
    assert "Stop-Process -Id $procId -Force" in chrome_text
    assert "wmic.exe" not in chrome_text
    assert "process where \"Name=''chrome.exe''" not in chrome_text


def test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "--user-data-dir" in text
    assert "\\aps\\chrome109profile" in text.lower()
    assert "$marker=''chrome109profile''" not in text


def test_chrome_installer_stop_helper_uses_current_user_profile_path_marker():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "CurrentUserChromeProfilePath" in text
    assert "ExpandConstant('{localappdata}\\APS\\Chrome109Profile')" in text
    assert "ApsChromeProfileSuffixMarker" in text
    assert "手动删除当前账户的 APS 浏览器用户数据目录" in text
    assert "BuildStopChromePowerShellParams(CurrentUserChromeProfilePath(), ApsChromeProfileSuffixMarker())" in text


def test_build_scripts_guard_vendor_and_launcher_path():
    repo_root = Path(_repo_root())
    onedir_text = (repo_root / "build_win7_onedir.bat").read_text(encoding="utf-8")
    installer_text = (repo_root / "build_win7_installer.bat").read_text(encoding="utf-8")

    assert "if exist vendor (" in onedir_text
    assert "vendor 目录不存在，跳过 vendor 数据目录。" in onedir_text
    assert r"assets\启动_排产系统_Chrome.bat" in installer_text
    assert "*Chrome*.bat" not in installer_text


def test_chrome_installer_remains_non_target_for_precleanup():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "function PrepareToInstall" not in text
    assert "Chrome109Profile" in text
