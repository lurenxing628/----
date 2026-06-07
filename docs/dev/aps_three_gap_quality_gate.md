# APS 三个差距方向开发测试收口说明

> 仅给开发和测试使用，不给用户看。
> 本文会出现程序内部字段、表名、测试文件名和命令。用户说明请看 `static/docs/aps_three_gap_user_guide.md`。

最后更新：2026-06-04

## 1. 当前口径

- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md` 和 `aps-three-gap-directions-items.yaml` 是第 1-14 项继续维护的事实源。
- 原 `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md` 后半段旧路线草案已经被本 roadmap 覆盖。后续实现、验收和文档说明都以 roadmap 主文档和 items.yaml 为准。
- 用户可见说明不能直接展示 `plan_role`、`scenario_id`、`source_table`、`candidate_id`、`event_type`、`ReasonCode`、`score tuple`、数据库字段名、函数名或内部异常堆栈。
- 开发和测试可以讨论 PlanIdentity、EvidenceLink、OperationExecutionEvents、OperationExecutionState、state_revision、execution_snapshot_revision、execution_snapshot_op_ids，但必须放在开发专用文档或测试断言里。

## 2. 已完成 feature 和精准测试

| 序号 | roadmap item | feature | 主要测试 |
|---:|---|---|---|
| 1 | shared-plan-identity-evidence-contract | 2026-05-27-shared-plan-identity-evidence-contract | `tests/schedule/route_view/test_scheduler_plan_identity_evidence_contract.py`、`tests/regression_scheduler_candidate_gantt_plan_role_contract.py` |
| 2 | delay-diagnosis-core-service | 2026-05-27-delay-diagnosis-core-service | `tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py`、`tests/algorithm/test_due_exclusive_consistency.py`、`tests/regression_gantt_adjustment_validate_simulate.py` |
| 3 | delay-diagnosis-overdue-report-entry | 2026-05-27-delay-diagnosis-overdue-report-entry | `tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py`、`tests/regression_frontend_offline_static_assets.py`、`tests/regression_gantt_degradation_surface.py`、`tests/web_pages/test_dashboard_overdue_count_tolerance.py` |
| 4 | candidate-recommendation-card | 2026-05-27-candidate-recommendation-card | `tests/candidate/test_scheduler_candidate_analysis_contract.py`、`tests/candidate/test_scheduler_analysis_candidate_links_and_roles.py`、`tests/candidate/test_scheduler_candidate_plain_language.py` |
| 5 | candidate-summary-delta-cards | 2026-05-27-candidate-summary-delta-cards | `tests/candidate/test_scheduler_candidate_summary_contract.py`、`tests/regression_scheduler_graph_auto_selection_contract.py`、`tests/candidate/test_scheduler_candidate_plain_language.py` |
| 6 | candidate-drilldown-empty-states | 2026-05-27-candidate-drilldown-empty-states | `tests/candidate/test_scheduler_candidate_week_plan_contract.py`、`tests/candidate/test_scheduler_candidate_plan_query_contract.py`、`tests/candidate/test_scheduler_candidate_reports_contract.py`、`tests/web_pages/test_scenario_preview_secondary_outputs.py` |
| 7 | dispatch-plan-identity-guardrails | 2026-05-27-dispatch-plan-identity-guardrails | `tests/resource_dispatch/test_scheduler_dispatch_plan_identity_guard.py`、`tests/resource_dispatch/test_scheduler_candidate_resource_dispatch_contract.py`、`tests/resource_dispatch/test_resource_dispatch_public_output_contract.py` |
| 8 | operation-execution-event-foundation | 2026-05-27-operation-execution-event-foundation | `tests/operation_execution/test_operation_execution_event_foundation.py`、`tests/operation_execution/test_operation_execution_state_revision.py`、`tests/migration_db/test_migrations.py` |
| 9 | resource-dispatch-start-finish-feedback | 2026-05-27-resource-dispatch-start-finish-feedback | `tests/operation_execution/test_operation_execution_feedback_routes.py`、`tests/resource_dispatch/test_scheduler_candidate_resource_dispatch_contract.py`、`tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes` |
| 10 | reschedule-minimum-execution-guardrails | 2026-05-27-reschedule-minimum-execution-guardrails | `tests/schedule/service/test_scheduler_reschedule_execution_minimum_guard.py`、`tests/operation_execution/test_operation_execution_feedback_routes.py`、`tests/operation_execution/test_operation_execution_state_revision.py` |
| 11 | shop-exception-feedback | 2026-05-27-shop-exception-feedback | `tests/operation_execution/test_operation_execution_exception_feedback.py`、`tests/schedule/service/test_scheduler_exception_blocks_auto_reschedule.py`、`tests/operation_execution/test_operation_execution_feedback_routes.py` |
| 12 | plan-vs-actual-review | 2026-05-27-plan-vs-actual-review | `tests/scheduler_analysis/test_plan_vs_actual_review.py`、`tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py` |
| 13 | reschedule-respects-execution-facts | 2026-05-27-reschedule-respects-execution-facts | `tests/operation_execution/test_scheduler_reschedule_execution_facts.py`、`tests/schedule/service/test_scheduler_reschedule_execution_minimum_guard.py`、`tests/regression_gantt_adjustment_publish_execution_revision.py` |

### 2.1 items.yaml 精准测试命令

下面是第 1-13 项在 `aps-three-gap-directions-items.yaml` 里的精准命令快照。收口验收不能只写“跑质量门禁”，需要能看到每条已完成 feature 自己要求的测试。

| 序号 | roadmap item | items.yaml test_commands |
|---:|---|---|
| 1 | shared-plan-identity-evidence-contract | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/schedule/route_view/test_scheduler_plan_identity_evidence_contract.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py` |
| 2 | delay-diagnosis-core-service | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py tests/algorithm/test_due_exclusive_consistency.py tests/regression_gantt_adjustment_validate_simulate.py` |
| 3 | delay-diagnosis-overdue-report-entry | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py tests/regression_frontend_offline_static_assets.py tests/regression_gantt_degradation_surface.py tests/web_pages/test_dashboard_overdue_count_tolerance.py` |
| 4 | candidate-recommendation-card | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/candidate/test_scheduler_candidate_analysis_contract.py tests/candidate/test_scheduler_analysis_candidate_links_and_roles.py tests/candidate/test_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py` |
| 5 | candidate-summary-delta-cards | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/candidate/test_scheduler_candidate_analysis_contract.py tests/candidate/test_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py tests/candidate/test_scheduler_candidate_summary_contract.py tests/regression_scheduler_graph_auto_selection_contract.py` |
| 6 | candidate-drilldown-empty-states | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/candidate/test_scheduler_analysis_candidate_links_and_roles.py tests/candidate/test_scheduler_candidate_week_plan_contract.py tests/candidate/test_scheduler_candidate_plan_query_contract.py tests/candidate/test_scheduler_candidate_reports_contract.py tests/candidate/test_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py tests/web_pages/test_scenario_preview_secondary_outputs.py tests/scheduler_analysis/test_report_export_size_mode_selection.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/resource_dispatch/test_scheduler_candidate_resource_dispatch_contract.py tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py` |
| 7 | dispatch-plan-identity-guardrails | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/resource_dispatch/test_scheduler_candidate_resource_dispatch_contract.py tests/resource_dispatch/test_scheduler_dispatch_plan_identity_guard.py tests/regression_frontend_offline_static_assets.py` |
| 8 | operation-execution-event-foundation | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/operation_execution/test_operation_execution_event_foundation.py tests/operation_execution/test_operation_execution_event_time_contract.py tests/operation_execution/test_operation_execution_state_revision.py tests/migration_db/test_migrations.py` |
| 9 | resource-dispatch-start-finish-feedback | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/resource_dispatch/test_scheduler_candidate_resource_dispatch_contract.py tests/operation_execution/test_operation_execution_feedback_routes.py tests/regression_frontend_offline_static_assets.py tests/resource_dispatch/test_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py` |
| 10 | reschedule-minimum-execution-guardrails | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/schedule/service/test_scheduler_reschedule_execution_minimum_guard.py tests/operation_execution/test_operation_execution_feedback_routes.py tests/regression_frontend_offline_static_assets.py tests/schedule/route_view/test_scheduler_run_surfaces_resource_pool_warning.py` |
| 11 | shop-exception-feedback | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/operation_execution/test_operation_execution_exception_feedback.py tests/operation_execution/test_operation_execution_feedback_routes.py tests/schedule/service/test_scheduler_exception_blocks_auto_reschedule.py tests/regression_frontend_offline_static_assets.py` |
| 12 | plan-vs-actual-review | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_analysis/test_plan_vs_actual_review.py tests/operation_execution/test_operation_execution_event_foundation.py tests/regression_frontend_offline_static_assets.py` |
| 13 | reschedule-respects-execution-facts | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/operation_execution/test_scheduler_reschedule_execution_facts.py tests/schedule/service/test_scheduler_reschedule_execution_minimum_guard.py tests/regression_gantt_adjustment_publish_execution_revision.py` |

