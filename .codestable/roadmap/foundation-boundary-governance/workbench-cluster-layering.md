# 工作台服务包簇层次设计（P1 / P2 依据）

日期：2026-09-20。对应路线图条目 `workbench-cluster-layering`（P1）与 `workbench-subpackages`（P2）。

## 1. 结论先行

- `core/services/workbench/` 平铺 245 个模块，按名字前缀能分出 16 个簇；簇之间有 50 条跨簇边，其中 5 对是双向的。
- 解法只有三种（下沉共享件、合并簇、显式接口注入）。本设计只用前两种：把"只读的持久证据读取器 + 纯叶子助手"下沉到 `facts/`，把误挂在看板下的候选对比搬回 `run`，把 `point_*`、`review_*`、`suppliers` 并入各自真正的簇。不引入接口注入，因为所有循环都能靠下沉解开，注入只会把依赖藏进构造参数。
- 下沉后按 2.2 的允许方向核对，跨簇违规边为 0（核对脚本见 §5）。

## 2. 目标结构

### 2.1 子包

| 子包 | 内容 | 规模 |
|---|---|---|
| 根（不分包） | `commands.py`、`messages.py`：命令事务框架与共享文案，谁都能用，自己不依赖任何簇 | 2 |
| `facts/` | 只读事实与叶子助手：零工时/点事件、排产前检查、候选存档读取（值/事实/投影/任务/存储/存档/基线核对）、试调方案存档、执行投影、计划序列化、系统日志读取与脱敏、表格与文件编解码 | 30 |
| `plan/` | 正式计划：基线、点证据、采纳基线核对、交期、占用、日历、导出、查询 | 22 |
| `execution/` | 执行侧：执行台账读取器、现场工作台、报工、实际甘特 | 16 |
| `run/` | 排产：输入、计算、作业、候选、候选采用、候选对比、排产前检查入口、计件采用 | 41 |
| `trial/` | 试调方案 | 18 |
| `report/` | 报表与 review 投影 | 11 |
| `dashboard/` | 看板 | 12 |
| `process/` | 工艺主数据与工艺文件 | 22 |
| `resource/` | 设备人员、日历、供应商、权限 | 19 |
| `material/` | 物料 | 6 |
| `batch/` | 批次 | 12 |
| `calibration/` | 校准与模板血缘 | 13 |
| `outsourcing/` | 外协 | 4 |
| `system/` | 系统维护与备份 | 5 |
| `master/` | 主数据总览 | 7 |

### 2.2 允许的依赖方向

一个簇只能 import 自己、根、以及下表列出的簇；表里没有的一律不许。

| 簇 | 允许依赖 |
|---|---|
| facts | （无） |
| plan / process / material / outsourcing / system / master | facts |
| execution | facts, plan |
| resource | facts, process |
| calibration | facts, process, execution, plan |
| batch | facts, process, resource, calibration, execution, plan |
| run | facts, plan, execution |
| trial | facts, plan, execution, run |
| report | facts, plan, execution, run, trial |
| dashboard | facts, plan, execution, run, trial, report, outsourcing |

结果侧链条：`facts ← plan ← execution ← run ← trial ← report ← dashboard`。主数据侧：`facts ← process ← resource`，`batch` 与 `calibration` 在其上。两侧只在 `batch → execution`、`calibration → execution/plan` 处相接，方向单一。

## 3. 五对双向依赖与解法

