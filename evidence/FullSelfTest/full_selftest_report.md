# APS 全量自测汇总报告（不打包）

- 生成时间：2026-02-01 18:07:32
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- Python 可执行：`D:\py3.8\python.exe`
- 仓库根目录：`D:/Github/APS Test`
- fail_fast：false
- complex_repeat：1

## 总结

- 结论：**PASS**
- 记录数：33

## 明细

| # | 脚本 | 结果 | exit | 耗时(s) | 证据(evidence) | runner日志 | 备注 |
|---:|---|---|---:|---:|---|---|---|
| 1 | `smoke_phase0_phase1.py` | PASS | 0 | 5.41 | evidence/Phase0_Phase1/smoke_test_report.md | evidence/FullSelfTest/logs/01_smoke_phase0_phase1.py.log.txt | - |
| 2 | `smoke_phase2.py` | PASS | 0 | 0.87 | evidence/Phase2/smoke_phase2_report.md | evidence/FullSelfTest/logs/02_smoke_phase2.py.log.txt | - |
| 3 | `smoke_phase3.py` | PASS | 0 | 1.44 | evidence/Phase3/smoke_phase3_report.md | evidence/FullSelfTest/logs/03_smoke_phase3.py.log.txt | - |
| 4 | `smoke_phase4.py` | PASS | 0 | 1.62 | evidence/Phase4/smoke_phase4_report.md | evidence/FullSelfTest/logs/04_smoke_phase4.py.log.txt | - |
| 5 | `smoke_phase5.py` | PASS | 0 | 0.96 | evidence/Phase5/smoke_phase5_report.md | evidence/FullSelfTest/logs/05_smoke_phase5.py.log.txt | - |
| 6 | `smoke_phase6.py` | PASS | 0 | 1.08 | evidence/Phase6/smoke_phase6_report.md | evidence/FullSelfTest/logs/06_smoke_phase6.py.log.txt | - |
| 7 | `smoke_phase7.py` | PASS | 0 | 2.66 | evidence/Phase7/smoke_phase7_report.md | evidence/FullSelfTest/logs/07_smoke_phase7.py.log.txt | - |
| 8 | `smoke_phase8.py` | PASS | 0 | 2.47 | evidence/Phase8/smoke_phase8_report.md | evidence/FullSelfTest/logs/08_smoke_phase8.py.log.txt | - |
| 9 | `smoke_phase9.py` | PASS | 0 | 27.21 | evidence/Phase9/smoke_phase9_report.md | evidence/FullSelfTest/logs/09_smoke_phase9.py.log.txt | - |
| 10 | `smoke_phase10_sgs_auto_assign.py` | PASS | 0 | 2.03 | evidence/Phase10/smoke_phase10_report.md | evidence/FullSelfTest/logs/10_smoke_phase10_sgs_auto_assign.py.log.txt | Phase10 报告显示 PASS：D:/Github/APS Test/evidence/Phase10/smoke_phase10_report.md |
| 11 | `smoke_web_phase0_5.py` | PASS | 0 | 3.11 | evidence/Phase0_to_Phase5/web_smoke_report.md | evidence/FullSelfTest/logs/11_smoke_web_phase0_5.py.log.txt | - |
| 12 | `smoke_web_phase0_6.py` | PASS | 0 | 3.31 | evidence/Phase0_to_Phase6/web_smoke_report.md | evidence/FullSelfTest/logs/12_smoke_web_phase0_6.py.log.txt | - |
| 13 | `smoke_e2e_excel_to_schedule.py` | PASS | 0 | 3.53 | evidence/FullE2E/excel_to_schedule_report.md | evidence/FullSelfTest/logs/13_smoke_e2e_excel_to_schedule.py.log.txt | - |
| 14 | `regression_auto_assign_empty_resource_pool.py` | PASS | 0 | 0.21 | - | evidence/FullSelfTest/logs/14_regression_auto_assign_empty_resource_pool.py.log.txt | - |
| 15 | `regression_batch_order_bid_unboundlocal.py` | PASS | 0 | 0.27 | - | evidence/FullSelfTest/logs/15_regression_batch_order_bid_unboundlocal.py.log.txt | - |
| 16 | `regression_batch_order_override_dedup.py` | PASS | 0 | 0.20 | - | evidence/FullSelfTest/logs/16_regression_batch_order_override_dedup.py.log.txt | - |
| 17 | `regression_dispatch_blocking_consistency.py` | PASS | 0 | 0.21 | - | evidence/FullSelfTest/logs/17_regression_dispatch_blocking_consistency.py.log.txt | - |
| 18 | `regression_freeze_window_bounds.py` | PASS | 0 | 1.02 | - | evidence/FullSelfTest/logs/18_regression_freeze_window_bounds.py.log.txt | - |
| 19 | `regression_migrate_backup_dir_none_creates_backup.py` | PASS | 0 | 0.76 | - | evidence/FullSelfTest/logs/19_regression_migrate_backup_dir_none_creates_backup.py.log.txt | - |
| 20 | `regression_migrate_v2_unify_workcalendar_day_type.py` | PASS | 0 | 0.76 | - | evidence/FullSelfTest/logs/20_regression_migrate_v2_unify_workcalendar_day_type.py.log.txt | - |
| 21 | `regression_operator_calendar_override_allows_work_on_global_holiday.py` | PASS | 0 | 1.06 | - | evidence/FullSelfTest/logs/21_regression_operator_calendar_override_allows_work_on_global_holiday.py.log.txt | - |
| 22 | `regression_operator_machine_missing_columns.py` | PASS | 0 | 0.76 | - | evidence/FullSelfTest/logs/22_regression_operator_machine_missing_columns.py.log.txt | - |
| 23 | `regression_optional_ready_constraint.py` | PASS | 0 | 1.07 | - | evidence/FullSelfTest/logs/23_regression_optional_ready_constraint.py.log.txt | - |
| 24 | `regression_priority_weight_case_insensitive.py` | PASS | 0 | 0.24 | - | evidence/FullSelfTest/logs/24_regression_priority_weight_case_insensitive.py.log.txt | - |
| 25 | `regression_sanitize_batch_dates_single_digit.py` | PASS | 0 | 0.79 | - | evidence/FullSelfTest/logs/25_regression_sanitize_batch_dates_single_digit.py.log.txt | - |
| 26 | `regression_seed_results_dedup.py` | PASS | 0 | 0.19 | - | evidence/FullSelfTest/logs/26_regression_seed_results_dedup.py.log.txt | - |
| 27 | `regression_seed_results_freeze_missing_resource.py` | PASS | 0 | 0.26 | - | evidence/FullSelfTest/logs/27_regression_seed_results_freeze_missing_resource.py.log.txt | - |
| 28 | `regression_seed_results_invalid_op_id_dedup.py` | PASS | 0 | 0.21 | - | evidence/FullSelfTest/logs/28_regression_seed_results_invalid_op_id_dedup.py.log.txt | - |
| 29 | `regression_sgs_scoring_fallback_unscorable.py` | PASS | 0 | 0.21 | - | evidence/FullSelfTest/logs/29_regression_sgs_scoring_fallback_unscorable.py.log.txt | - |
| 30 | `regression_skill_rank_mapping.py` | PASS | 0 | 1.07 | - | evidence/FullSelfTest/logs/30_regression_skill_rank_mapping.py.log.txt | - |
| 31 | `regression_sqlite_detect_types_enabled.py` | PASS | 0 | 0.16 | - | evidence/FullSelfTest/logs/31_regression_sqlite_detect_types_enabled.py.log.txt | - |
| 32 | `regression_template_urlfor_endpoints.py` | PASS | 0 | 2.37 | - | evidence/FullSelfTest/logs/32_regression_template_urlfor_endpoints.py.log.txt | - |
| 33 | `run_complex_excel_cases_e2e.py` | PASS | 0 | 80.65 | evidence/ComplexExcelCases/complex_cases_report.md<br/>evidence/ComplexExcelCases/complex_cases_summary.json | evidence/FullSelfTest/logs/33_run_complex_excel_cases_e2e.py.log.txt | - |

## 说明

- 本 runner **不会**执行 PyInstaller / dist / validate_dist_exe 等打包流程。
- 复杂 Excel 用例的重产物目录默认会被 `.gitignore` 忽略，仅保留报告与 summary JSON。

