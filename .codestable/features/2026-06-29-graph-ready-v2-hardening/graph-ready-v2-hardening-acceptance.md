---
doc_type: feature-acceptance
feature: 2026-06-29-graph-ready-v2-hardening
status: accepted
date: 2026-06-30
tags:
  - scheduler
  - optimizer
  - graph-ready
---

# GraphReady v2 hardening acceptance

## 范围

- 对应 roadmap `scheduler-global-optimizer` 中 3 个已置为 done 的条目:
  - `benchmark-reference-diagnostics-baseline`
  - `graph-ready-v2-comparison-baseline-contract`
  - `graph-ready-v2-objective-feature-contract`
- 本文件是补齐验收落档,避免 roadmap 指向不存在的 feature 目录。

## 验收结果

- GraphReady v2 的目标感知特征已进入生产候选生成链路。
- `due_date` 按批次模型和数据库合同保持可空；空交期不再让 v2 整池静默退化成 v1,而是生成 no-due 占位特征并在交期型公式中后置。
- 非空但不可解析的交期一律 fail-loud。
- 缺必要图指标、非法数字、NaN/Inf 仍 fail-loud,不走 v2 skip 后门。
- v2 候选池不再保留“整池跳过”中间态:候选要么成功生成,要么 fail-loud;public 诊断也不再投影 `v2_status` / `v2_skip_reason`。

## 关键代码落点

- `core/services/scheduler/run/optimizer_graph_ready_v2_features.py`
- `core/services/scheduler/run/optimizer_graph_ready_profile_selection.py`
- `core/services/scheduler/run/optimizer_graph_ready.py`
- `core/services/scheduler/run/optimizer_graph_ready_candidates.py`
- `core/services/scheduler/summary/optimizer_public_search_report.py`

## 验证

- `python3 -m pytest tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/algorithm/test_optimizer_candidate_profile_contract.py -q`
  - 结果: `82 passed`

## 边界

- 当前工作区是未提交改动状态,本文件不声明 clean-worktree proof。
