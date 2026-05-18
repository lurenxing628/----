---
doc_type: feature-design
feature: 2026-05-18-scheduler-graph-critical-score-on-mode
requirement:
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-critical-score-on-mode
status: approved
summary: PR-6 在 on + DAG + 图增强允许时，把关键路径评分接入 SGS ready 候选排序
tags: [scheduler, graph, networkx, scoring, sgs]
---

# scheduler-graph-critical-score-on-mode 设计方案

## 1. 目标

本 feature 执行 roadmap `networkx-scheduler-graph-introduction` 的 PR-6：`scheduler-graph-critical-score-on-mode`。

大白话说，PR-5 已经解决“哪些工序有资格进入候选”。PR-6 只解决下一步：“这些已经 ready 的候选里，关键路径更重要、影响后续更多、后续关键工作量更大的工序，要不要更靠前”。

## 2. 范围

- `core/services/scheduler/graph/scoring.py` 只做图评分纯函数。
  - 输入是普通 Python dict 和非负整数权重。
  - 不 import NetworkX。
  - 不读数据库、不读配置、不接日志、不碰排产状态。
  - 缺字段、坏字段、负数权重直接报合同错误，不当 0 分。
- `schedule_graph_report.py` 只负责准备普通 Python 调度上下文。
  - `off` 不加载图分析。
  - `report` 继续 basic，不为了评分算 full `node_metrics`。
  - `on + DAG + 权重大于 0` 才算 full `node_metrics`，并预先转成 `graph_priority_key_by_op_id`。
  - `on + 权重全 0` 是用户显式关闭评分，public 小摘要写 `score_weights_zero`，继续保持 PR-5 ready 队列行为。
- `sgs.py` / `sgs_scoring.py` 只接收并拼接预先算好的图 key。
  - 算法层不反向 import scheduler service。
  - 保留旧 `score_penalty` 第一位。
  - 旧 SLACK / CR / ATC base key 不改方向。
- 配置说明同步到用户能看懂的口径。
  - `graph_analysis_mode=on` 会启用图安全检查、ready 队列和图评分。
  - `graph_critical_weight` / `graph_impact_weight` 不再写“预留”。
- summary / OperationLogs 只保留小摘要。
  - public 只写 `score_enabled`、`score_metric_status`、`score_weight_summary` 等小字段。
  - diagnostics 只写少量 `graph_score_sample`。
  - OperationLogs 不拿 diagnostics，不泄漏完整图数据。

## 3. 明确不做

- 不做 PR-7 的多权重候选试跑。
- 不做自动择优。
- 不新增候选表、候选仓库、候选落库事务。
- 不改 `schema.sql` 或 migrations。
- 不新增页面按钮、页面路由、甘特图切换、周计划切换或导出切换。
- 不把完整 `node_metrics`、完整关键路径、完整拓扑序、nodes、edges、raw graph 写进 summary 或 OperationLogs。
- 不绕过 `build_dispatch_key()` 去改 `batch_order`、`best_order`、`selected_batch_ids` 或最终落库 rows。

## 4. 实现决策

- `graph_score_bonus()` 返回正向 bonus：bonus 越大，越应该提前。
- SGS 的 tuple key 是越小越优先，所以 `graph_priority_key_component()` 返回 `(-bonus, critical_path_rank)`。
- 图分量拼到旧 key 时保留 `score_penalty` 第一位：`(score_penalty,) + graph_key + base_key[1:]`。
- `graph_critical_weight=0` 且 `graph_impact_weight=0` 时，不计算 full metrics，不拼图 key，并写明 `score_disabled_reason="score_weights_zero"`。
- `downstream_critical_minutes` 作为图评分内部固定分量参与正权重场景；权重全 0 时不会单独改变排序。
- 2000 节点性能证据同时记录 basic 和 full/on-score 路径，full 指标不静默跳过。

## 5. 验收场景

- `on + DAG + 权重大于 0` 时，关键路径 ready 候选更靠前。
- `on + DAG + 权重大于 0` 时，影响更多后续工序的 ready 候选更靠前。
- `on + DAG + 权重大于 0` 时，后续关键工作量更大的 ready 候选更靠前。
- `graph_critical_weight=0` 且 `graph_impact_weight=0` 时，结果等价 PR-5 ready 队列行为。
- `off` / `report` / `on + 有环` / `on + 图不可用` 不伪装成图评分成功。
- SLACK / CR / ATC 原方向不改反。
- summary 和 OperationLogs 不泄漏完整图数据。
- 算法层没有 `core.services` 反向依赖。

## 6. 架构关系

本 feature 改变了排产工序图当前能力，需要更新 `.codestable/architecture/ARCHITECTURE.md` 的“排产工序图分析现状”小节：`on` 模式现在不仅有 ready 队列，还会在权重大于 0 时把图评分接入 SGS 候选排序。
