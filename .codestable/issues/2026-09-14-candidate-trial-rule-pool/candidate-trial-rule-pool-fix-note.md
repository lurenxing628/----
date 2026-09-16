---
doc_type: issue-fix-note
issue: 2026-09-14-candidate-trial-rule-pool
status: fixed
source: .codestable/audits/2026-09-14-scheduler-algorithm-optimization-space/finding-07.md
decision: .codestable/compound/2026-09-14-decision-candidate-comparability-lock-vs-rule-pool.md
summary: 候选试跑不再把 SGS 派工规则池收窄成配置单值；多起点恢复三条规则起点、换规则邻域真实搜索；候选方案如实上报采用的规则。
---

# 候选试跑收窄派工规则池，多起点退化为单起点、换规则邻域必空转

## 问题事实

- 触发路径：图分析开启（生产默认）→ `run_candidate_comparison` → 每个候选注入 `_CandidateTrialConfigService`（`core/services/scheduler/run/schedule_candidate_runner.py`），`VALID_DISPATCH_RULES` 被改成 `(配置规则,)`。
- 后果一：`_dispatch_rules_for_mode`（`optimizer_multi_start.py`）按清单枚举 sgs 起点，只剩配置的一条规则，多起点实际为单起点。
- 后果二：`sgs_dispatch_rule_move`（`optimizer_neighborhood_moves.py`）从清单挑不出与当前不同的规则，返回 `sgs_dispatch_rule_unavailable` 空转；`_resolve_sgs_dispatch_rules` 只在清单为空时回落默认三规则，单值清单回落不了。实测 200 次迭代全部 noop 仍消耗预算。
- 为什么此前被当成"已修"：`tests/_scripts_e2e/benchmark_smtwt_localsearch.py` 直接调 `_run_local_search` 且不传 `valid_dispatch_rules`，绕过了候选对比。

## 根因

PR7b 用同一把锁同时表达了两件事：候选之间的可比性（只差图权重）与候选内部允许搜索的规则池。后者本不该被锁。

## 改动

- `core/services/scheduler/run/schedule_candidate_runner.py`：`_CandidateTrialConfigService` 只锁排序策略、派工模式、目标函数、算法模式，不再定义 `VALID_DISPATCH_RULES`（经 `__getattr__` 落到基础配置服务的注册表规则池）；`CandidatePlan` 新增 `adopted_dispatch_rule`，由优化结果填入。
- `core/services/scheduler/run/optimizer_outcome.py`、`schedule_optimizer.py`：`OptimizationOutcome` 新增 `dispatch_mode` / `dispatch_rule`（最终采用方案的值，回落到配置值），基线结果同样填写。
- `core/services/scheduler/run/schedule_candidate_summary.py`：公开汇总加 `adopted_dispatch_rule`，与配置不同时再加 `configured_dispatch_rule`；持久化列 `dispatch_rule` 保持配置值不变。
- 合同：`tests/candidate/test_scheduler_candidate_runner_contract.py` 的锁定测试改为"锁策略与模式、保留规则池"；新增 `tests/candidate/test_scheduler_candidate_rule_pool_end_to_end.py`，用真实优化器 + 步进时钟走 `run_candidate_comparison`，断言基线 3 个起点全部解码、换规则邻域有效次数大于 0、采用规则如实上报（shift_pool 基线采用 atc 而配置为 slack）、图档仍锁 sgs。

## 验证

- `tests/candidate`：171 passed（改锁后、加新测试前）；新测试 3 passed。
- 广域回归 `tests/algorithm tests/scheduler_graph tests/candidate tests/workbench/test_run_compute_contracts.py tests/workbench/test_run_progress_ledger.py`：2949 passed。
- 真实入口实测（步进时钟，`shift_pool`）：基线 `configured_candidates=3, decoded=3`，`sgs_dispatch_rule` 邻域 174 次尝试 10 次有效（此前全部空转）；`frozen_ready_external` 基线 95 次尝试 95 次有效。
- 端到端 20 例（改动前后各跑一遍 `build_end_to_end_matrix`，快照在 `/tmp/aps-a1-20260914/e2e-before.json`、`e2e-after.json`）：选中方案 1 例更好（shift_pool/min_tardiness 1447 → 1423.5）、19 例相同、0 例更差；基线候选 tiny_improving 逾期 2 → 1、shift_pool 总拖期 3136.5 → 2937.0。
- 未跑全量质量门禁；工作区含他人未提交改动。

## 剩余风险与后续

- 这次是有意改行为，不能再拿哈希相同做证据；改进阶段按时间预算搜索，不同机器上迭代数不同。
- 只有三条规则可换且 atc 参数写死（finding-08），换规则邻域的有效改动比例低（shift_pool 174 次里 10 次有效，其余是重复决策）。下一步：把 atc 参数变成可搜旋钮，再做迭代贪心。
- 工作台候选目录只显示名称、状态、任务数与指标，前后端都不展示派工规则，所以目前没有会误导的界面；若后续在界面展示规则，必须用 `adopted_dispatch_rule`，配置值只作对照，并按 `PlanContract.js` 的精确键合同与文案词表补齐。
