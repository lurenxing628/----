---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-04"
classification: NEEDS_FEATURE
nature: maintainability
severity: P1
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 04：排产分析页缺影响面和稳定首屏行动摘要

## 结论

排产分析页的数据原料不少，推荐卡、三方案摘要、诊断块都有基础。但设计稿要的是“首屏先告诉用户该选哪个、风险是什么、下一步去哪”，当前页面还偏过程展示。

## 证据

- 当前模板顺序是概览、warnings、诊断、指标、方案对比、优化过程：`templates/scheduler/analysis.html:25`。
- 推荐卡和三方案摘要在 `_candidate_comparison.html` 里，但位置偏后：`templates/scheduler/analysis_parts/_candidate_comparison.html:20`、`:35`。
- 版本、时间、状态已有：`templates/scheduler/analysis_parts/_selected_overview.html:4`。
- 风险指标来自 specs：`web/viewmodels/scheduler_analysis_metrics.py:114`。
- 诊断块由 `build_diagnostic_sections` 输出：`web/viewmodels/scheduler_analysis_diagnostics.py:108`。
- 候选方案三角色固定输出：`web/viewmodels/scheduler_analysis_candidates.py:150`。
- 差值文案已有：`web/viewmodels/scheduler_analysis_candidate_helpers.py:167`。
- 当前候选公开指标只有失败、超期、拖期、工期、换型：`core/services/scheduler/run/schedule_candidate_summary.py:34`。
- 推荐卡当前只有候选、理由、备注：`web/viewmodels/scheduler_analysis_candidate_helpers.py:370`。
- summary size guard 会删除 `candidates`，页面依赖 candidates 时会退化：`tests/regression_scheduler_candidate_summary_contract.py:225`、`web/viewmodels/scheduler_analysis_candidate_helpers.py:91`。

## 当前能直接做

- 把推荐卡、三方案摘要、延期/诊断行动卡提前。
- 补“请选择一个排产版本查看分析结果”的空状态。
- 推荐卡动作先复用已有甘特、人员甘特、周计划、资源派工链接。

## 必须新增的功能

- 推荐卡影响面：受影响批次数、最晚超期、最忙资源利用率、换型次数、数据缺口。
- 每个候选方案的最忙资源利用率稳定字段。
- 历史 summary 被裁剪后，从候选表补水，不只依赖历史 summary。

## 风险

现有测试禁止模板里露出 `delta/diff/batch_impacts/resource_impacts/affected_batches` 这类内部字段。如果做影响面，要用中文公开字段，并同步调整测试口径。
