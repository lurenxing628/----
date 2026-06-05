# A(test-gate-cleanup) 对 B(80条水下债) 交叉影响 — 确定性真相源

> 本文件由脚本从 `L3_verdicts.csv`(A) 与 phase4-dep-safety 全部 .md(B) 机械求交生成,作为 SubAgent 核对靶子。数字=确定性,定性留给 agent。

## 表1 B依赖 ∩ A将删改(非KEEP) — 直接冲突候选
| B引用次数 | A裁决 | 当前存在 | 文件 | 引用它的B文档(节选) |
|---:|---|:--:|---|---|
| 58 | DROP | ✓ | tests/test_sp05_path_topology_contract.py | PHASE4-SAFE-BATCH-PLAN.md, _interference_rebuilt.md, _layer1_summary.md, clusters/C-CONFIG-DUAL.md, clusters/C-GRAPH-ERR-DIAG.md, clusters/C-LEAF-DUP-P4.md |
| 25 | KEEP_TRIM | ✓ | tests/regression_reports_workbench_navigation_contract.py | clusters/C-NAV-PLANID.md, dossiers/LB02.md, dossiers/LB05.md, dossiers/R42.md, dossiers/R44.md, dossiers/R54.md |
| 22 | DROP_WITH_TOOL | ✓ | tests/test_architecture_fitness.py | PHASE4-SAFE-BATCH-PLAN.md, _layer1_summary.md, clusters/C-PARSE-INT.md, dossiers/R15.md, dossiers/R28.md, redteam/explode_r1_C-PARSE-INT_LB.md |
| 21 | DROP | ✓ | tests/regression_sp06_no_duplicate_defs.py | clusters/C-CONFIG-DUAL.md, dossiers/R45.md, dossiers/R48.md, dossiers/R68.md, redteam/explode_r1_C-CONFIG-DUAL_LAYER.md, redteam/explode_r3_C-CONFIG-DUAL_SOUL.md |
| 18 | KEEP_TRIM | ✓ | tests/test_enum_display_consistency.py | PHASE4-SAFE-BATCH-PLAN.md, _layer3_explosion.md, clusters/C-LEAF-DUP-P4.md, dossiers/R41.md, redteam/explode_r1_C-LEAF-DUP-P4_LAYER.md, redteam/explode_r1_C-LEAF-DUP-P4_SOUL.md |
| 18 | KEEP_TRIM | ✓ | tests/regression_schedule_result_view_context.py | clusters/C-PLAN-IDENTITY.md, dossiers/R21.md, dossiers/R22.md, dossiers/R23.md, dossiers/R54.md, redteam/explode_r1_C-PLAN-IDENTITY_LAYER.md |
| 12 | KEEP_TRIM | ✓ | tests/regression_web_silent_fallback_contract.py | clusters/C-PARSE-INT.md, dossiers/R59.md, dossiers/R66.md, redteam/explode_r1_C-PARSE-INT_LAYER.md, redteam/explode_r1_C-PARSE-INT_LB.md, redteam/explode_r1_C-PARSE-INT_SOUL.md |
| 12 | ISOLATE_PERF | ✓ | tests/benchmark_fjsp.py | clusters/C-RESOURCE-REPO.md, dossiers/R34.md, dossiers/R35.md, dossiers/R36.md |
| 11 | KEEP_TRIM | ✓ | tests/regression_scheduler_week_plan_summary_observability.py | _layer1_summary.md, clusters/C-GANTT.md, dossiers/R10.md, redteam/explode_r1_C-GANTT_LB.md, redteam/explode_r1_C-GANTT_SOUL.md, redteam/explode_r2_C-GANTT_LB.md |
| 10 | KEEP_TRIM | ✓ | tests/test_greedy_refactor_contracts.py | _layer1_summary.md, clusters/C-LEAF-DUP-P4.md, dossiers/R27.md, dossiers/R50.md, dossiers/R53.md |
| 10 | KEEP_TRIM | ✓ | tests/regression_aps_three_gap_docs_quality_gate.py | dossiers/R15.md, dossiers/R20.md, dossiers/R49.md, dossiers/R69.md |
| 8 | MERGE:sort_strategy_case_insensitive | ✓ | tests/regression_sort_strategy_case_insensitive.py | dossiers/R51.md, redteam/explode_r1_C-COMPAT-DISPATCH_LAYER.md, redteam/explode_r1_C-COMPAT-DISPATCH_SOUL.md, redteam/explode_r2_C-COMPAT-DISPATCH_SOUL.md |
| 8 | MERGE:workbench_links_viewmodel | ✓ | tests/regression_scheduler_workbench_link_guardrails.py | dossiers/LB02.md, dossiers/LB05.md, dossiers/R54.md, redteam/explode_r2_C-NAV-GUARD_SOUL.md, redteam/explode_r3_C-NAV-GUARD_SOUL.md |
| 7 | KEEP_TRIM | ✓ | tests/regression_scheduler_analysis_diagnostic_contract.py | dossiers/R24.md, redteam/explode_r2_C-GRAPH-ERR-DIAG_SOUL.md |
| 6 | KEEP_TRIM | ✓ | tests/regression_resource_dispatch_workbench_lane_contract.py | dossiers/R08.md, dossiers/R09.md, redteam/explode_r1_C-PARSE-INT_LB.md |
| 6 | KEEP_TRIM | ✓ | tests/regression_gantt_task_detail_panel_contract.py | dossiers/R11.md, dossiers/R55.md, dossiers/R63.md |
| 6 | DROP | ✓ | tests/regression_scheduler_candidate_py38_contract.py | dossiers/LB07.md, dossiers/R02.md, dossiers/R71.md |
| 5 | KEEP_TRIM | ✓ | tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py | dossiers/R05.md, redteam/explode_r1_C-RESOURCE-REPO_LB.md, redteam/explode_r1_C-RESOURCE-REPO_SOUL.md |
| 3 | KEEP_TRIM | ✓ | tests/regression_schedule_persistence_reject_empty_actionable_schedule.py | dossiers/R04.md |
| 2 | KEEP_TRIM | ✓ | tests/regression_schedule_history_not_created_for_empty_schedule.py | dossiers/R70.md |
| 2 | KEEP_TRIM | ✓ | tests/regression_schedule_service_empty_reschedulable_rejected.py | dossiers/R70.md |
| 2 | KEEP_TRIM | ✓ | tests/regression_resource_dispatch_site_records_frontend_contract.py | dossiers/R09.md, dossiers/R54.md |
| 2 | KEEP_TRIM | ✓ | tests/regression_scheduler_dispatch_plan_identity_guardrails.py | dossiers/R09.md, dossiers/R54.md |
| 2 | ISOLATE_PERF | ✓ | tests/smoke_e2e_excel_to_schedule.py | dossiers/R40.md |
| 2 | KEEP_TRIM | ✓ | tests/regression_reports_workbench_backlink_contract.py | dossiers/LB02.md |
| 2 | KEEP_TRIM | ✓ | tests/regression_frontend_ui_language_polish.py | dossiers/R68.md |
| 2 | KEEP_TRIM | ✓ | tests/regression_scheduler_historical_plan_label_contract.py | dossiers/R66.md |
| 2 | MERGE:real_db_replay_e2e | ✓ | tests/run_real_db_replay_check.py | dossiers/R32.md |
| 2 | MERGE:real_db_replay_e2e | ✓ | tests/run_real_db_replay_smoke.py | dossiers/R32.md |
| 2 | KEEP_TRIM | ✓ | tests/regression_gantt_critical_outline_sync.py | dossiers/R12.md |
| 1 | KEEP_TRIM | ✓ | tests/regression_scheduler_candidate_week_plan_contract.py | ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md |
| 1 | KEEP_TRIM | ✓ | tests/regression_config_field_spec_contract.py | dossiers/LB07.md |
| 1 | KEEP_TRIM | ✓ | tests/regression_scheduler_candidate_config_contract.py | dossiers/LB07.md |
| 1 | KEEP_TRIM | ✓ | tests/regression_scheduler_plan_identity_summary_guardrail.py | dossiers/_fixed_confirm.md |
| 1 | MERGE:workbench_context_propagation | ✓ | tests/regression_aps_workbench_flow_contract.py | dossiers/_fixed_confirm.md |
| 1 | KEEP_TRIM | ✓ | tests/regression_scheduler_candidate_display_contract.py | dossiers/R03.md |
| 1 | KEEP_TRIM | ✓ | tests/test_scheduler_run_view_result_contract.py | dossiers/R43.md |
| 1 | KEEP_TRIM | ✓ | tests/regression_scheduler_config_route_contract.py | dossiers/R43.md |
| 1 | KEEP_TRIM | ✓ | tests/regression_manual_entry_scope.py | dossiers/R43.md |
| 1 | MERGE:scheduler_route_registration | ✓ | tests/test_scheduler_route_registration_contract.py | dossiers/R43.md |

