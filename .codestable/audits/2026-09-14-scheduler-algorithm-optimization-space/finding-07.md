---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: quality-07
nature: quality
severity: P1
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 07：候选对比 allowlist 收窄使多起点退化为 1 起点、SGS 规则邻域必 noop

## 速答

工作台候选对比给每个候选注入 `_CandidateTrialConfigService`，把 `VALID_STRATEGIES / VALID_DISPATCH_MODES / VALID_DISPATCH_RULES` 收窄成"当前值"单元素，于是多起点只剩 1 个起点，`sgs_dispatch_rule` 邻域的候选集为空，200 次迭代全部 noop 仍消耗预算。2026-06-29 审计里"SGS 局搜已修"的实测绕过了这条收窄。

## 关键证据

- `core/services/scheduler/run/schedule_candidate_runner.py:104-111,358` —— trial cfg_svc 单值 allowlist。
- `core/services/scheduler/run/optimizer_config.py:47-56,101-109` —— `strategy_keys()/dispatch_modes()` 与 allowlist 过滤。
- `core/services/scheduler/run/optimizer_local_search.py:309,415-426`、`optimizer_neighborhood_moves.py:240-245` —— 只有 allowlist 为空才回落默认 3 规则；候选空 → noop。
- `tests/candidate/test_scheduler_candidate_runner_contract.py:383` —— PR7b（git `d2ee6461`，2026-05-19）合同锁定当前值。
- 实测（S2）：`trial valid_dispatch_rules=('slack',)` → `sgs_dispatch_rule_move noop: True reason: sgs_dispatch_rule_unavailable`；SMTWT wt40[0] `iterations=200 decodes=4 noop 200`（改进 0），`rules=None` 时 6→4。
- `tests/_scripts_e2e/benchmark_smtwt_localsearch.py:76-89` —— 直接调 `_run_local_search` 不传 `valid_dispatch_rules`，绕过收窄。

## 影响

默认路径 baseline 候选从不尝试 SGS/ATC 起点（SMTWT 上 ATC 是 250/250 最佳规则）；用户选 dispatch_mode=sgs 时局搜空转。

## 修复方向

把"候选间锁定 sort/dispatch 以保证可比"与"候选内搜索允许的规则池"拆成两个合同（trial cfg_svc 只锁 objective/algo_mode，或给 `run_local_search`/`_run_multi_start` 单独传搜索规则池）；先确认 PR7b 锁定的产品意图（是否允许候选实际采用与用户配置不同的派工模式并如实报告）。补一条走 `run_candidate_comparison` 的真实端到端断言。

## 建议动作

`cs-issue`，需要先裁决产品意图再改合同。

## 处理结果

2026-09-14 用户裁决后落地（决定见 `.codestable/compound/2026-09-14-decision-candidate-comparability-lock-vs-rule-pool.md`，修复见 `.codestable/issues/2026-09-14-candidate-trial-rule-pool/`）：把 PR7b 的合同拆成"候选间锁排序策略、派工模式、目标函数、算法模式"与"候选内规则池不收窄"两条；`_CandidateTrialConfigService` 不再改写 `VALID_DISPATCH_RULES`，派工模式保持锁定（图档强制 sgs）。优化结果与候选方案新增"采用的派工规则"，公开汇总里与配置不同时同时给出 `adopted_dispatch_rule` 与 `configured_dispatch_rule`。真实候选对比入口的实测：shift_pool 基线候选 3 个起点全部解码、换规则邻域 174 次尝试 10 次有效（此前 200 次全部空转），基线采用 atc；端到端 20 例选中方案 1 例更好、19 例相同、0 例更差，基线候选在 tiny_improving 与 shift_pool 上明显变好。合同测试改为 `tests/candidate/test_scheduler_candidate_rule_pool_end_to_end.py` 与运行器合同里的"锁策略与模式、保留规则池"。
