---
doc_type: issue-fix
issue: 2026-06-15-reference-trace-systemic-hardening
status: fixed
path: standard
fix_date: 2026-06-15
tags:
  - reference-trace
  - fixed-file-security
  - query-pushdown
  - report-degradation
  - navigation-context
---

# 审计追踪问题系统性修复记录

## 1. 背景

本轮修复承接 `.codestable/audits/2026-06-14-subagent-reference-trace-verification/`
的 11 条已核实发现。目标不是在单个页面打补丁，而是把同类根因收口到公共读写、公共查询、公共展示和公共回跳链路上。

## 2. 根因

- 固定名运行文件：启动契约、launcher 日志、备份维护锁和维护清理各自读写文件，已有软链接防护样板没有抽成公共原语。
- 查询下推：页面和 URL 已经收集到日期、分页、批次、资源和任务身份，但 service/repo 签名没有完整承接，导致先取大集合再过滤。
- 诚实展示：利用率、停机影响和批次详情遇到坏时间时会少算，但页面/导出没有告诉用户结果是部分计算。
- 公开响应与回跳：甘特调整接口直接返回模型字典，批次/人员批量动作没有完整沿用已有安全 `next` 回跳。

## 3. 修复方案

- 新增 `core/infrastructure/safe_files.py`，统一固定名文件安全读写、JSON 读写、独占创建和删除。启动契约、launcher log、runtime probe、secret key、备份维护锁和维护清理改用同一个 helper；备份列表和清理只处理普通备份文件。
- 甘特显式日期范围加 62 天后端上限，只限制用户显式 `start_date/end_date`，不误伤版本自身跨度回填；默认版本跨度不再被导航链接写成显式日期。
- 批次列表把 `ready_status`、分页 `limit/offset` 下推到 `BatchRepo`；派工查询把 `batch_id/schedule_id/op_id` 传到 SQL 等值条件；延期诊断把 `resource_type/resource_id/batch_id` 传到服务和 repo。
- 超期清单/延期诊断明确按版本复盘延期风险，不再从页面、隐藏字段或导出 URL 传播日期参数。
- 报表计算新增 degradation collector，坏时间行会计数、采样，并传到页面提示和 Excel 摘要；批次详情 `_placement_span()` 返回部分计算状态和坏时间数量。
- 对抗复审后补强坏时间 SQL 入口：新增 `data/repositories/schedule_time_sql.py` 统一计划明细时间过滤片段；派工查询、报表明细、停机明细和甘特默认版本跨度不再在 SQL 层提前丢掉坏时间行；超期清单新增“排程时间异常”分桶，有排程但计划完成时间坏掉的批次不再被误报成“未排程逾期”，页面和导出摘要都会说明数据不完整。
- 甘特调整接口改成公开白名单响应，不再直接返回 `ScheduleAdjustment*Change.to_dict()`；页面跨计划上下文跳转优先使用 `plan_context_token`，批次详情工序保存改用 `update-token` 路由，避免把原始内部定位字段继续放到页面普通属性和公开响应里。
- 对抗复审后补强公开 token 链路：新增 `web/public_token_registry.py`，把 `plan_context_token` 和工序保存 token 从可 base64 解码的签名 payload 改成服务端内存随机 token；工作台导航、说明书回跳、报表/首页/排产分析/甘特/周计划/资源排班入口统一能读取公开 token。`scheduler_workbench_link_query.py` 在共享链接层把只有 `scenario_id` 的上下文转成 `plan_context_token`，无 token 生成环境时禁用链接，不退回裸 `scenario_id`；`static/js/report_plan_filter.js` 同时清理 `scenario_id` 和 `plan_context_token`，避免切换版本/方案后继续提交旧模拟方案。
- 对抗复审后补强公共回跳链路：`current_public_return_url` 统一丢弃 `scenario_id/op_id/schedule_id/candidate_id/source_table` 及候选/工序保存相关内部字段；需要保留模拟方案上下文时只派生 `plan_context_token`，不再把内部字段原样塞进隐藏 `next`。
- 批次新增失败、批量删除/复制/修改，以及人员单删/批量操作统一复用 `_safe_next_url` 保留筛选和页码，非法 next 仍拒绝。
- 对抗复审后补强固定文件边界：数据库恢复前先校验当前数据库路径不是软链接、硬链接或非普通文件，恢复写入前后也复核同一个普通文件；启动契约清理只信任当前状态目录，以及带有匹配运行契约的镜像日志目录，格式合法但指向外部目录的 JSON 不再触发外部固定名文件删除。

## 4. 主要改动文件

