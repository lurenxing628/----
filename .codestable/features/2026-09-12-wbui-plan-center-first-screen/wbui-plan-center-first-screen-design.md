---
doc_type: feature-design
feature: 2026-09-12-wbui-plan-center-first-screen
status: approved
summary: 计划中心默认选择、目录折叠和甘特首屏展示
tags:
- workbench
- ui
- gantt
roadmap: workbench-ui-refinement
roadmap_item: wbui-plan-center-first-screen
created: '2026-09-12'
---

## 0. 术语约定

当前正式计划以目录 is_current_official 且 capabilities.view 为准；读取时点来自响应 meta.as_of。

## 1. 决策与约束

用户 2026-09-12 已授权按审查意见并行实施。遵循 implementation-20260912.md：没有显式 planRef 和任何 initialContext 时才默认选择；不可读、多候选或读取失败均不改选。所有领域 API、计划范围和导出语义不变。

## 2. 名词与编排

目录保留游标分页和完整身份行，顶部提供下拉并在选中后收起；无当前正式时展开。先显示甘特再显示风险明细；条形首行显示批次号，次行保留工序和分件。图例覆盖准时、超期、冲突、基线和时间点。今日线按服务器 as_of 的日期标示，另标示确切读取时点，浏览器时钟不影响业务状态。

抽出 PlanSelectionModel 只处理默认选择判定，方便合同测试；共享 Format、EmptyState、Pager 必须消费。新增 app/styles/33-plan-gantt.css 由主线程登记，禁止本任务修改静态构建产物。

## 3. 验收契约

- 无上下文唯一可读当前正式自动选择；显式、恢复上下文、不可读和多当前不自动选择。
- 目录失败不替代计划，游标下一页/上一页仍绑定 snapshot_ref。
- analysis/gantt/delay 三入口甘特首行在 1366×768 可见；折叠目录可重新展开。
- 已指定或选中运行候选时，候选比较目录同样默认收起；原生 summary 可用鼠标和键盘重新展开。目录筛选、分页、全部指标和原引用不变；从目录切换候选后将焦点归还 summary，外部进入不抢焦点。
- DOM 与 dense canvas 条形首行均为批次号；今日与时点线用响应 as_of，点工序仍为零时长。
- 当前源码模型测试、JSX 编译、Chrome109 交互和几何证据通过后才可标 done。

## 4. 与项目级文档的关系

界面显示调整，不改领域架构与 requirements 能力范围；主线程统一回写 UI 共享结构和路线图，统一 build_id 与浏览器证据待集成。
