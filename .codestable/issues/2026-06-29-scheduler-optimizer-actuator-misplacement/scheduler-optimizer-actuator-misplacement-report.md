---
doc_type: issue-report
issue: 2026-06-29-scheduler-optimizer-actuator-misplacement
status: confirmed
severity: P0
summary: SGS 路径下局搜和 GRASP/IG 主要拧 batch_order,但 batch_order 在 SGS 里几乎不起作用,导致默认优化路径空烧。
tags: [scheduler, optimizer, local-search, sgs, graph-ready]
---

# 排产优化器作用点错位问题报告

## 1. 问题是什么

在排产优化器的默认路径里,局搜、业务邻域、GRASP/IG 候选主要改变 `batch_order`。但在 SGS 派工模式下,`batch_order` 只是很靠后的排序项,真实排产时经常完全影响不到最终结果。

可见现象是:

- `tests/_scripts_e2e/benchmark_smtwt_localsearch.py` 中 `sgs` 模式 250 个实例局搜改进数为 0。
- 同一批实例换成 `batch_order` 模式后,局搜能改进 165/250 个实例。
- 默认图分析路径会要求 SGS,所以很多候选预算花在无效旋钮上。

完整审计证据见 `.codestable/audits/2026-06-29-scheduler-optimizer-actuator-misplacement/index.md`。

## 2. 怎么复现

1. 在仓库根目录运行 `python3 tests/_scripts_e2e/benchmark_smtwt_localsearch.py`。
2. 观察输出里的 `sgs` 段。
3. `sgs` 合计 250 个实例中局搜改进个数为 0,平均 gap 没有缩小。
4. 同一脚本的 `batch_order` 段有明显改进,说明局搜本身不是完全无效,而是作用点放错了路径。

## 3. 期望行为 vs 实际行为

**期望行为**:

- `sgs` 路径下的优化动作应该改到 SGS 真正会使用的决策维度。
- 如果一个邻域只对 `batch_order` 有效,它不应该在图 ready / SGS 路径上伪装成有效动作。
- GRASP/IG 不应该强制把所有候选都用 SGS 解码后再发现结果相同。

**实际行为**:

- 业务邻域大量生成 `batch_order` 变更。
- SGS 解码时 `batch_order` 被更靠前的评分项压住。
- 图 ready 路径使用图自己的 ready 排序,不消费候选 `batch_order`。
- GRASP/IG 候选现在仍硬编码用 `sgs` 解码。

## 4. 环境信息

- 模块: 排产优化器、局搜、GRASP/IG 候选、图 ready 派工。
- 关键文件:
  - `core/services/scheduler/run/optimizer_grasp_ig_candidates.py`
  - `core/services/scheduler/run/optimizer_neighborhood_moves.py`
  - `core/services/scheduler/run/optimizer_local_search.py`
  - `core/services/scheduler/run/schedule_graph_dispatch_context.py`
  - `core/algorithms/greedy/dispatch/sgs_graph.py`
- 目标约束: Win7 x64、Python 3.8、离线交付。

## 5. 严重程度与优先级

严重程度定为 P0。

原因: 这不是显示问题,而是默认优化路径会消耗大量候选和局搜预算,但在 SGS 路径上无法改善结果。它直接影响 scheduler-global-optimizer roadmap item 6/7/8 的真实收益。
