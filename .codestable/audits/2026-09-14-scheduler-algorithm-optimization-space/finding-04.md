---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: performance-04
nature: performance
severity: P1
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 04：自动派工在同一状态下重复估算——胜出对复算 + 正式放置整套重跑

## 速答

`_choose_best_pair` 已经对胜出 (机,人) 对做过估算，评分层又复算一次；被选中的工序正式放置时 `_resolve_internal_resources` 再把全部 P 对跑一遍并再估算一次，中间没有任何状态变化。

## 关键证据

- `core/algorithms/greedy/auto_assign.py:289-311` —— 探测阶段已对胜出对估算。
- `core/algorithms/greedy/dispatch/sgs_scoring.py:243-255` —— `_estimate_scoring_slot` 对胜出对再估算一次。
- `core/algorithms/greedy/internal_operation.py:128-142,206-212` —— 正式放置再跑 `auto_assign_resources` 全部 P 对 + `_estimate_internal`。
- `core/algorithms/greedy/dispatch/sgs.py:222-254` —— 评分后立即放置，期间无状态变更。
- 实测（S1）：auto-1000 `_estimate_scoring_slot` 10.3s（11%）+ 正式放置约 1%；大资源池基准案例 1 的 601 次估算里 300 次是正式放置的重复。

## 影响

自动派工路径 12～16% 纯重复算力。

## 修复方向

`AutoAssignAttempt` 携带胜出估算交给评分层；把该步胜者的 (机,人,估算) 通过现有 reuse scope 交接给正式放置（现有 `selected_estimate` 只覆盖证书合格的固定候选）。需保持 `probe_only` 不计数、不写占用的契约（`auto_assign.py:103`）。

## 建议动作

`cs-refactor`，确定性解码下同状态同输入必同输出，等价性直接成立。

## 处理结果

2026-09-14 同日落地：评分估算与胜出机人对经 `sgs_handoff_scope` 交接正式放置，正式放置不再重跑机人对搜索。
