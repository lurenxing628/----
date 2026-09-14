---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: quality-07
nature: quality
severity: P1
confidence: high
suggested_action: cs-issue
status: open
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
