---
doc_type: feature-design
feature: 2026-05-18-scheduler-graph-candidate-transaction-persistence
requirement:
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-candidate-transaction-persistence
status: approved
summary: PR-7c 把 PR-7b 的内存候选比较接入正式排产主链，并让 Schedule / ScheduleHistory / Candidate 同事务落库
tags: [scheduler, graph, networkx, candidate, persistence]
---

# scheduler-graph-candidate-transaction-persistence 设计方案

## 1. 目标

本 feature 执行 roadmap `networkx-scheduler-graph-introduction` 的 PR-7c：`scheduler-graph-candidate-transaction-persistence`。

大白话说，PR-7a 已经建好了候选方案的表和查询底座，PR-7b 已经能在内存里生成、运行并自动选择候选方案。PR-7c 要做的是把这个结果接到正式排产主链：最终采用的方案写进 `Schedule` 和 `ScheduleHistory`，所有候选写摘要，代表候选写明细，三个角色写映射，而且这些正式数据必须在同一个数据库事务里写完。

本阶段不走 degraded 方案。候选持久化失败时，整次排产失败并回滚，不允许出现“正式排产成功了，但候选表缺失”的历史。

## 2. 范围

- 补强 `CandidatePlan`：
  - 保留优化器 outcome 里 summary 需要的字段：`used_strategy`、`used_params`、`best_order`、`attempts`、`improvement_trace`、`algo_mode`、`objective_name`、`algo_stats`、`time_budget_seconds`。
  - 这些字段只用于 adopted summary 和候选摘要，不用于页面切换。
- 补强 `CandidateComparisonOutcome`：
  - 返回本次候选比较实际使用的 `run_time_budget_seconds`。
  - summary / OperationLogs 只能从 outcome 读取这个值，不能从配置默认值反推，避免后续 PR-7e 接临时预算后口径漂移。
- 新增 `core/services/scheduler/run/schedule_candidate_summary.py`：
  - 把 `CandidateComparisonOutcome` 投影成 `result_summary.algo.candidate_comparison` 小摘要。
  - 明确禁止 `results`、candidate rows、nodes、edges、raw graph、完整 diagnostics 进入 summary。
- 改造 `core/services/scheduler/summary/summary_size_guard.py`：
  - 常规摘要超 512KB 后，即使进入最小摘要，也必须保留 `algo.candidate_comparison` 的极小字段。
  - 最小摘要只保留数量、预算、采用 key、代表 key、selection policy / reason code，不保留候选列表或明细。
- 新增 `core/services/scheduler/run/schedule_candidate_persistence.py`：
  - 把所有候选写入 `ScheduleCandidate` 摘要。
  - 只把非 adopted 的 `baseline_best / critical_best` 代表方案写入 `ScheduleCandidateRows`。
  - 写入 `ScheduleCandidateSelection` 的 `adopted / baseline_best / critical_best` 角色映射。
- 改造 `core/services/scheduler/run/schedule_persistence.py`：
  - 把现有 `persist_schedule()` 拆出事务内核心函数。
  - 新增 `persist_schedule_run_with_candidates()`，在一个事务里写 `Schedule`、状态更新、`ScheduleHistory`、候选摘要、候选代表明细和角色映射。
  - `OperationLogs` 仍然在事务后写，但只写极小算法摘要。
- 改造 `core/services/scheduler/run/schedule_orchestrator.py`：
  - 用 `run_candidate_comparison()` 运行候选。
  - 用 `selection.selected_plan` 作为 adopted。
  - adopted payload 校验通过后，再分配正式 version。
  - summary 使用 adopted 的优化器字段，并接入 candidate comparison 小摘要。
- 改造 `core/services/scheduler/schedule_service.py`：
  - 正式持久化改走 `persist_schedule_run_with_candidates()`。
- 新增两份合同测试：
  - `tests/regression_scheduler_candidate_persistence_contract.py`
  - `tests/regression_scheduler_candidate_summary_contract.py`

## 3. 明确不做

- 不改页面、模板、JS、导出、报表或 URL 参数；这些属于 PR-7d。
- 不新增配置页字段、候选档数配置、临时时间上限 UI、清理策略或性能守卫；这些属于 PR-7e。
- 不改 PR-6 图指标文件，尤其不碰用户正在修的 `core/services/scheduler/graph/metrics.py`、`tests/regression_scheduler_graph_on_mode_contract.py`、`tests/scheduler_graph/test_metrics_impact.py`。
- 不把所有候选明细都写入 `ScheduleCandidateRows`。
- 不把候选完整结果塞进 `ScheduleHistory.result_summary` 或 `OperationLogs.detail`。
- 不在候选运行阶段写数据库。

