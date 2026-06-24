"""契约测试：质量门禁回归测试注册表（test_registry 拆分文件 + quality_gate_shared）的 scope 绑定——拆分后的注册表文件本身、报表链路与几何探针等拆分文件都被纳入对应分组的 input/tool scope，工作台流程/历史方案标签/方案身份/资源派工/运行执行等关键回归测试齐备登记为 required 且归入正确分组，开发者指南列出的回归清单与注册表一致，门禁运行产物与全景图生成物均被 git hook 拦截提交。"""

from __future__ import annotations

import ast
import json
import re
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
    "tests/web_pages/reports_workbench_backlink_helpers.py",
}

GEOMETRY_SPLIT_SCOPES = {
    "tests/app_runtime/ui_geometry_contract_data.py",
    "tests/app_runtime/ui_geometry_runtime_support.py",
    "tests/app_runtime/ui_geometry_browser_support.py",
    "tests/ui_geometry_probe.mjs",
    "tests/ui_geometry_cdp_client.mjs",
    "tests/ui_geometry_probe_page_eval.mjs",
}

LOW_FREQUENCY_SECTION_3_TESTS = {
    "tests/config/test_config_manual_markdown.py",
    "tests/web_pages/test_frontend_ui_language_polish.py",
    "tests/web_pages/test_page_manual_registry.py",
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


# scope 空洞审计(2026-06-23)：tools/scripts 下服务门禁运行/测试地基的工具脚本，改它们影响
# 全套测试打标 / 门禁扫描步骤 / git hook 拦截 / 门禁测量，故纳入 common 走 by-design 全量。
GATE_INFRASTRUCTURE_TOOLS = {
    "tools/architecture_scan_cache.py",
    "tools/benchmark_full_test_debt_shards.py",
    "tools/capture_networkx_phase0_baseline.py",
    "tools/full_test_debt_shards.py",
    "tools/git_hook_blocked_paths.py",
    "tools/git_hook_cache.py",
    "tools/report_full_test_debt_durations.py",
    "tools/scan_aps_three_gap_py38_scope.py",
    "tools/scan_dead_code_islands.py",
    "tools/dead_code_usage/**/*.py",
    "tools/scan_py38plus_syntax.py",
    "scripts/build_test_inventory.py",
}

DEAD_CODE_TOOL_PROOF_FILES = {
    "tools/scan_dead_code_islands.py",
    "tools/dead_code_usage/__init__.py",
    "tools/dead_code_usage/ast_nodes.py",
    "tools/dead_code_usage/ast_usage.py",
    "tools/dead_code_usage/imports.py",
    "tools/dead_code_usage/model.py",
    "tools/dead_code_usage/scip_usage.py",
    "tools/dead_code_usage/scope.py",
    "tools/dead_code_usage/type_hints.py",
}


def test_gate_infrastructure_tools_are_common_scope() -> None:
    """防回潮：门禁/测试地基工具必须登记在 common tool_file_scopes，改它们走明确的全量而非
    "不命中任何 group → 漏网 fallback"。删除任一条目会让该工具退回未登记空洞，此测试届时报红。"""
    common_tools = set(REQUIRED_REGRESSION_COMMON_SCOPES["tool_file_scopes"])
    assert GATE_INFRASTRUCTURE_TOOLS <= common_tools


def test_dead_code_tools_are_in_quality_gate_source_proof() -> None:
    pyright_config = json.loads(Path("pyrightconfig.tools.json").read_text(encoding="utf-8"))

    assert DEAD_CODE_TOOL_PROOF_FILES <= set(quality_gate_shared.QUALITY_GATE_TOOL_PATHS)
    assert DEAD_CODE_TOOL_PROOF_FILES <= set(pyright_config["include"])


def test_symbol_locator_contract_is_required_and_grouped() -> None:
    test_path = "tests/gate_meta/test_symbol_locator_contract.py"
    tool_scope = "tools/symbol_locator/**/*.py"
    quality_group = _group("quality_gate")

    assert test_path in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert test_path in set(quality_group["target_paths"])
    assert tool_scope in set(quality_group["input_file_scopes"])
    assert tool_scope in set(quality_group["tool_file_scopes"])


def test_reports_and_geometry_split_files_are_group_scopes() -> None:
    reports_group = _group("scheduler_analysis_gantt_reports_week_plan")
    ui_group = _group("ui_layout_presenters_system")

    assert REPORT_CHAIN_SCOPES <= set(reports_group["input_file_scopes"])
    assert GEOMETRY_SPLIT_SCOPES <= set(ui_group["input_file_scopes"])


def test_three_gap_dev_guide_regression_list_is_required_and_grouped() -> None:
    guide = Path("docs/dev/aps_three_gap_quality_gate.md").read_text(encoding="utf-8")
    match = re.search(r"## 3\..*?\n(.*?)\n\s*## 4\.", guide, re.S)
    assert match is not None
    listed_tests = set(re.findall(r"tests/[A-Za-z0-9_./:-]+\.py", match.group(1)))
    grouped_tests = {
        path
        for group in SCHEDULER_REQUIRED_REGRESSION_GROUPS + MISC_REQUIRED_REGRESSION_GROUPS
        for path in group["target_paths"]
    }

    required_tests = set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)
    assert listed_tests - LOW_FREQUENCY_SECTION_3_TESTS <= required_tests
    assert LOW_FREQUENCY_SECTION_3_TESTS.isdisjoint(required_tests)
    assert listed_tests - LOW_FREQUENCY_SECTION_3_TESTS <= grouped_tests
    assert LOW_FREQUENCY_SECTION_3_TESTS.isdisjoint(grouped_tests)


