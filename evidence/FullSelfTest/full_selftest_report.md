# APS 全量自测汇总报告（不打包）

- 生成时间：2026-04-19 01:35:44
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- Python 可执行：`D:\py3.8\python.exe`
- 仓库根目录：`D:/Github/APS Test`
- fail_fast：false
- complex_repeat：1
- step_timeout_s：900
- head_sha：`33dc91b88f2fb4f14a60065c03d7e545c54756b7`
- git status --short：
  - ` M .github/workflows/quality.yml`
  - ` M .gitignore`
  - ` M README.md`
  - ` M core/algorithms/evaluation.py`
  - ` M core/algorithms/greedy/algo_stats.py`
  - ` M core/algorithms/greedy/config_adapter.py`
  - `M  core/algorithms/greedy/schedule_params.py`
  - ` M core/algorithms/greedy/scheduler.py`
  - `A  core/algorithms/objective_specs.py`
  - ` M core/infrastructure/database.py`
  - `A  core/models/objective.py`
  - ` M core/models/schedule.py`
  - ` M core/services/common/degradation.py`
  - ` M core/services/equipment/machine_downtime_service.py`
  - ` M core/services/equipment/machine_service.py`
  - ` M core/services/personnel/operator_service.py`
  - ` M core/services/personnel/resource_team_service.py`
  - ` M core/services/process/deletion_validator.py`
  - ` M core/services/process/op_type_service.py`
  - ` M core/services/scheduler/calendar_admin.py`
  - `A  core/services/scheduler/config/config_field_spec.py`
  - ` M core/services/scheduler/config/config_presets.py`
  - ` M core/services/scheduler/config/config_service.py`
  - ` M core/services/scheduler/config/config_snapshot.py`
  - ` M core/services/scheduler/config/config_validator.py`
  - ` M core/services/scheduler/gantt_critical_chain.py`
  - ` M core/services/scheduler/gantt_service.py`
  - ` M core/services/scheduler/resource_dispatch_range.py`
  - ` M core/services/scheduler/resource_dispatch_service.py`
  - ` M core/services/scheduler/resource_pool_builder.py`
  - ` M core/services/scheduler/run/freeze_window.py`
  - ` M core/services/scheduler/run/schedule_input_builder.py`
  - ` M core/services/scheduler/run/schedule_input_collector.py`
  - ` M core/services/scheduler/run/schedule_optimizer.py`
  - ` M core/services/scheduler/run/schedule_optimizer_steps.py`
  - ` M core/services/scheduler/run/schedule_orchestrator.py`
  - ` M core/services/scheduler/run/schedule_persistence.py`
  - ` M core/services/scheduler/schedule_service.py`
  - ` M core/services/scheduler/schedule_summary.py`
  - ` M core/services/scheduler/summary/schedule_summary.py`
  - ` M core/services/scheduler/summary/schedule_summary_assembly.py`
  - ` M core/services/scheduler/summary/schedule_summary_degradation.py`
  - ` M core/services/scheduler/summary/schedule_summary_freeze.py`
  - ` M core/services/scheduler/summary/schedule_summary_types.py`
  - ` M data/repositories/config_repo.py`
  - ` M data/repositories/machine_downtime_repo.py`
  - ` M data/repositories/schedule_history_repo.py`
  - ` M data/repositories/schedule_repo.py`
  - ` M evidence/ComplexExcelCases/complex_cases_report.md`
  - ` M evidence/ComplexExcelCases/complex_cases_summary.json`
  - ` M evidence/Conformance/quickref_vs_routes.md`
  - ` M evidence/DeepReview/reference_trace.md`
  - ` M evidence/FullE2E/excel_to_schedule_report.md`
  - ` M evidence/FullE2E/gantt_preview_complex_machine.html`
  - ` M evidence/FullE2E/gantt_preview_complex_operator.html`
  - ` M evidence/FullE2E/gantt_tasks_complex_machine.json`
  - ` M evidence/FullE2E/gantt_tasks_complex_operator.json`
  - ` M evidence/FullSelfTest/full_selftest_report.md`
  - ` M evidence/Phase0_Phase1/smoke_test_report.md`
  - ` M evidence/Phase0_to_Phase5/web_smoke_report.md`
  - ` M evidence/Phase0_to_Phase6/web_smoke_report.md`
  - ` M evidence/Phase10/smoke_phase10_report.md`
  - ` M evidence/Phase2/smoke_phase2_report.md`
  - ` M evidence/Phase3/smoke_phase3_report.md`
  - ` M evidence/Phase4/smoke_phase4_report.md`
  - ` M evidence/Phase5/smoke_phase5_report.md`
  - ` M evidence/Phase6/smoke_phase6_report.md`
  - ` M evidence/Phase7/smoke_phase7_report.md`
  - ` M evidence/Phase8/smoke_phase8_report.md`
  - ` M evidence/Phase9/smoke_phase9_report.md`
  - `A  pyrightconfig.gate.json`
  - ` M requirements-dev.txt`
  - `MM scripts/run_quality_gate.py`
  - ` M scripts/sync_debt_ledger.py`
  - ` M static/js/calendar_picker.js`
  - ` M static/js/gantt.js`
  - ` M static/js/gantt_boot.js`
  - ` M static/js/gantt_outline.js`
  - ` M static/js/gantt_render.js`
  - ` M templates/error.html`
  - ` M templates/personnel/calendar.html`
  - ` M templates/scheduler/analysis.html`
  - ` M templates/scheduler/batches.html`
  - ` M templates/scheduler/calendar.html`
  - ` M templates/scheduler/config.html`
  - ` M templates/scheduler/week_plan.html`
  - ` M templates/system/history.html`
  - ` M tests/regression_apply_preset_adjusted_marks_custom.py`
  - ` M tests/regression_auto_assign_persist_truthy_variants.py`
  - `A  tests/regression_config_field_metadata_shape.py`
  - `A  tests/regression_config_field_spec_contract.py`
  - ` M tests/regression_config_service_active_preset_custom_sync.py`
  - `AM tests/regression_config_service_relaxed_missing_visibility.py`
  - `A  tests/regression_config_snapshot_projection_sync.py`
  - ` M tests/regression_config_snapshot_strict_numeric.py`
  - ` M tests/regression_config_validator_preset_degradation.py`
  - ` M tests/regression_dict_cfg_contract.py`
  - `A  tests/regression_error_field_label_source.py`
  - ` M tests/regression_factory_request_lifecycle_observability.py`
  - ` M tests/regression_freeze_window_fail_closed_contract.py`
  - ` M tests/regression_gantt_contract_snapshot.py`
  - ` M tests/regression_gantt_critical_chain_cache_thread_safe.py`
  - ` M tests/regression_gantt_critical_outline_sync.py`
  - ` M tests/regression_improve_dispatch_modes.py`
  - ` M tests/regression_objective_case_normalization.py`
  - `A  tests/regression_objective_projection_contract.py`
  - ` M tests/regression_operator_machine_dirty_flags_visible.py`
  - `A  tests/regression_optimizer_seed_results_contract.py`
  - ` M tests/regression_request_scope_app_logger_binding.py`
  - `M  tests/regression_runtime_lock_reloader_parent_skip.py`
  - `M  tests/regression_runtime_stop_cli.py`
  - ` M tests/regression_safe_next_url_hardening.py`
  - ` M tests/regression_safe_next_url_observability.py`
  - ` M tests/regression_schedule_config_snapshot_optional_guard.py`
  - ` M tests/regression_schedule_input_builder_safe_float_parse.py`
  - ` M tests/regression_schedule_input_builder_template_missing_surfaces_event.py`
  - ` M tests/regression_schedule_optimizer_cfg_float_strict_blank.py`
  - `A  tests/regression_schedule_optimizer_cfg_snapshot_contract.py`
  - ` M tests/regression_schedule_orchestrator_contract.py`
  - ` M tests/regression_schedule_params_read_failure_visible.py`
  - ` M tests/regression_schedule_params_strict_blank_numeric.py`
  - ` M tests/regression_schedule_persistence_reject_empty_actionable_schedule.py`
  - ` M tests/regression_schedule_persistence_reschedulable_contract.py`
  - ` M tests/regression_schedule_service_all_frozen_short_circuit.py`
  - ` M tests/regression_schedule_service_facade_delegation.py`
  - ` M tests/regression_schedule_service_missing_resource_source_case_insensitive.py`
  - ` M tests/regression_schedule_service_passes_algo_stats_to_summary.py`
  - ` M tests/regression_schedule_service_reject_no_actionable_schedule_rows.py`
  - ` M tests/regression_schedule_service_reschedulable_contract.py`
  - ` M tests/regression_schedule_summary_algo_warnings_union.py`
  - `A  tests/regression_schedule_summary_cfg_snapshot_contract.py`
  - ` M tests/regression_schedule_summary_freeze_state_contract.py`
  - `AM tests/regression_schedule_summary_merge_context_degraded_code.py`
  - ` M tests/regression_schedule_summary_v11_contract.py`
  - ` M tests/regression_scheduler_analysis_observability.py`
  - ` M tests/regression_scheduler_analysis_route_contract.py`
  - `AM tests/regression_scheduler_analysis_vm_legacy_summary_bridge.py`
  - ` M tests/regression_scheduler_apply_preset_reject_invalid_numeric.py`
  - `AM tests/regression_scheduler_batches_degraded_visibility.py`
  - ` M tests/regression_scheduler_config_manual_url_normalization.py`
  - `MM tests/regression_scheduler_config_route_contract.py`
  - ` M tests/regression_scheduler_objective_labels.py`
  - ` M tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py`
  - `MM tests/regression_scheduler_run_surfaces_resource_pool_warning.py`
  - ` M tests/regression_scheduler_strict_mode_dispatch_flags.py`
  - `A  tests/regression_scheduler_user_visible_messages.py`
  - `A  tests/regression_scheduler_week_plan_summary_observability.py`
  - `A  tests/regression_scheduler_wrapper_import_order_contract.py`
  - `A  tests/regression_sp05_followup_contracts.py`
  - `D  tests/regression_sp05_path_topology_contract.py`
  - `A  tests/regression_sp06_no_duplicate_defs.py`
  - `M  tests/regression_startup_host_portfile.py`
  - `M  tests/regression_startup_host_portfile_new_ui.py`
  - ` M tests/regression_system_history_route_contract.py`
  - ` M tests/regression_week_plan_filename_uses_normalized_version.py`
  - ` M tests/regression_weighted_tardiness_objective.py`
  - ` M tests/run_complex_case_and_export_gantt.py`
  - `A  tests/runtime_cleanup_helper.py`
  - ` M tests/smoke_e2e_excel_to_schedule.py`
  - ` M tests/smoke_phase7.py`
  - ` M tests/smoke_phase8.py`
  - ` M tests/test_architecture_fitness.py`
  - ` M tests/test_holiday_default_efficiency_read_guard.py`
  - `AM tests/test_run_full_selftest_report_metadata.py`
  - `MM tests/test_run_quality_gate.py`
  - `R  tests/regression_schedule_input_builder_strict_hours_and_ext_days.py -> tests/test_schedule_input_builder_strict_hours_and_ext_days.py`
  - `A  tests/test_schedule_params_direct_call_contract.py`
  - ` M tests/test_schedule_summary_observability.py`
  - `A  tests/test_scheduler_followup_root_collect.py`
  - `A  tests/test_sp05_path_topology_contract.py`
  - ` M tests/test_sync_debt_ledger.py`
  - ` M tests/test_ui_mode.py`
  - `M  tests/test_win7_launcher_runtime_paths.py`
  - `MM tools/quality_gate_shared.py`
  - ` M tools/quality_gate_support.py`
  - `M  web/bootstrap/entrypoint.py`
  - ` M web/bootstrap/factory.py`
  - `M  web/bootstrap/launcher.py`
  - ` M web/error_handlers.py`
  - `A  web/routes/_scheduler_compat.py`
  - ` M web/routes/domains/scheduler/__init__.py`
  - ` M web/routes/domains/scheduler/scheduler_analysis.py`
  - ` M web/routes/domains/scheduler/scheduler_batches.py`
  - `MM web/routes/domains/scheduler/scheduler_bp.py`
  - ` M web/routes/domains/scheduler/scheduler_calendar_pages.py`
  - `MM web/routes/domains/scheduler/scheduler_config.py`
  - `AM web/routes/domains/scheduler/scheduler_config_display_state.py`
  - ` M web/routes/domains/scheduler/scheduler_pages.py`
  - ` M web/routes/domains/scheduler/scheduler_resource_dispatch.py`
  - `A  web/routes/domains/scheduler/scheduler_route_registrar.py`
  - `MM web/routes/domains/scheduler/scheduler_run.py`
  - `MM web/routes/domains/scheduler/scheduler_week_plan.py`
  - ` M web/routes/navigation_utils.py`
  - ` M web/routes/normalizers.py`
  - ` M web/routes/personnel_calendar_pages.py`
  - ` M web/routes/scheduler_analysis.py`
  - ` M web/routes/scheduler_batch_detail.py`
  - ` M web/routes/scheduler_batches.py`
  - ` M web/routes/scheduler_config.py`
  - ` M web/routes/scheduler_excel_batches.py`
  - ` M web/routes/scheduler_excel_calendar.py`
  - ` M web/routes/scheduler_ops.py`
  - ` M web/routes/scheduler_run.py`
  - ` M web/routes/scheduler_week_plan.py`
  - ` M web/routes/system_history.py`
  - ` M web/routes/system_ui_mode.py`
  - ` M web/routes/system_utils.py`
  - ` M web/ui_mode.py`
  - `A  web/viewmodels/scheduler_analysis_labels.py`
  - `A  web/viewmodels/scheduler_analysis_trends.py`
  - ` M web/viewmodels/scheduler_analysis_vm.py`
  - `AM web/viewmodels/scheduler_degradation_presenter.py`
  - `A  web/viewmodels/scheduler_summary_display.py`
  - ` M web_new_test/templates/scheduler/batches.html`
  - ` M web_new_test/templates/scheduler/config.html`
  - ` M "\345\274\200\345\217\221\346\226\207\346\241\243/README.md"`
  - ` M "\345\274\200\345\217\221\346\226\207\346\241\243/\345\256\236\347\216\260\350\256\241\345\210\222\350\241\250.md"`
  - ` M "\345\274\200\345\217\221\346\226\207\346\241\243/\345\274\200\345\217\221\346\226\207\346\241\243.md"`
  - `MM "\345\274\200\345\217\221\346\226\207\346\241\243/\346\212\200\346\234\257\345\200\272\345\212\241\346\262\273\347\220\206\345\217\260\350\264\246.md"`
  - ` M "\345\274\200\345\217\221\346\226\207\346\241\243/\347\263\273\347\273\237\351\200\237\346\237\245\350\241\250.md"`
  - ` M "\345\274\200\345\217\221\346\226\207\346\241\243/\351\230\266\346\256\265\347\225\231\347\227\225\344\270\216\351\252\214\346\224\266\350\256\260\345\275\225.md"`
  - `?? audit/2026-04/20260416_SP05_SP06_followup_fix_notes.md`
  - `?? audit/2026-04/20260417_1054_deep_review.md`
  - `?? audit/2026-04/20260417_pyright_gate_inventory.md`
  - `?? templates/error_base.html`
  - `?? tests/regression_config_presets_baseline_degraded_visible.py`
  - `?? tests/regression_config_service_strict_blank_contract.py`
  - `?? tests/regression_config_validator_relaxed_contract.py`
  - `?? tests/regression_error_boundary_contract.py`
  - `?? tests/regression_gantt_critical_chain_unavailable.py`
  - `?? tests/regression_schedule_summary_input_fallback_contract.py`
  - `?? web/error_boundary.py`
