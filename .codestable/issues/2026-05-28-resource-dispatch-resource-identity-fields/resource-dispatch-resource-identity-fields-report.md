---
doc_type: issue-report
issue: 2026-05-28-resource-dispatch-resource-identity-fields
status: confirmed
severity: P1
title: "资源排班资源编号和名称混在一起难读"
date: 2026-05-28
tags:
  - scheduler
  - resource-dispatch
  - execution-feedback
  - report
  - frontend
---

# 资源排班资源编号和名称混在一起难读

## 问题来源

用户在资源排班页现场反馈卡片里看到设备和人员显示成一个长字符串，例如：

`PX0528A-MILL-MC-02 PX0528A压测MILL-MC-02`

这类文本把编号和名称直接挤在一起，用户分不清前半段是编号、后半段是名称，也很难判断计划资源和实际资源是不是同一个。

## 当前现象

- 资源排班现场反馈卡片里，计划设备、实际设备、计划人员、实际人员都用一个拼好的文本展示。
- 任务明细表、日历、甘特弹窗、Excel 导出、计划和现场实际报表也沿用了类似的“一个字段装完所有身份”的展示方式。
- 有些地方只显示名称，有些地方显示“编号 + 名称”，同一套资源在不同页面看起来不一致。
- 当前浏览器地址可复现：`/scheduler/resource-dispatch?version=8&start_date=2026-06-01&end_date=2026-06-30&plan_role=adopted&period_preset=custom`。

## 影响

用户需要靠猜来理解设备和人员身份：

- 编号很长时，卡片和表格可读性明显下降。
- 计划资源和实际资源并排显示时，用户不容易确认它们是不是同一个资源。
- 导出到 Excel 后，长字段继续挤在一个单元格里，复盘和线下沟通都不方便。

## 期望

- 用户主视图优先看到好读的名称或业务文案。
- 完整编号身份也要看得到，但应作为第二行、标题提示、弹窗明细或 Excel 可读文本出现。
- 后端要输出干净字段，不能让前端靠拆字符串猜“哪段是编号、哪段是名称”。
- 页面和导出继续只展示中文大白话，不暴露内部字段名。

## 标准路径

本 issue 走标准 CodeStable issue 路径：

- `resource-dispatch-resource-identity-fields-report.md` 记录问题现象。
- `resource-dispatch-resource-identity-fields-analysis.md` 下钻根因、字段语义和修复边界。
- `resource-dispatch-resource-identity-fields-fix-note.md` 记录最终改动、验证和复审结果。