### 表1 各文件 A 的删改理由(原文)
- **tests/test_sp05_path_topology_contract.py** [DROP]: refactor-topology snapshot: hardcoded compat-module alias maps + __all__ symbol tuples + AST registrar _ROUTE_MODULES + doc-tree literals in 开发文档.md (line 309-664) rots on any restructure
- **tests/regression_reports_workbench_navigation_contract.py** [KEEP_TRIM]: 实跑build_scheduler/report_navigation_links防交叉接线+plan_role守卫+后端scope过滤+冲突400(L151-493)真导航逻辑但夹ui_macros.html源码grep(L142-148)脆性尾
- **tests/test_architecture_fitness.py** [DROP_WITH_TOOL]: architecture gate driven by tools.quality_gate_support ledger: oversize/complexity/silent allowlist reconciliation + stale-entry self-checks (line 25-451) gate self-ref
- **tests/regression_sp06_no_duplicate_defs.py** [DROP]: AST guard asserts no duplicate defs + no banned cfg_get helpers in pinned file list (lines 8-95) structural refactor-residue snapshot
- **tests/test_enum_display_consistency.py** [KEEP_TRIM]: real enum_display_zh wrappers: trim/unknown-passthrough/None-fallback behavior valuable but exact label pairs (active=可用 etc line 14-61) are translation-table snapshot
- **tests/regression_schedule_result_view_context.py** [KEEP_TRIM]: real plan-role resolution: adopted/baseline/critical/fallback/comparison + plan metadata field consistency (line:124-291); Chinese notice substrings line:160,183,202 brittle
- **tests/regression_web_silent_fallback_contract.py** [KEEP_TRIM]: core asserts real no-silent-fallback: safe_float/parse_failed flags + NaN/Infinity not leaked + ValidationError raises (line 38-419) but 3 fns grep week_plan/overview templates (line 424-456)
- **tests/benchmark_fjsp.py** [ISOLATE_PERF]: FJSP Brandimarte makespan/gap benchmark runner with main() CLI writing evidence/Benchmark report; tests/benchmark_fjsp.py:432
- **tests/regression_scheduler_week_plan_summary_observability.py** [KEEP_TRIM]: core tests build_summary_display_state status-precedence/simulated/warning-pipeline logic (L283-434) high value; trim HTML-copy render tests L469-513 (snapshot tail)
- **tests/test_greedy_refactor_contracts.py** [KEEP_TRIM]: deep algorithm tests legacy callback/seed normalize/auto-assign root-cause/strict reject (line 124-1117) but trim source-grep import contracts+line-count<500+function-span<80+radon complexity<15 gate snapshots (line 56-101)
- **tests/regression_aps_three_gap_docs_quality_gate.py** [KEEP_TRIM]: 绝大多数断言为脆性文档快照(中文短语in user_guide:163/术语清单in dev_guide:173/REGRESSION_TESTS+KEY_PYTHON_FILES路径清单逐条in文档:187),仅末test_quality_gate_plan_runs:217有真契约价值
- **tests/regression_sort_strategy_case_insensitive.py** [MERGE:sort_strategy_case_insensitive]: parse_strategy case/whitespace tolerance+unknown default fallback (line 20-25) same contract mergeable with priority case test
- **tests/regression_scheduler_workbench_link_guardrails.py** [MERGE:workbench_links_viewmodel]: tests scheduler_workbench_links guardrail logic: feedback-write/execution-review identity guards (build_workbench_link L27-258); same viewmodel+scaffold as links_contract
- **tests/regression_scheduler_analysis_diagnostic_contract.py** [KEEP_TRIM]: real diagnostic-section contract: payload shape, status translation, no-raw-field leak + sample truncation (line:263-273), bad/old shapes (line:313-350); many exact Chinese business-text asserts (line:253-254,304-310,430) brittle
- **tests/regression_resource_dispatch_workbench_lane_contract.py** [KEEP_TRIM]: 真测build_task_card与node实跑resource_execution_cards.js DOM回退及delta计算晚12分钟/早2分钟(L162-268)有价值但夹template/script顺序/JS源码grep(L100-159,207-215)脆性
- **tests/regression_gantt_task_detail_panel_contract.py** [KEEP_TRIM]: real viewmodel+integration: build_tasks no op_id leak, edges keep internal ids but public labels, meta uses execution facts via app+DB, detail links preserve context+guard review, preview no scenario_id leak (line 50-278); trim template/CSS layout snapshot (line 281-299)
- **tests/regression_scheduler_candidate_py38_contract.py** [DROP]: 门禁自指源码扫:正则+AST扫硬编码文件列表(含本测自身)查PEP585/X|None与重驱动import与CDN URL(L81-96)纯源码grep无业务逻辑应由CI/linter守
- **tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py** [KEEP_TRIM]: tests real route invalid-query redirect/sanitization+fail-closed 404+HTTP error mapping 400/500+_resolve_version logic (resource_dispatch_service.py L336-413); L27-32 greps template/js bundle as snippet tail
- **tests/regression_schedule_persistence_reject_empty_actionable_schedule.py** [KEEP_TRIM]: real persist safety-fuse + security redaction: empty payload rejected leaving no DB trace, user_message strips Traceback/sqlite/password/path (line:290-295); exact Chinese message parametrization line:122-146 brittle
- **tests/regression_schedule_history_not_created_for_empty_schedule.py** [KEEP_TRIM]: real no-op contract: empty actionable schedule raises ValidationError and leaves DB snapshot unchanged (line:91-97); line:89 Chinese message substring brittle
- **tests/regression_schedule_service_empty_reschedulable_rejected.py** [KEEP_TRIM]: real short-circuit: empty/terminal-only ops reject before build/optimize/persist/version (line:114-117); exact Chinese expected_message line:163-185 brittle
- **tests/regression_resource_dispatch_site_records_frontend_contract.py** [KEEP_TRIM]: 4个测真后端守卫_execution_review_link/_request_kwargs/incomplete-plan 400(L204-294)值得留但主体是JS/CSS/模板逐字串in source海量快照(L41-89,303-463)应删
- **tests/regression_scheduler_dispatch_plan_identity_guardrails.py** [KEEP_TRIM]: real ResourceDispatchService plan-identity write guardrails+readonly DB checks but tails read templates asserting copy presence (line 297-302) brittle
- **tests/smoke_e2e_excel_to_schedule.py** [ISOLATE_PERF]: 全链路happy-path smoke:全模块Excel导入->排产->甘特/周计划/报表/物料->OperationLogs键名抽检 慢全app E2E 写evidence line138 main 应隔离非删
- **tests/regression_reports_workbench_backlink_contract.py** [KEEP_TRIM]: 多场景验报表回链URL上下文透传+导出XLSX scope过滤+compute_downtime_impact真重叠算法(L416-439)有价值但夹report_plan_filter.js与模板源码grep(L240-248)脆性尾
- **tests/regression_frontend_ui_language_polish.py** [KEEP_TRIM]: real logic buried in copy-snapshot: normalizer round-trip on template enum values (line 462-481) + ensure_excel_templates overwrite-protect/preserve (line 484-619); trim heavy Chinese-hint/forbidden-term/source-grep snapshots (line 30-258,668-844)
- **tests/regression_scheduler_historical_plan_label_contract.py** [KEEP_TRIM]: viewmodel public_plan_role_options/build_report_context logic real (line 165-208) but route tests assert exact HTML span markup+literal labels via regex (line 54-162) brittle snapshot
- **tests/run_real_db_replay_check.py** [MERGE:real_db_replay_e2e]: E2E replay copies prod db + POST /scheduler/run + gantt/week-plan/reports checks (line 219-418) near-identical scaffold to _e2e/_smoke
- **tests/run_real_db_replay_smoke.py** [MERGE:real_db_replay_e2e]: E2E replay copies prod db + POST /scheduler/run + gantt/week-plan/reports sample (line 265-326) same contract as check/_e2e copy-pasted
- **tests/regression_gantt_critical_outline_sync.py** [KEEP_TRIM]: foundational shared DOM-shim+node-runner helpers imported by files 21/26 + real JS-exec tests: outline-sync geometry across zoom, task-name escaping sanitization (line 1688-1715), critical reason_code mapping without leaking sqlite/reason_code (line 1741-1825); trim template-scri
- **tests/regression_scheduler_candidate_week_plan_contract.py** [KEEP_TRIM]: L160-194 test _plan_context_from_data resolution + L233-271 verify Excel cells/DB-log filters real; but L205-216/227-230 assert exact Chinese copy+&amp; URL fragments in HTML (brittle snapshot tail)
- **tests/regression_config_field_spec_contract.py** [KEEP_TRIM]: real field-spec defaults/choices/strict-validation contract but heavy label+hint text snapshots (line91 最少超期, lines167-190 'X not in hint' negative text asserts)
- **tests/regression_scheduler_candidate_config_contract.py** [KEEP_TRIM]: 真测config字段默认/choices/严格数字校验/preset归一向后兼容/orchestrator按graph_analysis_mode开关方案对比与runtime字段透传(L195-403)真逻辑但夹模板缺串grep(L306-313)脆性尾
- **tests/regression_scheduler_plan_identity_summary_guardrail.py** [KEEP_TRIM]: resolve_plan summary parse_failed/superseded/writable logic real (line 116-223) but dashboard/dispatch/review tests assert exact visible Chinese copy+href absence on rendered pages (line 36-113 226-410) brittle snapshot
- **tests/regression_aps_workbench_flow_contract.py** [MERGE:workbench_context_propagation]: workbench home->page context propagation contract sharing reports_workbench_backlink_helpers (line 117-332)
- **tests/regression_scheduler_candidate_display_contract.py** [KEEP_TRIM]: 实跑build_candidate_comparison_display:按source_table判对比态/失败跳过候选surface/内部失败原因译为用户话/隐藏旧标签(L38-182)真viewmodel但夹_candidate_comparison.html源码grep(L17-35)脆性
- **tests/test_scheduler_run_view_result_contract.py** [KEEP_TRIM]: build_run_schedule_view_result headline/status/warning-filter/overdue-sample/secret-sanitization+route flash behavior (line 23-908) deep viewmodel logic but trim source-grep test asserting route symbols absent (line 372-380)
- **tests/regression_scheduler_config_route_contract.py** [KEEP_TRIM]: real route+ConfigService provenance/degradation logic but test at line 326 reads template+constants asserting exact Chinese copy presence/absence is brittle snapshot
- **tests/regression_manual_entry_scope.py** [KEEP_TRIM]: real src/page safe-url hardening (rejects evil.example) + manual md source-of-truth but bulk asserts exact HTML/aria/CSS class strings + greps ui_contract.css regression_manual_entry_scope.py:487
- **tests/test_scheduler_route_registration_contract.py** [MERGE:scheduler_route_registration]: subprocess verifies lazy registration registrar _REGISTERED+leaf-import isolation+idempotent register (line 42-101) structural invariant mergeable with factory registration smoke

