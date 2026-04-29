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


def _import_launcher_stop():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.launcher_stop", None)
    return importlib.import_module("web.bootstrap.launcher_stop")


def _import_factory():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.factory", None)
    return importlib.import_module("web.bootstrap.factory")


def _import_paths():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("web.bootstrap.paths", None)
    return importlib.import_module("web.bootstrap.paths")


def test_runtime_base_dir_fallback_logs_to_stderr(monkeypatch, capsys):
    paths_mod = _import_paths()
    original_resolve = paths_mod.Path.resolve

    def _boom_resolve(self):
        raise RuntimeError("resolve boom")

    monkeypatch.setattr(paths_mod.Path, "resolve", _boom_resolve)
    got = paths_mod.runtime_base_dir(anchor_file=str(Path("C:/demo/app.py")))
    assert got.endswith(os.path.join("demo"))
    assert "运行根目录解析失败" in capsys.readouterr().err
    monkeypatch.setattr(paths_mod.Path, "resolve", original_resolve)


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


def test_stop_runtime_from_dir_waits_for_pid_exit_before_success(monkeypatch, tmp_path):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    contract_path = state_dir / "aps_runtime.json"
    runtime_dir_json = str(tmp_path / "shared-data").replace("\\", "/")
    contract_path.write_text(
        (
            "{\n"
            '  "contract_version": 1,\n'
            '  "pid": 43210,\n'
            '  "host": "127.0.0.1",\n'
            '  "port": 5000,\n'
            '  "exe_path": "D:/py3.8/python.exe",\n'
            '  "chrome_profile_dir": "C:/Temp/chrome-profile",\n'
            '  "shutdown_token": "runtime-stop-token",\n'
            f'  "runtime_dir": "{runtime_dir_json}",\n'
            '  "data_dirs": {"log_dir": "C:/Temp/runtime-logs"}\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    calls = {"pid_checks": 0}

    monkeypatch.setattr(launcher, "_request_runtime_shutdown", lambda contract, timeout_s=3.0: True)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=0.5: False)

    pid_states = iter([True, True, False])

    def _fake_pid_exists(pid: int) -> bool:
        calls["pid_checks"] += 1
        return next(pid_states)

    monkeypatch.setattr(launcher, "_pid_exists", _fake_pid_exists)
    monkeypatch.setattr(launcher, "_pid_matches_contract", lambda pid, expected_exe_path: True)
    monkeypatch.setattr(launcher, "_kill_runtime_pid", lambda pid: calls.setdefault("kill", pid) or False)
    monkeypatch.setattr(launcher.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(launcher, "delete_runtime_contract_files", lambda path: calls.setdefault("delete", path))
    monkeypatch.setattr(
        launcher,
        "stop_aps_chrome_processes",
        lambda profile_dir, logger=None: calls.setdefault("chrome", profile_dir) or True,
    )

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 0
    assert calls["pid_checks"] >= 3
    assert calls["delete"] == os.path.abspath(str(state_dir))
    assert calls["chrome"] == "C:/Temp/chrome-profile"
    assert "kill" not in calls


def test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable(monkeypatch):
    launcher = _import_launcher()
    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: None)
    assert launcher.stop_aps_chrome_processes(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile") is False


def test_stop_aps_chrome_processes_treats_already_gone_pid_as_success_after_final_recheck(monkeypatch):
    launcher = _import_launcher()
    pid_snapshots = iter([[100, 101], []])
    killed: list[int] = []

    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: next(pid_snapshots))
    monkeypatch.setattr(launcher, "_kill_runtime_pid", lambda pid: killed.append(int(pid)) or int(pid) == 100)

    assert launcher.stop_aps_chrome_processes(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile") is True
    assert killed == [100, 101]


def test_stop_aps_chrome_processes_fails_when_final_recheck_still_finds_profile_process(monkeypatch):
    launcher = _import_launcher()
    pid_snapshots = iter([[100], [100]])

    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: next(pid_snapshots))
    monkeypatch.setattr(launcher, "_kill_runtime_pid", lambda pid: True)

    assert launcher.stop_aps_chrome_processes(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile") is False


PROFILE_PREFIX = "--user-data-dir="


def _split_command_line_args(cmd: str) -> list[str]:
    tokens: list[str] = []
    buf: list[str] = []
    in_quotes = False
    cmd_text = str(cmd or "")
    for index, ch in enumerate(cmd_text):
        if ch == '"':
            slash_count = 0
            slash_index = index - 1
            while slash_index >= 0 and cmd_text[slash_index] == "\\":
                slash_count += 1
                slash_index -= 1
            if slash_count % 2 == 0:
                in_quotes = not in_quotes
                continue
        if not in_quotes and ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _command_line_matches_exact_profile(cmd: str, marker: str) -> bool:
    marker_lower = marker.lower()
    for arg in _split_command_line_args(cmd):
        arg_lower = arg.lower()
        if arg_lower.startswith(PROFILE_PREFIX) and arg_lower[len(PROFILE_PREFIX) :] == marker_lower:
            return True
    return False


def _command_line_matches_installer_profile(cmd: str, exact_marker: str, suffix_marker: str) -> bool:
    exact_lower = exact_marker.lower()
    suffix_lower = suffix_marker.lower()
    for arg in _split_command_line_args(cmd):
        arg_lower = arg.lower()
        if not arg_lower.startswith(PROFILE_PREFIX):
            continue
        profile = arg_lower[len(PROFILE_PREFIX) :]
        if exact_lower and profile == exact_lower:
            return True
        if suffix_lower and profile.endswith(suffix_lower):
            return True
    return False


def test_chrome_pid_query_script_matches_exact_user_data_dir_argument():
    launcher_stop = _import_launcher_stop()

    script = launcher_stop._chrome_pid_query_script(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile")

    assert "--user-data-dir=" in script
    assert "function Split-CommandLineArgs" in script
    assert "$slashCount" in script
    assert "[char]92" in script
    assert "$argLower.StartsWith($prefix)" in script
    assert "$argLower.Substring($prefix.Length) -eq $marker" in script
    assert "$cmd -match $profilePattern" not in script
    assert "[Regex]::Escape($marker)" not in script
    assert "$cmdLower.Contains($marker)" not in script


def test_launcher_profile_pattern_rejects_adjacent_profile_names(tmp_path):
    profile_dir = tmp_path / "APS" / "Chrome109Profile"
    marker = str(profile_dir).lower()

    assert _command_line_matches_exact_profile(
        f'chrome.exe --user-data-dir="{marker}" --app=http://127.0.0.1:5000', marker
    )
    assert _command_line_matches_exact_profile(
        f'chrome.exe "--user-data-dir={marker}" --app=http://127.0.0.1:5000', marker
    )
    assert _command_line_matches_exact_profile(
        f'chrome.exe --user-data-dir="{marker.replace("chrome109profile", "Chrome109Profile")}"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --user-data-dir="{marker}2" --app=http://127.0.0.1:5000',
        marker,
    )
    assert not _command_line_matches_exact_profile(f'chrome.exe --user-data-dir="{marker}_bak"', marker)
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --disk-cache-dir="{marker}" --user-data-dir="/tmp/other"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --app="http://127.0.0.1:5000/?q= --user-data-dir={marker} " --user-data-dir="/tmp/other"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --note="before --user-data-dir=\\"{marker}\\" after" --user-data-dir="/tmp/other"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe "--app=http://127.0.0.1:5000/?q=\\" --user-data-dir={marker} \\"" --user-data-dir="d:\\other"',
        marker,
    )


def test_installer_profile_patterns_reject_adjacent_profile_names():
    exact_marker = r"c:\users\alice\appdata\local\aps\chrome109profile"
    suffix_marker = r"\aps\chrome109profile"
    other_user_profile = r"d:\other-user\appdata\local\aps\chrome109profile"

    assert _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{exact_marker}" --app=http://127.0.0.1:5000',
        exact_marker,
        suffix_marker,
    )
    assert _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{other_user_profile}" --app=http://127.0.0.1:5000',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{exact_marker}2" --app=http://127.0.0.1:5000',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{exact_marker}_bak"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{other_user_profile}2"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --user-data-dir="{other_user_profile}_bak"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --disk-cache-dir="{other_user_profile}" --user-data-dir="d:\\other"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe --app="http://127.0.0.1:5000/?q= --user-data-dir={other_user_profile} " --user-data-dir="d:\\other"',
        exact_marker,
        suffix_marker,
    )
    assert not _command_line_matches_installer_profile(
        f'chrome.exe "--app=http://127.0.0.1:5000/?q=\\" --user-data-dir={other_user_profile} \\"" --user-data-dir="d:\\other"',
        exact_marker,
        suffix_marker,
    )


