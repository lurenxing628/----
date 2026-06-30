---
doc_type: feature-acceptance
feature: 2026-06-30-graph-ready-v2-production-capacity
status: accepted
date: 2026-06-30
tags:
  - scheduler
  - optimizer
  - graph-ready
---

# GraphReady v2 production capacity acceptance

## 范围

- 对应 roadmap `scheduler-global-optimizer` 中 2 个已置为 done 的条目:
  - `graph-ready-v2-bottleneck-resource-score`
  - `graph-ready-v2-candidate-portfolio`
- 本文件是补齐验收落档,避免 roadmap 指向不存在的 feature 目录。

## 验收结果

- GraphReady v2 残余容量特征进入生产候选生成链路,包含 window、blocked、residual、ratio、pressure 与 candidate machine count。
- 交期压力计算区分两个口径:
  - `due_deadline_hours`: 自然小时交期,用于 EDD 这类纯交期顺序。
  - `due_budget_hours`: 可用于追交的预算小时,内制工序在有日历时使用**窗口产能小时**(start→交期窗口内的日历可用工时,**未扣** downtime/seed 占用,即毛窗口),外协仍使用自然小时。注:刻意用毛窗口而非净残余产能——争用另由 `residual_capacity_pressure` 表达,且经毛/净基准对比确认净口径无稳定收益(小实例被 rank01 归一化抹平、大实例有别但无一致赢家),口径决策与数据见 `.codestable/compound/2026-06-30-due-budget-window-vs-residual/`。
- 10 个 v2 公式不再大面积共享同一组首键；基准夹具锁住至少 6 种不同 ready 排序。
- `micro_perturbation` 仍只在主交期目标相同时作为可复现平局信号,不越过主交期分数。
- 容量扫描里的不可达分钟级兜底分支已清理,安全循环上限保留。

## 关键代码落点

- `core/services/scheduler/run/optimizer_graph_ready_v2_capacity.py`
- `core/services/scheduler/run/optimizer_graph_ready_v2_features.py`
- `core/services/scheduler/run/optimizer_graph_ready_candidates.py`
- `tests/algorithm/test_optimizer_graph_ready_candidate_contract.py`

## 验证

- `python3 -m pytest tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/algorithm/test_optimizer_candidate_profile_contract.py -q`
  - 结果: `82 passed`

## 边界

- 当前工作区是未提交改动状态,本文件不声明 clean-worktree proof。
