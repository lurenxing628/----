---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-layout-gap
finding_id: "arch-drift-07"
nature: arch-drift
severity: P2
confidence: medium
suggested_action: cs-roadmap
status: open
---

# Finding 07：现有布局测试不能证明成熟 APS 主流程完整

## 速答

当前布局测试很有用，但主要防页面撑破、按钮丢失、说明误导、表格不可读；它们不能证明“首页到甘特、延期解释、方案对比、资源派工、现场反馈”已经形成成熟 APS 主流程。

## 关键证据

- `开发文档/frontend_ui_contract_plan.md:81-91` — 当前策略是保留静态合同测试和真实浏览器几何 smoke，浏览器 smoke 不做截图比对，只查页面事实和计算样式。
- `docs/frontend_manual_audit_and_rewrite_blueprint.md:38-45` — 蓝本主要声明页面说明入口、页面说明登记、完整排产路线等说明体系已经覆盖。
- `docs/frontend_manual_audit_and_rewrite_blueprint.md:65-74` — 蓝本自己列出“需核实”项，说明部分口径不能直接当真实页面事实。
- `tests/regression_dashboard_workspace_layout_contract.py:12-25` — 首页测试锁住工作区按钮 grid 和旧 action-bar 不回归。
- `tests/regression_gantt_layout_contract.py:12-23` — 甘特布局测试锁控制面板结构和表单布局，不验证“详情抽屉/资源负荷摘要/联动工作台”。
- `tests/regression_table_layout_readability_contract.py:78-93` — 表格合同主要保护省略、换行、横向滚动和列宽。
- `tests/ui_geometry_contract_data.py:5-16` — 真实浏览器几何路径只覆盖批次、配置、系统、工艺、物料等页面，不包含首页 `/`、甘特图、排产分析、资源派工这四个工作台核心页面。
- `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml:18`、`:52`、`:85`、`:117`、`:151`、`:184`、`:223` — 新 roadmap 引用了多个待新增的工作台回归测试文件，但这些文件当前还未落地。

## 影响

后续如果直接做工作台大改，现有静态断言可能会挡住合理布局变化；反过来，即使所有现有布局测试都通过，也不能说明用户真的能按成熟 APS 流程顺利做完事。更麻烦的是，首页、甘特、分析、资源派工这些最要改的页面现在不在浏览器几何覆盖里，真实页面挤压、重叠、横向溢出这类问题不一定会被挡住。

## 修复方向

新增工作台级验收合同，例如：首页风险项能带版本跳转到对应解释页；甘特任务和明细表能互相定位；资源负荷摘要能跳到资源负荷报表；现场记录保存后四视图状态一致。同时把首页、甘特、排产分析、资源派工纳入浏览器几何覆盖，避免只测源码 class 名、不测真实排版。

## 建议动作

跟随 `aps-frontend-workbench` roadmap 一起补测试策略，不建议单独改现有测试。