def test_wait_for_runtime_stop_rechecks_after_last_sleep(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    status_snapshots = iter(
        [
            {"state": "mixed"},
            {"state": "active"},
            {"state": "stale"},
        ]
    )
    clock = iter([0.0, 0.3])

    monkeypatch.setattr(launcher_stop, "_classify_runtime_state", lambda state_dir: next(status_snapshots))
    monkeypatch.setattr(launcher_stop, "_runtime_stop_is_complete", lambda status: status["state"] == "stale")
    monkeypatch.setattr(launcher_stop.time, "time", lambda: next(clock))
    monkeypatch.setattr(launcher_stop.time, "sleep", lambda seconds: None)

    assert launcher_stop._wait_for_runtime_stop(str(tmp_path), 0.25)["state"] == "stale"


def test_force_kill_runtime_requires_confirmed_pid_match(monkeypatch, tmp_path):
    launcher_stop = _import_launcher_stop()
    base_status = {
        "contract": {"pid": 43210, "exe_path": sys.executable},
        "state": "active",
        "endpoint_up": True,
        "pid": 43210,
        "expected_exe_path": sys.executable,
    }

    assert launcher_stop._can_force_kill_runtime({**base_status, "pid_match": True}) is True
    assert launcher_stop._can_force_kill_runtime({**base_status, "pid_match": None}) is False

    calls: list[int] = []
    status = {**base_status, "pid_match": None}
    monkeypatch.setattr(launcher_stop, "_kill_runtime_pid", lambda pid: calls.append(int(pid)) or True)
    assert launcher_stop._try_force_kill_runtime(str(tmp_path), status) is status
    assert calls == []

    stopped_status = {"state": "stale", "endpoint_up": False}
    monkeypatch.setattr(launcher_stop, "_wait_for_runtime_stop", lambda state_dir, deadline: stopped_status)
    assert launcher_stop._try_force_kill_runtime(str(tmp_path), {**base_status, "pid_match": True}) == stopped_status
    assert calls == [43210]


def test_stop_runtime_from_dir_reports_chrome_stop_failure_reason_without_logger(monkeypatch, tmp_path, capsys):
    launcher = _import_launcher()
    state_dir = tmp_path / "shared-data" / "logs"
    state_dir.mkdir(parents=True)
    (state_dir / "aps_host.txt").write_text("127.0.0.1\n", encoding="utf-8")
    (state_dir / "aps_port.txt").write_text("5000\n", encoding="utf-8")

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(launcher, "_probe_runtime_health", lambda host, port, timeout_s=1.0: False)
    monkeypatch.setattr(launcher, "_list_aps_chrome_pids", lambda profile_dir: None)

    assert launcher.stop_runtime_from_dir(str(state_dir), stop_aps_chrome=True) == 1
    assert "chrome_stop" in capsys.readouterr().err


def test_runtime_stop_cli_passes_stop_aps_chrome_flag():
    from web.bootstrap.entrypoint import EntryPointDeps, app_main

    calls = {}

    deps = EntryPointDeps(
        create_app=lambda: Flask("unused-runtime-stop-test"),
        clear_launch_error=lambda *args, **kwargs: None,
        write_launch_error=lambda *args, **kwargs: None,
        current_runtime_owner=lambda: "LOCALBOX\\alice",
        resolve_prelaunch_log_dir=lambda runtime_dir: os.path.join(runtime_dir, "logs"),
        acquire_runtime_lock=lambda *args, **kwargs: {},
        release_runtime_lock=lambda *args, **kwargs: None,
        delete_runtime_contract_files=lambda *args, **kwargs: None,
        write_runtime_host_port_files=lambda *args, **kwargs: None,
        write_runtime_contract_file=lambda *args, **kwargs: "",
        default_chrome_profile_dir=lambda runtime_dir: os.path.join(runtime_dir, "chrome109_profile"),
        pick_bind_host=lambda raw_host, logger=None: "127.0.0.1",
        pick_port=lambda host, preferred, logger=None: (host, int(preferred)),
        stop_runtime_from_dir=lambda runtime_dir, stop_aps_chrome=False: (
            calls.setdefault("stop", (runtime_dir, stop_aps_chrome)) and 0
        ),
        serve_runtime_app=lambda app, host, port: None,
        should_use_runtime_reloader=lambda debug: False,
        should_own_runtime_resources=lambda debug: True,
        should_register_runtime_lifecycle_handlers=lambda debug: True,
        atexit_register=lambda *args, **kwargs: None,
    )

    assert (
        app_main("default", anchor_file=__file__, argv=["--runtime-stop", "D:/runtime", "--stop-aps-chrome"], deps=deps)
        == 0
    )
    assert calls["stop"] == ("D:/runtime", True)


def test_launcher_facade_exports_runtime_contract_surface():
    launcher = _import_launcher()
    expected_names = [
        "RuntimeLockError",
        "acquire_runtime_lock",
        "clear_launch_error",
        "current_runtime_owner",
        "default_chrome_profile_dir",
        "delete_runtime_contract_files",
        "pick_bind_host",
        "pick_port",
        "probe_runtime_health",
        "read_runtime_contract",
        "read_runtime_lock",
        "release_runtime_lock",
        "resolve_prelaunch_log_dir",
        "resolve_runtime_state_paths",
        "resolve_shared_data_root",
        "runtime_pid_exists",
        "runtime_pid_matches_executable",
        "stop_aps_chrome_processes",
        "stop_runtime_from_dir",
        "write_launch_error",
        "write_runtime_contract_file",
        "write_runtime_host_port_files",
    ]

    for name in expected_names:
        assert hasattr(launcher, name), name


def test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process():
    text = (Path(_repo_root()) / "assets" / "启动_排产系统_Chrome.bat").read_text(encoding="utf-8")
    marker = r"c:\users\alice\appdata\local\aps\chrome109profile"

    assert "--user-data-dir" in text
    assert "CHROME_PROFILE_DIR" in text
    assert "Get-CimInstance Win32_Process" in text or "Get-WmiObject Win32_Process" in text
    assert "function Split-CommandLineArgs" in text
    assert "$slashCount" in text
    assert "[char]92" in text
    assert "Test-ApsChromeCommandLine $cmd" in text
    assert "$cmd -match $profilePattern" not in text
    assert "$cmdLower.Contains($marker)" not in text
    assert 'tasklist /FI "IMAGENAME eq chrome.exe" /NH /FO CSV' not in text
    assert 'findstr /I /C:"\\"chrome.exe\\""' not in text
    assert _command_line_matches_exact_profile(
        f'chrome.exe --user-data-dir="{marker}" --app=http://127.0.0.1:5000', marker
    )
    assert not _command_line_matches_exact_profile(f'chrome.exe --user-data-dir="{marker}2"', marker)
    assert not _command_line_matches_exact_profile(f'chrome.exe --user-data-dir="{marker}_bak"', marker)
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --app="http://127.0.0.1:5000/?q= --user-data-dir={marker} " --user-data-dir="d:\\other"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe "--app=http://127.0.0.1:5000/?q=\\" --user-data-dir={marker} \\"" --user-data-dir="d:\\other"',
        marker,
    )


