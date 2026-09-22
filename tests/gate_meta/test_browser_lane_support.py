"""Browser lane entry points share a runtime without tools importing scripts."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from tests._support.paths import REPO_ROOT
from tools import browser_lane_support as support


def test_importing_sample_does_not_load_script_entry_points() -> None:
    probe = (
        "import sys; import tools.browser_lane_sample; "
        "assert not [name for name in sys.modules if name == 'scripts' or name.startswith('scripts.')]; "
        "assert tools.browser_lane_sample.lane_targets()"
    )
    result = subprocess.run([sys.executable, "-c", probe], cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("script", ["run_browser_test_lane.py", "run_workbench_opt_in_browser.py"])
def test_script_entry_points_list_targets_from_another_directory(script, tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / script), "--list"],
        cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines and all(line.startswith("tests/") for line in lines)
    if script == "run_browser_test_lane.py":
        assert lines == support.lane_targets()


def test_runtime_overrides_are_preserved_without_mutating_process_environment(tmp_path, monkeypatch) -> None:
    node, browser = tmp_path / "node", tmp_path / "browser"
    node.touch()
    browser.touch()
    monkeypatch.setenv("WORKBENCH_NODE", str(node))
    monkeypatch.setenv("WORKBENCH_BROWSER", str(browser))
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("COLORTERM", "truecolor")
    monkeypatch.setenv("NODE_PATH", str(tmp_path / "custom-modules"))
    monkeypatch.setattr(support, "BUNDLED_NODE", tmp_path / "bundle")
    before = dict(os.environ)
    env = support.runtime_environment()
    assert env["WORKBENCH_NODE"] == str(node)
    assert env["WORKBENCH_BROWSER"] == str(browser)
    assert env["NO_COLOR"] == "1"
    assert "FORCE_COLOR" not in env and "COLORTERM" not in env
    assert env["NODE_PATH"].split(os.pathsep) == [str(tmp_path / "custom-modules"), str(tmp_path / "bundle/node_modules")]
    assert dict(os.environ) == before


def test_missing_runtime_still_fails_before_running_tests(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_NODE", str(tmp_path / "missing-node"))
    monkeypatch.setenv("WORKBENCH_BROWSER", str(tmp_path / "missing-browser"))
    with pytest.raises(SystemExit) as error:
        support.runtime_environment()
    assert "WORKBENCH_NODE" in str(error.value)
    assert "WORKBENCH_BROWSER" in str(error.value)


def test_persistent_browser_precedes_temporary_fallback(tmp_path, monkeypatch) -> None:
    persistent, temporary = tmp_path / "persistent", tmp_path / "temporary"
    monkeypatch.setattr(support, "DEFAULT_BROWSER_CANDIDATES", (persistent, temporary))
    assert support.default_browser() == str(persistent)
    temporary.touch()
    assert support.default_browser() == str(temporary)
    persistent.touch()
    assert support.default_browser() == str(persistent)


def test_summary_uses_final_counts_and_keeps_skip_reasons() -> None:
    log = "1 passed in 1.00s\nSKIPPED [1] example: missing fixture\n=== 3 passed, 1 skipped in 2.50s ===\n"
    assert support.parse_summary(log) == {"passed": 3, "skipped": 1}
    assert support.skipped_reasons(log) == ["SKIPPED [1] example: missing fixture"]
    assert support.parse_summary("no pytest summary") == {}
