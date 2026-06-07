"""回归测试：full_test_debt_shards 的并行分片契约——classify_nodeid 把高风险/启动回归类用例（含全部 iter_startup_regressions）判为 serial、纯 helper 用例判为 parallel，split_nodeids 把 nodeid 切成串行集 + 若干分片且无重复无遗漏，并对重复 nodeid 与非法 shard_count 抛 ValueError。"""

from __future__ import annotations

import pytest

from tools.full_test_debt_shards import classify_nodeid, split_nodeids
from tools.test_registry import iter_startup_regressions


@pytest.mark.parametrize(
    "nodeid",
    [
        "tests/regression_ui_browser_geometry_smoke.py::test_ui_pages_do_not_create_body_level_overflow_in_real_browser",
        "tests/test_long_gate_full_test_debt_cache.py::test_runner_records_nodeid_incremental_mode_without_running_whole_entry",
        "tests/test_long_gate_cli_controls.py::test_controls",
        "tests/test_long_gate_summary_output.py::test_summary",
        "tests/test_long_gate_manifest.py::test_manifest",
        "tests/test_run_quality_gate.py::test_quality_gate",
        "tests/test_architecture_fitness.py::test_repository_bundle_consumption_does_not_drift",
        "tests/test_win7_launcher_runtime_paths.py::test_runtime_path",
        "tests/regression_runtime_stop_cli.py::regression_runtime_stop_cli",
        "tests/regression_check_manual_layout_runtime_resolution.py::test_check_manual_layout_runtime_resolution",
        "tests/regression_validate_dist_runtime_identity.py::test_validate_dist_runtime_identity_contract",
    ],
)
def test_classify_nodeid_keeps_risky_tests_serial(nodeid: str) -> None:
    assert classify_nodeid(nodeid) == "serial"


def test_classify_nodeid_allows_plain_helper_tests_parallel() -> None:
    assert classify_nodeid("tests/test_public_formatter.py::test_formats_public_label") == "parallel"


def test_classify_nodeid_keeps_all_startup_regressions_serial() -> None:
    assert iter_startup_regressions()
    assert {
        path
        for path in iter_startup_regressions()
        if classify_nodeid(f"{path}::test_sample") != "serial"
    } == set()


def test_split_nodeids_has_no_duplicates_or_omissions() -> None:
    nodeids = [
        "tests/test_public_a.py::test_one",
        "tests/test_public_a.py::test_two",
        "tests/test_public_b.py::test_one",
        "tests/regression_ui_browser_geometry_smoke.py::test_browser",
        "tests/test_long_gate_required_regression_cache.py::test_runner",
    ]

    serial, shards = split_nodeids(nodeids, 2)
    flattened = [*serial, *[nodeid for shard in shards for nodeid in shard]]

    assert sorted(flattened) == sorted(nodeids)
    assert len(flattened) == len(nodeids)
    assert serial == [
        "tests/regression_ui_browser_geometry_smoke.py::test_browser",
        "tests/test_long_gate_required_regression_cache.py::test_runner",
    ]
    assert shards == [
        ["tests/test_public_a.py::test_one", "tests/test_public_a.py::test_two"],
        ["tests/test_public_b.py::test_one"],
    ]


def test_split_nodeids_rejects_duplicate_nodeids() -> None:
    with pytest.raises(ValueError, match="duplicate nodeid"):
        split_nodeids(["tests/test_a.py::test_a", "tests/test_a.py::test_a"], 2)


def test_split_nodeids_rejects_invalid_shard_count() -> None:
    with pytest.raises(ValueError, match="shard_count"):
        split_nodeids(["tests/test_a.py::test_a"], 0)