def test_launcher_bat_contains_json_health_probe_and_owner_fallback():
    text = (Path(_repo_root()) / "assets" / "启动_排产系统_Chrome.bat").read_text(encoding="utf-8")
    assert "chcp 65001 >nul 2>&1" in text
    assert "ConvertFrom-Json" in text
    assert r"Contains('\"app\":\"aps\"')" not in text
    assert "%COMPUTERNAME%" in text
    assert "LOCK_ACTIVE=UNKNOWN" in text
    assert "BLOCKED_BY_UNCERTAIN" in text
    assert "RUNTIME_CONTRACT_FILE" in text
    assert "JavaScriptSerializer" in text
    assert "contract_parse_failed" in text
    assert "launcher_blocked=no_powershell" in text
    assert "PowerShell is required to verify the APS runtime owner and health." in text
    assert "port_file_invalid" in text
    assert 'set "HOST=!FILE_HOST!"' in text
    assert 'set "PORT=!FILE_PORT!"' in text
    assert 'call :log launch_error="!LAUNCH_ERROR!"' in text
    assert 'findstr /R /C:"\\"owner\\""' not in text
    assert 'set "CONTRACT_OWNER=!CONTRACT_OWNER:\\=\\!"' not in text
    assert 'tasklist /FI "PID eq !LOCK_PID!" /NH /FO CSV' in text
    assert "where wmic" not in text
    assert "wmic process where" not in text
    assert "contract_owner_normalized" in text
    assert "app_spawn_probe" in text
    assert "chrome_profile_probe" in text
    assert "chrome_alive_probe" in text