def test_workbench_flow_regression_is_required_and_grouped() -> None:
    from tools import quality_gate_shared

    test_paths = {
        "tests/web_pages/test_aps_workbench_context_propagation_contract.py",
        "tests/web_pages/test_dashboard_workbench_contract.py",
        "tests/web_pages/test_dashboard_overdue_count_tolerance.py",
        "tests/operation_execution/test_execution_review_identity_guard.py",
        "tests/schedule/route_view/test_scheduler_navigation_unknown_plan_role_contract.py",
        "tests/gantt/test_gantt_task_detail_panel_contract.py",
        "tests/gantt/test_gantt_task_detail_js_contract.py",
    }
    scheduler_group = _group("scheduler_analysis_gantt_reports_week_plan")

    assert test_paths <= set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)
    assert test_paths <= set(scheduler_group["target_paths"])
    assert {
        "web/routes/domains/scheduler/scheduler_resource_dispatch_execution_context.py",
        "web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py",
        "web/routes/domains/scheduler/scheduler_resource_dispatch_query.py",
    } <= set(scheduler_group["input_file_scopes"])
    assert "web/routes/dashboard.py" in set(scheduler_group["input_file_scopes"])
    assert "web/routes/domains/scheduler/scheduler_navigation_publish.py" in set(scheduler_group["input_file_scopes"])


def test_scheduler_historical_plan_label_contract_is_required_and_grouped() -> None:
    test_path = "tests/schedule/route_view/test_scheduler_historical_plan_label_contract.py"
    scheduler_group = _group("scheduler_analysis_gantt_reports_week_plan")

    assert test_path in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert test_path in set(scheduler_group["target_paths"])


def test_plan_identity_summary_guardrail_is_required_and_grouped() -> None:
    from tools import quality_gate_shared

    test_paths = {
        "tests/schedule/route_view/test_scheduler_plan_identity_summary_guard.py",
        "tests/schedule/route_view/test_scheduler_plan_identity_evidence_contract.py",
        "tests/schedule/route_view/test_scheduler_plan_identity_evidence_link_contract.py",
    }
    scheduler_group = _group("scheduler_run_core")

    assert test_paths <= set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)
    assert test_paths <= set(scheduler_group["target_paths"])
    assert "tests/operation_execution/operation_execution_state_revision_support.py" in set(scheduler_group["input_file_scopes"])


def test_phase4_root_safety_nets_are_required_and_grouped() -> None:
    run_core_tests = {
        "tests/models_domain/test_strict_parse_blank_required.py",
        "tests/models_domain/test_schedule_resource_filter.py",
        "tests/models_domain/test_yesno_normalization_contract.py",
        "tests/resource_dispatch/test_scheduler_resource_dispatch_smoke.py",
    }
    config_tests = {
        "tests/config/test_scheduler_config_spec_sync_contract.py",
    }
    run_core_group = _group("scheduler_run_core")
    config_group = _group("scheduler_config")

    assert run_core_tests | config_tests <= set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)
    assert run_core_tests <= set(run_core_group["target_paths"])
    assert config_tests <= set(config_group["target_paths"])


def test_resource_dispatch_result_status_label_contract_is_required_and_grouped() -> None:
    from tools import quality_gate_shared

    test_path = "tests/resource_dispatch/test_resource_dispatch_result_status_label_contract.py"
    scheduler_group = _group("scheduler_analysis_gantt_reports_week_plan")

    assert test_path in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert test_path in set(scheduler_group["target_paths"])


