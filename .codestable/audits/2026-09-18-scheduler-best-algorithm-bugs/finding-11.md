---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: quality-11
nature: quality
severity: P2
confidence: high
suggested_action: cs-decide
status: fixed
---

# Finding 11：slack/CR 规则下批次优先级基本不起作用

## 速答

派工键为 `(primary, changeover, pr_rank, time_left, batch_order, seq, op_id)`，只有 ATC 分支用到权重 `w`；slack / CR 下 critical 批次只在主键浮点完全相等、且换型罚分也相等时才靠 `pr_rank` 领先。目标 `min_overdue` 第二键是加权拖期，解码器却不看权重。

## 关键证据

- `core/algorithm_contracts/dispatch_rules.py:173,179-187`；`core/models/objective.py:19-25`；`core/algorithm_contracts/priority_constants.py:12`（critical 3 / urgent 2 / normal 1）。

## 影响

用户标 critical 得不到派工优先（图档下图键在前，同样忽略）。

## 修复方向

主键按权重做保序变换：`slack_w >= 0` 时除以 w、`< 0` 时乘以 w（两个方向都是越重要越紧急），CR 同理按符号处理；normal 批次键值不变。裁决记入 `.codestable/compound/2026-09-18-decision-dispatch-rule-working-hour-slack-and-priority-weight.md`。

## 处理结果

2026-09-18 同日落地：`dispatch_rules._weighted_urgency` 余量 ≥ 0 除以权重、< 0 乘以权重，slack 与 CR 主键按此缩放，ATC 不叠加，`pr_rank` 平手键保留；普通优先级键值逐位不变。`tests/algorithm/test_resource_demand_total_blocking.py` 的 shift_pool 黄金指纹逐项开关归因后确认只由本项造成，已按新语义更新并写明归因。
