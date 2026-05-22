---
doc_type: feature-design
feature: 2026-05-19-scheduler-graph-candidate-config-closeout
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-candidate-config-closeout
status: approved
summary: PR-7e 收口默认候选比较、配置字段、临时时间上限、候选清理和性能守卫
tags: [scheduler, graph, networkx, candidate, config]
---

# scheduler-graph-candidate-config-closeout 设计方案

## 目标

本 feature 执行 PR-7e。

大白话说，PR-7a 到 PR-7d 已经把候选表、候选试跑、同事务保存、页面按方案查看都做出来了；PR-7e 要把这套能力正式打开。调度员点排产后，系统默认先跑原算法，再跑多档重点工序优先方案，最后自动选一套正式采用方案。

## 范围

- 新库默认 `graph_analysis_mode=on`。
- 旧库已有 `graph_analysis_mode=off/report/on` 时不覆盖用户值。
- 新增 4 个可保存配置：
  - `graph_candidate_weight_count`：3 / 5 / 7，默认 5。
  - `graph_selection_policy`：balanced / score_only，默认 balanced。
  - `graph_overdue_tolerance_count`：0 / 1 / 2，默认 1。
  - `graph_tardiness_tolerance_ratio`：0.05 / 0.10 / 0.20，默认 0.10。
- 新增本次运行临时时间上限 `run_time_budget_seconds`，只随本次排产请求传入，不写回高级设置。
- `on` 默认跑候选比较；`off/report` 保留单方案，用于开发、排障和回滚。
- 分析页只在候选摘要和候选明细完整时展示方案对比；没有开启或记录不完整时给出明确中文提示。
- 候选清理跟正式排产历史保留策略走同一口径，只清没有正式历史的候选，不删 `ScheduleHistory` 和正式 `Schedule`。
- 增加 CandidateRows 时间索引和性能守卫。

## 明确不做

- 不给调度员新增“是否开启候选比较”的页面开关。
- 不并行跑候选，不做续跑，不换数据库。
- 不引入 Python 3.9+ 语法、新数据库驱动、外部 CDN 或重依赖。
- 不把候选失败吞成伪成功历史。
- 不让页面在没有候选数据时假装可以切换方案。

## 验收口径

- 默认排产会生成 baseline + 5 档重点工序优先候选。
- `balanced` 会按整体评分、超期数容差、拖期比例容差和重点工序健康结果择优。
- `score_only` 只看原始综合评分。
- 最终 `Schedule` 只保存采用方案，候选摘要和代表方案明细仍在候选表。
- 分析页展示“最终采用 / 原算法最好 / 重点工序优先方案最好”，并说明采用原因。
- 旧历史或记录不完整时，页面只提示情况，不展示假对比。
