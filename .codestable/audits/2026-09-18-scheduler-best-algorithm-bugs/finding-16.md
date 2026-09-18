---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: quality-16
nature: quality
severity: P2
confidence: high
suggested_action: cs-decide
status: fixed
---

# Finding 16：任一批次未完成时目标全分量置 float max，同 failed_ops 的候选全部平局，搜索失去信号

## 速答

`objective_score` 在 `incomplete_batch_ids` 非空时把全部分量置 `sys.float_info.max`；C 批失败时"B 拖期 10h"与"B 准时"两候选分数元组完全相同。2026-09-08 incomplete-batch-objective 决定明确接受了这个保守边界。

## 关键证据

- `core/algorithms/evaluation.py:377-380`；`evaluation_completion.py:27-29,74`。
- 实测：`/tmp/aps-audit-20260918/S5/probe_objective.py`。

## 影响

生产里一个批次缺资质/资料或撞排产截止窗，整个 improve 预算就只剩 `failed_ops` 一个键，5–20 秒搜索对其余批次零收益。

## 修复方向

保持第一键 `failed_ops`；未完成候选的分量改为只在已完成批次上计算并带 `objective_scope`；不同未完成集合之间不得靠任意哈希排序、不得为未完成批次编造拖期（若需排序用被丢弃工作的重要度）；已完成候选的元组形状与数值完全不变。裁决记入 `.codestable/compound/2026-09-18-decision-incomplete-batch-objective-comparability.md`，作为对 09-08 决定的修订。

## 处理结果

2026-09-18 同日落地：`BatchCompletion` 新增 `explained` / `incomplete_work_weight` / `components_known` / `objective_scope`（`evaluation_completion.py`），所有未完成批次都有失败明细归属且无预期外结果时视为"可解释"；`objective_score` 只在分量不可知时返回哨兵，可解释的不完整候选按已完成批次算分量（`evaluation.py`）；公共投影放行新标签（`optimizer_public_safety.py`）。裁决 (c) 的"丢弃工作重要度"只以 `incomplete_work_weight` 上报、未注入分数元组，因为消费方按下标读分量、注入会破坏裁决 (d)。A18 合同测试按新口径修订，新增 `tests/algorithm/test_incomplete_batch_objective_completed_subset_contract.py`。决定见 `.codestable/compound/2026-09-18-decision-incomplete-batch-objective-comparability.md`（修订 2026-09-08 决定）。

盲审提出的已知限制（未改行为，记入决定第 6 条）：`failed_ops` 相同但未完成集合不同的两个候选按各自已完成子集比分量，会系统性偏好"丢掉最拖期批次"的方案，`incomplete_work_weight` 只上报不进比较；发生频率未验证。若实测出现该偏好，须另起决定在比较层（不改元组形状）先比丢弃工作量，并同步所有按下标读分量的消费方。
