---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: quality-10
nature: quality
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 10：精英修补批次邻域的基座不是精英本身，恒等决策解出不同排程

## 速答

修补的批次类邻域（adjacent_swap / single_insert / tardy_boundary_move）把优先键整体替换成 `(batch_rank,)`，批序取父候选解码后"按首个开工时刻"的批次顺序；而父候选是用逐工序 v2 特征键解码的。结果"零移动"的恒等决策解出的排程和父候选不同，邻域实际是"另一个基点 + 一步"，与 roadmap"修复接近好解但差一两步的排序"的意图不符。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_repair_neighbors.py:74-85` —— `repair_priority_context` 整体替换优先键为 `(batch_rank,)`。
- `core/services/scheduler/run/optimizer_graph_ready_candidate_payload.py:52-69` —— `decoded_batch_order` 按首个 start_time。
- 实测（S3，8 批×3 工序双机链、29 个生产 profile、真实 SGS）：12/12 个 v2 父候选的恒等决策解出与父不同的排程，例 `v2_spt` 父 (0,2,23,23,44) → 恒等决策 (0,1,8,8,48)；`v2_successor_seeded_micro_perturbation` 父 (0,2,13,13,40) → (0,0,0,0,43)。

## 影响

修补预算花在偏离精英的基点上，命中"差一两步"的机会被稀释；同时恒等重解码有时反而严格改善，说明"用解码结果重建优先级再解一次"这个廉价候选被浪费。

## 修复方向

批次邻域以父候选的 `operation_order`（已解码拓扑序，`optimizer_graph_ready_operation_neighbors.py:65-83`）为基座做移动；或先把恒等决策作为 0 号邻居解码并以其指纹作为父。

## 建议动作

`cs-issue`，属修补语义与设计意图不符的定点修复。
