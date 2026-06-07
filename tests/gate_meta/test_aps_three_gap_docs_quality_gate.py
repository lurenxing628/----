"""守护 APS 三缺口（方案对比/延期解释/现场反馈）文档质量门禁：用户指南只用业务白话且不泄露 plan_role/event_type 等内部术语，开发者指南标注仅供开发测试、覆盖全部 roadmap feature、列全回归测试与关键 .py 文件及 Win7 离线门禁手册，且质量门禁计划包含 validate-yaml 与 py38 扫描命令。"""

from __future__ import annotations

import re
from pathlib import Path

from tests._support.paths import REPO_ROOT
from tools import quality_gate_shared

USER_GUIDE = REPO_ROOT / "static" / "docs" / "aps_three_gap_user_guide.md"
DEV_GUIDE = REPO_ROOT / "docs" / "dev" / "aps_three_gap_quality_gate.md"

ROADMAP_FEATURES = (
    "2026-05-27-shared-plan-identity-evidence-contract",
    "2026-05-27-delay-diagnosis-core-service",
    "2026-05-27-delay-diagnosis-overdue-report-entry",
    "2026-05-27-candidate-recommendation-card",
    "2026-05-27-candidate-summary-delta-cards",
    "2026-05-27-candidate-drilldown-empty-states",
    "2026-05-27-dispatch-plan-identity-guardrails",
    "2026-05-27-operation-execution-event-foundation",
    "2026-05-27-resource-dispatch-start-finish-feedback",
    "2026-05-27-reschedule-minimum-execution-guardrails",
    "2026-05-27-shop-exception-feedback",
    "2026-05-27-plan-vs-actual-review",
    "2026-05-27-reschedule-respects-execution-facts",
)

USER_REQUIRED_PHRASES = (
    "方案对比更好懂",
    "延期解释更可查",
    "现场反馈能进系统",
    "计划和现场实际",
    "重排时现场事实怎么保护",
    "Win7 x64",
    "Chrome 109",
    "不依赖外部网站",
)

USER_FORBIDDEN_TERMS = (
    "plan_role",
    "scenario_id",
    "source_table",
    "candidate_id",
    "event_type",
    "ReasonCode",
    "score tuple",
    "ExecutionSnapshot",
    "OperationExecutionEvents",
    "state_revision",
    "数据库字段",
    "函数名",
)

DEV_REQUIRED_TERMS = (
    "仅给开发和测试使用，不给用户看",
    "PlanIdentity",
    "EvidenceLink",
    "OperationExecutionEvents",
    "OperationExecutionState",
    "state_revision",
    "execution_snapshot_revision",
    "execution_snapshot_op_ids",
    "原 `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md` 后半段旧路线草案已经被本 roadmap 覆盖",
    "git diff --name-only d4589d77 -- 'tests/*.py'",
    "git diff --name-only d4589d77 -- '*.py'",
    "tools/scan_aps_three_gap_py38_scope.py --base-ref d4589d77",
)

REGRESSION_TESTS = (
    "tests/calendar_maintenance/test_freeze_window_bounds.py",
    "tests/schedule/route_view/test_scheduler_plan_identity_evidence_contract.py",
    "tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py",
    "tests/algorithm/test_due_exclusive_consistency.py",
    "tests/gantt/test_gantt_adjustment_validate_simulate.py",
    "tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py",
    "tests/gantt/test_gantt_degradation_surface.py",
    "tests/web_pages/test_dashboard_overdue_count_tolerance.py",
    "tests/candidate/test_scheduler_candidate_analysis_contract.py",
    "tests/candidate/test_scheduler_candidate_summary_contract.py",
    "tests/candidate/test_scheduler_candidate_week_plan_contract.py",
    "tests/resource_dispatch/test_scheduler_dispatch_plan_identity_guard.py",
    "tests/schedule/route_view/test_scheduler_workbench_links_contract.py",
    "tests/web_pages/test_web_silent_fallback_contract.py",
    "tests/operation_execution/test_operation_execution_event_foundation.py",
    "tests/operation_execution/test_operation_execution_event_time_contract.py",
    "tests/operation_execution/test_operation_execution_feedback_routes.py",
    "tests/resource_dispatch/test_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py",
    "tests/schedule/service/test_scheduler_reschedule_execution_minimum_guard.py",
    "tests/operation_execution/test_operation_execution_exception_feedback.py",
    "tests/scheduler_analysis/test_plan_vs_actual_review.py",
    "tests/operation_execution/test_scheduler_reschedule_execution_facts.py",
    "tests/gantt/test_gantt_adjustment_publish_execution_revision.py",
    "tests/app_runtime/test_frontend_offline_static_assets.py",
    "tests/web_pages/test_frontend_ui_language_polish.py",
    "tests/config/test_config_manual_markdown.py",
    "tests/web_pages/test_page_manual_registry.py",
    "tests/schedule/service/test_schedule_input_collector_legacy_compat.py",
    "tests/schedule/service/test_schedule_service_missing_resource_source_case_insensitive.py",
    "tests/schedule/service/test_schedule_service_reschedulable_contract.py",
    "tests/scheduler_graph/test_scheduler_graph_report_mode_service_contract.py",
    "tests/gate_meta/test_scheduler_data_route_error_contract.py",
    "tests/scheduler_analysis/test_scheduler_analysis_diagnostic_graph_score_contract.py",
    "tests/resource_dispatch/test_scheduler_resource_dispatch_invalid_query_cleanup.py",
    "tests/algorithm/test_skill_rank_mapping.py",
    "tests/gate_meta/test_architecture_fitness.py",
    "tests/gate_meta/test_codestable_tools_contract.py",
    "tests/gate_meta/test_scan_py38plus_syntax.py",
    "tests/gate_meta/test_aps_three_gap_docs_quality_gate.py",
    "tests/gate_meta/test_run_quality_gate.py",
    "tests/schedule/service/test_schedule_service_input_merge_context_contract.py",
)

