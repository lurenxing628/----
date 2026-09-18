---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: performance-19
nature: performance
severity: P3
confidence: medium
suggested_action: cs-refactor
status: partially_fixed
---

# Finding 19：全部输出恒等无停滞退出；图模式每步全量 sorted；小实例搜索耗尽仍烧满预算

## 速答

三个小项合并记录：

1. 图档全部输出恒等时没有停滞退出：wide_parallel_chains 图档 29 次解码 28 次 `same_fingerprint`（96%），各阶段照跑到截止；预解码只抓精确弱序相等（`optimizer_graph_ready_predecode.py:75-77`）。
2. 图模式每拣一道工序就对整个就绪集重新 `sorted()`（`core/algorithms/greedy/dispatch/sgs_graph.py:311-320`），O(R log R)/轮；键末尾含 op_id，`_pick_best_candidate` 的 `min` 与候选顺序无关，这次排序只影响评分副作用顺序。堆路径只在唯一图键、固定资源、≥128 工序且守卫通过时启用。
3. 质量矩阵 tiny（8 工序）耗时 48ms → 950ms、medium 4.1s → 10.0s：轮转把剩余预算全部用掉是 09-14 决定的设计，但小实例搜索空间耗尽后仍烧预算。

## 影响

退化实例无质量损失，只烧时间。

## 修复方向

有界、可报告的停滞退出；确认无顺序依赖后去掉每步 sorted 或改惰性。

## 处理结果

2026-09-18：(1) 剖面阶段加停滞退出——连续 6 次解码只得已见排程即结束剖面阶段，报 `stagnation_stop` / `profiles_stagnated`（`optimizer_graph_ready_stages.py`），合同测试 `tests/algorithm/test_graph_ready_stage_reporting_contract.py`；四个 SMTWT 基准里未触发，只有单元合同证据。(2) `sgs_graph.py` 每步排序保留：剖析只占解码 0.2%，且它决定"第一个抛错的候选是谁"，去掉会让报错顺序不可复现；只加了单元素跳过。(3) 小实例搜索耗尽仍烧满预算：未动，修补与 IG 阶段没有对应的停滞退出，仍 open。
