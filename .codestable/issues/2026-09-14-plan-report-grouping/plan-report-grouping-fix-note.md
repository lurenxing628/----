---
doc_type: issue-fix-note
status: fixed
date: 2026-09-14
title: 计划与报表页面按功能合并分区
---

## 范围

用户指出计划页和报表中心仍与执行排产页不一致。只读对比后，确认问题是零散横条和重复卡片边框；用户以“修改完善吧”批准按功能重新分组。此次只调整前端结构与样式，保留查询、统计、导出和计划切换逻辑。

## 修改

- `PlanWorkspace.jsx`：新增“方案与范围”功能卡片，收纳版本入口、当前状态、所选计划、试调/导出、读取范围、读取时间、异常/空态与四项统计。删除重复的独立标题和范围横条。
- `SchedulingWorkspace.jsx`、`PlanCatalogUI.jsx`：使用可选插槽把版本/记录导航与计划操作放进所属卡片；候选方案和历史记录分支保持原路由。
- `main.jsx`、`styles/33-plan-gantt.css`：计划页签与范围卡片视觉衔接，同时保留原tablist/tabpanel语义与键盘行为；甘特、分析与任务详情继续独立分区。
- `ReportWorkspace.jsx`：一级页签与筛选合成查询区；专题页签、指标、排序/导出、结果表格和分页合成结果区。详情使用结果区内部侧栏，只保留一条分隔线。
- `ReportControls.jsx`、`styles/37-reports.css`：固定来源移为查询区说明文字，取消控件外观；保留第三项指标的“道”单位、10分钟口径说明和原统计。报表与执行复盘共用新结构。
- `styles/30-workspaces.css`：显式启用的共用功能卡片样式，12px区域间距、16px横向内距、1px边界。未更改未启用这些类的页面。
- 同步上述编译产物和asset-manifest；已有测试定位随结构更新，业务断言保留。

## 定向验证

- `.venv/bin/python -m pytest -q tests/workbench/test_plan_ui.py tests/workbench/test_fg_plan_workspace_actions.py tests/workbench/test_plan_scope_caption.py --tb=short --show-capture=no`：初次7 passed、1 failed。失败为此前文案精简后遗留的导出说明旧字串；同步为当前文本后单独重跑`test_plan_ui.py::test_plan_ui_browser`，1 passed。八个测试最终均通过。
- 计划UI：Chrome109，51场景、509断言、31截图；计划列表、请求取消、范围读取、CSV/XLSX导出、无数据、深浅主题、600px窄屏均通过。
- 正式计划动作：candidate/trial两个真实隔离采用来源，各32个场景；1920/1392/1366/1280宽度及深浅主题通过，小屏甘特首行可见；数据库保留断言通过。
- 计划范围：四种真实采用数据覆盖零工时单点、末端单点、首端单点及普通工序；完整范围和子范围文案、边界与数值不变。
- 报表/复盘：基于现有EI源码探针，44/44浏览器场景和8组新增分组/对齐检查通过；覆盖两种宽度、深浅主题、空态、专题切换、详情、导出和返回。临时库77张表未变，SQL写入0。显示契约通过。
- 本地5000服务实际核对：计划列表/范围展开正常，查询与结果区各一层边框，来源0px边框，1280px页面没有横向溢出，浏览器无错误日志。
- `.venv/bin/python scripts/workbench/build.py`通过：`f1f8674197ced228925862bc72554037ac829ed7e95ae8ada36507e4883a949e`，Chrome109，260份资产。17份CSS源码与静态产物逐文件一致，`git diff --check`通过。

证据：`/tmp/aps-plan-report-grouping-20260914/analysis.png`、`reports.png`；报表多状态截图在`/tmp/aps-reporting-surfaces-20260914/grouping-final/`。计划完整探针报告：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-plan-ui-zjqhfft3/plan-ui-result.json`。报表完整报告：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-jy8xy1ft/ei-result.json`。

## 交付状态

修改已构建到当前服务；无需重启后端。按用户要求未跑质量门禁，未提交。保留此前所有未提交修改、数据库和修复备份。本轮为脏工作区上的局部验证，不构成clean-worktree proof。
