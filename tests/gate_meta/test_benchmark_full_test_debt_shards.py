"""回归测试：守护 benchmark_full_test_debt_shards 的分片基准工具——build_distribution 按 nodeid 统计串行/并行各分片数量与不均衡度，_parse_counts 去重并拒绝空分片数列表，main 按 argv 的 mode/shard-counts 正确驱动每个分片数并透传 allow-dirty-worktree-proof。"""

from __future__ import annotations

import json
from pathlib import Path

from tools import benchmark_full_test_debt_shards as benchmark
from tools.full_test_debt_shards import split_nodeids


def test_optimizer_matrix_fixture_is_not_split_between_serial_and_parallel() -> None:
    matrix = "tests/algorithm/test_optimizer_quality_matrix_contract.py::"
    nodes = [matrix + "test_real_matrix_minimum_coverage_feasibility_and_provenance",
             matrix + "test_large_real_runtime_regression_fails_and_tolerant_noise_passes"]
    serial, parallel = split_nodeids(nodes, 3)
    assert serial == nodes
    assert parallel == [[], [], []]


def test_algorithm_comparison_modules_run_in_one_serial_shard() -> None:
    modules = ("compare_algorithms_contract", "smtwt_compare_algorithms_contract",
               "graph_ready_v2_long_run_contract", "benchmark_timing_contract",
               "end_to_end_matrix_contract", "end_to_end_snapshot_contract", "benchmark_ratchet_gate")
    nodes = ["tests/algorithm/test_optimizer_" + name + ".py::test_real_case" for name in modules]
    serial, parallel = split_nodeids(nodes, 3)
    assert serial == nodes
    assert parallel == [[], [], []]


def test_build_distribution_reports_serial_and_parallel_counts(tmp_path: Path) -> None:
    payload_path = tmp_path / "current_full_test_debt.json"
    payload_path.write_text(
        json.dumps(
            {
                "collected_nodeids": [
                    "tests/gate_meta/test_run_quality_gate.py::test_a",
                    "tests/test_alpha.py::test_a",
                    "tests/test_alpha.py::test_b",
                    "tests/test_beta.py::test_a",
                ]
            }
        ),
        encoding="utf-8",
    )

    result = benchmark.build_distribution(payload_path, [2])

    assert result["total_count"] == 4
    row = result["distributions"][0]
    assert row["shard_count"] == 2
    assert row["serial_count"] == 1
    assert row["parallel_counts"] == [2, 1]
    assert row["parallel_imbalance"] == 1


def test_parse_counts_dedupes_and_rejects_empty() -> None:
    assert benchmark._parse_counts("3,4,3") == [3, 4]

    try:
        benchmark._parse_counts("")
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("empty count list should fail")


def test_main_honors_argv_mode_run_and_shard_counts(monkeypatch, tmp_path: Path, capsys) -> None:
    payload_path = tmp_path / "current_full_test_debt.json"
    payload_path.write_text(
        json.dumps({"collected_nodeids": ["tests/test_alpha.py::test_a", "tests/test_beta.py::test_b"]}),
        encoding="utf-8",
    )
    calls = []

    def fake_run_shard_count(shard_count: int, *, allow_dirty_worktree_proof: bool = False):
        calls.append((shard_count, allow_dirty_worktree_proof))
        return {
            "shard_count": shard_count,
            "duration_s": 0.0,
            "returncode": 0,
            "command": ["fake", str(shard_count)],
        }

    monkeypatch.setattr(benchmark, "_run_shard_count", fake_run_shard_count)

    assert benchmark.main(
        [
            "--payload",
            str(payload_path),
            "--mode",
            "run",
            "--shard-counts",
            "2,5",
            "--allow-dirty-worktree-proof",
        ]
    ) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "run"
    assert [row["shard_count"] for row in output["runs"]] == [2, 5]
    assert calls == [(2, True), (5, True)]
