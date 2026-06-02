from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests import ui_geometry_browser_support as browser
from tests import ui_geometry_runtime_support as runtime


def test_find_chrome_explicit_bad_path_does_not_fallback(monkeypatch, tmp_path: Path) -> None:
    fallback = tmp_path / "fallback-chrome"
    fallback.write_text("fallback\n", encoding="utf-8")
    monkeypatch.setenv("APS_CHROME_PATH", str(tmp_path / "missing-chrome"))
    monkeypatch.setattr(runtime, "_chrome_default_candidates", lambda: (("PATH:google-chrome", str(fallback)),))

    with pytest.raises(pytest.fail.Exception) as exc_info:
        runtime._find_chrome()

    message = str(exc_info.value)
    assert "browser_env_bad_chrome_path" in message
    assert "APS_CHROME_PATH" in message
    assert "missing-chrome" in message


def test_find_chrome_missing_local_can_skip(monkeypatch) -> None:
    monkeypatch.delenv("APS_CHROME_PATH", raising=False)
    monkeypatch.delenv("APS_BROWSER_SMOKE_REQUIRED", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(runtime, "_chrome_default_candidates", lambda: ())

    with pytest.raises(pytest.skip.Exception) as exc_info:
        runtime._find_chrome()

    assert "browser_env_missing_chrome" in str(exc_info.value)


def test_find_chrome_required_missing_fails(monkeypatch) -> None:
    monkeypatch.delenv("APS_CHROME_PATH", raising=False)
    monkeypatch.setenv("APS_BROWSER_SMOKE_REQUIRED", "1")
    monkeypatch.setattr(runtime, "_chrome_default_candidates", lambda: ())

    with pytest.raises(pytest.fail.Exception) as exc_info:
        runtime._find_chrome()

    message = str(exc_info.value)
    assert "browser_env_missing_chrome" in message
    assert "APS_BROWSER_SMOKE_REQUIRED" in message


def test_find_chrome_version_failure_reports_stdout_stderr(monkeypatch, tmp_path: Path) -> None:
    chrome = tmp_path / "chrome"
    chrome.write_text("not really chrome\n", encoding="utf-8")
    monkeypatch.setenv("APS_CHROME_PATH", str(chrome))
    monkeypatch.setattr(
        runtime,
        "_probe_chrome_version",
        lambda _path: subprocess.CompletedProcess([str(chrome), "--version"], 7, "version out", "version err"),
    )

    with pytest.raises(pytest.fail.Exception) as exc_info:
        runtime._find_chrome()

    message = str(exc_info.value)
    assert "browser_env_chrome_version_failed" in message
    assert "version out" in message
    assert "version err" in message


def test_find_node_missing_local_can_skip(monkeypatch) -> None:
    monkeypatch.delenv("APS_BROWSER_SMOKE_REQUIRED", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(runtime.shutil, "which", lambda _name: None)

    with pytest.raises(pytest.skip.Exception) as exc_info:
        runtime._find_node_with_browser_runtime()

    assert "browser_env_missing_node" in str(exc_info.value)


def test_find_node_required_missing_fails(monkeypatch) -> None:
    monkeypatch.setenv("APS_BROWSER_SMOKE_REQUIRED", "1")
    monkeypatch.setattr(runtime.shutil, "which", lambda _name: None)

    with pytest.raises(pytest.fail.Exception) as exc_info:
        runtime._find_node_with_browser_runtime()

    assert "browser_env_missing_node" in str(exc_info.value)


def test_find_node_capability_failure_reports_version(monkeypatch) -> None:
    monkeypatch.setenv("APS_BROWSER_SMOKE_REQUIRED", "1")
    monkeypatch.setattr(runtime.shutil, "which", lambda _name: "/tmp/node")
    monkeypatch.setattr(runtime.os.path, "realpath", lambda value: str(value))

    def fake_run(args, *, timeout=10):
        if list(args) == ["/tmp/node", "--version"]:
            return subprocess.CompletedProcess(list(args), 0, "v18.0.0", "")
        return subprocess.CompletedProcess(list(args), 1, "", "missing WebSocket")

    monkeypatch.setattr(runtime, "_run_probe_command", fake_run)

    with pytest.raises(pytest.fail.Exception) as exc_info:
        runtime._find_node_with_browser_runtime()

    message = str(exc_info.value)
    assert "browser_env_node_capability_failed" in message
    assert "v18.0.0" in message
    assert "missing WebSocket" in message
    assert "当前检查的是能力，不是只看版本号" in message


def test_run_chrome_probe_spawn_error_reports_kind(tmp_path: Path) -> None:
    node = runtime._resolve_node_with_browser_runtime()
    if node.failure_kind:
        pytest.skip(node.message)
    chrome_info = runtime.ChromeRuntimeInfo(
        chrome_path=str(tmp_path / "missing-chrome"),
        chrome_source="APS_CHROME_PATH",
        chrome_version_stdout="Fake Chrome 120",
        chrome_version_returncode=0,
        exists=True,
        explicit_config=True,
    )

    with pytest.raises(AssertionError) as exc_info:
        browser._run_chrome_geometry_probe(
            chrome_path=str(tmp_path / "missing-chrome"),
            node_path=node.node_path,
            base_url="http://127.0.0.1:9",
            tmp_path=tmp_path,
            chrome_info=chrome_info,
            node_info=node,
        )

    message = str(exc_info.value)
    assert "chrome_spawn_failed" in message
    assert "runtime_context" in message
    assert "APS_CHROME_PATH" in message
    assert "Fake Chrome 120" in message
    assert node.node_realpath in message


def test_chrome_geometry_probe_requests_graceful_chrome_exit_before_sigkill() -> None:
    source = runtime.UI_GEOMETRY_PROBE_SOURCE.read_text(encoding="utf-8")

    assert 'chrome.kill("SIGTERM")' in source
    assert "if (!chromeExitWait.exited)" in source
    assert 'try { chrome.kill("SIGKILL"); } catch {}\n              const chromeExitWait' not in source