## 表2 B依赖 ∩ A=KEEP — 内容保留但 P3改写/P6迁目录去前缀 会让锚点路径+行号漂移 (67个)
| B引用次数 | 文件 |
|---:|---|
| 53 | tests/test_ready_queue.py |
| 33 | tests/regression_execution_review_identity_guardrail.py |
| 25 | tests/regression_scheduler_config_spec_sync_contract.py |
| 18 | tests/regression_operation_execution_event_foundation.py |
| 18 | tests/regression_value_policies_matrix_contract.py |
| 17 | tests/regression_config_service_component_contract.py |
| 17 | tests/regression_number_utils_facade_delegates_strict_parse.py |
| 13 | tests/test_graph_dispatch_context.py |
| 13 | tests/regression_scheduler_user_visible_messages.py |
| 12 | tests/test_metrics_topology.py |
| 12 | tests/regression_compat_parse_emits_degradation.py |
| 11 | tests/regression_scheduler_graph_lazy_runtime_contract.py |
| 11 | tests/regression_plan_vs_actual_review.py |
| 10 | tests/regression_ortools_warmstart_failure_contract.py |
| 10 | tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py |
| 10 | tests/regression_gantt_critical_chain_unavailable.py |
| 10 | tests/regression_scheduler_plan_identity_evidence_contract.py |
| 9 | tests/regression_dispatch_rule_case_insensitive.py |
| 9 | tests/regression_report_context_filters_contract.py |
| 9 | tests/regression_gantt_contract_snapshot.py |
| 8 | tests/regression_schedule_service_facade_delegation.py |
| 8 | tests/regression_gantt_critical_chain_provider.py |
| 7 | tests/regression_config_validator_preset_degradation.py |
| 7 | tests/regression_config_snapshot_projection_sync.py |
| 6 | tests/regression_scheduler_wrapper_import_order_contract.py |
| 5 | tests/regression_schedule_config_snapshot_optional_guard.py |
| 5 | tests/regression_scheduler_delay_diagnosis_contract.py |
| 4 | tests/regression_migrations.py |
| 4 | tests/regression_migration_schema_contract.py |
| 4 | tests/test_scheduler_resource_dispatch_smoke.py |
| 4 | tests/regression_resource_dispatch_viewmodel_public_output_contract.py |
| 4 | tests/test_resource_dispatch_viewmodel.py |
| 4 | tests/regression_scheduler_reschedule_execution_facts.py |
| 4 | tests/test_schedule_repository_detail_queries.py |
| 4 | tests/regression_models_numeric_parse_hybrid_safe.py |
| 4 | tests/test_query_services.py |
| 4 | tests/test_greedy_scheduler_base_date.py |
| 3 | tests/regression_dashboard_workbench_contract.py |
| 3 | tests/regression_resource_dispatch_actual_import.py |
| 3 | tests/regression_operation_execution_feedback_routes.py |
| 3 | tests/regression_operation_execution_exception_feedback.py |
| 3 | tests/regression_due_exclusive_consistency.py |
| 3 | tests/regression_scheduler_candidate_runner_contract.py |
| 2 | tests/regression_scheduler_candidate_resource_dispatch_contract.py |
| 2 | tests/regression_due_exclusive_guard_contract.py |
| 2 | tests/regression_operation_execution_scope_read_contract.py |
| 2 | tests/regression_scheduler_candidate_plan_query_contract.py |
| 2 | tests/regression_restore_success_condition.py |
| 2 | tests/regression_config_service_strict_blank_contract.py |
| 2 | tests/regression_schedule_summary_cfg_snapshot_contract.py |
| 1 | tests/regression_operation_execution_event_sequence_contract.py |
| 1 | tests/regression_scheduler_navigation_unknown_plan_role_contract.py |
| 1 | tests/test_schedule_params_direct_call_contract.py |
| 1 | tests/regression_strict_parse_blank_required.py |
| 1 | tests/regression_schedule_optimizer_cfg_snapshot_contract.py |
| 1 | tests/regression_scheduler_graph_on_mode_contract.py |
| 1 | tests/regression_scheduler_candidate_summary_contract.py |
| 1 | tests/regression_operation_execution_state_flow.py |
| 1 | tests/regression_backup_restore_pending_verify_code.py |
| 1 | tests/smoke_phase0_phase1.py |
| 1 | tests/regression_maintenance_window_mutex.py |
| 1 | tests/regression_scheduler_config_manual_url_normalization.py |
| 1 | tests/regression_scheduler_run_surfaces_resource_pool_warning.py |
| 1 | tests/regression_safe_next_url_hardening.py |
| 1 | tests/regression_scheduler_excel_calendar_uses_executor.py |
| 1 | tests/regression_scheduler_missing_resource_message.py |
| 1 | tests/test_greedy_ordering_contract.py |

