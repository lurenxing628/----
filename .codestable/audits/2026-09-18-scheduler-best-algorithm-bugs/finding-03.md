---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: bug-03
nature: bug
severity: P2
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 03：IG 启动时"预计父方案解码放不下"被报成 time_budget / skipped_by_budget

## 速答

IG 启动用 `best["runtime_ms"]` 估算父方案解码成本，放不下时 `raise _BudgetExhausted("time_budget")`，报告与公开文案变成"预算不足，未执行"。这违反 2026-09-15 决定第 5 项"不能把估算不足伪装成已经到达实际截止"。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy_run.py:102-104`；同款 `optimizer_graph_ready_iterated_greedy.py:152-155`。
- 复现（`/tmp/aps-audit-20260918/S3/probe_start_mislabel.py`）：剩余 3.0s、`time_budget_ms=3000`、`decodes=0`、`budget_pruned_before_decode=0`、无 `decode_admission`，报告仍是 `time_budget`。

## 影响

用户看到"预算不足"却查不到是估算准入拒绝，与 `_require_budget` / Large `_before_decode` 已有的 `decode_would_overrun` 口径不一致。

## 修复方向

改报 `decode_would_overrun` 并写 `decode_admission{estimated_decode_ms, remaining_ms}`，公开文案映射同步。

## 处理结果

2026-09-18 同日落地：父方案放不下报 `decode_would_overrun` 并写 `decode_admission{policy, estimated_decode_ms, remaining_ms}`（`optimizer_graph_ready_iterated_greedy.py`、`_run.py`），公开文案映射在 `_contract.py`；合同测试锁住"0 次解码时不得报 time_budget"（`tests/algorithm/test_graph_ready_ig_reference_contract.py`）。
