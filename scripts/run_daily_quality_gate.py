#!/usr/bin/env python3
"""Run the fast local development gate.

This script is intentionally smaller than scripts/run_quality_gate.py. It is a
push-time smoke gate for obvious mistakes, not the final clean proof.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FOCUSED_PYTEST_NODEIDS: Tuple[str, ...] = (
    "tests/test_long_gate_full_test_debt_cache.py::test_validated_previous_success_accepts_zero_returncode",
    "tests/test_long_gate_full_test_debt_cache.py::test_nodeid_incremental_plan_selects_changed_test_file_nodeids",
    "tests/test_long_gate_required_regression_cache.py::test_required_entry_comes_from_real_command_plan_and_enables_only_next7",
    "tests/test_long_gate_startup_regression_cache.py::test_startup_entry_comes_from_real_command_plan_and_enables_only_next6",
    "tests/test_scheduler_batches_page_viewmodel.py::test_batches_filter_state_preserves_default_and_empty_status_contract",
    "tests/test_scheduler_batches_page_viewmodel.py::test_batch_rows_filter_ready_and_add_public_labels",
    "tests/test_ui_geometry_html_contract.py::test_ui_smoke_pages_render_expected_html_contract",
    "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
)


def _gate_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("APS_SKIP_QUALITY_GATE", None)
    return env


def _commands() -> List[Tuple[str, List[str]]]:
    return [
        (
            "block staged runtime artifacts",
            [sys.executable, "tools/git_hook_checks.py", "check-staged-artifacts"],
        ),
        (
            "pytest collect-only",
            [sys.executable, "-m", "pytest", "--collect-only", "tests", "-q"],
        ),
        (
            "ruff check",
            [sys.executable, "-m", "ruff", "check"],
        ),
        (
            "focused pytest",
            [sys.executable, "-m", "pytest", "-q", *FOCUSED_PYTEST_NODEIDS],
        ),
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv:
        print("run_daily_quality_gate.py does not accept arguments", file=sys.stderr)
        return 2

    print("FAST DAILY GATE ONLY: not final clean proof", flush=True)
    print("快速日常门禁只挡明显问题，不声明 full-test-debt / clean proof。", flush=True)
    print(
        "最终收口必须运行：PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 "
        ".venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache",
        flush=True,
    )
    env = _gate_env()
    for index, (label, command) in enumerate(_commands(), start=1):
        print(f"[daily-fast-gate] {index}/{len(_commands())} {label}", flush=True)
        returncode = subprocess.call(command, cwd=REPO_ROOT, env=env)
        if int(returncode) != 0:
            print(f"[daily-fast-gate] failed: {label} returncode={returncode}", file=sys.stderr, flush=True)
            return int(returncode)
    print("[daily-fast-gate] passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
