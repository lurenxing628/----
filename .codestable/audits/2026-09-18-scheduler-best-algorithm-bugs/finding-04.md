---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: bug-04
nature: bug
severity: P2
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 04：batch_order 模式下 GRASP/IG 起点轮换派工规则并上报 adopted_dispatch_rule=cr/atc

## 速答

`optimizer_grasp_ig_specs._dispatch_rules` 不看派工模式，按 slack/cr/atc 轮换起点并把规则写进候选；batch_order 解码根本不消费派工规则，4 个场景实测换规则解码哈希完全相同，但公开汇总却同时给出 `adopted_dispatch_rule=cr` 与 `configured_dispatch_rule=slack`。

## 关键证据

- `core/services/scheduler/run/optimizer_grasp_ig_specs.py:22-28,81,93`；`optimizer_grasp_ig_candidates.py:95-96`；`schedule_optimizer.py:170` → `outcome.dispatch_rule`；`schedule_candidate_runner.py:463`；`schedule_candidate_summary.py:132-142`。
- `_spec_decision_fingerprint`（`:305-314`）含规则，同序不同规则不去重。
- 实测（S4，`/tmp/aps-audit-20260918/S4/probe_rule_irrelevance.py`）：batch_order 下 slack/cr/atc/atc:k=16 解码哈希完全相同；步进时钟基线 shift_pool/frozen 上报 `adopted cr`，tiny 上报 `adopted atc`。

## 影响

错报采用规则；同序候选按规则重复解码浪费起点。

## 修复方向

派工模式不是 sgs 时起点只用配置规则；`adopted_dispatch_rule` 在 batch_order 下等于配置值。

## 处理结果

2026-09-18 同日落地：`optimizer_grasp_ig_specs._dispatch_rules` 增加 `dispatch_mode`，非 sgs 只带配置规则；`schedule_optimizer._adopted_dispatch_rule` 在采用模式不是 sgs 时一律等于配置规则。合同测试 `tests/algorithm/test_optimizer_graph_rule_scope_contract.py`。决定见 `.codestable/compound/2026-09-18-decision-optimizer-budget-and-rule-pool-corrections.md`。