- quality_gate_manifest：`evidence\QualityGate\quality_gate_manifest.json`

## 总结

- 结论：**FAIL**
- 记录数：318

## 明细

| # | 脚本 | 结果 | exit | 耗时(s) | 证据(evidence) | runner日志 | 备注 |
|---:|---|---|---:|---:|---|---|---|
| 1 | `smoke_phase0_phase1.py` | PASS | 0 | 2.70 | evidence/Phase0_Phase1/smoke_test_report.md | evidence/FullSelfTest/logs/01_smoke_phase0_phase1.py.log.txt | - |
| 2 | `smoke_phase2.py` | PASS | 0 | 0.40 | evidence/Phase2/smoke_phase2_report.md | evidence/FullSelfTest/logs/02_smoke_phase2.py.log.txt | - |
| 3 | `smoke_phase3.py` | PASS | 0 | 1.14 | evidence/Phase3/smoke_phase3_report.md | evidence/FullSelfTest/logs/03_smoke_phase3.py.log.txt | - |
| 4 | `smoke_phase4.py` | PASS | 0 | 1.17 | evidence/Phase4/smoke_phase4_report.md | evidence/FullSelfTest/logs/04_smoke_phase4.py.log.txt | - |
| 5 | `smoke_phase5.py` | PASS | 0 | 1.25 | evidence/Phase5/smoke_phase5_report.md | evidence/FullSelfTest/logs/05_smoke_phase5.py.log.txt | - |
| 6 | `smoke_phase6.py` | PASS | 0 | 1.45 | evidence/Phase6/smoke_phase6_report.md | evidence/FullSelfTest/logs/06_smoke_phase6.py.log.txt | - |
| 7 | `smoke_phase7.py` | PASS | 0 | 1.88 | evidence/Phase7/smoke_phase7_report.md | evidence/FullSelfTest/logs/07_smoke_phase7.py.log.txt | - |
| 8 | `smoke_phase8.py` | PASS | 0 | 2.59 | evidence/Phase8/smoke_phase8_report.md | evidence/FullSelfTest/logs/08_smoke_phase8.py.log.txt | - |
| 9 | `smoke_phase9.py` | PASS | 0 | 27.25 | evidence/Phase9/smoke_phase9_report.md | evidence/FullSelfTest/logs/09_smoke_phase9.py.log.txt | - |
| 10 | `smoke_phase10_sgs_auto_assign.py` | PASS | 0 | 1.86 | evidence/Phase10/smoke_phase10_report.md | evidence/FullSelfTest/logs/10_smoke_phase10_sgs_auto_assign.py.log.txt | Phase10 报告显示 PASS：D:/Github/APS Test/evidence/Phase10/smoke_phase10_report.md |
| 11 | `smoke_web_phase0_5.py` | PASS | 0 | 3.24 | evidence/Phase0_to_Phase5/web_smoke_report.md | evidence/FullSelfTest/logs/11_smoke_web_phase0_5.py.log.txt | - |
| 12 | `smoke_web_phase0_6.py` | PASS | 0 | 3.03 | evidence/Phase0_to_Phase6/web_smoke_report.md | evidence/FullSelfTest/logs/12_smoke_web_phase0_6.py.log.txt | - |
| 13 | `smoke_e2e_excel_to_schedule.py` | PASS | 0 | 3.95 | evidence/FullE2E/excel_to_schedule_report.md | evidence/FullSelfTest/logs/13_smoke_e2e_excel_to_schedule.py.log.txt | - |
| 14 | `regression_analysis_page_version_default_latest.py` | PASS | 0 | 3.44 | - | evidence/FullSelfTest/logs/14_regression_analysis_page_version_default_latest.py.log.txt | - |
| 15 | `regression_app_db_path_no_dirname.py` | PASS | 0 | 3.02 | - | evidence/FullSelfTest/logs/15_regression_app_db_path_no_dirname.py.log.txt | - |
| 16 | `regression_app_new_ui_secret_key_runtime_ensure.py` | PASS | 0 | 3.04 | - | evidence/FullSelfTest/logs/16_regression_app_new_ui_secret_key_runtime_ensure.py.log.txt | - |
| 17 | `regression_app_new_ui_security_hardening_enabled.py` | PASS | 0 | 3.37 | - | evidence/FullSelfTest/logs/17_regression_app_new_ui_security_hardening_enabled.py.log.txt | - |
| 18 | `regression_app_new_ui_session_contract.py` | PASS | 0 | 3.18 | - | evidence/FullSelfTest/logs/18_regression_app_new_ui_session_contract.py.log.txt | - |
| 19 | `regression_apply_preset_adjusted_marks_custom.py` | PASS | 0 | 2.04 | - | evidence/FullSelfTest/logs/19_regression_apply_preset_adjusted_marks_custom.py.log.txt | - |
| 20 | `regression_auto_assign_empty_resource_pool.py` | PASS | 0 | 2.03 | - | evidence/FullSelfTest/logs/20_regression_auto_assign_empty_resource_pool.py.log.txt | - |
| 21 | `regression_auto_assign_fixed_operator_respects_op_type.py` | PASS | 0 | 2.02 | - | evidence/FullSelfTest/logs/21_regression_auto_assign_fixed_operator_respects_op_type.py.log.txt | - |
| 22 | `regression_auto_assign_persist_truthy_variants.py` | PASS | 0 | 2.25 | - | evidence/FullSelfTest/logs/22_regression_auto_assign_persist_truthy_variants.py.log.txt | - |
| 23 | `regression_backup_restore_pending_verify_code.py` | PASS | 0 | 1.19 | - | evidence/FullSelfTest/logs/23_regression_backup_restore_pending_verify_code.py.log.txt | - |
| 24 | `regression_batch_detail_linkage.py` | PASS | 0 | 3.10 | - | evidence/FullSelfTest/logs/24_regression_batch_detail_linkage.py.log.txt | - |
| 25 | `regression_batch_excel_import_reject_part_change_without_rebuild.py` | PASS | 0 | 2.02 | - | evidence/FullSelfTest/logs/25_regression_batch_excel_import_reject_part_change_without_rebuild.py.log.txt | - |
| 26 | `regression_batch_excel_import_strict_mode_hardfail_atomic.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/26_regression_batch_excel_import_strict_mode_hardfail_atomic.py.log.txt | - |
| 27 | `regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py` | PASS | 0 | 3.14 | - | evidence/FullSelfTest/logs/27_regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py.log.txt | - |
| 28 | `regression_batch_import_unchanged_no_rebuild.py` | PASS | 0 | 2.01 | - | evidence/FullSelfTest/logs/28_regression_batch_import_unchanged_no_rebuild.py.log.txt | - |
| 29 | `regression_batch_order_bid_unboundlocal.py` | PASS | 0 | 2.01 | - | evidence/FullSelfTest/logs/29_regression_batch_order_bid_unboundlocal.py.log.txt | - |
| 30 | `regression_batch_order_override_dedup.py` | PASS | 0 | 2.04 | - | evidence/FullSelfTest/logs/30_regression_batch_order_override_dedup.py.log.txt | - |
| 31 | `regression_batch_service_legacy_template_resolver_rejects_strict_mode.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/31_regression_batch_service_legacy_template_resolver_rejects_strict_mode.py.log.txt | - |
| 32 | `regression_batch_service_strict_mode_template_autoparse.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/32_regression_batch_service_strict_mode_template_autoparse.py.log.txt | - |
| 33 | `regression_batch_service_update_reject_part_change_without_rebuild.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/33_regression_batch_service_update_reject_part_change_without_rebuild.py.log.txt | - |
| 34 | `regression_batch_template_autobuild_same_tx.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/34_regression_batch_template_autobuild_same_tx.py.log.txt | - |
| 35 | `regression_build_outcome_contract.py` | PASS | 0 | 1.10 | - | evidence/FullSelfTest/logs/35_regression_build_outcome_contract.py.log.txt | - |
| 36 | `regression_calendar_export_normalization.py` | PASS | 0 | 3.26 | - | evidence/FullSelfTest/logs/36_regression_calendar_export_normalization.py.log.txt | - |
| 37 | `regression_calendar_no_tx_hardening.py` | PASS | 0 | 2.15 | - | evidence/FullSelfTest/logs/37_regression_calendar_no_tx_hardening.py.log.txt | - |
| 38 | `regression_calendar_pages_readside_normalization.py` | PASS | 0 | 3.17 | - | evidence/FullSelfTest/logs/38_regression_calendar_pages_readside_normalization.py.log.txt | - |
| 39 | `regression_calendar_shift_hours_roundtrip.py` | PASS | 0 | 2.17 | - | evidence/FullSelfTest/logs/39_regression_calendar_shift_hours_roundtrip.py.log.txt | - |
| 40 | `regression_calendar_shift_start_rollover.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/40_regression_calendar_shift_start_rollover.py.log.txt | - |
| 41 | `regression_check_manual_layout_runtime_resolution.py` | PASS | 0 | 2.45 | - | evidence/FullSelfTest/logs/41_regression_check_manual_layout_runtime_resolution.py.log.txt | - |
| 42 | `regression_common_broad_false_fixed.py` | PASS | 0 | 1.12 | - | evidence/FullSelfTest/logs/42_regression_common_broad_false_fixed.py.log.txt | - |
| 43 | `regression_compat_parse_emits_degradation.py` | PASS | 0 | 1.09 | - | evidence/FullSelfTest/logs/43_regression_compat_parse_emits_degradation.py.log.txt | - |
| 44 | `regression_config_field_metadata_shape.py` | PASS | 0 | 2.12 | - | evidence/FullSelfTest/logs/44_regression_config_field_metadata_shape.py.log.txt | - |
| 45 | `regression_config_field_spec_contract.py` | PASS | 0 | 2.20 | - | evidence/FullSelfTest/logs/45_regression_config_field_spec_contract.py.log.txt | - |
| 46 | `regression_config_manual_markdown.py` | PASS | 0 | 3.32 | - | evidence/FullSelfTest/logs/46_regression_config_manual_markdown.py.log.txt | - |
| 47 | `regression_config_service_active_preset_custom_sync.py` | PASS | 0 | 2.15 | - | evidence/FullSelfTest/logs/47_regression_config_service_active_preset_custom_sync.py.log.txt | - |
| 48 | `regression_config_service_relaxed_missing_visibility.py` | PASS | 0 | 2.10 | - | evidence/FullSelfTest/logs/48_regression_config_service_relaxed_missing_visibility.py.log.txt | - |
| 49 | `regression_config_snapshot_projection_sync.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/49_regression_config_snapshot_projection_sync.py.log.txt | - |
| 50 | `regression_config_snapshot_strict_numeric.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/50_regression_config_snapshot_strict_numeric.py.log.txt | - |
| 51 | `regression_config_validator_preset_degradation.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/51_regression_config_validator_preset_degradation.py.log.txt | - |
| 52 | `regression_dashboard_overdue_count_tolerance.py` | PASS | 0 | 3.20 | - | evidence/FullSelfTest/logs/52_regression_dashboard_overdue_count_tolerance.py.log.txt | - |
| 53 | `regression_degradation_collector_merge_counts.py` | PASS | 0 | 1.13 | - | evidence/FullSelfTest/logs/53_regression_degradation_collector_merge_counts.py.log.txt | - |
| 54 | `regression_deletion_validator_source_case_insensitive.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/54_regression_deletion_validator_source_case_insensitive.py.log.txt | - |
| 55 | `regression_dict_cfg_contract.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/55_regression_dict_cfg_contract.py.log.txt | - |
| 56 | `regression_dispatch_blocking_consistency.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/56_regression_dispatch_blocking_consistency.py.log.txt | - |
| 57 | `regression_dispatch_rule_case_insensitive.py` | PASS | 0 | 1.15 | - | evidence/FullSelfTest/logs/57_regression_dispatch_rule_case_insensitive.py.log.txt | - |
| 58 | `regression_dispatch_rules_nonfinite_proc_hours_safe.py` | PASS | 0 | 1.15 | - | evidence/FullSelfTest/logs/58_regression_dispatch_rules_nonfinite_proc_hours_safe.py.log.txt | - |
| 59 | `regression_dispatch_rules_priority_case_insensitive.py` | PASS | 0 | 1.15 | - | evidence/FullSelfTest/logs/59_regression_dispatch_rules_priority_case_insensitive.py.log.txt | - |
| 60 | `regression_downtime_overlap_skips_invalid_segments.py` | PASS | 0 | 1.14 | - | evidence/FullSelfTest/logs/60_regression_downtime_overlap_skips_invalid_segments.py.log.txt | - |
| 61 | `regression_due_exclusive_consistency.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/61_regression_due_exclusive_consistency.py.log.txt | - |
| 62 | `regression_due_exclusive_guard_contract.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/62_regression_due_exclusive_guard_contract.py.log.txt | - |
| 63 | `regression_efficiency_greater_than_one_shortens_hours.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/63_regression_efficiency_greater_than_one_shortens_hours.py.log.txt | - |
| 64 | `regression_ensure_schema_fastforward_empty_only.py` | PASS | 0 | 1.83 | - | evidence/FullSelfTest/logs/64_regression_ensure_schema_fastforward_empty_only.py.log.txt | - |
| 65 | `regression_entrypoint_meta_failure_visible.py` | PASS | 0 | 2.67 | - | evidence/FullSelfTest/logs/65_regression_entrypoint_meta_failure_visible.py.log.txt | - |
| 66 | `regression_error_field_label_source.py` | PASS | 0 | 3.15 | - | evidence/FullSelfTest/logs/66_regression_error_field_label_source.py.log.txt | - |
| 67 | `regression_excel_backend_factory_observability.py` | PASS | 0 | 1.89 | - | evidence/FullSelfTest/logs/67_regression_excel_backend_factory_observability.py.log.txt | - |
| 68 | `regression_excel_demo_upload_guard.py` | PASS | 0 | 3.19 | - | evidence/FullSelfTest/logs/68_regression_excel_demo_upload_guard.py.log.txt | - |
| 69 | `regression_excel_failure_semantics_contracts.py` | PASS | 0 | 2.22 | - | evidence/FullSelfTest/logs/69_regression_excel_failure_semantics_contracts.py.log.txt | - |
| 70 | `regression_excel_import_executor_status_gate.py` | PASS | 0 | 1.12 | - | evidence/FullSelfTest/logs/70_regression_excel_import_executor_status_gate.py.log.txt | - |
| 71 | `regression_excel_import_result_semantics.py` | FAIL | 1 | 4.09 | - | evidence/FullSelfTest/logs/71_regression_excel_import_result_semantics.py.log.txt | exit_code!=0 |
| 72 | `regression_excel_import_strict_reference_apply.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/72_regression_excel_import_strict_reference_apply.py.log.txt | - |
| 73 | `regression_excel_normalizers_mixed_case.py` | PASS | 0 | 2.40 | - | evidence/FullSelfTest/logs/73_regression_excel_normalizers_mixed_case.py.log.txt | - |
| 74 | `regression_excel_operator_calendar_cross_midnight.py` | PASS | 0 | 1.21 | - | evidence/FullSelfTest/logs/74_regression_excel_operator_calendar_cross_midnight.py.log.txt | - |
| 75 | `regression_excel_preview_confirm_baseline_guard.py` | FAIL | 1 | 4.04 | - | evidence/FullSelfTest/logs/75_regression_excel_preview_confirm_baseline_guard.py.log.txt | exit_code!=0 |
| 76 | `regression_excel_preview_confirm_extra_state_guard.py` | FAIL | 1 | 4.06 | - | evidence/FullSelfTest/logs/76_regression_excel_preview_confirm_extra_state_guard.py.log.txt | exit_code!=0 |
| 77 | `regression_excel_route_strict_numeric.py` | PASS | 0 | 2.37 | - | evidence/FullSelfTest/logs/77_regression_excel_route_strict_numeric.py.log.txt | - |
| 78 | `regression_excel_routes_no_tx_surface_hidden.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/78_regression_excel_routes_no_tx_surface_hidden.py.log.txt | - |
| 79 | `regression_excel_service_calc_changes_row.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/79_regression_excel_service_calc_changes_row.py.log.txt | - |
| 80 | `regression_excel_source_row_num_preserved.py` | PASS | 0 | 1.26 | - | evidence/FullSelfTest/logs/80_regression_excel_source_row_num_preserved.py.log.txt | - |
| 81 | `regression_excel_validators_yesno_mixed_case.py` | PASS | 0 | 1.19 | - | evidence/FullSelfTest/logs/81_regression_excel_validators_yesno_mixed_case.py.log.txt | - |
| 82 | `regression_exit_backup_maintenance.py` | PASS | 0 | 2.57 | - | evidence/FullSelfTest/logs/82_regression_exit_backup_maintenance.py.log.txt | - |
| 83 | `regression_exit_backup_reloader_parent_skip.py` | PASS | 0 | 2.54 | - | evidence/FullSelfTest/logs/83_regression_exit_backup_reloader_parent_skip.py.log.txt | - |
| 84 | `regression_exit_backup_respects_config.py` | PASS | 0 | 2.60 | - | evidence/FullSelfTest/logs/84_regression_exit_backup_respects_config.py.log.txt | - |
| 85 | `regression_external_group_route_surfaces_fallback_warning.py` | PASS | 0 | 3.13 | - | evidence/FullSelfTest/logs/85_regression_external_group_route_surfaces_fallback_warning.py.log.txt | - |
| 86 | `regression_external_group_service_compatible_mode_logs_fallback.py` | PASS | 0 | 1.97 | - | evidence/FullSelfTest/logs/86_regression_external_group_service_compatible_mode_logs_fallback.py.log.txt | - |
| 87 | `regression_external_group_service_merge_mode_case_insensitive.py` | PASS | 0 | 1.96 | - | evidence/FullSelfTest/logs/87_regression_external_group_service_merge_mode_case_insensitive.py.log.txt | - |
| 88 | `regression_external_group_service_strict_mode_blank_days.py` | PASS | 0 | 1.94 | - | evidence/FullSelfTest/logs/88_regression_external_group_service_strict_mode_blank_days.py.log.txt | - |
| 89 | `regression_external_merge_mode_case_insensitive.py` | PASS | 0 | 1.16 | - | evidence/FullSelfTest/logs/89_regression_external_merge_mode_case_insensitive.py.log.txt | - |
| 90 | `regression_factory_request_lifecycle_observability.py` | PASS | 0 | 9.09 | - | evidence/FullSelfTest/logs/90_regression_factory_request_lifecycle_observability.py.log.txt | - |
| 91 | `regression_field_parse_contract.py` | PASS | 0 | 1.07 | - | evidence/FullSelfTest/logs/91_regression_field_parse_contract.py.log.txt | - |
| 92 | `regression_freeze_window_bounds.py` | PASS | 0 | 2.25 | - | evidence/FullSelfTest/logs/92_regression_freeze_window_bounds.py.log.txt | - |
| 93 | `regression_freeze_window_fail_closed_contract.py` | PASS | 0 | 2.05 | - | evidence/FullSelfTest/logs/93_regression_freeze_window_fail_closed_contract.py.log.txt | - |
| 94 | `regression_frontend_common_interactions.py` | PASS | 0 | 1.10 | - | evidence/FullSelfTest/logs/94_regression_frontend_common_interactions.py.log.txt | - |
| 95 | `regression_gantt_bad_time_rows_surface_degraded.py` | PASS | 0 | 2.03 | - | evidence/FullSelfTest/logs/95_regression_gantt_bad_time_rows_surface_degraded.py.log.txt | - |
| 96 | `regression_gantt_calendar_load_failed_degraded.py` | PASS | 0 | 3.17 | - | evidence/FullSelfTest/logs/96_regression_gantt_calendar_load_failed_degraded.py.log.txt | - |
| 97 | `regression_gantt_contract_snapshot.py` | PASS | 0 | 3.27 | - | evidence/FullSelfTest/logs/97_regression_gantt_contract_snapshot.py.log.txt | - |
| 98 | `regression_gantt_critical_chain_cache_thread_safe.py` | PASS | 0 | 3.11 | - | evidence/FullSelfTest/logs/98_regression_gantt_critical_chain_cache_thread_safe.py.log.txt | - |
| 99 | `regression_gantt_critical_outline_sync.py` | PASS | 0 | 1.48 | - | evidence/FullSelfTest/logs/99_regression_gantt_critical_outline_sync.py.log.txt | - |
| 100 | `regression_gantt_invalid_summary_surfaces_overdue_degraded.py` | PASS | 0 | 3.20 | - | evidence/FullSelfTest/logs/100_regression_gantt_invalid_summary_surfaces_overdue_degraded.py.log.txt | - |
| 101 | `regression_gantt_offset_range_consistency.py` | PASS | 0 | 3.19 | - | evidence/FullSelfTest/logs/101_regression_gantt_offset_range_consistency.py.log.txt | - |
| 102 | `regression_gantt_page_version_default_latest.py` | PASS | 0 | 3.23 | - | evidence/FullSelfTest/logs/102_regression_gantt_page_version_default_latest.py.log.txt | - |
| 103 | `regression_gantt_partial_overdue_summary_surfaces_warning.py` | PASS | 0 | 3.34 | - | evidence/FullSelfTest/logs/103_regression_gantt_partial_overdue_summary_surfaces_warning.py.log.txt | - |
| 104 | `regression_gantt_status_mode_semantics.py` | PASS | 0 | 1.19 | - | evidence/FullSelfTest/logs/104_regression_gantt_status_mode_semantics.py.log.txt | - |
| 105 | `regression_gantt_url_persistence.py` | PASS | 0 | 3.15 | - | evidence/FullSelfTest/logs/105_regression_gantt_url_persistence.py.log.txt | - |
| 106 | `regression_greedy_date_parsers.py` | PASS | 0 | 1.16 | - | evidence/FullSelfTest/logs/106_regression_greedy_date_parsers.py.log.txt | - |
| 107 | `regression_greedy_scheduler_algo_stats_auto_assign.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/107_regression_greedy_scheduler_algo_stats_auto_assign.py.log.txt | - |
| 108 | `regression_greedy_scheduler_algo_stats_seed_counts.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/108_regression_greedy_scheduler_algo_stats_seed_counts.py.log.txt | - |
| 109 | `regression_import_execution_stats_source_row_num.py` | PASS | 0 | 1.18 | - | evidence/FullSelfTest/logs/109_regression_import_execution_stats_source_row_num.py.log.txt | - |
| 110 | `regression_improve_dispatch_modes.py` | PASS | 0 | 2.02 | - | evidence/FullSelfTest/logs/110_regression_improve_dispatch_modes.py.log.txt | - |
| 111 | `regression_lazy_select_orphan_option.py` | PASS | 0 | 3.11 | - | evidence/FullSelfTest/logs/111_regression_lazy_select_orphan_option.py.log.txt | - |
| 112 | `regression_legacy_external_days_defaulted_visible.py` | PASS | 0 | 2.04 | - | evidence/FullSelfTest/logs/112_regression_legacy_external_days_defaulted_visible.py.log.txt | - |
| 113 | `regression_maintenance_jobstate_retry_signal.py` | PASS | 0 | 1.33 | - | evidence/FullSelfTest/logs/113_regression_maintenance_jobstate_retry_signal.py.log.txt | - |
| 114 | `regression_maintenance_real_oplog_visibility.py` | PASS | 0 | 1.33 | - | evidence/FullSelfTest/logs/114_regression_maintenance_real_oplog_visibility.py.log.txt | - |
| 115 | `regression_maintenance_telemetry_isolation.py` | PASS | 0 | 1.37 | - | evidence/FullSelfTest/logs/115_regression_maintenance_telemetry_isolation.py.log.txt | - |
| 116 | `regression_maintenance_window_mutex.py` | PASS | 0 | 1.36 | - | evidence/FullSelfTest/logs/116_regression_maintenance_window_mutex.py.log.txt | - |
| 117 | `regression_manual_entry_scope.py` | PASS | 0 | 4.47 | - | evidence/FullSelfTest/logs/117_regression_manual_entry_scope.py.log.txt | - |
| 118 | `regression_metrics_horizon_semantics.py` | PASS | 0 | 1.15 | - | evidence/FullSelfTest/logs/118_regression_metrics_horizon_semantics.py.log.txt | - |
| 119 | `regression_metrics_to_dict_nonfinite_safe.py` | PASS | 0 | 1.14 | - | evidence/FullSelfTest/logs/119_regression_metrics_to_dict_nonfinite_safe.py.log.txt | - |
| 120 | `regression_migrate_backup_dir_none_creates_backup.py` | PASS | 0 | 1.27 | - | evidence/FullSelfTest/logs/120_regression_migrate_backup_dir_none_creates_backup.py.log.txt | - |
| 121 | `regression_migrate_v2_unify_workcalendar_day_type.py` | PASS | 0 | 1.76 | - | evidence/FullSelfTest/logs/121_regression_migrate_v2_unify_workcalendar_day_type.py.log.txt | - |
| 122 | `regression_migrate_v4_sanitize_enum_text_fields.py` | PASS | 0 | 1.77 | - | evidence/FullSelfTest/logs/122_regression_migrate_v4_sanitize_enum_text_fields.py.log.txt | - |
| 123 | `regression_migrate_v5_normalize_operator_machine_legacy_values.py` | PASS | 0 | 1.80 | - | evidence/FullSelfTest/logs/123_regression_migrate_v5_normalize_operator_machine_legacy_values.py.log.txt | - |
| 124 | `regression_migration_failfast_no_backup_storm.py` | PASS | 0 | 1.25 | - | evidence/FullSelfTest/logs/124_regression_migration_failfast_no_backup_storm.py.log.txt | - |
| 125 | `regression_migration_outcome_partial_no_upgrade.py` | PASS | 0 | 1.23 | - | evidence/FullSelfTest/logs/125_regression_migration_outcome_partial_no_upgrade.py.log.txt | - |
| 126 | `regression_migration_outcome_skip_no_upgrade.py` | PASS | 0 | 1.80 | - | evidence/FullSelfTest/logs/126_regression_migration_outcome_skip_no_upgrade.py.log.txt | - |
| 127 | `regression_model_enums_case_insensitive.py` | PASS | 0 | 1.13 | - | evidence/FullSelfTest/logs/127_regression_model_enums_case_insensitive.py.log.txt | - |
| 128 | `regression_models_numeric_parse_hybrid_safe.py` | PASS | 0 | 1.08 | - | evidence/FullSelfTest/logs/128_regression_models_numeric_parse_hybrid_safe.py.log.txt | - |
| 129 | `regression_new_ui_strict_mode_controls_present.py` | PASS | 0 | 1.10 | - | evidence/FullSelfTest/logs/129_regression_new_ui_strict_mode_controls_present.py.log.txt | - |
| 130 | `regression_normalization_matrix_single_source.py` | PASS | 0 | 2.28 | - | evidence/FullSelfTest/logs/130_regression_normalization_matrix_single_source.py.log.txt | - |
| 131 | `regression_number_utils_facade_delegates_strict_parse.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/131_regression_number_utils_facade_delegates_strict_parse.py.log.txt | - |
| 132 | `regression_objective_case_normalization.py` | PASS | 0 | 2.11 | - | evidence/FullSelfTest/logs/132_regression_objective_case_normalization.py.log.txt | - |
| 133 | `regression_objective_projection_contract.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/133_regression_objective_projection_contract.py.log.txt | - |
| 134 | `regression_operation_edit_external_days_required.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/134_regression_operation_edit_external_days_required.py.log.txt | - |
| 135 | `regression_operator_calendar_override_allows_work_on_global_holiday.py` | PASS | 0 | 2.14 | - | evidence/FullSelfTest/logs/135_regression_operator_calendar_override_allows_work_on_global_holiday.py.log.txt | - |
| 136 | `regression_operator_machine_detail_readside_normalization.py` | PASS | 0 | 3.23 | - | evidence/FullSelfTest/logs/136_regression_operator_machine_detail_readside_normalization.py.log.txt | - |
| 137 | `regression_operator_machine_dirty_flags_visible.py` | PASS | 0 | 3.16 | - | evidence/FullSelfTest/logs/137_regression_operator_machine_dirty_flags_visible.py.log.txt | - |
| 138 | `regression_operator_machine_missing_columns.py` | PASS | 0 | 1.29 | - | evidence/FullSelfTest/logs/138_regression_operator_machine_missing_columns.py.log.txt | - |
| 139 | `regression_optimizer_choice_case_normalization.py` | PASS | 0 | 2.05 | - | evidence/FullSelfTest/logs/139_regression_optimizer_choice_case_normalization.py.log.txt | - |
| 140 | `regression_optimizer_ortools_logging_exc_info_safe.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/140_regression_optimizer_ortools_logging_exc_info_safe.py.log.txt | - |
| 141 | `regression_optimizer_outcome_algo_stats.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/141_regression_optimizer_outcome_algo_stats.py.log.txt | - |
| 142 | `regression_optimizer_seed_results_contract.py` | PASS | 0 | 2.05 | - | evidence/FullSelfTest/logs/142_regression_optimizer_seed_results_contract.py.log.txt | - |
| 143 | `regression_optimizer_zero_weight_cfg_preserved.py` | PASS | 0 | 2.04 | - | evidence/FullSelfTest/logs/143_regression_optimizer_zero_weight_cfg_preserved.py.log.txt | - |
| 144 | `regression_optional_ready_constraint.py` | PASS | 0 | 2.20 | - | evidence/FullSelfTest/logs/144_regression_optional_ready_constraint.py.log.txt | - |
| 145 | `regression_ortools_budget_guard_skip_when_no_time.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/145_regression_ortools_budget_guard_skip_when_no_time.py.log.txt | - |
| 146 | `regression_ortools_priority_weight_contract.py` | PASS | 0 | 1.16 | - | evidence/FullSelfTest/logs/146_regression_ortools_priority_weight_contract.py.log.txt | - |
| 147 | `regression_ortools_warmstart_skip_nonfinite.py` | PASS | 0 | 1.07 | - | evidence/FullSelfTest/logs/147_regression_ortools_warmstart_skip_nonfinite.py.log.txt | - |
| 148 | `regression_page_manual_registry.py` | PASS | 0 | 3.04 | - | evidence/FullSelfTest/logs/148_regression_page_manual_registry.py.log.txt | - |
| 149 | `regression_part_operation_hours_service_stats_gate.py` | PASS | 0 | 1.91 | - | evidence/FullSelfTest/logs/149_regression_part_operation_hours_service_stats_gate.py.log.txt | - |
| 150 | `regression_part_service_create_strict_mode_atomic.py` | PASS | 0 | 1.93 | - | evidence/FullSelfTest/logs/150_regression_part_service_create_strict_mode_atomic.py.log.txt | - |
| 151 | `regression_part_service_external_default_days_fallback.py` | PASS | 0 | 1.95 | - | evidence/FullSelfTest/logs/151_regression_part_service_external_default_days_fallback.py.log.txt | - |
| 152 | `regression_personnel_excel_links_header_aliases.py` | PASS | 0 | 3.31 | - | evidence/FullSelfTest/logs/152_regression_personnel_excel_links_header_aliases.py.log.txt | - |
| 153 | `regression_plugin_bootstrap_config_failure_visible.py` | PASS | 0 | 1.32 | - | evidence/FullSelfTest/logs/153_regression_plugin_bootstrap_config_failure_visible.py.log.txt | - |
| 154 | `regression_plugin_bootstrap_injects_config_reader.py` | PASS | 0 | 1.23 | - | evidence/FullSelfTest/logs/154_regression_plugin_bootstrap_injects_config_reader.py.log.txt | - |
| 155 | `regression_plugin_bootstrap_telemetry_failure_visible.py` | PASS | 0 | 1.29 | - | evidence/FullSelfTest/logs/155_regression_plugin_bootstrap_telemetry_failure_visible.py.log.txt | - |
| 156 | `regression_plugin_capability_conflict_visible.py` | PASS | 0 | 1.16 | - | evidence/FullSelfTest/logs/156_regression_plugin_capability_conflict_visible.py.log.txt | - |
| 157 | `regression_plugin_manager_error_trace_visible.py` | PASS | 0 | 1.16 | - | evidence/FullSelfTest/logs/157_regression_plugin_manager_error_trace_visible.py.log.txt | - |
| 158 | `regression_priority_weight_case_insensitive.py` | PASS | 0 | 1.15 | - | evidence/FullSelfTest/logs/158_regression_priority_weight_case_insensitive.py.log.txt | - |
| 159 | `regression_process_create_part_surfaces_autoparse_failure.py` | PASS | 0 | 3.13 | - | evidence/FullSelfTest/logs/159_regression_process_create_part_surfaces_autoparse_failure.py.log.txt | - |
| 160 | `regression_process_excel_part_operation_hours_append_fill_empty_only.py` | PASS | 0 | 3.44 | - | evidence/FullSelfTest/logs/160_regression_process_excel_part_operation_hours_append_fill_empty_only.py.log.txt | - |
| 161 | `regression_process_excel_part_operation_hours_import.py` | PASS | 0 | 3.52 | - | evidence/FullSelfTest/logs/161_regression_process_excel_part_operation_hours_import.py.log.txt | - |
| 162 | `regression_process_excel_part_operation_hours_source_row_num.py` | PASS | 0 | 3.20 | - | evidence/FullSelfTest/logs/162_regression_process_excel_part_operation_hours_source_row_num.py.log.txt | - |
| 163 | `regression_process_excel_routes_extra_state_guard.py` | PASS | 0 | 3.56 | - | evidence/FullSelfTest/logs/163_regression_process_excel_routes_extra_state_guard.py.log.txt | - |
| 164 | `regression_process_reparse_part_surfaces_warning_text.py` | PASS | 0 | 3.14 | - | evidence/FullSelfTest/logs/164_regression_process_reparse_part_surfaces_warning_text.py.log.txt | - |
| 165 | `regression_process_reparse_preserve_internal_hours.py` | PASS | 0 | 3.35 | - | evidence/FullSelfTest/logs/165_regression_process_reparse_preserve_internal_hours.py.log.txt | - |
| 166 | `regression_process_suppliers_route_reject_blank_default_days.py` | PASS | 0 | 3.15 | - | evidence/FullSelfTest/logs/166_regression_process_suppliers_route_reject_blank_default_days.py.log.txt | - |
| 167 | `regression_quality_gate_scan_contract.py` | PASS | 0 | 1.13 | - | evidence/FullSelfTest/logs/167_regression_quality_gate_scan_contract.py.log.txt | - |
| 168 | `regression_report_export_large_scope_rejects_need_async.py` | PASS | 0 | 3.14 | - | evidence/FullSelfTest/logs/168_regression_report_export_large_scope_rejects_need_async.py.log.txt | - |
| 169 | `regression_report_export_size_mode_selection.py` | PASS | 0 | 3.10 | - | evidence/FullSelfTest/logs/169_regression_report_export_size_mode_selection.py.log.txt | - |
| 170 | `regression_report_source_case_insensitive.py` | PASS | 0 | 2.10 | - | evidence/FullSelfTest/logs/170_regression_report_source_case_insensitive.py.log.txt | - |
| 171 | `regression_reports_default_range_from_version_span.py` | PASS | 0 | 3.14 | - | evidence/FullSelfTest/logs/171_regression_reports_default_range_from_version_span.py.log.txt | - |
| 172 | `regression_reports_export_version_default_latest.py` | PASS | 0 | 3.22 | - | evidence/FullSelfTest/logs/172_regression_reports_export_version_default_latest.py.log.txt | - |
| 173 | `regression_reports_page_version_default_latest.py` | PASS | 0 | 3.22 | - | evidence/FullSelfTest/logs/173_regression_reports_page_version_default_latest.py.log.txt | - |
| 174 | `regression_request_scope_app_logger_binding.py` | PASS | 0 | 3.08 | - | evidence/FullSelfTest/logs/174_regression_request_scope_app_logger_binding.py.log.txt | - |
| 175 | `regression_request_service_test_factory_invariant.py` | PASS | 0 | 2.94 | - | evidence/FullSelfTest/logs/175_regression_request_service_test_factory_invariant.py.log.txt | - |
| 176 | `regression_request_services_contract.py` | PASS | 0 | 2.12 | - | evidence/FullSelfTest/logs/176_regression_request_services_contract.py.log.txt | - |
| 177 | `regression_request_services_failure_propagation.py` | PASS | 0 | 2.12 | - | evidence/FullSelfTest/logs/177_regression_request_services_failure_propagation.py.log.txt | - |
| 178 | `regression_request_services_lazy_construction.py` | PASS | 0 | 2.12 | - | evidence/FullSelfTest/logs/178_regression_request_services_lazy_construction.py.log.txt | - |
| 179 | `regression_resource_dispatch_bad_time_rows_surface_degraded.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/179_regression_resource_dispatch_bad_time_rows_surface_degraded.py.log.txt | - |
| 180 | `regression_resource_dispatch_export_surfaces_degraded.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/180_regression_resource_dispatch_export_surfaces_degraded.py.log.txt | - |
| 181 | `regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py` | PASS | 0 | 3.16 | - | evidence/FullSelfTest/logs/181_regression_resource_dispatch_invalid_summary_surfaces_overdue_degraded.py.log.txt | - |
| 182 | `regression_resource_dispatch_overdue_summary_formats.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/182_regression_resource_dispatch_overdue_summary_formats.py.log.txt | - |
| 183 | `regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py` | PASS | 0 | 3.18 | - | evidence/FullSelfTest/logs/183_regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py.log.txt | - |
| 184 | `regression_resource_reference_guard_schedule.py` | PASS | 0 | 1.43 | - | evidence/FullSelfTest/logs/184_regression_resource_reference_guard_schedule.py.log.txt | - |
| 185 | `regression_restore_success_condition.py` | PASS | 0 | 3.26 | - | evidence/FullSelfTest/logs/185_regression_restore_success_condition.py.log.txt | - |
| 186 | `regression_route_parser_missing_supplier_warning.py` | PASS | 0 | 1.94 | - | evidence/FullSelfTest/logs/186_regression_route_parser_missing_supplier_warning.py.log.txt | - |
| 187 | `regression_route_parser_op_type_category_case_insensitive.py` | PASS | 0 | 1.92 | - | evidence/FullSelfTest/logs/187_regression_route_parser_op_type_category_case_insensitive.py.log.txt | - |
| 188 | `regression_route_parser_preserve_errors_when_no_matches.py` | PASS | 0 | 1.92 | - | evidence/FullSelfTest/logs/188_regression_route_parser_preserve_errors_when_no_matches.py.log.txt | - |
| 189 | `regression_route_parser_strict_mode_rejects_supplier_fallback.py` | PASS | 0 | 1.96 | - | evidence/FullSelfTest/logs/189_regression_route_parser_strict_mode_rejects_supplier_fallback.py.log.txt | - |
| 190 | `regression_route_parser_supplier_default_days_zero_trace.py` | PASS | 0 | 1.93 | - | evidence/FullSelfTest/logs/190_regression_route_parser_supplier_default_days_zero_trace.py.log.txt | - |
| 191 | `regression_runtime_contract_launcher.py` | PASS | 0 | 1.17 | - | evidence/FullSelfTest/logs/191_regression_runtime_contract_launcher.py.log.txt | - |
| 192 | `regression_runtime_lock_reloader_parent_skip.py` | PASS | 0 | 4.85 | - | evidence/FullSelfTest/logs/192_regression_runtime_lock_reloader_parent_skip.py.log.txt | - |
| 193 | `regression_runtime_probe_resolution.py` | PASS | 0 | 3.03 | - | evidence/FullSelfTest/logs/193_regression_runtime_probe_resolution.py.log.txt | - |
| 194 | `regression_runtime_server_shutdown_observability.py` | PASS | 0 | 2.64 | - | evidence/FullSelfTest/logs/194_regression_runtime_server_shutdown_observability.py.log.txt | - |
| 195 | `regression_runtime_stop_cli.py` | PASS | 0 | 9.40 | - | evidence/FullSelfTest/logs/195_regression_runtime_stop_cli.py.log.txt | - |
| 196 | `regression_safe_next_url_hardening.py` | PASS | 0 | 3.04 | - | evidence/FullSelfTest/logs/196_regression_safe_next_url_hardening.py.log.txt | - |
| 197 | `regression_safe_next_url_observability.py` | PASS | 0 | 2.36 | - | evidence/FullSelfTest/logs/197_regression_safe_next_url_observability.py.log.txt | - |
| 198 | `regression_sanitize_batch_dates_single_digit.py` | PASS | 0 | 1.28 | - | evidence/FullSelfTest/logs/198_regression_sanitize_batch_dates_single_digit.py.log.txt | - |
| 199 | `regression_schedule_config_snapshot_optional_guard.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/199_regression_schedule_config_snapshot_optional_guard.py.log.txt | - |
| 200 | `regression_schedule_history_not_created_for_empty_schedule.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/200_regression_schedule_history_not_created_for_empty_schedule.py.log.txt | - |
| 201 | `regression_schedule_input_builder_safe_float_parse.py` | PASS | 0 | 2.05 | - | evidence/FullSelfTest/logs/201_regression_schedule_input_builder_safe_float_parse.py.log.txt | - |
| 202 | `regression_schedule_input_builder_template_missing_surfaces_event.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/202_regression_schedule_input_builder_template_missing_surfaces_event.py.log.txt | - |
| 203 | `regression_schedule_input_collector_contract.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/203_regression_schedule_input_collector_contract.py.log.txt | - |
| 204 | `regression_schedule_input_collector_legacy_compat.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/204_regression_schedule_input_collector_legacy_compat.py.log.txt | - |
| 205 | `regression_schedule_optimizer_cfg_float_strict_blank.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/205_regression_schedule_optimizer_cfg_float_strict_blank.py.log.txt | - |
| 206 | `regression_schedule_optimizer_cfg_snapshot_contract.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/206_regression_schedule_optimizer_cfg_snapshot_contract.py.log.txt | - |
| 207 | `regression_schedule_orchestrator_contract.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/207_regression_schedule_orchestrator_contract.py.log.txt | - |
| 208 | `regression_schedule_params_read_failure_visible.py` | PASS | 0 | 2.05 | - | evidence/FullSelfTest/logs/208_regression_schedule_params_read_failure_visible.py.log.txt | - |
| 209 | `regression_schedule_params_strict_blank_numeric.py` | PASS | 0 | 2.10 | - | evidence/FullSelfTest/logs/209_regression_schedule_params_strict_blank_numeric.py.log.txt | - |
| 210 | `regression_schedule_persistence_reject_empty_actionable_schedule.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/210_regression_schedule_persistence_reject_empty_actionable_schedule.py.log.txt | - |
| 211 | `regression_schedule_persistence_reschedulable_contract.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/211_regression_schedule_persistence_reschedulable_contract.py.log.txt | - |
| 212 | `regression_schedule_repository_bundle_contract.py` | PASS | 0 | 2.02 | - | evidence/FullSelfTest/logs/212_regression_schedule_repository_bundle_contract.py.log.txt | - |
| 213 | `regression_schedule_service_all_frozen_short_circuit.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/213_regression_schedule_service_all_frozen_short_circuit.py.log.txt | - |
| 214 | `regression_schedule_service_empty_reschedulable_rejected.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/214_regression_schedule_service_empty_reschedulable_rejected.py.log.txt | - |
| 215 | `regression_schedule_service_facade_delegation.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/215_regression_schedule_service_facade_delegation.py.log.txt | - |
| 216 | `regression_schedule_service_missing_resource_source_case_insensitive.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/216_regression_schedule_service_missing_resource_source_case_insensitive.py.log.txt | - |
| 217 | `regression_schedule_service_passes_algo_stats_to_summary.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/217_regression_schedule_service_passes_algo_stats_to_summary.py.log.txt | - |
| 218 | `regression_schedule_service_reject_no_actionable_schedule_rows.py` | PASS | 0 | 2.10 | - | evidence/FullSelfTest/logs/218_regression_schedule_service_reject_no_actionable_schedule_rows.py.log.txt | - |
| 219 | `regression_schedule_service_reschedulable_contract.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/219_regression_schedule_service_reschedulable_contract.py.log.txt | - |
| 220 | `regression_schedule_service_signature_contract.py` | PASS | 0 | 2.05 | - | evidence/FullSelfTest/logs/220_regression_schedule_service_signature_contract.py.log.txt | - |
| 221 | `regression_schedule_service_strict_snapshot_guard.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/221_regression_schedule_service_strict_snapshot_guard.py.log.txt | - |
| 222 | `regression_schedule_summary_algo_warnings_union.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/222_regression_schedule_summary_algo_warnings_union.py.log.txt | - |
| 223 | `regression_schedule_summary_cfg_snapshot_contract.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/223_regression_schedule_summary_cfg_snapshot_contract.py.log.txt | - |
| 224 | `regression_schedule_summary_end_date_type_guard.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/224_regression_schedule_summary_end_date_type_guard.py.log.txt | - |
| 225 | `regression_schedule_summary_fallback_counts_output.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/225_regression_schedule_summary_fallback_counts_output.py.log.txt | - |
| 226 | `regression_schedule_summary_freeze_state_contract.py` | PASS | 0 | 2.01 | - | evidence/FullSelfTest/logs/226_regression_schedule_summary_freeze_state_contract.py.log.txt | - |
| 227 | `regression_schedule_summary_invalid_due_and_unscheduled_counts.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/227_regression_schedule_summary_invalid_due_and_unscheduled_counts.py.log.txt | - |
| 228 | `regression_schedule_summary_merge_context_degraded_code.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/228_regression_schedule_summary_merge_context_degraded_code.py.log.txt | - |
| 229 | `regression_schedule_summary_overdue_warning_append_fallback.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/229_regression_schedule_summary_overdue_warning_append_fallback.py.log.txt | - |
| 230 | `regression_schedule_summary_size_guard_large_lists.py` | PASS | 0 | 2.14 | - | evidence/FullSelfTest/logs/230_regression_schedule_summary_size_guard_large_lists.py.log.txt | - |
| 231 | `regression_schedule_summary_v11_contract.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/231_regression_schedule_summary_v11_contract.py.log.txt | - |
| 232 | `regression_scheduler_accepts_start_dt_string_and_safe_weights.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/232_regression_scheduler_accepts_start_dt_string_and_safe_weights.py.log.txt | - |
| 233 | `regression_scheduler_analysis_observability.py` | PASS | 0 | 3.14 | - | evidence/FullSelfTest/logs/233_regression_scheduler_analysis_observability.py.log.txt | - |
| 234 | `regression_scheduler_analysis_route_contract.py` | PASS | 0 | 2.43 | - | evidence/FullSelfTest/logs/234_regression_scheduler_analysis_route_contract.py.log.txt | - |
| 235 | `regression_scheduler_analysis_vm_legacy_summary_bridge.py` | PASS | 0 | 1.21 | - | evidence/FullSelfTest/logs/235_regression_scheduler_analysis_vm_legacy_summary_bridge.py.log.txt | - |
| 236 | `regression_scheduler_apply_preset_reject_invalid_numeric.py` | PASS | 0 | 2.26 | - | evidence/FullSelfTest/logs/236_regression_scheduler_apply_preset_reject_invalid_numeric.py.log.txt | - |
| 237 | `regression_scheduler_batch_detail_merge_hint_fast_path.py` | PASS | 0 | 2.38 | - | evidence/FullSelfTest/logs/237_regression_scheduler_batch_detail_merge_hint_fast_path.py.log.txt | - |
| 238 | `regression_scheduler_batch_detail_route_contract.py` | PASS | 0 | 2.42 | - | evidence/FullSelfTest/logs/238_regression_scheduler_batch_detail_route_contract.py.log.txt | - |
| 239 | `regression_scheduler_batch_template_warning_surface.py` | PASS | 0 | 3.80 | - | evidence/FullSelfTest/logs/239_regression_scheduler_batch_template_warning_surface.py.log.txt | - |
| 240 | `regression_scheduler_batches_degraded_visibility.py` | PASS | 0 | 2.41 | - | evidence/FullSelfTest/logs/240_regression_scheduler_batches_degraded_visibility.py.log.txt | - |
| 241 | `regression_scheduler_bp_result_summary_guard.py` | PASS | 0 | 1.62 | - | evidence/FullSelfTest/logs/241_regression_scheduler_bp_result_summary_guard.py.log.txt | - |
| 242 | `regression_scheduler_config_manual_url_normalization.py` | PASS | 0 | 2.39 | - | evidence/FullSelfTest/logs/242_regression_scheduler_config_manual_url_normalization.py.log.txt | - |
| 243 | `regression_scheduler_config_route_contract.py` | PASS | 0 | 4.06 | - | evidence/FullSelfTest/logs/243_regression_scheduler_config_route_contract.py.log.txt | - |
| 244 | `regression_scheduler_enforce_ready_default_from_config.py` | PASS | 0 | 2.21 | - | evidence/FullSelfTest/logs/244_regression_scheduler_enforce_ready_default_from_config.py.log.txt | - |
| 245 | `regression_scheduler_excel_batches_helper_injection_contract.py` | PASS | 0 | 2.36 | - | evidence/FullSelfTest/logs/245_regression_scheduler_excel_batches_helper_injection_contract.py.log.txt | - |
| 246 | `regression_scheduler_excel_batches_preview_baseline_precision.py` | PASS | 0 | 5.32 | - | evidence/FullSelfTest/logs/246_regression_scheduler_excel_batches_preview_baseline_precision.py.log.txt | - |
| 247 | `regression_scheduler_excel_calendar_strict_numeric.py` | FAIL | 1 | 4.03 | - | evidence/FullSelfTest/logs/247_regression_scheduler_excel_calendar_strict_numeric.py.log.txt | exit_code!=0 |
| 248 | `regression_scheduler_excel_calendar_uses_executor.py` | FAIL | 1 | 3.92 | - | evidence/FullSelfTest/logs/248_regression_scheduler_excel_calendar_uses_executor.py.log.txt | exit_code!=0 |
| 249 | `regression_scheduler_nonfinite_efficiency_fallback.py` | PASS | 0 | 2.03 | - | evidence/FullSelfTest/logs/249_regression_scheduler_nonfinite_efficiency_fallback.py.log.txt | - |
| 250 | `regression_scheduler_objective_labels.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/250_regression_scheduler_objective_labels.py.log.txt | - |
| 251 | `regression_scheduler_ops_update_route_contract.py` | PASS | 0 | 2.37 | - | evidence/FullSelfTest/logs/251_regression_scheduler_ops_update_route_contract.py.log.txt | - |
| 252 | `regression_scheduler_reject_nonfinite_and_invalid_status.py` | PASS | 0 | 2.13 | - | evidence/FullSelfTest/logs/252_regression_scheduler_reject_nonfinite_and_invalid_status.py.log.txt | - |
| 253 | `regression_scheduler_resource_dispatch_invalid_query_cleanup.py` | PASS | 0 | 7.27 | - | evidence/FullSelfTest/logs/253_regression_scheduler_resource_dispatch_invalid_query_cleanup.py.log.txt | - |
| 254 | `regression_scheduler_route_enforce_ready_tristate.py` | PASS | 0 | 2.37 | - | evidence/FullSelfTest/logs/254_regression_scheduler_route_enforce_ready_tristate.py.log.txt | - |
| 255 | `regression_scheduler_run_no_reschedulable_flash.py` | PASS | 0 | 3.14 | - | evidence/FullSelfTest/logs/255_regression_scheduler_run_no_reschedulable_flash.py.log.txt | - |
| 256 | `regression_scheduler_run_surfaces_resource_pool_warning.py` | PASS | 0 | 2.56 | - | evidence/FullSelfTest/logs/256_regression_scheduler_run_surfaces_resource_pool_warning.py.log.txt | - |
| 257 | `regression_scheduler_strict_mode_dispatch_flags.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/257_regression_scheduler_strict_mode_dispatch_flags.py.log.txt | - |
| 258 | `regression_scheduler_user_visible_messages.py` | PASS | 0 | 2.33 | - | evidence/FullSelfTest/logs/258_regression_scheduler_user_visible_messages.py.log.txt | - |
| 259 | `regression_scheduler_week_plan_no_reschedulable_flash.py` | PASS | 0 | 3.15 | - | evidence/FullSelfTest/logs/259_regression_scheduler_week_plan_no_reschedulable_flash.py.log.txt | - |
| 260 | `regression_scheduler_week_plan_summary_observability.py` | PASS | 0 | 2.41 | - | evidence/FullSelfTest/logs/260_regression_scheduler_week_plan_summary_observability.py.log.txt | - |
| 261 | `regression_scheduler_wrapper_import_order_contract.py` | PASS | 0 | 16.09 | - | evidence/FullSelfTest/logs/261_regression_scheduler_wrapper_import_order_contract.py.log.txt | - |
| 262 | `regression_security_secret_key_observability.py` | PASS | 0 | 1.60 | - | evidence/FullSelfTest/logs/262_regression_security_secret_key_observability.py.log.txt | - |
| 263 | `regression_seed_results_dedup.py` | PASS | 0 | 2.01 | - | evidence/FullSelfTest/logs/263_regression_seed_results_dedup.py.log.txt | - |
| 264 | `regression_seed_results_drop_duplicate_op_id_and_bad_time.py` | PASS | 0 | 2.04 | - | evidence/FullSelfTest/logs/264_regression_seed_results_drop_duplicate_op_id_and_bad_time.py.log.txt | - |
| 265 | `regression_seed_results_freeze_missing_resource.py` | PASS | 0 | 2.03 | - | evidence/FullSelfTest/logs/265_regression_seed_results_freeze_missing_resource.py.log.txt | - |
| 266 | `regression_seed_results_invalid_op_id_dedup.py` | PASS | 0 | 2.05 | - | evidence/FullSelfTest/logs/266_regression_seed_results_invalid_op_id_dedup.py.log.txt | - |
| 267 | `regression_sgs_atc_penalize_missing_resources.py` | PASS | 0 | 1.13 | - | evidence/FullSelfTest/logs/267_regression_sgs_atc_penalize_missing_resources.py.log.txt | - |
| 268 | `regression_sgs_penalize_nonfinite_proc_hours.py` | PASS | 0 | 1.12 | - | evidence/FullSelfTest/logs/268_regression_sgs_penalize_nonfinite_proc_hours.py.log.txt | - |
| 269 | `regression_sgs_pre_sort_strict_nonfinite_rejected.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/269_regression_sgs_pre_sort_strict_nonfinite_rejected.py.log.txt | - |
| 270 | `regression_sgs_scoring_fallback_unscorable.py` | PASS | 0 | 2.08 | - | evidence/FullSelfTest/logs/270_regression_sgs_scoring_fallback_unscorable.py.log.txt | - |
| 271 | `regression_sgs_scoring_machine_operator_id_type_safe.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/271_regression_sgs_scoring_machine_operator_id_type_safe.py.log.txt | - |
| 272 | `regression_shared_runtime_state.py` | PASS | 0 | 1.99 | - | evidence/FullSelfTest/logs/272_regression_shared_runtime_state.py.log.txt | - |
| 273 | `regression_skill_rank_mapping.py` | PASS | 0 | 2.23 | - | evidence/FullSelfTest/logs/273_regression_skill_rank_mapping.py.log.txt | - |
| 274 | `regression_sort_strategies_priority_case_insensitive.py` | PASS | 0 | 1.14 | - | evidence/FullSelfTest/logs/274_regression_sort_strategies_priority_case_insensitive.py.log.txt | - |
| 275 | `regression_sort_strategy_case_insensitive.py` | PASS | 0 | 1.14 | - | evidence/FullSelfTest/logs/275_regression_sort_strategy_case_insensitive.py.log.txt | - |
| 276 | `regression_sp05_followup_contracts.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/276_regression_sp05_followup_contracts.py.log.txt | - |
| 277 | `regression_sp06_no_duplicate_defs.py` | PASS | 0 | 1.09 | - | evidence/FullSelfTest/logs/277_regression_sp06_no_duplicate_defs.py.log.txt | - |
| 278 | `regression_sqlite_detect_types_enabled.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/278_regression_sqlite_detect_types_enabled.py.log.txt | - |
| 279 | `regression_start_and_rerun_route_resolution.py` | PASS | 0 | 1.18 | - | evidence/FullSelfTest/logs/279_regression_start_and_rerun_route_resolution.py.log.txt | - |
| 280 | `regression_startup_host_portfile.py` | PASS | 0 | 31.16 | - | evidence/FullSelfTest/logs/280_regression_startup_host_portfile.py.log.txt | - |
| 281 | `regression_startup_host_portfile_new_ui.py` | PASS | 0 | 30.88 | - | evidence/FullSelfTest/logs/281_regression_startup_host_portfile_new_ui.py.log.txt | - |
| 282 | `regression_status_category_mixed_case.py` | PASS | 0 | 2.09 | - | evidence/FullSelfTest/logs/282_regression_status_category_mixed_case.py.log.txt | - |
| 283 | `regression_strict_parse_blank_required.py` | PASS | 0 | 1.13 | - | evidence/FullSelfTest/logs/283_regression_strict_parse_blank_required.py.log.txt | - |
| 284 | `regression_supplier_effective_selection_contract.py` | PASS | 0 | 2.04 | - | evidence/FullSelfTest/logs/284_regression_supplier_effective_selection_contract.py.log.txt | - |
| 285 | `regression_supplier_service_invalid_default_days_not_silent.py` | PASS | 0 | 1.95 | - | evidence/FullSelfTest/logs/285_regression_supplier_service_invalid_default_days_not_silent.py.log.txt | - |
| 286 | `regression_system_config_dirty_fields_contract.py` | PASS | 0 | 1.29 | - | evidence/FullSelfTest/logs/286_regression_system_config_dirty_fields_contract.py.log.txt | - |
| 287 | `regression_system_health_route.py` | PASS | 0 | 3.46 | - | evidence/FullSelfTest/logs/287_regression_system_health_route.py.log.txt | - |
| 288 | `regression_system_history_route_contract.py` | PASS | 0 | 1.77 | - | evidence/FullSelfTest/logs/288_regression_system_history_route_contract.py.log.txt | - |
| 289 | `regression_system_logs_delete_no_clamp.py` | PASS | 0 | 3.18 | - | evidence/FullSelfTest/logs/289_regression_system_logs_delete_no_clamp.py.log.txt | - |
| 290 | `regression_system_maintenance_invalid_last_run_visible.py` | PASS | 0 | 3.19 | - | evidence/FullSelfTest/logs/290_regression_system_maintenance_invalid_last_run_visible.py.log.txt | - |
| 291 | `regression_system_maintenance_jobstate_commit.py` | PASS | 0 | 1.87 | - | evidence/FullSelfTest/logs/291_regression_system_maintenance_jobstate_commit.py.log.txt | - |
| 292 | `regression_system_maintenance_throttle_short_circuit.py` | PASS | 0 | 1.21 | - | evidence/FullSelfTest/logs/292_regression_system_maintenance_throttle_short_circuit.py.log.txt | - |
| 293 | `regression_system_request_services_contract.py` | PASS | 0 | 1.75 | - | evidence/FullSelfTest/logs/293_regression_system_request_services_contract.py.log.txt | - |
| 294 | `regression_template_no_inline_event_jinja.py` | PASS | 0 | 1.11 | - | evidence/FullSelfTest/logs/294_regression_template_no_inline_event_jinja.py.log.txt | - |
| 295 | `regression_template_urlfor_endpoints.py` | PASS | 0 | 3.04 | - | evidence/FullSelfTest/logs/295_regression_template_urlfor_endpoints.py.log.txt | - |
| 296 | `regression_tojson_zh_autoescape.py` | PASS | 0 | 3.02 | - | evidence/FullSelfTest/logs/296_regression_tojson_zh_autoescape.py.log.txt | - |
| 297 | `regression_transaction_savepoint_nested.py` | PASS | 0 | 1.16 | - | evidence/FullSelfTest/logs/297_regression_transaction_savepoint_nested.py.log.txt | - |
| 298 | `regression_ui_contract_table_overflow_guard.py` | PASS | 0 | 1.08 | - | evidence/FullSelfTest/logs/298_regression_ui_contract_table_overflow_guard.py.log.txt | - |
| 299 | `regression_ui_mode_startup_guard_observability.py` | PASS | 0 | 1.65 | - | evidence/FullSelfTest/logs/299_regression_ui_mode_startup_guard_observability.py.log.txt | - |
| 300 | `regression_unit_excel_converter_diagnostics_visible.py` | PASS | 0 | 2.12 | - | evidence/FullSelfTest/logs/300_regression_unit_excel_converter_diagnostics_visible.py.log.txt | - |
| 301 | `regression_unit_excel_converter_duplicate_part_rows_no_override.py` | PASS | 0 | 1.95 | - | evidence/FullSelfTest/logs/301_regression_unit_excel_converter_duplicate_part_rows_no_override.py.log.txt | - |
| 302 | `regression_unit_excel_converter_facade_binding.py` | PASS | 0 | 1.88 | - | evidence/FullSelfTest/logs/302_regression_unit_excel_converter_facade_binding.py.log.txt | - |
| 303 | `regression_unit_excel_converter_merge_steps_and_classify.py` | PASS | 0 | 2.18 | - | evidence/FullSelfTest/logs/303_regression_unit_excel_converter_merge_steps_and_classify.py.log.txt | - |
| 304 | `regression_unit_excel_template_headers.py` | PASS | 0 | 1.91 | - | evidence/FullSelfTest/logs/304_regression_unit_excel_template_headers.py.log.txt | - |
| 305 | `regression_v2_strategy_zh_contract.py` | PASS | 0 | 1.09 | - | evidence/FullSelfTest/logs/305_regression_v2_strategy_zh_contract.py.log.txt | - |
| 306 | `regression_validate_dist_runtime_identity.py` | PASS | 0 | 1.59 | - | evidence/FullSelfTest/logs/306_regression_validate_dist_runtime_identity.py.log.txt | - |
| 307 | `regression_value_policies_matrix_contract.py` | PASS | 0 | 1.10 | - | evidence/FullSelfTest/logs/307_regression_value_policies_matrix_contract.py.log.txt | - |
| 308 | `regression_warmstart_failure_surfaces_degradation.py` | PASS | 0 | 2.07 | - | evidence/FullSelfTest/logs/308_regression_warmstart_failure_surfaces_degradation.py.log.txt | - |
| 309 | `regression_week_plan_bad_time_rows_surface_degraded.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/309_regression_week_plan_bad_time_rows_surface_degraded.py.log.txt | - |
| 310 | `regression_week_plan_filename_uses_normalized_version.py` | PASS | 0 | 3.33 | - | evidence/FullSelfTest/logs/310_regression_week_plan_filename_uses_normalized_version.py.log.txt | - |
| 311 | `regression_weighted_tardiness_objective.py` | PASS | 0 | 2.05 | - | evidence/FullSelfTest/logs/311_regression_weighted_tardiness_objective.py.log.txt | - |
| 312 | `test_sp05_path_topology_contract.py` | PASS | 0 | 23.04 | - | evidence/FullSelfTest/logs/312_test_sp05_path_topology_contract.py.log.txt | - |
| 313 | `test_schedule_input_builder_strict_hours_and_ext_days.py` | PASS | 0 | 2.06 | - | evidence/FullSelfTest/logs/313_test_schedule_input_builder_strict_hours_and_ext_days.py.log.txt | - |
| 314 | `test_schedule_summary_observability.py` | PASS | 0 | 7.17 | - | evidence/FullSelfTest/logs/314_test_schedule_summary_observability.py.log.txt | - |
| 315 | `test_schedule_params_direct_call_contract.py` | PASS | 0 | 2.10 | - | evidence/FullSelfTest/logs/315_test_schedule_params_direct_call_contract.py.log.txt | - |
| 316 | `test_ui_mode.py` | PASS | 0 | 1.77 | - | evidence/FullSelfTest/logs/316_test_ui_mode.py.log.txt | - |
| 317 | `test_holiday_default_efficiency_read_guard.py` | PASS | 0 | 6.61 | - | evidence/FullSelfTest/logs/317_test_holiday_default_efficiency_read_guard.py.log.txt | - |
| 318 | `run_complex_excel_cases_e2e.py` | FAIL | 1 | 7.27 | evidence/ComplexExcelCases/complex_cases_report.md<br/>evidence/ComplexExcelCases/complex_cases_summary.json | evidence/FullSelfTest/logs/318_run_complex_excel_cases_e2e.py.log.txt | exit_code!=0 |

