from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_run_quality_gate():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("scripts.run_quality_gate", None)
    return importlib.import_module("scripts.run_quality_gate")


def test_assert_no_active_runtime_reports_cleanup_hint_when_uncertain(monkeypatch):
    module = _import_run_quality_gate()

    monkeypatch.setattr(
        module,
        "_load_runtime_state",
        lambda: (
            {"pid": 321, "host": "127.0.0.1", "port": 0, "exe_path": ""},
            {"pid": 321, "exe_path": ""},
            {"contract_path": "C:/tmp/aps_runtime.json", "lock_path": "C:/tmp/aps_runtime.lock"},
        ),
    )
    monkeypatch.setattr(module, "_pid_signal", lambda payload: ("unknown", 321, None, ""))
    monkeypatch.setattr(module, "_health_signal", lambda contract: ("absent", None, None))

    with pytest.raises(module.QualityGateError) as exc_info:
        module._assert_no_active_runtime()

    message = str(exc_info.value)
    assert "活动实例判定不确定" in message
    assert "手动删除后重试" in message
    assert "contract=C:/tmp/aps_runtime.json" in message
    assert "lock=C:/tmp/aps_runtime.lock" in message
    assert "缺少 exe_path" in message
    assert "缺少运行时契约" in message
    assert "无法做健康探测" in message


def test_assert_no_active_runtime_allows_stale_trace_and_prints_paths(monkeypatch, capsys):
    module = _import_run_quality_gate()

    monkeypatch.setattr(
        module,
        "_load_runtime_state",
        lambda: (
            {"pid": 0, "host": "127.0.0.1", "port": 5000, "exe_path": sys.executable},
            None,
            {"contract_path": "C:/tmp/aps_runtime.json", "lock_path": "C:/tmp/aps_runtime.lock"},
        ),
    )
    monkeypatch.setattr(module, "_pid_signal", lambda payload: ("stale", 0, False, sys.executable))
    monkeypatch.setattr(module, "_health_signal", lambda contract: ("stale", "127.0.0.1", 5000))

    module._assert_no_active_runtime()

    stdout = capsys.readouterr().out
    assert "陈旧运行时痕迹" in stdout
    assert "contract=C:/tmp/aps_runtime.json" in stdout
    assert "lock=C:/tmp/aps_runtime.lock" in stdout


def test_main_includes_ledger_check_before_startup_regression(monkeypatch):
    module = _import_run_quality_gate()

    calls = []

    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)

    def fake_run_command(display, args, capture_output=False):
        calls.append((display, list(args), bool(capture_output)))
        if display == "python -m ruff --version":
            return "ruff 0.15.4"
        return ""

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main() == 0

    displays = [display for display, _args, _capture_output in calls]
    assert "python scripts/sync_debt_ledger.py check" in displays
    assert displays.index("python -m pytest -q tests/test_architecture_fitness.py") < displays.index(
        "python scripts/sync_debt_ledger.py check"
    )
    assert displays.index("python scripts/sync_debt_ledger.py check") < displays.index(
        "python -m pytest -q " + " ".join(module.STARTUP_REGRESSION_ARGS)
    )
