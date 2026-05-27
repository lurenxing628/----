---
doc_type: feature-design
feature: 2026-05-27-candidate-summary-delta-cards
status: approved
roadmap: aps-three-gap-directions
roadmap_item: candidate-summary-delta-cards
created: 2026-05-27
retrospective_backfill: true
---

# 代表三方案摘要卡和差值设计

## 背景

推荐结论卡只能告诉用户“建议哪套”，但用户还需要知道三套代表方案在关键指标上差多少。本阶段把正式采用方案、原算法代表方案、重点工序优先代表方案做成三张摘要卡，并且所有差值只和正式采用方案比较。

这份设计是回溯补档，用来补齐 CodeStable 事实源。它记录的边界和后续 checklist、acceptance 保持一致。

## 目标

- 固定展示三张卡：正式采用方案、原算法代表方案、重点工序优先代表方案。
- 指标覆盖失败工序、超期批次、总拖期、加权拖期、总工期、换型次数。
- 差值固定写成“比正式采用方案多了 / 少了 / 基本持平 / 暂无对比数据”。
- 缺数据时写“暂无数据”，不能把缺失误当 0。

## 不做

- 不做任意两方案自由比较。
- 不展示全部候选明细。
- 不做批次级或资源级影响清单。
- 不新增导出、不改算法、不改数据库。

## 实现范围

- `web/viewmodels/scheduler_analysis_candidates.py`：生成 `summary_cards`，只放公开展示字段。
- `templates/scheduler/analysis_parts/_candidate_comparison.html`：在推荐结论卡后、表格前展示摘要卡。
- `tests/regression_scheduler_candidate_summary_contract.py`、`tests/regression_scheduler_candidate_analysis_contract.py`、`tests/regression_scheduler_candidate_plain_language.py`：覆盖卡片顺序、差值文案、缺数据和内部字段不外露。

## 验收口径

- 三张卡数量、顺序和身份固定。
- 差值只相对正式采用方案。
- 用户看不到 `plan_role`、`candidate_id`、`source_table`、`score tuple` 等内部字段。
- 不影响现有方案表格和跳转。