def test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup():
    text = (Path(_repo_root()) / "web" / "bootstrap" / "launcher_processes.py").read_text(encoding="utf-8")
    stop_text = (Path(_repo_root()) / "web" / "bootstrap" / "launcher_stop.py").read_text(encoding="utf-8")
    assert "_run_powershell_text" in text
    assert "ProcessId=$pid0" in text
    assert "Get-WmiObject Win32_Process" in text
    assert "ExecutablePath" in text
    assert "Get-Process -Id $pid0" not in text
    assert "Get-CimInstance Win32_Process" in stop_text
    assert "pids is None" in stop_text
    assert "_stop_aps_chrome_if_requested" in stop_text
    assert '["wmic"' not in text
    assert '["wmic"' not in stop_text
    assert "[string]::IsNullOrWhiteSpace" not in text
    assert "[string]::IsNullOrWhiteSpace" not in stop_text


def test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths():
    text = (Path(_repo_root()) / ".limcode" / "skills" / "aps-package-win7" / "scripts" / "package_win7.ps1").read_text(
        encoding="utf-8"
    )
    assert "Invoke-ChromeRuntimeSmoke" in text
    assert "BROWSER SMOKE OK" in text
    assert "--app=$url" in text
    assert 'Invoke-ChromeRuntimeSmoke (Join-Path $payloadDir "chrome.exe") "chrome runtime payload"' in text
    assert (
        'Invoke-ChromeRuntimeSmoke (Join-Path $distDir "tools\\chrome109\\chrome.exe") "legacy dist chrome runtime"'
        in text
    )


