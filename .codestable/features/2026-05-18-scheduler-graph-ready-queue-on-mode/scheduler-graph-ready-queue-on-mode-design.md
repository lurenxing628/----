---
doc_type: feature-design
feature: 2026-05-18-scheduler-graph-ready-queue-on-mode
requirement:
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-ready-queue-on-mode
status: approved
summary: PR-5 实现有环安全门，并让 on 模式下可用 DAG 使用 ready 队列筛 SGS 候选
tags: [scheduler, graph, networkx, ready-queue, sgs]
---

# scheduler-graph-ready-queue-on-mode 设计方案

## 1. 目标

本 feature 执行 roadmap `networkx-scheduler-graph-introduction` 的 PR-5：`scheduler-graph-ready-queue-on-mode`。

大白话说，这一步开始让工序图真正影响排产，但只影响一件事：哪些工序“现在有资格进入 SGS 候选”。它不改评分方向，不改资源匹配，不做图评分，也不落库候选方案。

## 2. 范围

- 阶段 11：实现有环安全门。
  - `report` 模式只提示循环依赖，不阻止排产。
  - `on + graph_block_on_cycle=yes + 有环` 在 version 分配前阻止排产，返回中文业务错误。
  - `on + graph_block_on_cycle=no + 有环` 继续原排产逻辑，但 public 摘要明确写图增强未启用。
  - known graph error / unknown graph error 不伪装成有环，也不静默吞掉。
- 阶段 12a：实现 ready 队列 helper。
  - 只处理普通 Python 集合和映射。
  - 不接收 `nx.DiGraph`。
  - 不读数据库、不读配置、不调用评分、不调用资源匹配。
  - 只回答当前哪些 `op_id` 已经 ready。
  - 实际实现放在 `core/algorithms/greedy/dispatch/ready_queue.py`，`core/services/scheduler/graph/ready_queue.py` 保留兼容导出，避免算法层反向 import service。
- 阶段 12b/12c：在 optimizer 前准备并传递 `graph_ready_context`。
  - 图分析结论给排产和 `result_summary` 共用。
  - 不用 optimizer 后的 report 投影冒充排产输入。
  - 传给算法层的只有普通 Python 结构。
- 阶段 12d：SGS 候选集合接入 ready 队列。
  - 无 `graph_ready_context` 时旧 SGS 候选逻辑保持。
  - 有 `graph_ready_context` 时，只替换候选资格集合。
  - 评分、资源匹配、`build_dispatch_key()`、内部/外协评分方向不改。
  - frozen / seed 工序只作为已固定前置，不重复进入 candidates，不重复写 rows。

## 3. 明确不做

- 不实现 PR-6 图评分。
- 不把关键路径、影响范围、后续关键工作量放进评分。
- 不实现候选池、多权重试跑、自动择优或候选落库。
- 不改 `core/services/scheduler/graph/scoring.py`。
- 不改 `core/algorithms/dispatch_rules.py`。
- 不改资源匹配、外协组合并、内部工时估算、SLACK/CR/ATC 方向。
- 不新增页面按钮或路由。本次只同步已有配置说明文字，避免用户看到旧口径。

## 4. 实现决策

- `prepare_schedule_graph_for_dispatch()` 放在 optimizer 前，只构建一次图准备结果。
- 同一份图准备结果同时提供：
  - `graph_analysis_public`
  - `graph_analysis_diagnostics`
  - `graph_ready_context`
- `graph_ready_context` 只使用 `dict`、`set`、`tuple`、`int` 等普通 Python 数据。
- `graph_analysis_mode=on + DAG` 时，optimizer 强制使用 SGS，因为 ready 队列当前只接入 SGS 候选集合。
- `dispatch_sgs()` 在无图上下文时继续调用旧 `_collect_sgs_candidates()`。
- `dispatch_sgs()` 在有图上下文时用 ready `op_id` 映射回 `(batch_id, op)`，再交给原评分函数。
- 前置工序排产失败时，图后继不会被释放；这些被图依赖阻断的工序会计入失败数，并写清楚“依赖的前序工序排产失败，本次跳过”。
