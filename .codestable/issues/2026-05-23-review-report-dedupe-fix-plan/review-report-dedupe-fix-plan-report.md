---
doc_type: issue-report
issue: 2026-05-23-review-report-dedupe-fix-plan
status: confirmed
severity: P1
title: "Review 报告去重后剩余问题修复"
date: 2026-05-23
source_audit: "../../audits/2026-05-23-review-report-dedupe/index.md"
summary: "两份 review 报告去重核实后，当前分支仍有分析页、报表日期、Gantt 错误边界、资源排班输出、数据库高版本保护、质量门禁和 P2 维护项需要修复。"
tags: [review, scheduler, gantt, resource-dispatch, quality-gate, database, codestable]
---

# Review 报告去重后剩余问题修复

## 问题来源

本 issue 来自 `.codestable/audits/2026-05-23-review-report-dedupe/index.md`。

那份审计把两份 review 报告重新核实、去重，并把已经不符合当前分支事实的问题剔除掉。剩下的问题不是一个单点 bug，而是一组需要一起收口的用户可见问题和质量门禁缺口。

## 当前现象

审计后确认，当前分支仍需要处理这些问题：

- 分析页不能把未知状态、坏数字、`NaN`、`Infinity` 当成正常数据展示。
- 报表页只填开始日期或结束日期时，不能悄悄换成版本范围或默认 7 天。
- Gantt 页面遇到接口失败、数据结构错误、脚本缺失、渲染异常时，要给用户看得懂的中文错误。
- 资源排班页面和 Excel 公开输出不能泄漏内部枚举或不适合用户看的字段说法。
- 数据库遇到未来更高版本时，要在补表、迁移、备份前直接失败。
- 新增高风险回归必须进入质量门禁，不能只散落在普通测试里。
- Gantt 前端脚本、关键链原因、Week/Month 假期背景和相关文档需要同步收口。

## 影响

如果这些问题不修，用户可能会看到“正常”但实际不能相信的数据，或者以为自己筛了日期但页面用了别的范围。开发侧也可能因为必跑门禁漏项，后续改动把同类问题重新带回来。

## 标准路径

本 issue 走标准 CodeStable issue 路径：

- `review-report-dedupe-fix-plan-report.md` 记录问题来源和现象。
- `review-report-dedupe-fix-plan-analysis.md` 下钻根因、方案和批次边界。
- `review-report-dedupe-fix-plan-fix-note.md` 记录实际修复范围、验证结果和剩余 clean proof 状态。