### 2.2 回归类型对照

| 类型 | 覆盖方式 |
|---|---|
| 精准功能测试 | 上表每条 feature 的 `test_commands` |
| 迁移测试 | `tests/migration_db/test_migrations.py`、`tests/regression_gantt_adjustment_publish_execution_revision.py` |
| 页面大白话测试 | `tests/candidate/test_scheduler_candidate_plain_language.py`、`tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py`、`tests/regression_aps_three_gap_docs_quality_gate.py` |
| Win7/offline 测试 | `tests/regression_frontend_offline_static_assets.py`、`tests/test_scan_py38plus_syntax.py` |
| CodeStable YAML 测试 | `.codestable/tools/validate-yaml.py` 命令和 `tests/test_codestable_tools_contract.py` |
| 长门禁 | `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，其中命令计划已包含 roadmap YAML 校验和 Python 3.8 扫描 |

## 3. 第 1-13 项回归测试清单

收集方式：合并 `aps-three-gap-directions-items.yaml` 第 1-13 项 `test_commands` 和 `git diff --name-only d4589d77 -- 'tests/*.py'`。下面既包含本 roadmap 改过的测试，也包含第 1-13 项精准命令引用的既有测试。

- `tests/regression_gantt_adjustment_publish_execution_revision.py`
- `tests/regression_gantt_draft_save_and_preview.py`
- `tests/migration_db/test_migrations.py`
- `tests/operation_execution/test_operation_execution_event_foundation.py`
- `tests/operation_execution/test_operation_execution_event_time_contract.py`
- `tests/operation_execution/test_operation_execution_exception_feedback.py`
- `tests/operation_execution/test_operation_execution_feedback_routes.py`
- `tests/operation_execution/test_operation_execution_state_revision.py`
- `tests/web_pages/test_page_manual_registry.py`
- `tests/scheduler_analysis/test_plan_vs_actual_review.py`
- `tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py`
- `tests/scheduler_analysis/test_report_export_large_scope_rejects_need_async.py`
- `tests/scheduler_analysis/test_report_export_size_mode_selection.py`
- `tests/web_pages/test_scenario_preview_secondary_outputs.py`
- `tests/schedule/service/test_schedule_input_collector_contract.py`
- `tests/candidate/test_scheduler_analysis_candidate_links_and_roles.py`
- `tests/candidate/test_scheduler_candidate_analysis_contract.py`
- `tests/regression_scheduler_candidate_gantt_plan_role_contract.py`
- `tests/candidate/test_scheduler_candidate_summary_contract.py`
- `tests/candidate/test_scheduler_candidate_plain_language.py`
- `tests/candidate/test_scheduler_candidate_plan_query_contract.py`
- `tests/candidate/test_scheduler_candidate_reports_contract.py`
- `tests/resource_dispatch/test_scheduler_candidate_resource_dispatch_contract.py`
- `tests/candidate/test_scheduler_candidate_week_plan_contract.py`
- `tests/regression_scheduler_graph_auto_selection_contract.py`
- `tests/web_pages/test_dashboard_overdue_count_tolerance.py`
- `tests/algorithm/test_due_exclusive_consistency.py`
- `tests/calendar_maintenance/test_freeze_window_bounds.py`
- `tests/regression_frontend_offline_static_assets.py`
- `tests/web_pages/test_frontend_ui_language_polish.py`
- `tests/config/test_config_manual_markdown.py`
- `tests/regression_gantt_adjustment_validate_simulate.py`
- `tests/regression_gantt_degradation_surface.py`
- `tests/resource_dispatch/test_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py`
- `tests/schedule/service/test_schedule_input_collector_legacy_compat.py`
- `tests/schedule/service/test_schedule_service_missing_resource_source_case_insensitive.py`
- `tests/schedule/service/test_schedule_service_reschedulable_contract.py`
- `tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py`
- `tests/resource_dispatch/test_scheduler_dispatch_plan_identity_guard.py`
- `tests/schedule/route_view/test_scheduler_workbench_links_contract.py`
- `tests/web_pages/test_web_silent_fallback_contract.py`
- `tests/schedule/service/test_scheduler_exception_blocks_auto_reschedule.py`
- `tests/regression_scheduler_graph_report_mode_service_contract.py`
- `tests/schedule/route_view/test_scheduler_plan_identity_evidence_contract.py`
- `tests/operation_execution/test_scheduler_reschedule_execution_facts.py`
- `tests/schedule/service/test_scheduler_reschedule_execution_minimum_guard.py`
- `tests/regression_scheduler_data_route_error_contract.py`
- `tests/scheduler_analysis/test_scheduler_analysis_diagnostic_graph_score_contract.py`
- `tests/resource_dispatch/test_scheduler_resource_dispatch_invalid_query_cleanup.py`
- `tests/schedule/route_view/test_scheduler_run_surfaces_resource_pool_warning.py`
- `tests/algorithm/test_skill_rank_mapping.py`
- `tests/test_architecture_fitness.py`
- `tests/test_codestable_tools_contract.py`
- `tests/test_scan_py38plus_syntax.py`
- `tests/regression_aps_three_gap_docs_quality_gate.py`
- `tests/test_run_quality_gate.py`
- `tests/schedule/service/test_schedule_service_input_merge_context_contract.py`

## 4. 本 roadmap 新增或修改过的关键 Python 文件

收集方式：`git diff --name-only d4589d77 -- '*.py'`。下面列关键业务和测试入口；完整 Python 3.8 扫描由 `tools/scan_aps_three_gap_py38_scope.py --base-ref d4589d77` 自动收集同一范围并执行。

- `core/models/schedule_plan_identity.py`
- `core/models/schedule_plan_resolution.py`
- `core/models/schedule_delay_diagnosis.py`
- `core/models/operation_execution_event.py`
- `core/models/operation_execution_state.py`
- `core/models/schedule_adjustment.py`
- `core/infrastructure/operation_execution_event_data_contract.py`
- `core/infrastructure/migration_operation_execution_contract.py`
- `core/services/scheduler/schedule_plan_identity_builder.py`
- `core/services/scheduler/schedule_plan_query_service.py`
- `core/services/scheduler/schedule_result_view_context.py`
- `core/services/scheduler/schedule_delay_diagnosis_service.py`
- `core/services/scheduler/schedule_delay_diagnosis_clues.py`
- `core/services/scheduler/execution_fact_provider.py`
- `core/services/scheduler/execution_snapshot.py`
- `core/services/scheduler/gantt_adjustment_validation_service.py`
- `core/services/scheduler/operation_execution_feedback_actions.py`
- `core/services/scheduler/operation_execution_feedback_service.py`
- `core/services/scheduler/operation_execution_feedback_support.py`
- `core/services/scheduler/operation_execution_labels.py`
- `core/services/scheduler/resource_dispatch_execution_enrichment.py`
- `core/services/scheduler/resource_dispatch_execution_service.py`
- `core/services/scheduler/resource_dispatch_service.py`
- `core/services/scheduler/run/schedule_execution_guardrails.py`
- `core/services/scheduler/run/schedule_execution_persistence_guard.py`
- `core/services/scheduler/run/schedule_candidate_persistence_helpers.py`
- `core/services/scheduler/run/schedule_input_collector.py`
- `core/services/scheduler/run/schedule_input_runtime_support.py`
- `core/services/scheduler/run/schedule_persistence.py`
- `core/services/scheduler/gantt_adjustment_publish_service.py`
- `core/services/scheduler/gantt_adjustment_scenario_service.py`
- `core/services/report/execution_review.py`
- `core/services/report/report_plan_helpers.py`
- `core/services/report/report_engine.py`
- `core/services/report/exporters/xlsx.py`
- `data/repositories/schedule_plan_query_repo.py`
- `data/repositories/batch_repo.py`
- `data/repositories/machine_downtime_repo.py`
- `data/repositories/operation_execution_event_repo.py`
- `data/repositories/operation_execution_state_builder.py`
- `data/repositories/schedule_adjustment_scenario_repo.py`
- `web/routes/reports.py`
- `web/routes/report_plan_preview.py`
- `web/routes/domains/scheduler/scheduler_resource_dispatch.py`
- `web/routes/domains/scheduler/scheduler_gantt_adjustments.py`
- `web/viewmodels/scheduler_analysis_candidates.py`
- `web/viewmodels/scheduler_analysis_candidate_helpers.py`
- `web/viewmodels/scheduler_plan_guardrail_messages.py`
- `web/viewmodels/scheduler_resource_dispatch.py`
- `web/viewmodels/scheduler_resource_dispatch_execution.py`
- `.codestable/tools/validate-yaml.py`
- `tools/quality_gate_shared.py`
- `tools/scan_py38plus_syntax.py`
- `tools/scan_aps_three_gap_py38_scope.py`

## 5. 内部协议维护提示

- PlanIdentity 只负责描述“当前读取的是哪套计划结果、能不能派工、能不能写现场反馈”。用户页面要翻译成“正式采用方案、对比参考方案、模拟预览、历史正式方案”。
- EvidenceLink 只负责追证据来源。用户页面要翻译成“证据来源、当前数据不足、建议复核”，不要显示内部范围名。
- OperationExecutionEvents 是现场事实追加表。不要把 `Schedule.start_time/end_time` 改成实际时间，也不要只靠 `BatchOperations.status` 表示现场事实。
- OperationExecutionState 是按事件聚合出来的读模型。`state_revision` 用来阻止用户拿旧页面继续写现场反馈。
- `execution_snapshot_revision` 和 `execution_snapshot_op_ids` 用来阻止排程或发布时现场状态已经变化。它们只能出现在开发测试说明、日志或内部摘要里，不给普通用户直接看。

## 6. Win7、Python 3.8、Chrome 109 和离线验收手册

> 仅给开发和测试使用，不给用户看。

1. Python 语法验收：对本 roadmap 改动过的 Python 文件运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_aps_three_gap_py38_scope.py --base-ref d4589d77`。该命令会用 `git diff --name-only d4589d77 -- '*.py'` 收集仍存在的 Python 文件，再调用 `tools/scan_py38plus_syntax.py`。
2. CodeStable YAML 验收：运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items`。
3. 离线静态资源验收：运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_frontend_offline_static_assets.py`。它会扫描模板、静态资源和 `docs/aps_frontend_workbench_mockup.html`，阻止外链脚本、样式、字体、图片和 CDN。
4. Chrome 109 人工验收：在交付浏览器环境打开首页、排产优化分析、超期清单、资源排班、计划和现场实际、甘特图模拟预览，检查页面能打开、按钮和筛选能操作、导出能下载、长文字不遮挡。
5. Win7 x64 人工验收：在目标系统或同等离线环境里启动打包后的应用，确认不需要联网、不需要目标机安装 Python，页面静态资源从本地加载。
6. 长门禁：工作区干净时运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。如果有无关 dirty worktree，只能用 `--allow-dirty-worktree` 做本地反馈，不能当 clean proof。

## 7. 第 14 项最小命令

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_frontend_offline_static_assets.py tests/web_pages/test_frontend_ui_language_polish.py tests/config/test_config_manual_markdown.py tests/web_pages/test_page_manual_registry.py tests/test_codestable_tools_contract.py tests/test_scan_py38plus_syntax.py tests/regression_aps_three_gap_docs_quality_gate.py tests/test_run_quality_gate.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_aps_three_gap_py38_scope.py --base-ref d4589d77
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit scripts/run_quality_gate.py tools/quality_gate_shared.py tools/scan_aps_three_gap_py38_scope.py tests/regression_frontend_offline_static_assets.py tests/web_pages/test_frontend_ui_language_polish.py tests/config/test_config_manual_markdown.py tests/web_pages/test_page_manual_registry.py tests/operation_execution/test_operation_execution_event_time_contract.py tests/regression_scheduler_data_route_error_contract.py tests/resource_dispatch/test_scheduler_resource_dispatch_invalid_query_cleanup.py tests/regression_aps_three_gap_docs_quality_gate.py tests/test_run_quality_gate.py
git diff --check
```
