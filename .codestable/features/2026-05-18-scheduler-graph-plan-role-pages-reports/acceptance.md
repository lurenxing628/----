---
doc_type: feature-acceptance
feature: 2026-05-18-scheduler-graph-plan-role-pages-reports
created: 2026-05-18
status: accepted
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-plan-role-pages-reports
---

# PR-7d 验收记录

## 验收结论

PR-7d 已完成。

本次把 `plan_role` 接到了甘特图、周计划、资源派工、排产优化分析页，以及超期清单、资源负荷与利用率、停机影响统计三类独立报表。旧链接不带 `plan_role` 时仍看“最终采用”；请求原算法最好或关键链最好时，页面、接口和导出读取同一套实际方案明细。

## 已完成范围

- 甘特图页面和 `/scheduler/gantt/data` 支持 `plan_role`，切换视图、周范围和日期范围时不会丢参数。
- 甘特关键链按实际方案隔离缓存，`adopted` 保留旧关键链入口，候选方案从当前方案 rows 计算。
- 周计划页面预览和导出读取同一个 effective plan，并把方案小字段写入导出日志。
- 资源派工 page/data/export 读取同一个 effective plan，导出文件名和日志都能看出实际方案。
- 三类报表页面和导出按当前方案 rows 计算，报表导出日志只写 requested/effective/status/candidate 小字段。
- 分析页展示候选对比表，并给 adopted / baseline_best / critical_best 提供带 `version + plan_role` 的跳转入口。
- 合法但缺失的候选角色会可见 fallback 到 adopted；未知 `plan_role` 直接返回校验错误，不静默成功。

## 明确未做

- 未实现 PR-7e 的配置、临时时间上限、候选清理策略和性能守卫。
- 未修改 PR-8 的 report-only 资源匹配计划。
- 未改 PR-6 的图评分语义和用户并行修复的 PR-6 dirty 文件。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_candidate_schema_contract.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_generation_contract.py tests/regression_scheduler_candidate_runner_contract.py tests/regression_scheduler_candidate_health_contract.py tests/regression_scheduler_graph_auto_selection_contract.py tests/regression_scheduler_candidate_persistence_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_analysis_contract.py tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold` -> 50 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_gantt_default_version_span.py tests/regression_gantt_page_version_default_latest.py tests/regression_gantt_contract_snapshot.py tests/regression_gantt_status_mode_semantics.py tests/regression_gantt_critical_chain_unavailable.py tests/regression_gantt_critical_chain_cache_thread_safe.py tests/regression_scheduler_week_plan_summary_observability.py tests/regression_week_plan_filename_uses_normalized_version.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py tests/test_resource_dispatch_viewmodel.py tests/regression_reports_page_version_default_latest.py tests/regression_reports_layout_contract.py tests/regression_scheduler_analysis_route_contract.py tests/regression_analysis_page_version_default_latest.py tests/regression_scheduler_analysis_vm_legacy_summary_bridge.py` -> 76 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_gantt_offset_range_consistency.py && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_reports_default_range_from_version_span.py && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_reports_export_version_default_latest.py` -> OK。
- PR7d touched code `ruff` -> All checks passed。
- PR7d touched code `pyright` -> 0 errors。

## 注意

当前工作区仍有 PR-6 并行修复文件和整条 PR-7 未提交改动，因此这里是 targeted proof，不是 clean-worktree proof。