def test_resource_dispatch_site_records_frontend_contract_is_required_and_grouped() -> None:
    from tools import quality_gate_shared

    test_path = "tests/resource_dispatch/test_resource_dispatch_site_records_frontend_contract.py"
    scheduler_group = _group("scheduler_analysis_gantt_reports_week_plan")

    assert test_path in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert test_path in set(scheduler_group["target_paths"])
    assert "web/routes/domains/scheduler/scheduler_resource_dispatch.py" in set(scheduler_group["input_file_scopes"])


def test_resource_dispatch_workbench_lane_contract_is_required_and_grouped() -> None:
    from tools import quality_gate_shared

    test_path = "tests/resource_dispatch/test_resource_dispatch_workbench_lane_contract.py"
    scheduler_group = _group("scheduler_analysis_gantt_reports_week_plan")

    assert test_path in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert test_path in set(scheduler_group["target_paths"])
    assert "tests/operation_execution/operation_execution_feedback_test_support.py" in set(scheduler_group["input_file_scopes"])


def test_scheduler_data_route_error_contract_is_required_and_grouped() -> None:
    test_path = "tests/gate_meta/test_scheduler_data_route_error_contract.py"
    runtime_group = _group("request_services_runtime_error_boundary")

    assert test_path in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert test_path in set(runtime_group["target_paths"])
    assert "web/routes/**/*.py" in set(runtime_group["input_file_scopes"])
    assert "web/routes/system_utils.py" in set(runtime_group["input_file_scopes"])


def test_scheduler_analysis_diagnostic_contracts_are_required_and_grouped() -> None:
    test_paths = {
        "tests/scheduler_analysis/test_scheduler_analysis_diagnostic_error_contract.py",
        "tests/scheduler_analysis/test_scheduler_analysis_diagnostic_graph_score_contract.py",
    }
    scheduler_group = _group("scheduler_analysis_gantt_reports_week_plan")

    assert test_paths <= set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)
    assert test_paths <= set(scheduler_group["target_paths"])
    assert "web/viewmodels/**/*.py" in set(scheduler_group["input_file_scopes"])


def test_operation_execution_core_regressions_are_required_and_grouped() -> None:
    test_paths = {
        "tests/operation_execution/test_operation_execution_event_foundation.py",
        "tests/operation_execution/test_operation_execution_event_sequence_contract.py",
        "tests/operation_execution/test_operation_execution_event_time_contract.py",
        "tests/operation_execution/test_operation_execution_state_revision.py",
        "tests/operation_execution/test_scheduler_reschedule_execution_facts.py",
        "tests/schedule/service/test_scheduler_reschedule_execution_minimum_guard.py",
    }
    scheduler_group = _group("scheduler_run_core")

    assert test_paths <= set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)
    assert test_paths <= set(scheduler_group["target_paths"])


def test_three_gap_docs_quality_contract_is_required_and_grouped() -> None:
    test_path = "tests/gate_meta/test_aps_three_gap_docs_quality_gate.py"
    quality_group = _group("quality_gate")

    assert test_path in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert test_path in set(quality_group["target_paths"])
    assert "docs/dev/**/*.md" in set(quality_group["input_file_scopes"])


def test_three_gap_contract_tests_are_required_in_registry() -> None:
    expected_paths = {
        "tests/operation_execution/test_operation_execution_event_time_contract.py",
        "tests/gate_meta/test_scheduler_data_route_error_contract.py",
    }

    assert expected_paths <= set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)


def test_operation_execution_feedback_regressions_are_required_and_grouped() -> None:
    test_paths = {
        "tests/operation_execution/test_operation_execution_feedback_routes.py",
        "tests/operation_execution/test_operation_execution_exception_feedback.py",
        "tests/operation_execution/test_operation_execution_exception_surfaces.py",
        "tests/operation_execution/test_operation_execution_scope_read_contract.py",
        "tests/gantt/test_gantt_adjustment_publish_execution_revision.py",
        "tests/resource_dispatch/test_resource_dispatch_actual_records.py",
        "tests/resource_dispatch/test_resource_dispatch_actual_task_key_frontend_contract.py",
        "tests/resource_dispatch/test_resource_dispatch_actual_import.py",
    }
    scheduler_group = _group("scheduler_analysis_gantt_reports_week_plan")

    assert test_paths <= set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)
    assert test_paths <= set(scheduler_group["target_paths"])


def test_operation_execution_migration_regressions_are_required_and_grouped() -> None:
    test_paths = {
        "tests/migration_db/test_migration_schema_contract.py",
        "tests/migration_db/test_migrations.py",
        "tests/operation_execution/test_operation_execution_migration_v16_contract.py",
        "tests/operation_execution/test_operation_execution_migration_v18_contract.py",
        "tests/operation_execution/test_operation_execution_migration_v19_contract.py",
    }
    runtime_group = _group("request_services_runtime_error_boundary")

    assert test_paths <= set(quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS)
    assert test_paths <= set(runtime_group["target_paths"])
    assert "tests/operation_execution/operation_execution_migration_support.py" in set(runtime_group["input_file_scopes"])