- 固定文件安全：`core/infrastructure/safe_files.py`、`core/infrastructure/backup.py`、`core/services/system/maintenance/cleanup_task.py`、`web/bootstrap/launcher_*.py`、`web/bootstrap/runtime_probe.py`、`web/bootstrap/security.py`
- 查询下推：`core/services/scheduler/gantt_plan_query.py`、`core/services/scheduler/schedule_result_view_range.py`、`data/repositories/batch_repo.py`、`core/services/scheduler/batch_service.py`、`data/repositories/schedule_plan_query_repo.py`、`data/repositories/schedule_time_sql.py`、`core/services/scheduler/schedule_plan_query_service.py`、`core/services/scheduler/resource_dispatch_service.py`、`core/services/scheduler/resource_dispatch_execution_service.py`
- 报表与延期诊断：`core/services/common/overdue_calculations.py`、`core/services/report/report_degradation.py`、`core/services/report/utilization.py`、`core/services/report/downtime_impact.py`、`core/services/report/report_engine.py`、`core/services/report/report_plan_helpers.py`、`core/services/scheduler/schedule_delay_diagnosis_service.py`、`web/routes/reports_page_support.py`、`web/routes/reports_export_support.py`
- 页面与公开响应：`web/public_token_registry.py`、`web/navigation_context.py`、`web/manual_src_security.py`、`web/routes/report_plan_preview.py`、`web/routes/dashboard.py`、`web/routes/domains/scheduler/scheduler_analysis.py`、`web/routes/domains/scheduler/scheduler_batches.py`、`web/routes/personnel_pages.py`、`web/routes/domains/scheduler/scheduler_batch_detail.py`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py`、`web/viewmodels/scheduler_batch_schedule_placement.py`、`web/viewmodels/scheduler_workbench_link_query.py`、相关模板和 JS
- 回归测试：`tests/app_runtime/test_fixed_file_security.py`、`tests/scheduler_analysis/test_batch_list_pushdown_contract.py`、`tests/web_pages/test_report_plan_filter_js_contract.py` 以及甘特、报表、派工、批次详情、回跳上下文相关测试
- 架构/速查文档：`.codestable/architecture/ARCHITECTURE.md`、`开发文档/系统速查表.md`

## 5. 验证结果

- `.venv/bin/python -m compileall -q core web tests tools`：通过。
- `.venv/bin/python -m pytest -q tests/app_runtime/test_fixed_file_security.py tests/app_runtime/test_win7_launcher_runtime_paths.py tests/web_pages/test_reports_workbench_backlink_contract.py tests/scheduler_analysis/test_report_context_filters_contract.py tests/schedule/route_view/test_batch_schedule_placement_helpers.py tests/schedule/route_view/test_batch_detail_linkage.py tests/web_pages/test_scheduler_batch_schedule_placement.py tests/scheduler_analysis/test_batch_list_pushdown_contract.py tests/gantt/test_gantt_task_detail_panel_contract.py tests/gantt/test_gantt_task_detail_js_contract.py tests/gantt/test_gantt_contract_snapshot.py tests/gantt/test_gantt_draft_save_and_preview.py tests/resource_dispatch/test_resource_dispatch_bad_time_rows_surface_degraded.py`：137 passed。
- `.venv/bin/python -m pytest -q tests/gantt`：224 passed。
- `.venv/bin/python -m pytest -q tests/app_runtime tests/scheduler_analysis tests/web_pages tests/resource_dispatch tests/gantt tests/schedule/route_view/test_batch_schedule_placement_helpers.py tests/schedule/route_view/test_batch_detail_linkage.py`：1140 passed。
- `.venv/bin/python -m pytest -q tests/app_runtime/test_fixed_file_security.py tests/app_runtime/test_win7_launcher_runtime_paths.py tests/web_pages/test_reports_workbench_backlink_contract.py tests/scheduler_analysis/test_report_context_filters_contract.py tests/schedule/route_view/test_batch_schedule_placement_helpers.py tests/schedule/route_view/test_batch_detail_linkage.py tests/web_pages/test_scheduler_batch_schedule_placement.py tests/scheduler_analysis/test_batch_list_pushdown_contract.py tests/gantt tests/resource_dispatch/test_resource_dispatch_bad_time_rows_surface_degraded.py`：345 passed。
- `.venv/bin/python -m pytest tests/app_runtime/test_fixed_file_security.py tests/app_runtime/test_runtime_contract_launcher.py tests/app_runtime/test_launcher_observability.py tests/app_runtime/test_runtime_probe_resolution.py tests/migration_db/test_backup_integrity_check_contract.py tests/migration_db/test_backup_restore_pending_verify_code.py tests/migration_db/test_restore_pre_snapshot_failure_contract.py tests/resource_dispatch/test_resource_dispatch_bad_time_rows_surface_degraded.py tests/resource_dispatch/test_resource_dispatch_site_records_frontend_contract.py tests/resource_dispatch/test_scheduler_candidate_resource_dispatch_contract.py tests/gantt/test_gantt_default_version_span.py tests/gantt/test_gantt_degradation_surface.py tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py tests/scheduler_analysis/test_report_context_filters_contract.py tests/scheduler_analysis/test_report_source_case_insensitive.py tests/web_pages/test_reports_default_range_from_version_span.py -q`：130 passed。
- `.venv/bin/python -m pytest tests/algorithm/test_due_exclusive_consistency.py tests/scheduler_analysis/test_report_export_size_mode_selection.py tests/scheduler_analysis/test_report_export_large_scope_rejects_need_async.py -q`：3 passed。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python -m pytest -q -p no:cacheprovider tests/web_pages/test_report_plan_filter_js_contract.py tests/schedule/route_view/test_batch_detail_linkage.py tests/web_pages/test_scenario_preview_secondary_outputs.py tests/web_pages/test_reports_workbench_navigation_contract.py tests/schedule/route_view/test_scheduler_ops_update_route_contract.py tests/gantt/test_gantt_draft_save_and_preview.py tests/resource_dispatch/test_scheduler_candidate_resource_dispatch_contract.py tests/web_pages/test_aps_workbench_context_propagation_contract.py tests/web_pages/test_aps_workbench_first_round_flow_contract.py tests/web_pages/test_reports_workbench_backlink_contract.py tests/web_pages/test_dashboard_workbench_contract.py tests/web_pages/test_page_manual_registry.py tests/web_pages/test_manual_entry_scope.py tests/schedule/route_view/test_scheduler_workbench_links_contract.py tests/candidate/test_scheduler_candidate_analysis_links_contract.py tests/gantt/test_gantt_contract_snapshot.py tests/gantt/test_gantt_task_detail_panel_contract.py`：158 passed。
- `.venv/bin/python -m pytest tests/schedule/route_view/test_scheduler_workbench_links_contract.py tests/schedule/route_view/test_week_plan_span_jump.py tests/web_pages/test_history_links_adoption.py tests/web_pages/test_workbench_nav_entry_contract.py tests/web_pages/test_reports_workbench_navigation_contract.py tests/web_pages/test_reports_workbench_backlink_contract.py tests/web_pages/test_scenario_preview_secondary_outputs.py tests/app_runtime/test_safe_next_url_hardening.py`：90 passed。
- `.venv/bin/python -m ruff check web/viewmodels/scheduler_workbench_link_query.py web/viewmodels/scheduler_workbench_links.py web/manual_src_security.py web/routes/reports_export_support.py web/routes/reports_page_support.py tests/app_runtime/test_safe_next_url_hardening.py tests/web_pages/test_reports_workbench_navigation_contract.py tests/schedule/route_view/test_scheduler_workbench_links_contract.py tests/schedule/route_view/test_week_plan_span_jump.py tests/web_pages/test_history_links_adoption.py`：通过。
- `.venv/bin/python -m pytest tests/calendar_maintenance/test_maintenance_window_mutex.py tests/test_architecture_fitness.py::test_file_size_limit tests/resource_dispatch/test_resource_dispatch_bad_time_rows_surface_degraded.py tests/gantt/test_gantt_default_version_span.py tests/scheduler_analysis/test_report_delay_diagnosis_plain_language.py tests/app_runtime/test_fixed_file_security.py tests/migration_db/test_backup_integrity_check_contract.py -q`：67 passed。
- `.venv/bin/python -m pytest tests/app_runtime/test_safe_next_url_hardening.py tests/app_runtime/test_safe_next_url_observability.py tests/web_pages/test_reports_workbench_navigation_contract.py tests/web_pages/test_reports_workbench_backlink_contract.py tests/web_pages/test_dashboard_workbench_contract.py tests/web_pages/test_aps_workbench_context_propagation_contract.py tests/schedule/route_view/test_scheduler_workbench_links_contract.py tests/candidate/test_scheduler_candidate_analysis_links_contract.py -q`：79 passed。
- `.venv/bin/python tools/check_full_test_debt.py --allow-dirty-worktree-proof --sharded --shard-count 3`：收集 4217 个测试，unexpected failure 为 0，通过。
- `.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache`：17 步内容检查全部通过；因为当前工作区不是 clean，脚本按设计返回 `passed_but_unbound`，不能称为 clean-worktree proof。

## 6. Subagent 对抗复审

- 第 4 轮定向复审覆盖固定名文件安全、派工/甘特坏时间入口、超期坏结束时间，结论均为 `recheck_passed`。
- 第 4 轮盲审覆盖固定文件、查询/报表、公开响应和回跳上下文。其中一个盲审发现 `current_public_return_url` 会把候选和工序保存相关内部字段带进隐藏 `next`，已修复并由替换盲审复核为 `recheck_passed`。
- 截止本记录更新，已知阻塞项均已闭环，没有剩余 Subagent 阻塞结论。

## 7. 遗留事项

- 当前工作区包含用户先前已有的未提交审计材料，以及本轮修复改动；因此即使后续质量门禁通过，也不能称为 clean-worktree proof。
- 旧模型对象里的 `to_dict()` 保留给服务端内部或既有单元测试使用；公开路由已经改成白名单投影。
