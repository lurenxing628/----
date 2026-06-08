"""契约测试：质量门禁回归测试注册表（test_registry 拆分文件 + quality_gate_shared）的 scope 绑定——拆分后的注册表文件本身、报表链路与几何探针等拆分文件都被纳入对应分组的 input/tool scope，工作台流程/历史方案标签/方案身份/资源派工/运行执行等关键回归测试齐备登记为 required 且归入正确分组，开发者指南列出的回归清单与注册表一致，门禁运行产物与全景图生成物均被 git hook 拦截提交。"""

from __future__ import annotations

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