def test_import_execution_stats_regression_is_required_and_grouped() -> None:
    test_path = "tests/excel_data_io/test_import_execution_stats_source_row_num.py"
    excel_group = _group("frontend_manual_excel")

    assert test_path in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert test_path in set(excel_group["target_paths"])


def test_quality_gate_ignored_runtime_outputs_are_blocked_by_git_hook() -> None:
    gitignore_source = Path(".gitignore").read_text(encoding="utf-8")
    blocked = git_hook_checks._blocked_paths(
        [
            "evidence/QualityGate/silent_fallback_inventory_acceptance/report.json",
            "output/playwright/workbench-flow-regression-suite-reports-history.png",
        ]
    )

    assert "evidence/QualityGate/silent_fallback_inventory_acceptance/" in gitignore_source
    assert "output/" in gitignore_source
    assert blocked == [
        (
            "evidence/QualityGate/silent_fallback_inventory_acceptance/report.json",
            "silent fallback 验收清单是运行产物，应由当前门禁重新生成",
        ),
        (
            "output/playwright/workbench-flow-regression-suite-reports-history.png",
            "本地测试截图和临时输出，不属于项目源码",
        ),
    ]


def test_panorama_runtime_outputs_are_blocked_by_git_hook() -> None:
    blocked = git_hook_checks._blocked_paths(
        [
            "docs/_panorama_data/boundary.json",
            "docs/panorama.css",
            "docs/panorama.js",
            "docs/APS全景图.html",
            "docs/项目演进时间线.html",
            "docs/nested/模块全景图.html",
        ]
    )

    blocked_paths = [path for path, _reason in blocked]
    assert blocked_paths == [
        "docs/_panorama_data/boundary.json",
        "docs/panorama.css",
        "docs/panorama.js",
        "docs/APS全景图.html",
        "docs/项目演进时间线.html",
        "docs/nested/模块全景图.html",
    ]
    assert all("本地生成物" in reason for _path, reason in blocked)


def test_real_browser_geometry_smoke_stays_manual_acceptance_target() -> None:
    smoke_test = "tests/app_runtime/test_ui_browser_geometry_smoke.py"
    ui_group = _group("ui_layout_presenters_system")

    assert smoke_test not in quality_gate_shared.QUALITY_GATE_REQUIRED_TESTS
    assert smoke_test not in quality_gate_shared.QUALITY_GATE_SOURCE_FILES
    assert smoke_test not in set(ui_group["target_paths"])
    assert "tests/app_runtime/test_ui_browser_geometry_env.py" in set(ui_group["target_paths"])
    assert "tests/app_runtime/test_ui_geometry_html_contract.py" in set(ui_group["target_paths"])


def test_test_registry_facade_tools_imports_are_all_quality_gate_tool_paths() -> None:
    """自动发现型元测试：tools/test_registry.py 这个 facade 的每个 `from tools.X import ...`
    直接实现依赖，对应的 tools/X.py 必须全部进 QUALITY_GATE_TOOL_PATHS。

    现在三个拆分文件（test_registry_data / groups_misc / groups_scheduler）都已登记；本测试守护
    “将来再拆第四个实现文件却忘记登记”——届时自动报红，而非静默漏掉门禁源码证明范围（finding-06）。
    """
    facade_rel = "tools/test_registry.py"
    tree = ast.parse(Path(facade_rel).read_text(encoding="utf-8"), filename=facade_rel)

    imported_tool_paths = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            parts = node.module.split(".")
            # 仅约束直接实现依赖 `from tools.X import ...`（单层子模块），不误伤 tools.sub.pkg 或 from tools import ...
            if len(parts) == 2 and parts[0] == "tools":
                imported_tool_paths.add(f"tools/{parts[1]}.py")

    # 至少应覆盖三条已知拆分依赖，保证不是空断言
    assert REGISTRY_SPLIT_FILES <= imported_tool_paths

    missing = sorted(imported_tool_paths - set(quality_gate_shared.QUALITY_GATE_TOOL_PATHS))
    assert not missing, (
        "tools/test_registry.py 的直接实现依赖未全部登记进 QUALITY_GATE_TOOL_PATHS：\n"
        + "\n".join(missing)
        + "\n拆分注册表实现文件后，必须同步加入 quality_gate_shared.QUALITY_GATE_TOOL_PATHS"
        "（及 pyrightconfig.tools.json），否则门禁证明范围不完整。"
    )
