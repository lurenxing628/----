---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: bug-05
nature: bug
severity: P2
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 05：交期构造起点被采用时 parent_order_score / parent_order_consistent 写的是起点的值

## 速答

`_start.py` 里 `entry` 来自 `_due_date_reference` 时仍写入 `parent_order_*`，成功采用交期起点反而报 `parent_order_consistent=False`；另外解池首选条目重解码不可行时直接 `parent_order_rejected` 结束 IG，不尝试其他池条目。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy_start.py:26-32`、`:28-30`。
- 实测：SMTWT-40 真实时钟 4 个实例开起点全部 `parent_order_consistent=false` 且 `parent_order_score == initial_seed.validated_score`；关起点全部 `true`。

## 影响

报告误导；解池有多个条目时首条不可行就放弃整个 IG。

## 修复方向

分开字段或只对父顺序解码写这两个字段；首选条目不可行时有界地尝试其余池条目。

## 处理结果

2026-09-18 同日落地：`optimizer_graph_ready_iterated_greedy_start.py` 种子只在首次尝试；种子成为参考时 `reference_basis=due_date_seed` 且父字段留空；首条目失败按分数尝试其余池条目并计 `pool.start_captures_failed`；`parent_order_consistent` 改为按输出逐位判定。合同测试 `tests/algorithm/test_graph_ready_ig_reference_contract.py`。
