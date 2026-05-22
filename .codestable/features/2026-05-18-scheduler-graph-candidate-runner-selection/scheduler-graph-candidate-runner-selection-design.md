---
doc_type: feature-design
feature: 2026-05-18-scheduler-graph-candidate-runner-selection
requirement:
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-candidate-runner-selection
status: approved
summary: PR-7b 在内存里生成候选、串行试跑、自动择优并计算关键链健康，不接数据库持久化和页面切换
tags: [scheduler, graph, networkx, candidate, selection]
---

# scheduler-graph-candidate-runner-selection 设计方案

## 1. 目标

本 feature 执行 roadmap `networkx-scheduler-graph-introduction` 的 PR-7b：`scheduler-graph-candidate-runner-selection`。

大白话说，PR-7a 已经把候选方案的表、仓库和统一查询底座建好了。PR-7b 先不把候选写进数据库，也不改页面。它只回答一个问题：同一份排产输入下，原算法和多档关键链方案在内存里各跑一遍，系统怎么稳定生成这些候选、怎么按总时间预算串行执行、怎么选出采用方案、怎么判断关键链方案是不是真的更健康。

本阶段仍然优先简洁和可见错误：候选失败要有状态和原因；输入错误、配置错误、数据范围错误直接终止；不把异常吞成空成功，不为了“看起来稳”加一堆宽泛兜底。

## 2. 范围

- 新增 `core/services/scheduler/run/schedule_candidate_specs.py`：
  - 定义 `CandidateRunSpec`。
  - 稳定生成 `baseline + N 档 critical_chain`，默认 N=5，支持 3 / 5 / 7。
  - 候选 key 固定为 `baseline`、`graph_w1_of_5` 这类可复现格式。
- 新增 `core/services/scheduler/run/schedule_candidate_health.py`：
  - 纯函数计算关键链健康状态。
  - 输出 `better / same / worse / unavailable` 和小时口径小字段。
- 新增 `core/services/scheduler/run/schedule_candidate_selection.py`：
  - 定义候选选择用值对象。
  - 实现 `score_only` 和 `balanced` 选择策略。
  - raw score 直接复用 `OptimizationOutcome.best_score`，tuple 越小越好。
- 新增 `core/services/scheduler/run/schedule_candidate_runner.py`：
  - 定义 `CandidatePlan` 和 `CandidateComparisonOutcome`。
  - baseline 永远先跑。
  - 使用整次候选比较总 deadline，不给每个候选重新发一份完整预算。
  - 不走 `orchestrate_schedule_run()`，避免分配正式 version 或写库。
  - 每个候选先用临时 cfg 构造候选级 `ScheduleRunInput`，调用 `prepare_schedule_graph_for_dispatch()` 取得图 ready 上下文和派工覆盖值，再把它们传给 `optimize_schedule()`。
  - 用临时 cfg 副本跑候选，不写 `ScheduleConfig`。
- 新增四份合同测试：
  - `tests/regression_scheduler_candidate_generation_contract.py`
  - `tests/regression_scheduler_candidate_runner_contract.py`
  - `tests/regression_scheduler_graph_auto_selection_contract.py`
  - `tests/regression_scheduler_candidate_health_contract.py`

## 3. 明确不做

- 不改 `Schedule` / `ScheduleHistory` / Candidate 表的持久化主链；那是 PR-7c。
- 不分配正式 version。
- 不调用 `persist_schedule()`。
- 不写 `ScheduleCandidate`、`ScheduleCandidateRows`、`ScheduleCandidateSelection`。
- 不改 `/scheduler/run` route。
- 不接甘特图、周计划、资源派工、报表或导出里的 `plan_role`；那是 PR-7d。
- 不新增配置字段、配置页、旧 preset 补字段、清理策略或性能守卫；那是 PR-7e。
- 不改 PR-6 图分析相关文件，尤其不碰用户正在修的 `graph/metrics.py` 和图分析回归测试。
- 不引入 NetworkX 顶层 import、新依赖、新数据库、后台续跑、多进程或 Python 3.9+ 语法。

## 4. 候选生成

- baseline：
  - `candidate_key = "baseline"`
  - `kind = "baseline"`
  - `graph_enabled = False`
  - 三类图权重全部为 0
- 关键链候选：
  - `candidate_key = "graph_w{level}_of_{count}"`
  - `kind = "critical_chain"`
  - `graph_enabled = True`
  - `weight_count` 只允许 3 / 5 / 7
  - 倍数固定：
    - 3 档：0.50 / 1.00 / 1.50
    - 5 档：0.50 / 0.75 / 1.00 / 1.25 / 1.50
    - 7 档：0.40 / 0.60 / 0.80 / 1.00 / 1.20 / 1.40 / 1.60
  - `critical_weight = round(base_critical_weight * multiplier)`
  - `impact_weight = round(base_impact_weight * multiplier)`
  - `downstream_weight = max(1, round(1 * multiplier))`

