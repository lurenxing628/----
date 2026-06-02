from __future__ import annotations

from pathlib import Path

from tools import git_hook_checks, quality_gate_shared
from tools.test_registry_data import REQUIRED_REGRESSION_COMMON_SCOPES
from tools.test_registry_groups_misc import MISC_REQUIRED_REGRESSION_GROUPS
from tools.test_registry_groups_scheduler import SCHEDULER_REQUIRED_REGRESSION_GROUPS

REGISTRY_SPLIT_FILES = {
    "tools/test_registry_data.py",
    "tools/test_registry_groups_misc.py",
    "tools/test_registry_groups_scheduler.py",
}

REPORT_CHAIN_SCOPES = {
    "web/routes/reports*.py",
    "core/services/report/**/*.py",
    "tests/reports_workbench_backlink_helpers.py",
}

GEOMETRY_SPLIT_SCOPES = {
    "tests/ui_geometry_contract_data.py",
    "tests/ui_geometry_runtime_support.py",
    "tests/ui_geometry_browser_support.py",
    "tests/ui_geometry_probe.mjs",
    "tests/ui_geometry_cdp_client.mjs",
    "tests/ui_geometry_probe_page_eval.mjs",
}


def _group(group_id: str):
    for item in SCHEDULER_REQUIRED_REGRESSION_GROUPS + MISC_REQUIRED_REGRESSION_GROUPS:
        if item["group_id"] == group_id:
            return item
    raise AssertionError(f"缺少回归测试分组：{group_id}")


def test_registry_split_files_are_quality_gate_inputs() -> None:
    common_config = set(REQUIRED_REGRESSION_COMMON_SCOPES["config_file_scopes"])
    common_tools = set(REQUIRED_REGRESSION_COMMON_SCOPES["tool_file_scopes"])
    quality_group = _group("quality_gate")

    assert REGISTRY_SPLIT_FILES <= common_config
    assert REGISTRY_SPLIT_FILES <= common_tools
    assert REGISTRY_SPLIT_FILES <= set(quality_group["input_file_scopes"])
    assert REGISTRY_SPLIT_FILES <= set(quality_group["tool_file_scopes"])


def test_reports_and_geometry_split_files_are_group_scopes() -> None:
    reports_group = _group("scheduler_analysis_gantt_reports_week_plan")
    ui_group = _group("ui_layout_presenters_system")

    assert REPORT_CHAIN_SCOPES <= set(reports_group["input_file_scopes"])
    assert GEOMETRY_SPLIT_SCOPES <= set(ui_group["input_file_scopes"])


def test_quality_gate_ignored_runtime_outputs_are_blocked_by_git_hook() -> None:
    gitignore_source = Path(".gitignore").read_text(encoding="utf-8")
    blocked = git_hook_checks._blocked_paths(
        ["evidence/QualityGate/silent_fallback_inventory_acceptance/report.json"]
    )

    assert "evidence/QualityGate/silent_fallback_inventory_acceptance/" in gitignore_source
    assert blocked == [
        (
            "evidence/QualityGate/silent_fallback_inventory_acceptance/report.json",
            "silent fallback 验收清单是运行产物，应由当前门禁重新生成",
        )
    ]


def test_real_browser_geometry_smoke_stays_manual_acceptance_target() -> None:
    smoke_test = "tests/regression_ui_browser_geometry_smoke.py"
    ui_group = _group("ui_layout_presenters_system")

    assert smoke_test not in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert smoke_test not in quality_gate_shared.QUALITY_GATE_SOURCE_FILES
    assert smoke_test not in set(ui_group["target_paths"])
    assert "tests/test_ui_browser_geometry_env.py" in set(ui_group["target_paths"])
    assert "tests/test_ui_geometry_html_contract.py" in set(ui_group["target_paths"])