## 表3 B引用但不在A的645基线 — 需核实真身/是否B计划新建的安全网 (8个)
| B引用次数 | 文件 | tests/下存在? |
|---:|---|:--:|
| 21 | test_sgs_graph_ready.py | ✗(可能B拟新建/已改名/在别处) |
| 11 | regression_gantt_critical_chain_normalize_parity.py | ✗(可能B拟新建/已改名/在别处) |
| 6 | run_semantic_guards.py | ✗(可能B拟新建/已改名/在别处) |
| 6 | regression_boolean_normalize_wide_parity_contract.py | ✗(可能B拟新建/已改名/在别处) |
| 5 | run_drift_scan.py | ✗(可能B拟新建/已改名/在别处) |
| 2 | test_registry_groups_scheduler.py | ✗(可能B拟新建/已改名/在别处) |
| 1 | test_scheduler_utils.py | ✗(可能B拟新建/已改名/在别处) |
| 1 | run_state.py | ✗(可能B拟新建/已改名/在别处) |

## A 计划要改动的【门禁工具链/脚手架】文件(来自 PLAN.md/GOVERNANCE.md,非测试)
- scripts/run_daily_quality_gate.py  (P0.1 改 FOCUSED_PYTEST_NODEIDS)
- tools/test_registry_groups_scheduler.py (P0.3 收窄36个**通配)
- tools/test_registry_groups_misc.py (P0.3 收窄30个**通配)
- scripts/run_quality_gate.py (CLI不可改,内部编排P2可能动)
- scripts/sync_debt_ledger.py (基线SOP依赖)
- tools/check_full_test_debt.py (基线SOP依赖)
- tools/full_test_debt_shards.py (P2.1连带删硬编码文件名; load-bearing保留)
- tools/verify_required_regressions_from_full_test_debt.py (P2.2 M4 删)
- tools/long_gate_full_test_debt.py / long_gate_test_body_diff.py (P2.2 M2 删/简化)
- tools/long_gate_fingerprint.py (P2.2 M3 删Chrome指纹)
- tools/architecture_scan_cache.py (P2.2 删)
- tools/quality_gate_shared.py / quality_gate_ledger.py / quality_gate_support.py (门禁登记,近期task#16/#17刚改)
- tests/conftest.py:51-106 (P3.4 删main-style collector)
- tests/main_style_regression_runner.py (P3.4 删)
- tests/test_registry.py (P2.2 M4 删大半)

## B 的承重纪律(核对违规的判据)
- 承重护栏/灵魂线守卫:**只许补『我是故意的』注释 + 加 parity/contract 测试,严禁删/合并/passthrough/统一**。
- B 大量裁定把现有 parity/contract/regression 当『安全网』『差分oracle』『锚点』:如 R05/R22 parity、R52留作差分oracle、R71只加parity、R43整文件删wrapper契约测试、R13先迁测试后删。
- adopted-only 不变量已下沉 v19 DB CHECK。

## 待核对的8个维度(workflow agent 认领)
- D1 DROP直删冲突(sp05_topology引58次/sp06_no_dup引21次/candidate_py38引6次):B当它们什么用?删了塌不塌?
- D2 DROP_WITH_TOOL+门禁元系统(architecture_fitness引22次/check_quickref/selftest/缓存族):B执行验证+STARTUP_SAMPLE_EXPECTATIONS依赖
- D3 MERGE合并(5个B依赖文件入簇):合并后B锚点/断言在不在
- D4 KEEP_TRIM剪尾(~30个,重点silent_fallback/value_policies/parity/差分oracle):剪尾误删B依赖断言?
- D5 门禁基础设施(P0/P2改run_daily/test_registry_groups/long_gate/verify_required/sync_debt/conftest collector):B的三连验证+基线SOP+承重parity跑门禁被破坏?
- D6 锚点漂移量化(P3改写197+P6迁626去前缀+P5剪123):B的76份dossier有多少file:line锚点失效?
- D7 表3基线外8文件:真身/是否B拟新建安全网/A会不会碰
- D8 承重纪律冲突:A的删/合/剪有没有命中B标记的承重护栏/灵魂线守卫(最严重)