def test_package_script_exposes_explicit_best_effort_cleanup_wrapper():
    text = (Path(_repo_root()) / ".limcode" / "skills" / "aps-package-win7" / "scripts" / "package_win7.ps1").read_text(
        encoding="utf-8"
    )
    marker = r"c:\temp\aps-smoke\chrome109profile"

    assert "function Stop-ProcessTreeByIdsBestEffort" in text
    assert "Stop-ProcessTreeByIdsBestEffort $cleanupChromeIds" in text
    assert "Stop-ProcessTreeByIds $cleanupChromeIds" not in text
    assert "function Split-CommandLineArgs" in text
    assert "$slashCount" in text
    assert "[char]92" in text
    assert "$argLower.StartsWith($prefix)" in text
    assert "$cmdLine -match $profilePattern" not in text
    assert ".Contains($markerLower)" not in text
    assert "taskkill /IM chrome.exe" not in text
    assert "function Stop-LegacyDistChromeBestEffort" in text
    legacy_preclean = text.split("function Invoke-LegacyPackageBuild", 1)[1].split(
        'Remove-PathWithRetry "build"',
        1,
    )[0]
    assert "Stop-LegacyDistChromeBestEffort" in legacy_preclean
    assert "Get-ChromeIdsByExecutablePath" in text
    assert "[string]::IsNullOrWhiteSpace" not in text
    assert _command_line_matches_exact_profile(
        f'chrome.exe --user-data-dir="{marker}" --app=http://127.0.0.1:5000', marker
    )
    assert not _command_line_matches_exact_profile(f'chrome.exe --user-data-dir="{marker}2"', marker)
    assert not _command_line_matches_exact_profile(f'chrome.exe --user-data-dir="{marker}_bak"', marker)
    assert not _command_line_matches_exact_profile(
        f'chrome.exe --note="before --user-data-dir={marker} after" --user-data-dir="d:\\other"',
        marker,
    )
    assert not _command_line_matches_exact_profile(
        f'chrome.exe "--app=http://127.0.0.1:5000/?q=\\" --user-data-dir={marker} \\"" --user-data-dir="d:\\other"',
        marker,
    )


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


