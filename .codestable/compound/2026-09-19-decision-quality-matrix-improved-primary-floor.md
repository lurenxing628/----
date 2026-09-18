---
doc_type: decision
status: active
created_at: 2026-09-19
slug: quality-matrix-improved-primary-floor
tags: [scheduler, quality-matrix, historical-baseline, real-clock, test-contract]
---

# 质量矩阵历史非回归：改进分只比主目标并保留 3/4 历史改进量

2026-09-19 在干净 HEAD 上重生成正式基线夹具 `tests/fixtures/optimizer_quality_matrix_baseline.json`（提交 034e4d86）后，推送触发的日常门禁串行车道两条失败：

- `test_real_matrix_does_not_regress_against_formal_historical_baseline`：`medium_shift_pool/min_changeover: improved objective regressed`。
- `test_quality_uses_lexicographic_target_order_not_componentwise_non_degradation`：`tiny fixture must exercise a real lexicographic quality tradeoff`。

原因不是解码或搜索退化。improved 是 10 秒真实时钟搜索的结果，同一输入每次落在不同轨迹上：同日 11 次运行里 `min_changeover` 的前两个分量只见过 [8,11]/[9,10]/[11,10]/[8,12]，`min_weighted_tardiness` 主目标见过 1128/1132.5/1149/1199.5，尾部分量（拖期、换型计数）随之整体变动。旧合同 `_quality_comparison_failures` 对 baseline 与 improved 都做**全向量字典序**严格非回归，任何一次夹具都只是噪声分布里的一个样本，选噪声下限那次晋升也挡不住尾部分量更差的运行。字典序权衡测试则用夹具 tiny 行的具体数值去凑"迟到批次更少、拖期更大"的候选，夹具一变就凑不出。

## 决定

1. **baseline 仍逐位比较。** 单次确定性贪心解码没有噪声，历史比较保持全向量字典序严格非回归，半小时的滑动也报 `baseline objective regressed`。
2. **improved 只比罚分分量与主目标，并保留至少 3/4 的历史改进量。** 令历史 baseline 主目标为 B、历史 improved 主目标为 I，本次 improved 主目标不得超过 `I + (B − I) × (1 − 0.75)`（`IMPROVEMENT_RETENTION = 0.75`，`improved_primary_floor`），罚分分量不得高于历史值；尾部分量不再比较。当前夹具的地板：medium 迟到批次 8 → 9、拖期 849 → 897.75、加权拖期 1132.5 → 1396.25、换型 9 → 12.5；tiny 拖期 12 → 13.375。观测到的噪声全部落在地板内。
3. **同快照内的 improved ≤ baseline（全向量字典序）不变**，`validate_snapshot` 仍据此拒绝"搜索比不搜索还差"的快照；`objective_score` 必须与序列化排程重算一致，测试不能靠改分数绕过。
4. `compare_quality_only`、`compare_quality_matrices`、`update-baseline` 共用同一规则；耗时门槛与机器一致性要求不变。
5. 接受的代价：`min_changeover` 这类主目标是计数的目标，improved 只在换型计数上受约束，纯延迟造成的拖期变差不会被历史比较报出（`test_other_machine_does_not_hide_full_objective_quality_regression` 对该目标只期望 baseline 一条失败）。真正的解码错误仍由 baseline 逐位比较和同快照检查兜住。
6. 字典序权衡测试改为只把已经迟到的批次整体推到排程结束之后（迟到数不变、拖期必增、无资源重叠），不再依赖夹具具体数值。

## 合同测试

- `tests/algorithm/test_optimizer_quality_matrix_quality_contract.py`：`test_improved_primary_target_keeps_most_of_the_historical_gain`（末道工序延后 0.5 h 在地板内通过，延后 2 h 越过地板报 `improved objective regressed`，两者都是通过审计的真实排程）、`test_deterministic_baseline_decode_stays_exact`（同样 0.5 h 加在 baseline 上必报 `baseline objective regressed`）、`test_quality_uses_lexicographic_target_order_not_componentwise_non_degradation`（构造不依赖夹具数值）、`test_other_machine_does_not_hide_full_objective_quality_regression`（按目标区分期望的失败集合）。
- `tests/algorithm/test_optimizer_quality_matrix_contract.py`：真实矩阵运行对正式基线的历史比较、同快照守卫、10 天平移必报回归，均沿用。

## 关联

- 正式基线夹具的生成规则见 `tests/_support/optimizer_quality_matrix_compare.py` 的 `update_baseline`；2026-09-12 基准信任修复说明里"完整 `objective_score` 字典序"的表述自本决定起只对 baseline 成立。
- 本轮触发背景：`.codestable/compound/2026-09-19-decision-graph-priority-pruning-auto-assign.md`（剪枝让 10 秒内解码次数翻倍，搜索轨迹差异被放大）。
