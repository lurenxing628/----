"""回归测试：GraphReady v2 专属长跑证据合同。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests._support.benchmark_git_state import proof_binding_status
from tests._support.optimizer_compare_algorithms import POSTHOC_UPPER_BOUND_SEMANTICS
from tests._support.optimizer_graph_ready_v2_long_run import (
    GRAPH_READY_V2_NO_REPAIR_PROFILE,
    build_graph_ready_v2_long_run,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_graph_ready_v2_long_run_uses_compare_matrix_and_reports_v2_summary() -> None:
    payload = build_graph_ready_v2_long_run(seeds=10, workers=1)
    rows = payload["comparison"]["rows"]
    v2_rows = [row for row in rows if row["algorithm_profile"] == GRAPH_READY_V2_NO_REPAIR_PROFILE]
    summary = payload["v2_summary"]

    assert payload["status"] == "passed"
    assert len(v2_rows) == 10
    assert summary["algorithm_profile"] == GRAPH_READY_V2_NO_REPAIR_PROFILE
    assert summary["seed_count"] == 10
    assert summary["portfolio_all_comparison_semantics"] == POSTHOC_UPPER_BOUND_SEMANTICS
    assert summary["portfolio_all_win_loss_status"] == "not_comparable"
    assert summary["proof_binding_status"] in {"clean_worktree", "unbound_dirty_worktree"}
    assert set(["algorithm_profile", "algorithm_version", "seed"]).issubset(set(payload["ratchet_key_fields"]))


def test_graph_ready_v2_long_run_rejects_short_seed_count() -> None:
    with pytest.raises(ValueError, match="at least 10 seeds"):
        build_graph_ready_v2_long_run(seeds=9, profiles=["greedy"])


def test_dirty_git_state_never_becomes_clean_proof() -> None:
    assert proof_binding_status(dirty_worktree=True) == "unbound_dirty_worktree"
    assert proof_binding_status(dirty_worktree=False) == "clean_worktree"


def test_graph_ready_v2_long_run_script_no_write_does_not_create_output(tmp_path: Path) -> None:
    repo_root = _repo_root()
    script = repo_root / "tests" / "_scripts_e2e" / "benchmark_optimizer_graph_ready_v2_long_run.py"
    output_path = tmp_path / "graph-ready-v2-long-run.json"

    out = subprocess.check_output(
        [
            sys.executable,
            str(script),
            "--profiles",
            "greedy,graph_ready_v2_no_repair,portfolio_all",
            "--seeds",
            "10",
            "--workers",
            "1",
            "--output",
            str(output_path),
            "--no-write",
        ],
        cwd=str(repo_root),
        text=True,
    )

    payload = json.loads(out)
    assert payload["long_run"]["status"] == "passed"
    assert payload["long_run"]["v2_summary"]["algorithm_profile"] == GRAPH_READY_V2_NO_REPAIR_PROFILE
    assert not output_path.exists()