| 对 | 现状 | 解法 |
|---|---|---|
| plan ↔ run | `plan_adoption_baseline_sources`、`plan_point_evidence`、`plan_projection`、`plan_process_order` 读候选存档（`run_candidate_*`）；`run_candidate_history`、`run_input_runtime` 读计划基线与点证据 | 候选存档读取器整体下沉 `facts/`：`candidate_values/facts/projection/tasks/store`；`run_candidate_adoption_storage` 拆成读取半部（`load_adoption_candidate`、`require_adoption_schema` → `facts/candidate_archive.py`）与采用时校验半部（留 run）；`run_candidate_baseline` 拆成 `AdmissionBaseline` 核对类（→ `facts/candidate_baseline.py`）与查询服务（留 run） |
| plan ↔ trial | plan 侧 4 个模块读已保存方案（`trial_adoption_storage`）；trial 读计划 | `trial_adoption_storage` + `trial_policy` 下沉 `facts/trial_scenario_archive.py`、`facts/trial_policy.py` |
| run ↔ dashboard | `run_candidate_analysis` 用看板下的候选对比私有助手 | `dashboard_candidate_comparison/metrics` 本来就是候选对比，搬回 run（`run/candidate_comparison.py`、`run/candidate_metrics.py`）；它们依赖的 `dashboard_resource_metrics` 是纯叶子，下沉 `facts/resource_pressure.py` |
| run ↔ system | `run_data_context` 读系统日志；`system_files` 反过来用 `run_data_context` | `run_data_context`、`system_reads`、`system_journal`、`system_redaction` 全部下沉 `facts/` |
| facts ↔ run | `zero_duration → preflight_checks` | `preflight_checks`、`preflight_dependencies` 属于叶子，下沉 `facts/` |

其余单向但方向反的边：

- `process → resource`（表格与文件编解码 5 处）：`resource_table_cells/index`、`resource_file_codec/writer` 是纯助手，下沉 `facts/table_*.py`、`facts/file_*.py`。
- `resource → process`（`suppliers`）：`suppliers` 只被 `resource_queries` 用，归 `resource/`。
- `plan → point`、`point → plan`：`point_plan_query` 只是计划的点查询，并入 `plan/point_query.py`。
- `report → review`、`dashboard → review`：`review_*` 只被报表用，并入 `report/`。
- `run → process/resource`（导出用 `process_file_xml`、`resource_file_writer`）：随编解码一起下沉 `facts/`。
- `execution ↔ plan`：`execution` 依赖 `plan_queries/plan_projection`，`run` 依赖 `execution_ledger`，plan 不依赖 execution，因此 execution 放在 plan 与 run 之间。

## 4. 命名与执行规则

- 子包内去掉簇前缀：`run_candidate_adoption` → `run/candidate_adoption.py`；前缀不是簇名的保留原名：`piece_adoption` → `run/piece_adoption.py`。
- 与簇同名的主服务模块改为 `service.py`：`trial.py` → `trial/service.py`，`batches.py` → `batch/service.py`。
- 下沉到 `facts/` 的模块按"事实含义"命名：`run_candidate_storage` → `facts/candidate_store.py`，`trial_adoption_storage` → `facts/trial_scenario_archive.py`。
- 调用方（含测试、注册表、monkeypatch 字符串）用 `tools/move_modules.py` 一次改完；模块改名时保留本地绑定名（`from ..run import jobs as run_jobs`），不留任何垫片或 `__getattr__`。
- 子包 `__init__.py` 只有 docstring。
- 搬迁计划落在 `moves/workbench-p1-facts.json` 与 `moves/workbench-p2-NN-<簇>.json`，一簇一提交。
- 适应度测试 `tests/gate_meta/test_workbench_cluster_layering.py` 锁住 §2.2；P1 阶段按前缀+覆盖表判簇，P2 全部分包后改按目录判簇。

## 5. 核对方法

```bash
# 按分配表与允许方向核对跨簇边（P1 前用前缀判簇，P2 后按目录判簇）
.venv/bin/python -m pytest tests/gate_meta/test_workbench_cluster_layering.py -q
# 分包后目录级环由既有门禁覆盖
.venv/bin/python -m tools.scan_import_cycles --fail-on-new-cycle
```

## 6. 模块分配表

