"""The new workbench evidence gate is explicit and cannot pass on missing tests."""

import sys

import pytest

import scripts.run_daily_quality_gate as daily_gate


def _empty_scope():
    return daily_gate.DailyGateScope(
        daily_gate.ChangedPathSet([], True, "test scope"),
        daily_gate.ImpactPlan([], [], False, "test scope"),
        daily_gate.RuffPlan([], False, "test scope"),
    )


def _stub_daily_steps(monkeypatch, evidence_returncode=0):
    calls = []
    monkeypatch.setattr(daily_gate, "build_daily_gate_scope", lambda **kwargs: _empty_scope())
    monkeypatch.setattr(daily_gate, "_run_collect_only", lambda env: (0, ""))
    monkeypatch.setattr(daily_gate, "_failure_log_path", lambda: None)

    def run_step(command, env):
        calls.append(command)
        if "tests/workbench/ui_refinement_gate.py" in command:
            return evidence_returncode, "UI evidence fixture\n"
        return 0, ""

    monkeypatch.setattr(daily_gate, "_run_step_streaming", run_step)
    return calls


def test_default_commands_and_environment_do_not_enable_ui_evidence(monkeypatch):
    monkeypatch.setenv("WORKBENCH_UI_EVIDENCE", "/tmp/ignored-evidence")
    assert daily_gate._parse_args([]).workbench_ui_evidence is None
    assert daily_gate._commands([], _empty_scope().ruff_plan) == [
        (
            "block staged runtime artifacts",
            [sys.executable, "tools/git_hook_checks.py", "check-staged-artifacts"],
            False,
        ),
        (
            "focused pytest",
            [sys.executable, "-m", "pytest", "-q", "-rfE", *daily_gate.FOCUSED_PYTEST_NODEIDS],
            False,
        ),
    ]
    calls = _stub_daily_steps(monkeypatch)
    assert daily_gate.main([]) == 0
    assert len(calls) == 2
    assert not any("ui_refinement_gate.py" in " ".join(command) for command in calls)


def test_opt_in_appends_independent_gate_without_changing_existing_steps():
    scope = _empty_scope()
    evidence = "evidence/UI checks with spaces"
    base = daily_gate._commands(["tests/regression_stub.py"], scope.ruff_plan)
    enabled = daily_gate._commands(
        ["tests/regression_stub.py"], scope.ruff_plan, workbench_ui_evidence=evidence,
    )
    assert enabled[:-1] == base
    assert enabled[-1] == (
        "workbench UI refinement evidence",
        [sys.executable, "-B", "tests/workbench/ui_refinement_gate.py", "--evidence-dir", evidence],
        False,
    )


def test_main_forwards_explicit_directory_as_one_argument(monkeypatch):
    calls = _stub_daily_steps(monkeypatch)
    evidence = "evidence/UI checks with spaces"
    assert daily_gate.main(["--workbench-ui-evidence", evidence]) == 0
    assert len(calls) == 3
    assert calls[-1] == [
        sys.executable, "-B", "tests/workbench/ui_refinement_gate.py", "--evidence-dir", evidence,
    ]


@pytest.mark.parametrize("returncode", [1, 2, 5])
def test_evidence_failure_or_no_tests_cannot_be_swallowed(monkeypatch, capsys, returncode):
    _stub_daily_steps(monkeypatch, evidence_returncode=returncode)
    assert daily_gate.main(["--workbench-ui-evidence", "evidence/checks"]) == returncode
    captured = capsys.readouterr()
    assert "failed: workbench UI refinement evidence" in captured.err
    assert "[daily-fast-gate] passed" not in captured.out


@pytest.mark.parametrize("value", ["", " \t "])
def test_empty_opt_in_directory_is_a_usage_error(value):
    with pytest.raises(SystemExit) as error:
        daily_gate._parse_args(["--workbench-ui-evidence", value])
    assert error.value.code == 2
