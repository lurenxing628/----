---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: performance-14
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
status: partially_fixed
---

# Finding 14：IG 起点、换起点、采纳现任都对已解码方案再全量解码一次，并计成 same_fingerprint 拒绝

## 速答

起点必解码 `parent.order`、adopt_incumbent 必解码、重启时 pool 条目 `decoded_order=False` 必解码；这些重解码按 `same_fingerprint` 计入 `rejected_by_reason`。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy_start.py:19-28`；`optimizer_graph_ready_iterated_greedy.py:171-186,229-251`；`optimizer_graph_ready_iterated_greedy_incumbent.py:37-44`。
- 实测（S3）：步进时钟 SMTWT-40 IG 8 次解码里 2 次是父顺序重解码（25%）且恰好 `same_fingerprint=2`；tiny 400 次解码 `same_fingerprint=37`、`context_switches=6`、`incumbent_adoptions=2`。

## 影响

短预算下 IG 本就只拿到零星解码，四分之一花在重解已知方案上；报告把参考捕获记成拒绝。

## 修复方向

与 finding-07 一并：父方案按拣选序重建后直接沿用父解码的结果与检查点；仍需重解码的记成 `reference_captures`。

## 处理结果

2026-09-18 部分落地：复现来源的解码记 `reference_captures`，不再计入 `same_fingerprint` 拒绝；分歧记 `reference_capture_divergences` / `reference_capture_improvements`；大实例重启同样走 `capture_reference`（`optimizer_graph_ready_iterated_greedy_incumbent.py`、`_diversify.py`）。仍未做：参考捕获本身的那一次解码（为了拿续排检查点）还在；搜索报告层 `mark_candidate_evaluated`（外层文件）仍把复现捕获记为 `same_fingerprint`。