def test_chrome_installer_stop_helper_matches_user_data_dir_argument_exactly():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "--user-data-dir=" in text
    assert "function Split-CommandLineArgs" in text
    assert "$slashCount" in text
    assert "[char]92" in text
    assert "$argLower.StartsWith($prefix)" in text
    assert "$profile -eq $exactMarker" in text
    assert "$profile.EndsWith($suffixMarker)" in text
    assert "[Regex]::Escape($exactMarker)" not in text
    assert "[Regex]::Escape($suffixMarker)" not in text
    assert "$cmd -match $suffixPattern" not in text
    assert "$cmd -match $exactPattern" not in text
    assert "$cmdLower.Contains($exactMarker)" not in text
    assert "$cmdLower.Contains($suffixMarker)" not in text
    assert "[string]::IsNullOrWhiteSpace" not in text


def test_chrome_installer_stop_helper_uses_current_user_profile_path_marker():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "CurrentUserChromeProfilePath" in text
    assert "ExpandConstant('{localappdata}\\APS\\Chrome109Profile')" in text
    assert "ApsChromeProfileSuffixMarker" in text
    assert "手动删除当前账户的 APS 浏览器用户数据目录" in text
    assert "BuildStopChromePowerShellParams(CurrentUserChromeProfilePath(), ApsChromeProfileSuffixMarker())" in text


def test_chrome_installer_stop_helper_uses_final_remaining_process_check():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "$failedStopIds=@()" in text
    assert "Stop-Process -Id $procId -Force -ErrorAction Stop } catch { $failedStopIds += [int]$procId }" in text
    assert "foreach ($item in @($remainingItems))" in text
    assert "Stop-Process -Id $procId -Force -ErrorAction Stop } catch { exit 1 }" not in text


def test_build_scripts_guard_vendor_and_launcher_path():
    repo_root = Path(_repo_root())
    onedir_text = (repo_root / "build_win7_onedir.bat").read_text(encoding="utf-8")
    installer_text = (repo_root / "build_win7_installer.bat").read_text(encoding="utf-8")
    package_text = (repo_root / ".limcode" / "skills" / "aps-package-win7" / "scripts" / "package_win7.ps1").read_text(
        encoding="utf-8"
    )

    assert "if exist vendor (" in onedir_text
    assert "vendor 目录不存在，跳过 vendor 数据目录。" in onedir_text
    assert r"assets\启动_排产系统_Chrome.bat" in installer_text
    assert "*Chrome*.bat" not in installer_text
    assert "[char[]](21551, 21160, 95, 25490, 20135, 31995, 32479" in package_text
    assert "*Chrome*.bat" not in package_text


def test_chrome_installer_remains_non_target_for_precleanup():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "function PrepareToInstall" not in text
    assert "Chrome109Profile" in text