## 4. 主链顺序

PR-7c 的主链顺序固定为：

```text
collect_schedule_run_input()
run_candidate_comparison()              # 只在内存里跑，不写 DB
adopted = selection.selected_plan
build_validated_schedule_payload(adopted.results)
allocate_next_version()                 # adopted payload 校验通过后，只分配一次正式 version
build_result_summary(adopted + candidate_comparison 小摘要)
persist_schedule_run_with_candidates()  # Schedule + ScheduleHistory + Candidate 同事务
OperationLogs 极小摘要                 # 事务后写
```

候选 runner 里的 `optimizer_seed_version` 仍然只是内存试跑标签，不是正式落库 version。

## 5. 同事务写入

同一个事务里按下面顺序写：

1. 写 adopted `Schedule` rows。
2. `simulate=False` 时更新 `BatchOperations` / `Batches` 状态；`simulate=True` 不更新。
3. 写 `ScheduleHistory`。
4. 写所有 `ScheduleCandidate` 摘要，并拿到 `candidate_id` map。
5. 对非 adopted 的 `baseline_best / critical_best` 写 `ScheduleCandidateRows`。
6. 写 `ScheduleCandidateSelection` 三个角色。

任何一步失败，整个事务回滚。`OperationLogs` 不参与这个事务，仍然事务后写。

## 6. 候选落库规则

- `ScheduleCandidate`：
  - 所有候选都写摘要，包括 `completed / failed / skipped`。
  - `status` 只写候选运行状态，不写 adopted。
  - `selection_reason` 只给最终 adopted 候选写选择原因。
  - `detail_saved=yes` 只表示这个候选在 `ScheduleCandidateRows` 里真的写了代表明细。
- `ScheduleCandidateRows`：
  - adopted 不写，因为正式采用方案已经在 `Schedule`。
  - `baseline_best` 如果不是 adopted，写代表明细。
  - `critical_best` 如果不是 adopted，写代表明细。
  - failed / skipped 不写明细。
- `ScheduleCandidateSelection`：
  - adopted 永远写，`source_table="schedule"`。
  - baseline_best 有 key 才写；等于 adopted 时 `source_table="schedule"`，否则 `source_table="candidate_rows"`。
  - critical_best 有 key 才写；等于 adopted 时 `source_table="schedule"`，否则 `source_table="candidate_rows"`。

## 7. Summary 和 OperationLogs

`result_summary.algo.candidate_comparison` 只放小摘要：

- planned / completed / failed / skipped 数量。
- time_budget_reached。
- run_time_budget_seconds，来源必须是 `CandidateComparisonOutcome.run_time_budget_seconds`。
- adopted / raw_score_best / baseline_best / critical_best candidate key。
- selection_policy / selection_reason_code。
- 候选小列表只允许 key、label、kind、status、score、核心 metrics、health 小字段、detail_saved、roles。

禁止进入 `result_summary`：

- `ScheduleResult` rows。
- candidate rows 明细。
- nodes / edges / raw graph。
- 完整 graph diagnostics。
- 完整 attempts / improvement_trace。

`summary_size_guard` 的最小摘要也必须保留 `algo.candidate_comparison` 极小字段：

- planned / completed / failed / skipped 数量。
- time_budget_reached。
- run_time_budget_seconds。
- adopted / raw_score_best / baseline_best / critical_best candidate key。
- selection_policy / selection_reason_code。

最小摘要里禁止保留候选小列表、候选明细、完整图诊断和完整 optimizer outcome。

`OperationLogs.detail.algo.candidate_comparison` 更小，只保留：

- enabled。
- planned_candidate_count。
- completed_candidate_count。
- time_budget_reached。
- run_time_budget_seconds。
- adopted_candidate_key。
- selection_policy。
- selection_reason_code。

## 8. 验收场景

- adopted 只写 `Schedule`。
- 所有候选都写 `ScheduleCandidate` 摘要。
- 非 adopted 的 baseline_best / critical_best 代表方案写 `ScheduleCandidateRows`。
- 三个 role selection 正确，`source_table` 只允许 `schedule / candidate_rows`。
- 候选持久化失败时 `Schedule / ScheduleHistory / Candidate` 全部回滚，且不写成功 OperationLogs。
- result_summary 保留 candidate comparison 小摘要，但不包含完整 rows / graph diagnostics。
- result_summary 被 `summary_size_guard` 裁到最小时，也保留 candidate comparison 极小摘要。
- OperationLogs 只写极小候选摘要，不包含 candidates 列表、rows、nodes、edges、raw、node_metrics。
- PR-7c 不改页面、配置、PR-6 图指标文件。
