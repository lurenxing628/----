---
doc_type: feature-acceptance
feature: 2026-05-18-scheduler-graph-candidate-transaction-persistence
requirement:
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-candidate-transaction-persistence
status: accepted
summary: PR-7c 已把内存候选比较接入正式排产主链，并实现 Schedule / History / Candidate 同事务落库
tags: [scheduler, graph, networkx, candidate, persistence]
---

# scheduler-graph-candidate-transaction-persistence 验收说明

## 完成内容

- 正式排产主链现在先运行 `run_candidate_comparison()`。
- 主链只采用 `selection.selected_plan` 作为最终 adopted 方案。
- adopted 方案通过 `build_validated_schedule_payload()` 校验后，才分配正式 `version`。
- `Schedule`、状态更新、`ScheduleHistory`、`ScheduleCandidate`、`ScheduleCandidateRows`、`ScheduleCandidateSelection` 通过 `persist_schedule_run_with_candidates()` 同事务写入。
- 候选写入失败时，正式 `Schedule` 和 `ScheduleHistory` 会一起回滚，不留下“正式排产成功但候选表缺失”的半套历史。
- `OperationLogs` 仍在事务提交后写；日志里的 `algo.candidate_comparison` 只保留极小字段，不写候选列表、排产行、图节点边、raw graph 或完整 diagnostics。
- `result_summary.algo.candidate_comparison` 只保留候选比较小摘要；即使触发 `summary_size_guard` 最小摘要，也保留 adopted key、代表 key、数量、时间预算和选择原因这些极小字段。
- 当最终 adopted 是 baseline，但本次有关键链候选图报告时，正式 summary 仍保留图分析 public 小报告；日志仍不带 diagnostics。
- 本阶段没有改页面、模板、JS、导出、报表 `plan_role` 切换或配置页字段，这些继续留给 PR-7d / PR-7e。
- 本阶段没有编辑用户并行处理的 PR-6 文件：
  - `core/services/scheduler/graph/metrics.py`
  - `tests/regression_scheduler_graph_on_mode_contract.py`
  - `tests/scheduler_graph/test_metrics_impact.py`

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_candidate_schema_contract.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_generation_contract.py tests/regression_scheduler_candidate_runner_contract.py tests/regression_scheduler_candidate_health_contract.py tests/regression_scheduler_graph_auto_selection_contract.py tests/regression_scheduler_candidate_persistence_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_schedule_orchestrator_contract.py tests/regression_schedule_summary_v11_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py tests/regression_schedule_history_not_created_for_empty_schedule.py tests/regression_schedule_service_reschedulable_contract.py tests/regression_schedule_service_missing_resource_source_case_insensitive.py tests/regression_schedule_service_passes_algo_stats_to_summary.py tests/regression_schedule_service_empty_reschedulable_rejected.py tests/regression_schedule_service_all_frozen_short_circuit.py tests/regression_schedule_service_facade_delegation.py tests/test_schedule_service_input_merge_context_contract.py`
  - 结果：57 passed。
- `ruff check` 针对 PR-7c 代码和测试文件：
  - 结果：All checks passed。
- `pyright` 针对 PR-7c 代码和测试文件：
  - 结果：0 errors。
- CodeStable YAML 校验：
  - PR-7c feature 目录通过。
  - roadmap items.yaml 通过。
- `git diff --check`：
  - 通过。

## 已知边界

- PR-7c 没有实现页面/接口/导出/报表按 `plan_role` 切换；下一步由 PR-7d 承接。
- PR-7c 没有实现候选档数配置、临时时间上限 UI、候选清理策略或性能守卫；后续由 PR-7e 承接。
- 额外跑 PR-6 邻近图回归时，`tests/regression_scheduler_graph_on_mode_contract.py::test_on_cycle_block_no_uses_real_optimizer_sgs_override` 仍有一个旧断言冲突：它把旧主链“只跑一次优化器”的调用次数写死了，而 PR-7c 正式接入候选多方案后会多次试跑。该文件属于用户并行修复的 PR-6 范围，本阶段未修改。
