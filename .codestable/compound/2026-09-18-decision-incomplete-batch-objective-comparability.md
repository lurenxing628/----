---
doc_type: decision
status: active
created_at: 2026-09-18
slug: incomplete-batch-objective-comparability
tags: [scheduler, optimizer, objective, A18, incomplete-batch, python38]
---

# 未完成候选的目标可比性

本决定修订 2026-09-08 的未完成批次目标决定（`.codestable/issues/2026-09-08-incomplete-batch-objective/incomplete-batch-objective-fix-note.md`）中的“保守限制”：该决定把任一批次未完成的候选全部分量置为 `UNKNOWN_OBJECTIVE_VALUE`，于是 `failed_ops` 相同的两个不完整候选目标恒持平，优化器分不清“只丢一批、其余很好”与“其余也很差”，`improve_only` 也永远看不到改善。2026-09-18 的只读审计把它列为 P2，用户随后要求全修。其余 2026-09-08 合同（完成性证据、预期集合、seed 与 failure_details 必传、proof 拒绝不完整输入）不变。

1. `failed_ops` 仍是候选分数的第一比较键，不改位置、不改口径。
2. 未完成被“解释”的定义：每个未完成批次都能由记录在案的失败明细归属，且没有预期外结果。此时目标分量只在已完成批次上计算，`ScheduleMetrics.completion` 标注 `objective_scope=completed_batches_only`、`objective_score_policy=completed_batches_only`，并带 `incomplete_batch_ids` 与 `incomplete_work_weight`（未完成批次的优先级权重之和，再按已排工时衡量丢弃工作量属后续可选项）。这些分量描述真实已完成批次，不是未知批次的零拖期预测。
3. 未被解释的未完成（缺工序却无失败证据、出现预期外结果、只解释了一部分）继续沿用 2026-09-08 的全哨兵元组，`objective_scope=unknown`、`objective_score_policy=unknown_all_components`；哨兵仍是排序用的有限最大值，不写入拖期或日期字段。
4. 不为丢掉的批次编造拖期，不用哈希或插入顺序裁决同分候选。丢弃工作量的重要性只作为可查字段上报，不进入分数元组：分数消费方按位置读取分量（`_objective_primary_score` 读 `score[1]`、`best_score_schema` 按下标标注、proof 检查等长），把严重度塞进元组会改变完整候选的形状；因此完整候选的元组长度与数值逐位不变，`failed_ops` 相同且已完成子集分量也相同的不完整候选仍然持平。若后续要在不完整候选之间按丢弃工作量排序，须另起决定改比较函数，并同步所有按下标读取的消费方。
5. 安全边界：有失败明细即有 `failed_ops ≥ 1`，被解释的不完整候选只能排在 `failed_ops` 更小的完整候选之后；合同测试锁定“被解释的不完整候选不会越过任何完整候选”。公共投影允许上述两组标签与非负有限的 `incomplete_work_weight`，其余标签值仍被拒绝。
6. 已知限制（2026-09-18 盲审提出，本决定不改行为）：`failed_ops` 相同但未完成集合不同的两个候选按各自已完成子集比分量，会系统性偏好“丢掉最拖期批次”的方案（典型场景是撞排产截止窗时不同候选丢掉不同批次）；`incomplete_work_weight` 只上报、不进比较，发生频率未验证。若实测出现该偏好，走新决定在比较层（不改元组形状）先比丢弃工作量、再比已完成子集分量，并加合同测试、同步所有按下标读分量的消费方。

验收数据（单机、`.venv` Python 3.8.10，工作树 `fix/dispatch-semantics`）：

- 新增 `tests/algorithm/test_incomplete_batch_objective_completed_subset_contract.py`：被解释的不完整候选按已完成批次给出 overdue / tardiness 与权重；同 `failed_ops` 的两个不完整候选按已完成子集排序；不完整候选不越过完整候选；未解释、部分解释、预期外结果三种情形回到全哨兵；真实调度的时间窗失败被解释且权重来自未完成批次优先级；公共投影带标签。
- `tests/algorithm/test_incomplete_batch_optimizer_contract.py` 的真实调度部分输出用例改为断言已完成子集分数并保持在 `failed_ops` 之后；`test_incomplete_batch_metrics_contract.py`、`test_incomplete_metrics_public_projection.py` 原断言不变。
- 完整候选不受影响：三套基准夹具全部完整排产，其最终结果的变化全部归因于同日的派工规则决定（见 `2026-09-18-decision-dispatch-rule-working-hour-slack-and-priority-weight.md`），本决定对完整候选的分数元组逐位无影响。