KEY_PYTHON_FILES = (
    "core/models/schedule_plan_identity.py",
    "core/models/schedule_delay_diagnosis.py",
    "core/models/operation_execution_event.py",
    "core/infrastructure/operation_execution_event_data_contract.py",
    "core/infrastructure/migration_operation_execution_contract.py",
    "core/services/scheduler/schedule_plan_query_service.py",
    "core/services/scheduler/schedule_delay_diagnosis_service.py",
    "core/services/scheduler/schedule_delay_diagnosis_clues.py",
    "core/services/scheduler/gantt_adjustment_validation_service.py",
    "core/services/scheduler/operation_execution_feedback_actions.py",
    "core/services/scheduler/operation_execution_feedback_service.py",
    "core/services/scheduler/operation_execution_feedback_support.py",
    "core/services/scheduler/operation_execution_labels.py",
    "core/services/scheduler/execution_snapshot.py",
    "core/services/scheduler/resource_dispatch_execution_enrichment.py",
    "core/services/scheduler/run/schedule_execution_guardrails.py",
    "core/services/scheduler/run/schedule_execution_persistence_guard.py",
    "core/services/scheduler/run/schedule_candidate_persistence_helpers.py",
    "core/services/scheduler/run/schedule_input_collector.py",
    "core/services/scheduler/run/schedule_persistence.py",
    "core/services/scheduler/gantt_adjustment_publish_service.py",
    "core/services/report/execution_review.py",
    "core/services/report/report_plan_helpers.py",
    "data/repositories/batch_repo.py",
    "data/repositories/machine_downtime_repo.py",
    "data/repositories/operation_execution_event_repo.py",
    "data/repositories/operation_execution_state_builder.py",
    "data/repositories/schedule_adjustment_scenario_repo.py",
    "web/routes/reports.py",
    "web/routes/domains/scheduler/scheduler_resource_dispatch.py",
    "web/viewmodels/scheduler_analysis_candidates.py",
    "web/viewmodels/scheduler_analysis_candidate_helpers.py",
    "web/viewmodels/scheduler_plan_guardrail_messages.py",
    ".codestable/tools/validate-yaml.py",
    "tools/quality_gate_shared.py",
    "tools/scan_py38plus_syntax.py",
    "tools/scan_aps_three_gap_py38_scope.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_user_guide_exists_and_uses_plain_business_language() -> None:
    text = _read(USER_GUIDE)

    for phrase in USER_REQUIRED_PHRASES:
        assert phrase in text

    offenders = [term for term in USER_FORBIDDEN_TERMS if term in text]
    assert offenders == []


def test_developer_guide_is_marked_as_developer_only_and_keeps_internal_contracts() -> None:
    text = _read(DEV_GUIDE)

    for term in DEV_REQUIRED_TERMS:
        assert term in text


def test_developer_guide_lists_all_completed_roadmap_features() -> None:
    text = _read(DEV_GUIDE)

    missing = [feature for feature in ROADMAP_FEATURES if feature not in text]
    assert missing == []


def test_developer_guide_lists_regression_tests_and_key_python_files() -> None:
    text = _read(DEV_GUIDE)

    missing_tests = [path for path in REGRESSION_TESTS if path not in text]
    missing_python = [path for path in KEY_PYTHON_FILES if path not in text]

    assert missing_tests == []
    assert missing_python == []


def test_developer_guide_mentions_every_item_test_command_file() -> None:
    items_text = _read(REPO_ROOT / ".codestable" / "roadmap" / "aps-three-gap-directions" / "aps-three-gap-directions-items.yaml")
    dev_text = _read(DEV_GUIDE)
    test_files = sorted(set(re.findall(r"tests/[A-Za-z0-9_./:-]+\.py", items_text)))

    assert "tests/gate_meta/test_aps_three_gap_docs_quality_gate.py" in test_files
    missing = [path for path in test_files if path not in dev_text]
    assert missing == []


def test_developer_guide_contains_win7_offline_quality_gate_manual() -> None:
    text = _read(DEV_GUIDE)

    for phrase in (
        "Win7 x64",
        "Python 3.8",
        "Chrome 109",
        "离线静态资源",
        "scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache",
    ):
        assert phrase in text


def test_quality_gate_plan_runs_codestable_yaml_and_py38_scan() -> None:
    displays = [command["display"] for command in quality_gate_shared.build_quality_gate_command_plan()]

    assert any("validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions" in item for item in displays)
    assert any("scan_aps_three_gap_py38_scope.py --base-ref d4589d77" in item for item in displays)
    assert any("scan_py38plus_syntax.py --fail-on-hit" in item for item in displays)
