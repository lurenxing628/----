# Pyright 文件索引

全部为迁移相关现行文件；原有/新增时间归属无法区分。完整报错见 pyright-diagnostics.json。

| 文件 | 错误数 | 行号 | 派工 |
| --- | ---: | --- | --- |
| `core/models/workbench_batch.py` | 2 | 86, 87 | FE-05 |
| `core/models/workbench_execution_input.py` | 2 | 111, 114 | queued-unassigned |
| `core/models/workbench_outsourcing_input.py` | 3 | 74, 76 | queued-unassigned |
| `core/models/workbench_process_commands.py` | 1 | 81 | queued-unassigned |
| `core/models/workbench_report.py` | 1 | 59 | queued-unassigned |
| `core/models/workbench_resource_table_query.py` | 2 | 21 | FE-01 |
| `core/models/workbench_run_adoption.py` | 1 | 36 | queued-unassigned |
| `core/services/workbench/actual_gantt_scope.py` | 6 | 31, 32, 33, 34, 35, 36 | FB-related-reserved |
| `core/services/workbench/batch_execution.py` | 2 | 46, 47 | FE-05 |
| `core/services/workbench/batch_facts.py` | 2 | 32, 33 | FE-05 |
| `core/services/workbench/batch_file_codec.py` | 7 | 69, 70, 72, 74, 79, 84, 88 | FE-05 |
| `core/services/workbench/batch_files.py` | 3 | 68, 71 | FE-05 |
| `core/services/workbench/execution_ledger.py` | 8 | 130, 132, 134, 135, 144 | queued-unassigned |
| `core/services/workbench/field_report_files.py` | 2 | 148, 152 | FB-related-reserved |
| `core/services/workbench/field_report_files_codec.py` | 15 | 43, 61, 63, 157, 158, 162, 182, 183, 186, 187, 188, 189, 190, 191 | FB-related-reserved |
| `core/services/workbench/field_report_files_xml.py` | 2 | 24, 69 | FB-related-reserved |
| `core/services/workbench/outsourcing_commands.py` | 1 | 55 | queued-unassigned |
| `core/services/workbench/plan_adoption_baseline.py` | 4 | 56, 62, 64 | queued-unassigned |
| `core/services/workbench/plan_adoption_baseline_identity.py` | 5 | 111, 112, 132 | queued-unassigned |
| `core/services/workbench/plan_delivery_projection.py` | 2 | 26 | queued-unassigned |
| `core/services/workbench/plan_queries.py` | 1 | 185 | queued-unassigned |
| `core/services/workbench/point_plan_query.py` | 2 | 33, 34 | queued-unassigned |
| `core/services/workbench/production_report_prepare.py` | 5 | 35, 80, 115, 129, 132 | queued-unassigned |
| `core/services/workbench/production_report_validation.py` | 2 | 79 | queued-unassigned |
| `core/services/workbench/report_catalog.py` | 2 | 47 | queued-unassigned |
| `core/services/workbench/resource_table_facts.py` | 3 | 83, 97 | FE-01 |
| `core/services/workbench/review_legacy.py` | 6 | 34, 37, 40, 41 | queued-unassigned |
| `core/services/workbench/run_candidate_adoption.py` | 2 | 58, 77 | queued-unassigned |
| `core/services/workbench/trial.py` | 3 | 120, 121, 123 | FE-02 |
| `core/services/workbench/trial_adoption.py` | 2 | 60, 74 | FE-02 |
| `core/services/workbench/trial_adoption_history.py` | 40 | 60, 70, 71, 72 | FE-02 |
| `core/services/workbench/trial_adoption_history_evidence.py` | 32 | 48, 49, 50, 53 | FE-02 |
| `core/services/workbench/trial_adoption_storage.py` | 13 | 28, 32, 36, 69 | FE-02 |
| `core/services/workbench/trial_base.py` | 8 | 63, 64, 68, 75, 79, 142, 172, 173 | FE-02 |
| `core/services/workbench/trial_capacity.py` | 1 | 77 | FE-02 |
| `data/repositories/workbench_execution_repo.py` | 2 | 26 | queued-unassigned |
| `data/repositories/workbench_outsourcing_source_repo.py` | 1 | 46 | queued-unassigned |
| `data/repositories/workbench_trial_raw_repo.py` | 1 | 35 | FE-02 |
| `data/repositories/workbench_trial_repo.py` | 7 | 40, 103 | FE-02 |
| `web/bootstrap/workbench_request_lifecycle_state.py` | 3 | 113, 138, 166 | FE-03 |
| `web/bootstrap/workbench_request_lifecycle_wsgi.py` | 6 | 41, 46, 48, 50, 55, 64 | FE-03 |
| `web/routes/workbench/batch_context.py` | 1 | 25 | FE-05 |
| `web/routes/workbench/batches.py` | 2 | 105, 113 | FE-05 |
| `web/routes/workbench/outsourcing.py` | 10 | 43, 44, 70, 72, 74, 84, 85 | queued-unassigned |
| `web/routes/workbench/reports.py` | 1 | 54 | queued-unassigned |
| `web/routes/workbench/resource_table_queries.py` | 2 | 102, 108 | FE-01 |
| `web/routes/workbench/trial_adoption_history.py` | 1 | 29 | FE-02 |