## 失败项（按出现顺序）

- `regression_excel_import_result_semantics.py`（exit=1）：exit_code!=0
  - runner日志：`evidence/FullSelfTest/logs/71_regression_excel_import_result_semantics.py.log.txt`
- `regression_excel_preview_confirm_baseline_guard.py`（exit=1）：exit_code!=0
  - runner日志：`evidence/FullSelfTest/logs/75_regression_excel_preview_confirm_baseline_guard.py.log.txt`
- `regression_excel_preview_confirm_extra_state_guard.py`（exit=1）：exit_code!=0
  - runner日志：`evidence/FullSelfTest/logs/76_regression_excel_preview_confirm_extra_state_guard.py.log.txt`
- `regression_scheduler_excel_calendar_strict_numeric.py`（exit=1）：exit_code!=0
  - runner日志：`evidence/FullSelfTest/logs/247_regression_scheduler_excel_calendar_strict_numeric.py.log.txt`
- `regression_scheduler_excel_calendar_uses_executor.py`（exit=1）：exit_code!=0
  - runner日志：`evidence/FullSelfTest/logs/248_regression_scheduler_excel_calendar_uses_executor.py.log.txt`
- `run_complex_excel_cases_e2e.py`（exit=1）：exit_code!=0
  - 证据：`evidence/ComplexExcelCases/complex_cases_report.md`
  - 证据：`evidence/ComplexExcelCases/complex_cases_summary.json`
  - runner日志：`evidence/FullSelfTest/logs/318_run_complex_excel_cases_e2e.py.log.txt`

## 说明

- 本 runner **不会**执行 PyInstaller / dist / validate_dist_exe 等打包流程。
- 复杂 Excel 用例的重产物目录默认会被 `.gitignore` 忽略，仅保留报告与 summary JSON。