## 5. 候选运行

运行规则：

- baseline 永远先跑。
- 每个候选启动前检查全局 deadline。
- deadline 已到，不再启动新的候选，后续候选标为 `skipped`。
- 已经启动的候选第一版允许自然完成，不强杀。
- 单个关键链候选失败时，记录 `failed + failure_reason`，继续后续候选。
- 输入错误、配置错误、数据范围错误要直接抛出，终止整次排产。
- 如果所有候选都没有 completed，选择阶段必须报错，不生成伪成功。

临时 cfg：

- baseline 用临时 cfg 关闭图增强，并把 `algo_mode` 设为 `greedy`，保证不进入 improve 多起点搜索。
- 关键链候选用临时 cfg 设定 `graph_analysis_mode="on"`、当前档位权重，并把 `algo_mode` 设为 `greedy`。
- 候选 runner 进入 `optimize_schedule()` 前，必须用内存态 trial 配置或等价 helper，把当前 `sort_strategy`、`dispatch_mode`、`dispatch_rule` 都收窄为单值；不能只依赖 `algo_mode="greedy"`。
- 不原地修改 `schedule_input.cfg`。
- 不调用任何写配置的方法。

图上下文准备：

- runner 不调用正式总编排，所以不会分配正式 version，也不会写 `Schedule`、`ScheduleHistory` 或候选表。
- baseline 候选仍然走同一个准备入口，但临时 cfg 已关闭图增强，得到的图上下文应为空或未启用。
- 关键链候选必须先用候选级 `ScheduleRunInput` 调用 `prepare_schedule_graph_for_dispatch()`。
- `prepare_schedule_graph_for_dispatch()` 返回的 `graph_ready_context` 和 `graph_dispatch_mode_override` 必须原样传给 `optimize_schedule()`。
- `algo_mode="greedy"` 只用来禁止 improve 多起点搜索；排序策略、派工方式、派工规则三个候选范围必须另外显式锁住，不能顺手扩展组合搜索。
- 如果图准备阶段发现输入、配置或数据范围错误，直接抛出并终止整次候选比较；如果是单个关键链候选内部计算失败，才记录为该候选 `failed` 并继续后续候选。

## 6. 自动择优

共同规则：

- 只在 `status == "completed"` 的候选中选择。
- raw score 直接取 `CandidatePlan.score` / `OptimizationOutcome.best_score`。
- raw score 越小越好。
- score 相同时，baseline 优先，然后按候选生成顺序稳定排序。

`score_only`：

- 直接采用 raw score 最小的候选。
- 不看关键链健康，不允许健康指标反超 raw score。

`balanced`：

- 先找到 raw score 最好的候选。
- 再找完成的关键链候选里健康最好的候选。
- 只有同时满足下面条件，关键链候选才允许反超 raw score 最佳：
  - 关键链候选 completed。
  - baseline_best completed。
  - `critical_best.failed_ops <= raw_score_best.failed_ops`。
  - `critical_best.overdue_count <= raw_score_best.overdue_count + graph_overdue_tolerance_count`。
  - `critical_best.total_tardiness_hours <= raw_score_best.total_tardiness_hours * (1 + graph_tardiness_tolerance_ratio)`。
  - `critical_best.health.state == "better"`。

## 7. 关键链健康

- 纯函数，不读数据库，不写数据库，不拿 NetworkX 图对象。
- 输入使用普通 `ScheduleResult`、graph public/diagnostics 小字段或测试构造的小 metrics。
- 输出只使用小时字段：
  - `critical_chain_finish_hours_delta`
  - `critical_chain_wait_hours_delta`
  - `top_impact_ops_avg_start_hours_delta`
  - `critical_chain_slack_hours_delta`
- 状态：
  - `better`
  - `same`
  - `worse`
  - `unavailable`
- `unavailable` 不能作为 balanced 反超依据。

## 8. 验收场景

- 默认生成 baseline + 5 档关键链候选。
- 支持 3 / 5 / 7 档，其他档数直接报错。
- candidate key 稳定，不使用随机数。
- baseline 第一个执行。
- 关键链候选在调用优化器前确实拿到图 ready 上下文。
- 候选 trial 模式不会把试跑扩成排序策略、派工模式或派工规则组合搜索，即使 cfg_svc 暴露多个可选值也只能跑当前三项组合。
- 全局时间预算到期后不启动新候选，后续候选不伪装 completed。
- 单个关键链候选失败不影响后续候选继续。
- 全部候选都失败时选择阶段直接报错。
- `score_only` 只看 raw score。
- `balanced` 只有关键链健康更好且超期/拖期/失败没有明显变差时才允许反超。
- 健康指标不足时是 `unavailable`，不能反超。
- PR-7b 不新增落库、页面、配置和 PR-6 图分析改动。
