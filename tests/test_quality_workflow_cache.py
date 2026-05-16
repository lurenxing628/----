from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "quality.yml"
QUALITY_GATE_COMMAND = "python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache"
DEPENDENCY_HASH = "${{ hashFiles('requirements.txt', 'requirements-dev.txt') }}"
TOOLING_HASH = (
    "${{ hashFiles('.github/workflows/quality.yml', '.pre-commit-config.yaml', "
    "'scripts/run_quality_gate.py', 'scripts/run_daily_quality_gate.py', "
    "'tools/**/*.py', 'pyrightconfig.gate.json', 'pyrightconfig.tools.json') }}"
)


def _quality_steps() -> List[Dict[str, Any]]:
    workflow = yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    return list(workflow["jobs"]["quality-gate"]["steps"])


def _step_by_name(steps: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
    return next(step for step in steps if step.get("name") == name)


def _cache_paths(step: Dict[str, Any]) -> List[str]:
    path_value = str(step["with"]["path"])
    return [line.strip() for line in path_value.splitlines() if line.strip()]


def test_quality_workflow_long_gate_cache_key_is_bound_to_tooling_and_sha() -> None:
    steps = _quality_steps()
    restore_step = _step_by_name(steps, "恢复 long gate cache")
    save_step = _step_by_name(steps, "保存 long gate cache")

    restore_key = str(restore_step["with"]["key"])
    save_key = str(save_step["with"]["key"])
    restore_keys = str(restore_step["with"]["restore-keys"])
    expected_prefix = f"quality-long-gate-${{{{ runner.os }}}}-py38-deps-{DEPENDENCY_HASH}-tooling-{TOOLING_HASH}-"

    assert restore_key.startswith(expected_prefix)
    assert save_key.startswith(expected_prefix)
    assert "-sha-${{ github.sha }}-run-${{ github.run_id }}-${{ github.run_attempt }}" in restore_key
    assert "-sha-${{ github.sha }}-run-${{ github.run_id }}-${{ github.run_attempt }}" in save_key
    assert restore_keys.strip() == expected_prefix
    assert "${{ github.sha }}" not in restore_keys
    assert "${{ github.run_id }}" not in restore_keys
    assert "${{ github.run_attempt }}" not in restore_keys


def test_quality_workflow_long_gate_cache_only_saves_trusted_runtime_outputs() -> None:
    steps = _quality_steps()
    restore_step = _step_by_name(steps, "恢复 long gate cache")
    run_step = _step_by_name(steps, "执行统一质量门禁")
    save_step = _step_by_name(steps, "保存 long gate cache")
    restore_index = steps.index(restore_step)
    run_index = steps.index(run_step)
    save_index = steps.index(save_step)

    assert restore_index < run_index < save_index
    assert run_step["run"] == QUALITY_GATE_COMMAND
    assert "success()" in str(save_step["if"])
    assert "github.event.pull_request.head.repo.full_name == github.repository" in str(save_step["if"])

    restore_paths = _cache_paths(restore_step)
    save_paths = _cache_paths(save_step)
    assert save_paths == restore_paths
    assert "evidence/Conformance/quickref_vs_routes.md" not in save_paths
    assert all(path.startswith("evidence/QualityGate/") for path in save_paths)
