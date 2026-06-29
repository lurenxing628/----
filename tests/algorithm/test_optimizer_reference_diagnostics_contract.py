"""回归测试：GraphReady v2 前置参考量尺诊断。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests._support.optimizer_reference_diagnostics import build_reference_diagnostics


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_reference_diagnostics_separates_comparable_and_not_comparable_references() -> None:
    payload = build_reference_diagnostics(objective_name="min_overdue")
    rows = payload["references"]
    by_slug = {str(row["case_slug"]): row for row in rows}

    assert payload["status"] == "passed"
    assert by_slug["tiny-sgs-single-machine"]["bound_is_objective_comparable"] is True
    assert by_slug["tiny-sgs-single-machine"]["bound_metric"] == "objective_score"
    assert by_slug["jackson-single-machine-preemptive"]["bound_is_objective_comparable"] is False
    assert by_slug["jackson-single-machine-preemptive"]["not_comparable_reason"]
    assert by_slug["wtsds-loader-contract"]["changeover_baseline_status"] == "not_available"
    assert by_slug["cicirello-sdst-loader-contract"]["loader_contract"]["tracked_data"] == "not_written"
    assert payload["tracked_external_data_written"] is False


def test_jackson_reference_is_not_comparable_even_for_tardiness_named_objective() -> None:
    payload = build_reference_diagnostics(objective_name="min_tardiness")
    by_slug = {str(row["case_slug"]): row for row in payload["references"]}

    assert by_slug["jackson-single-machine-preemptive"]["bound_is_objective_comparable"] is False
    assert "最大迟延" in by_slug["jackson-single-machine-preemptive"]["not_comparable_reason"]


def test_reference_diagnostics_script_prints_without_writing_when_no_write() -> None:
    repo_root = _repo_root()
    script = repo_root / "tests" / "_scripts_e2e" / "benchmark_optimizer_reference_diagnostics.py"

    out = subprocess.check_output(
        [str(repo_root / ".venv" / "bin" / "python"), str(script), "--no-write"],
        cwd=str(repo_root),
        text=True,
    )

    assert '"status": "passed"' in out
    assert "jackson-single-machine-preemptive" in out
    assert "wtsds-loader-contract" in out
