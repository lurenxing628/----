from __future__ import annotations

import json
from pathlib import Path

from tools import benchmark_full_test_debt_shards as benchmark


def test_build_distribution_reports_serial_and_parallel_counts(tmp_path: Path) -> None:
    payload_path = tmp_path / "current_full_test_debt.json"
    payload_path.write_text(
        json.dumps(
            {
                "collected_nodeids": [
                    "tests/test_run_quality_gate.py::test_a",
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
