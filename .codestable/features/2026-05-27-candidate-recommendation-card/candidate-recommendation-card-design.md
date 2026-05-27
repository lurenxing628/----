---
doc_type: feature-design
feature: 2026-05-27-candidate-recommendation-card
status: approved
roadmap: aps-three-gap-directions
roadmap_item: candidate-recommendation-card
created: 2026-05-27
retrospective_backfill: true
---

# 方案推荐结论卡设计

## 背景

方案对比区原来主要是表格，用户需要自己看指标判断哪套方案更合适。本阶段只补一个“推荐结论卡”，把正式采用方案和推荐理由用中文讲清楚，不做三方案差值，不改候选生成和排程算法。

这份设计是回溯补档，用来补齐 CodeStable 事实源。它记录的边界和后续 checklist、acceptance 保持一致。

## 目标

- 在方案对比区域顶部展示系统建议采用哪套代表方案。
- 推荐理由只用中文大白话表达，例如超期批次、失败工序、总拖期等业务指标。
- 页面不显示 `score tuple`、`candidate_key`、`source_table`、`candidate_id` 等内部字段。
- 候选未开启、候选失败或历史数据不完整时，不伪造推荐卡；正式采用行自身也必须是已完成状态，失败、跳过、缺状态或未知状态都不展示“系统建议采用”。

## 不做

- 不计算三方案差值。
- 不展示全部 3/5/7 档候选明细。
- 不新增导出。
- 不改数据库、迁移、排程算法、派工确认或现场反馈。

## 实现范围

- `web/viewmodels/scheduler_analysis_candidates.py`：整理推荐卡公开字段，只输出模板需要的中文展示数据。
- `templates/scheduler/analysis_parts/_candidate_comparison.html`：在方案对比表格前显示推荐结论卡。
- `tests/regression_scheduler_candidate_analysis_contract.py`、`tests/regression_scheduler_candidate_plain_language.py`：锁住推荐卡中文文案、内部字段不外露和不越界。

## 验收口径

- 页面能直接看到“系统建议采用”的中文结论。
- 推荐卡只围绕正式采用方案和推荐理由，不提前出现摘要差值卡。
- 用户可见文案没有内部字段和英文枚举。
- 不完整数据不生成假推荐。
- 正式采用行不是已完成状态时不生成推荐卡，并给中文提醒让用户复核方案对比记录。