| 模块（分包前） | 簇 | 新路径 |
|---|---|---|
| `batch_bulk` | batch | `batch/bulk.py` |
| `batch_execution` | batch | `batch/execution.py` |
| `batch_facts` | batch | `batch/facts.py` |
| `batch_file_codec` | batch | `batch/file_codec.py` |
| `batch_file_preview` | batch | `batch/file_preview.py` |
| `batch_files` | batch | `batch/files.py` |
| `batch_operations` | batch | `batch/operations.py` |
| `batch_projection` | batch | `batch/projection.py` |
| `batch_queries` | batch | `batch/queries.py` |
| `batch_template_preview` | batch | `batch/template_preview.py` |
| `batch_template_validation` | batch | `batch/template_validation.py` |
| `batches` | batch | `batch/service.py` |
| `calibration` | calibration | `calibration/service.py` |
| `calibration_adoption` | calibration | `calibration/adoption.py` |
| `calibration_adoption_evidence` | calibration | `calibration/adoption_evidence.py` |
| `calibration_adoption_policy` | calibration | `calibration/adoption_policy.py` |
| `calibration_export` | calibration | `calibration/export.py` |
| `calibration_facts` | calibration | `calibration/facts.py` |
| `calibration_integrity` | calibration | `calibration/integrity.py` |
| `calibration_method` | calibration | `calibration/method.py` |
| `calibration_samples` | calibration | `calibration/samples.py` |
| `calibration_table` | calibration | `calibration/table.py` |
| `template_lineage` | calibration | `calibration/template_lineage.py` |
| `template_lineage_calibration` | calibration | `calibration/template_lineage_calibration.py` |
| `template_lineage_query` | calibration | `calibration/template_lineage_query.py` |
| `dashboard` | dashboard | `dashboard/service.py` |
| `dashboard_analysis` | dashboard | `dashboard/analysis.py` |
| `dashboard_catalogs` | dashboard | `dashboard/catalogs.py` |
| `dashboard_commands` | dashboard | `dashboard/commands.py` |
| `dashboard_downtime` | dashboard | `dashboard/downtime.py` |
| `dashboard_execution` | dashboard | `dashboard/execution.py` |
| `dashboard_external` | dashboard | `dashboard/external.py` |
| `dashboard_external_handling` | dashboard | `dashboard/external_handling.py` |
| `dashboard_external_sources` | dashboard | `dashboard/external_sources.py` |
| `dashboard_facts` | dashboard | `dashboard/facts.py` |
| `dashboard_policy` | dashboard | `dashboard/policy.py` |
| `dashboard_projection` | dashboard | `dashboard/projection.py` |
| `actual_gantt` | execution | `execution/actual_gantt.py` |
| `actual_gantt_chain` | execution | `execution/actual_gantt_chain.py` |
| `actual_gantt_export` | execution | `execution/actual_gantt_export.py` |
| `actual_gantt_scope` | execution | `execution/actual_gantt_scope.py` |
| `execution_ledger` | execution | `execution/ledger.py` |
| `field_report_files` | execution | `execution/field_report_files.py` |
| `field_report_files_codec` | execution | `execution/field_report_files_codec.py` |
| `field_report_files_identity` | execution | `execution/field_report_files_identity.py` |
| `field_report_files_xml` | execution | `execution/field_report_files_xml.py` |
| `field_workspace` | execution | `execution/field_workspace.py` |
| `field_workspace_scope` | execution | `execution/field_workspace_scope.py` |
| `production_report` | execution | `execution/production_report.py` |
| `production_report_prepare` | execution | `execution/production_report_prepare.py` |
| `production_report_validation` | execution | `execution/production_report_validation.py` |
| `production_report_void` | execution | `execution/production_report_void.py` |
| `production_report_void_dependencies` | execution | `execution/production_report_void_dependencies.py` |
| `dashboard_resource_metrics` | facts | `facts/resource_pressure.py` |
| `execution_ledger_projection` | facts | `facts/execution_projection.py` |
| `piece_adoption_scope` | facts | `facts/piece_scope.py` |
| `plan_fact_serialization` | facts | `facts/plan_serialization.py` |
| `preflight_checks` | facts | `facts/preflight_checks.py` |
| `preflight_dependencies` | facts | `facts/preflight_dependencies.py` |
| `process_file_xml` | facts | `facts/process_file_xml.py` |
| `resource_file_codec` | facts | `facts/file_codec.py` |
| `resource_file_writer` | facts | `facts/file_writer.py` |
| `resource_table_cells` | facts | `facts/table_cells.py` |
| `resource_table_index` | facts | `facts/table_index.py` |
| `run_candidate_facts` | facts | `facts/candidate_facts.py` |
| `run_candidate_projection` | facts | `facts/candidate_projection.py` |
| `run_candidate_storage` | facts | `facts/candidate_store.py` |
| `run_candidate_tasks` | facts | `facts/candidate_tasks.py` |
| `run_candidate_values` | facts | `facts/candidate_values.py` |
| `run_data_context` | facts | `facts/run_data_context.py` |
| `run_input_projection_codec` | facts | `facts/run_input_codec.py` |
| `run_input_readonly` | facts | `facts/run_input_readonly.py` |
| `run_input_rows` | facts | `facts/run_input_rows.py` |
| `run_policy` | facts | `facts/run_policy.py` |
| `system_journal` | facts | `facts/system_journal.py` |
| `system_reads` | facts | `facts/system_reads.py` |
| `system_redaction` | facts | `facts/system_redaction.py` |
| `trial_adoption_storage` | facts | `facts/trial_scenario_archive.py` |
| `trial_policy` | facts | `facts/trial_policy.py` |
| `zero_duration` | facts | `facts/zero_duration.py` |
| `zero_duration_evidence` | facts | `facts/zero_duration_evidence.py` |
| `master_overview` | master | `master/overview.py` |
| `master_overview_calendar` | master | `master/overview_calendar.py` |
| `master_overview_facts` | master | `master/overview_facts.py` |
| `master_overview_graph` | master | `master/overview_graph.py` |
| `master_overview_process` | master | `master/overview_process.py` |
| `master_overview_relations` | master | `master/overview_relations.py` |
| `master_overview_resources` | master | `master/overview_resources.py` |
| `material_bulk` | material | `material/bulk.py` |
| `material_file_codec` | material | `material/file_codec.py` |
| `material_files` | material | `material/files.py` |
| `material_queries` | material | `material/queries.py` |
| `material_table_facts` | material | `material/table_facts.py` |
| `materials` | material | `material/service.py` |
| `outsourcing` | outsourcing | `outsourcing/service.py` |
| `outsourcing_commands` | outsourcing | `outsourcing/commands.py` |
| `outsourcing_projection` | outsourcing | `outsourcing/projection.py` |
| `outsourcing_source` | outsourcing | `outsourcing/source.py` |
| `legacy_navigation_queries` | plan | `plan/legacy_navigation_queries.py` |
| `official_plan_persistence` | plan | `plan/official_persistence.py` |
| `plan_adoption_baseline` | plan | `plan/adoption_baseline.py` |
| `plan_adoption_baseline_identity` | plan | `plan/adoption_baseline_identity.py` |
| `plan_adoption_baseline_sources` | plan | `plan/adoption_baseline_sources.py` |
| `plan_adoption_baseline_values` | plan | `plan/adoption_baseline_values.py` |
| `plan_baseline` | plan | `plan/baseline.py` |
| `plan_calendar` | plan | `plan/calendar.py` |
| `plan_calendar_context` | plan | `plan/calendar_context.py` |
| `plan_delivery` | plan | `plan/delivery.py` |
| `plan_delivery_completeness` | plan | `plan/delivery_completeness.py` |
| `plan_delivery_projection` | plan | `plan/delivery_projection.py` |
| `plan_delivery_repository` | plan | `plan/delivery_repository.py` |
| `plan_export` | plan | `plan/export.py` |
| `plan_occupancy` | plan | `plan/occupancy.py` |
| `plan_occupancy_constraints` | plan | `plan/occupancy_constraints.py` |
| `plan_point_evidence` | plan | `plan/point_evidence.py` |
| `plan_process_order` | plan | `plan/process_order.py` |
| `plan_projection` | plan | `plan/projection.py` |
| `plan_queries` | plan | `plan/queries.py` |
| `plan_workspace_dto` | plan | `plan/workspace_dto.py` |
| `point_plan_query` | plan | `plan/point_query.py` |
| `process_file_codec` | process | `process/file_codec.py` |
| `process_file_export` | process | `process/file_export.py` |
| `process_file_hours` | process | `process/file_hours.py` |
| `process_file_hours_preview` | process | `process/file_hours_preview.py` |
| `process_file_hours_values` | process | `process/file_hours_values.py` |
| `process_file_reader` | process | `process/file_reader.py` |
| `process_file_route` | process | `process/file_route.py` |
| `process_file_route_preview` | process | `process/file_route_preview.py` |
| `process_file_values` | process | `process/file_values.py` |
| `process_file_writer` | process | `process/file_writer.py` |
| `process_files` | process | `process/files.py` |
| `process_mutations` | process | `process/mutations.py` |
| `process_part_actions` | process | `process/part_actions.py` |
| `process_part_actions_facts` | process | `process/part_actions_facts.py` |
| `process_projection` | process | `process/projection.py` |
| `process_queries` | process | `process/queries.py` |
| `process_quota_protection` | process | `process/quota_protection.py` |
| `process_route_apply` | process | `process/route_apply.py` |
| `process_route_preview` | process | `process/route_preview.py` |
| `process_stage_apply` | process | `process/stage_apply.py` |
| `process_table` | process | `process/table.py` |
| `process_zero_hours` | process | `process/zero_hours.py` |
| `report_catalog` | report | `report/catalog.py` |
| `report_columns` | report | `report/columns.py` |
| `report_exports` | report | `report/exports.py` |
| `report_facts` | report | `report/facts.py` |
| `report_queries` | report | `report/queries.py` |
| `review_export_labels` | report | `report/review_export_labels.py` |
| `review_legacy` | report | `report/review_legacy.py` |
| `review_projection` | report | `report/review_projection.py` |
| `review_records` | report | `report/review_records.py` |
| `review_summary` | report | `report/review_summary.py` |
| `review_values` | report | `report/review_values.py` |
| `calendars` | resource | `resource/calendars.py` |
| `operator_machine_permissions` | resource | `resource/operator_machine_permissions.py` |
| `resource_bulk` | resource | `resource/bulk.py` |
| `resource_calendar_summary` | resource | `resource/calendar_summary.py` |
| `resource_catalogs` | resource | `resource/catalogs.py` |
| `resource_entities` | resource | `resource/entities.py` |
| `resource_file_input` | resource | `resource/file_input.py` |
| `resource_file_projection` | resource | `resource/file_projection.py` |
| `resource_files` | resource | `resource/files.py` |
| `resource_metrics` | resource | `resource/metrics.py` |
| `resource_projection` | resource | `resource/projection.py` |
| `resource_queries` | resource | `resource/queries.py` |
| `resource_readiness` | resource | `resource/readiness.py` |
| `resource_relations` | resource | `resource/relations.py` |
| `resource_relations_projection` | resource | `resource/relations_projection.py` |
| `resource_states` | resource | `resource/states.py` |
| `resource_table_facts` | resource | `resource/table_facts.py` |
| `resource_table_states` | resource | `resource/table_states.py` |
| `suppliers` | resource | `resource/suppliers.py` |
| `commands` | root | `root/commands.py`（留根） |
| `messages` | root | `root/messages.py`（留根） |
| `dashboard_candidate_comparison` | run | `run/candidate_comparison.py` |
| `dashboard_candidate_metrics` | run | `run/candidate_metrics.py` |
| `piece_adoption` | run | `run/piece_adoption.py` |
| `piece_adoption_execution` | run | `run/piece_adoption_execution.py` |
| `piece_adoption_facts` | run | `run/piece_adoption_facts.py` |
| `piece_adoption_trial` | run | `run/piece_adoption_trial.py` |
| `preflight` | run | `run/preflight.py` |
| `preflight_execution` | run | `run/preflight_execution.py` |
| `preflight_facts` | run | `run/preflight_facts.py` |
| `preflight_result` | run | `run/preflight_result.py` |
| `run_candidate_adoption` | run | `run/candidate_adoption.py` |
| `run_candidate_adoption_constraints` | run | `run/candidate_adoption_constraints.py` |
| `run_candidate_adoption_persistence` | run | `run/candidate_adoption_persistence.py` |
| `run_candidate_adoption_storage` | run | `run/candidate_adoption_storage.py` |
| `run_candidate_adoption_validation` | run | `run/candidate_adoption_validation.py` |
| `run_candidate_analysis` | run | `run/candidate_analysis.py` |
| `run_candidate_baseline` | run | `run/candidate_baseline.py` |
| `run_candidate_delivery` | run | `run/candidate_delivery.py` |
| `run_candidate_export` | run | `run/candidate_export.py` |
| `run_candidate_history` | run | `run/candidate_history.py` |
| `run_candidates` | run | `run/candidates.py` |
| `run_compute` | run | `run/compute.py` |
| `run_compute_graph` | run | `run/compute_graph.py` |
| `run_compute_validation` | run | `run/compute_validation.py` |
| `run_history` | run | `run/history.py` |
| `run_history_projection` | run | `run/history_projection.py` |
| `run_history_storage` | run | `run/history_storage.py` |
| `run_input` | run | `run/input.py` |
| `run_input_admission` | run | `run/input_admission.py` |
| `run_input_config` | run | `run/input_config.py` |
| `run_input_execution` | run | `run/input_execution.py` |
| `run_input_external` | run | `run/input_external.py` |
| `run_input_piece` | run | `run/input_piece.py` |
| `run_input_points` | run | `run/input_points.py` |
| `run_input_runtime` | run | `run/input_runtime.py` |
| `run_jobs` | run | `run/jobs.py` |
| `run_jobs_facts` | run | `run/jobs_facts.py` |
| `run_progress` | run | `run/progress.py` |
| `run_worker` | run | `run/worker.py` |
| `run_worker_recovery` | run | `run/worker_recovery.py` |
| `run_worker_snapshot` | run | `run/worker_snapshot.py` |
| `system_config` | system | `system/config.py` |
| `system_exports` | system | `system/exports.py` |
| `system_files` | system | `system/files.py` |
| `system_maintenance_records` | system | `system/maintenance_records.py` |
| `system_restore` | system | `system/restore.py` |
| `trial` | trial | `trial/service.py` |
| `trial_adoption` | trial | `trial/adoption.py` |
| `trial_adoption_history` | trial | `trial/adoption_history.py` |
| `trial_adoption_history_evidence` | trial | `trial/adoption_history_evidence.py` |
| `trial_adoption_history_policy` | trial | `trial/adoption_history_policy.py` |
| `trial_adoption_input` | trial | `trial/adoption_input.py` |
| `trial_adoption_persistence` | trial | `trial/adoption_persistence.py` |
| `trial_adoption_validation` | trial | `trial/adoption_validation.py` |
| `trial_base` | trial | `trial/base.py` |
| `trial_calendar` | trial | `trial/calendar.py` |
| `trial_capacity` | trial | `trial/capacity.py` |
| `trial_catalog` | trial | `trial/catalog.py` |
| `trial_constraints` | trial | `trial/constraints.py` |
| `trial_execution_anchors` | trial | `trial/execution_anchors.py` |
| `trial_facts` | trial | `trial/facts.py` |
| `trial_projection` | trial | `trial/projection.py` |
| `trial_protection` | trial | `trial/protection.py` |
| `trial_validation` | trial | `trial/validation.py` |
