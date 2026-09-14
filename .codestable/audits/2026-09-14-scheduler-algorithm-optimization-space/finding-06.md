---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: performance-06
nature: performance
severity: P0
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 06：外层"1 基线 + N 图权重档"各起独立内层优化器，5 档输出重复，预算等分使内层搜索零机会

## 速答

工作台默认 `graph_candidate_weight_count=5` → 6 个外层候选，每个都完整跑一遍 `optimize_schedule`；5 个图档只是把外层图权重按 0.5～1.5 倍缩放，而内层 GraphReady 组合（9 个 v1 + 20 个 v2 profile + 精英修补）用的是与外层权重无关的绝对权重表，所以 5 档解出来的最优几乎总是同一张表。5 秒总预算六等分后每候选只剩 0.8～1.25 秒，千级工序连一次解码都不够，被跳过的还常常是用户自己配置的 1.0× 档。

## 关键证据

- `core/services/scheduler/run/schedule_candidate_specs.py:14-18,59-88` —— `_WEIGHT_MULTIPLIERS` 0.5/1.0/1.5…，每档只改 `graph_critical_weight/impact/downstream`。
- `core/services/scheduler/run/optimizer_graph_ready_profiles.py:37-47,194-235` —— v1 九组与 v2 组合使用绝对权重，`candidate_policy=weight_grid/objective_aware_portfolio`，与外层 cfg 权重无关；`optimizer_graph_ready_candidates.py:158-179` profile 整体覆盖 `graph_priority_key_by_op_id`。
- `core/services/scheduler/run/schedule_candidate_runner.py:136-143,193-219` + `optimizer_search_budget.py:48-61` —— 严格串行、等分预算；`schedule_optimizer.py:151-175` 内层 deadline = min(slice, cfg)。
- 主代理端到端矩阵实测：20/20 用例里 graph_w1/w2/w3 分数向量完全相同；5 档复验 `frozen_ready_external` 5/5 相同，`shift_pool` w1=w2、w3/w4/w5 只因 1s 预算截断不同而略差。
- S3 证据 zip `native-new-1000-improve5-resume2/result.json`：图候选 `assigned_time_budget_ms=1225`，`runtime_ms=3595`，`decoder_invocations=1`，图阶段 `time_budget` 跳过，修补 `skipped_no_elite`。
- 记录：`2026-09-12-quality-efficiency.md:61`（8.87s，计划 4 / 完成 2 / 跳过 2）、`algorithm-capability-efficiency-acceptance.md:97`（新代码 5.10s 仍 2/2）。

## 影响

默认配置下 improve 的全部搜索机制在 ≥1000 工序时一次都跑不到；5/6 的总预算花在重复枚举同一组合上；用户看到 5 个"不同方案"其实是同一张表。

## 修复方向

在一次 `run_candidate_comparison` 内让图档共享内层解码结果（按完整决策键做跨候选 memo，命中按 `reused_from_sibling` 如实入账，不计入 `evaluated_candidates`），并按候选族分配预算：第一个图档拿到族内合并预算减去其余档各一次解码的预留，其余档只需解自己的基线权重。更彻底的方案是把 N 档收成一次图优化里的 N 个额外 v1 profile，但会改变工作台候选列表合同，留待产品裁决。

## 建议动作

`cs-refactor`（共享解码结果 + 预算按族）；候选列表合同变更另走 `cs-feat`。

## 处理结果

2026-09-14 同日落地：`schedule_candidate_dedup.py` 按“去权重配置 + 图上下文 + 优先键弱序”指纹复用兄弟方案并按真正需要搜索的候选数分预算；“把 N 档收成内层 profile”的合同变更仍留待产品裁决。
