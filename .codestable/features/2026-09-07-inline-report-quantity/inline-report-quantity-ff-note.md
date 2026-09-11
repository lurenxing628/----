---
doc_type: feature-ff-note
feature: inline-report-quantity
date: 2026-09-07
requirement:
tags: [frontend, prototype, field-reporting]
---

## 做了什么
在原工作台现场记录页实现普通报工行内填写，历史记录与主表共用列，取消嵌套小表。数量支持键盘、上下箭头、最小 0、最大可报量；更正时扣除其他记录而不重复扣本条。最大按钮不确认完工；单独的剩余全部完工命令必须校验真实起止时间和工时，只关闭当前工序。

## 改了哪些
- `前端设计/ui_kits/workbench/field-report-model.js`、`field-report-form.js`、`field-report-editor.js`：数量边界、共用表单、行内填写、历史更正、同会话草稿和完工操作。
- 同目录 `field-reporting.js`、`field-report-views.js`、`field-reporting.css`、`FieldReportCalendar.jsx`、`index.html`：页面装配、对齐的历史子行、原日历复用、切页清理及样式。日历自有节点先脱离页面，再在宿主提交结束后卸载，防止清空 DOM 与 React 卸载冲突。
- 同目录 `tests/field-report-inline.cjs` 及现有报工/导入/配色测试：补充新交互和生命周期回归。未改生产后端、数据库或其他人的暂存内容，未提交。

## 怎么验证的
JSDOM 原入口：行内与数量 62 项、报工回归 67 项、真实 XLSX 导入联动 45 项、现场甘特宿主联动 233 项、原导航与值班台回归 149 项均通过；导入器 23 个测试用例通过。浅深色 3998 处文字状态检查通过，最低对比度 4.58:1。测试使用已存在的 `.qa-dom/node_modules`，没有新增运行时下载依赖。

本地文件浏览器访问受限，未做浏览器截图或像素验收；未运行后端整仓门禁，本轮是脏工作区中的静态原型局部验证。原型目录被 `.gitignore` 忽略，修改前备份与 SHA-256 位于 `/Users/lurenxing/.codex/visualizations/2026/09/07/01a079ea-544f-73f0-aef0-d63b087bb017/workbench-before-inline-reporting/`。宿主原有 `fill-opacity` React 警告未在本轮越界修改。
