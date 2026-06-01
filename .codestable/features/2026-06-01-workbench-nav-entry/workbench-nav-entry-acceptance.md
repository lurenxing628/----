---
doc_type: feature-acceptance
feature: 2026-06-01-workbench-nav-entry
status: accepted
summary: 顶层计划工作台入口已落地，经典顶栏可一跳进入首页值班台、排产分析、设备甘特、人员甘特、资源派工和计划现场复盘。
tags: [aps, workbench, navigation, frontend]
roadmap: aps-frontend-workbench
roadmap_item: workbench-nav-entry
---

# workbench-nav-entry acceptance

## 1. 接口契约核对

- 已新增 `templates/components/ui_macros.html` 里的 `workbench_nav_menu()` 宏，统一输出顶层计划工作台菜单。
- 菜单包含 6 个只读页面入口：`dashboard.index`、`scheduler.analysis_page`、`scheduler.gantt_page(view='machine')`、`scheduler.gantt_page(view='operator')`、`scheduler.resource_dispatch_page`、`reports.execution_review_page`。
- `templates/base.html` 在顶层导航最左侧调用 `ui.workbench_nav_menu()`，让任意继承经典 `base.html` 的页面都能看到入口。
- `static/css/ui_contract.css` 新增 `aps-workbench-nav`、`aps-workbench-nav-summary`、`aps-workbench-nav-menu`、`aps-workbench-nav-link` 等本地样式。
- 菜单使用原生 `<details>/<summary>` 和普通 `<a>`，没有新增 JS 接口、数据库接口或后端运行时服务。

## 2. 行为与决策核对

- 顶层导航已经出现“计划工作台”，而且保留旧的首页、排产、工艺、人员、设备、物料、报表、系统入口。
- 菜单链接都是普通 GET 页面链接，不包含现场记录写入、Excel 导入、模板下载、表单 action 或任何写入接口地址。
- 设备甘特图和人员甘特图分别带 `view=machine` / `view=operator`。
- 菜单文案只显示中文业务名和中文说明，不显示 `plan_role`、`scenario_id`、`source_table`、`candidate_id`、`op_id`、`schedule_id`。
- 第 1 轮 SubAgent 复审发现原测试只证明 6 个目标“存在”，没有证明菜单“只能有这 6 个只读入口”；已加硬合同测试，解析菜单 HTML 后断言菜单里所有 `<a>` 和 `.aps-workbench-nav-link` 都刚好是 6 个白名单入口，并禁止表单、按钮、输入框、脚本、iframe/object/embed/base/link/style、`data-*`、`on*`、`download`、`method`、`formaction`、`javascript:`、导入和模板下载线索。
- 本阶段没有新增工作台页面，没有修改首页待处理内容，没有修改排程算法、数据库、vendor 或 installer。
- 挂载点反向核对已完成：本 feature 的代码引用只落在 `templates/base.html`、`templates/components/ui_macros.html`、`static/css/ui_contract.css` 和 `tests/regression_workbench_nav_entry_contract.py`；按这些挂载点拔除后不会残留运行时代码。

## 3. 验收场景核对

- 顶层入口存在：`tests/regression_workbench_nav_entry_contract.py` 覆盖，浏览器实测也确认经典顶栏只出现 1 个 `details.aps-workbench-nav`。
- 六个一跳入口：测试和浏览器实测均确认菜单有首页值班台、排产分析、设备甘特图、人员甘特图、资源派工、计划和现场实际。
- 甘特视图参数：测试确认设备甘特图 URL 为 `/scheduler/gantt?view=machine`，人员甘特图 URL 为 `/scheduler/gantt?view=operator`。
- 无写入入口：测试确认菜单刚好只有 6 个白名单链接，不包含现场记录写入、Excel 导入、模板下载、表单、按钮、输入框、脚本、危险嵌入标签、`data-*`、事件属性、`javascript:` 或下载属性；浏览器实测 `forbiddenHits=[]`。
- 无外部资源：测试确认未新增外部 JS/CSS/CDN/字体依赖。
- 浏览器验证：用临时经典模式本地服务打开 `http://127.0.0.1:5018/`，点开菜单后截图确认菜单正常展开，未出现侧边栏误判，菜单不遮挡顶层导航文字。
- Claude Code 同步对抗复审：新开 delegate 会话并要求 Claude Code 自行调用 `model="opus"` 子代理；SubAgent A（`a04f85c6def4c3d39`，定向复审测试护栏）和 SubAgent B（`ab8d5a7a60922b13a`，盲审整体范围）均成功创建。Claude Code 总结结论为 OK；A 提到的测试护栏非阻塞加固建议已回收进本阶段合同测试。

## 4. 术语一致性

- 方案第 0 节术语已落地：页面使用“计划工作台”“首页值班台”“排产分析”“设备甘特图”“人员甘特图”“资源派工”“计划和现场实际”。
- 禁用内部字段 grep 和测试均通过：菜单 HTML 不出现 `plan_role`、`scenario_id`、`source_table`、`candidate_id`、`op_id`、`schedule_id`。
- “计划和现场实际”仍是只读复盘入口，没有被写成可编辑现场记录入口。

## 5. 架构归并

- 已更新 `.codestable/architecture/ARCHITECTURE.md`：
  - 记录经典界面顶层导航已有“计划工作台”入口。
  - 明确菜单挂载点是 `templates/base.html` + `templates/components/ui_macros.html` + `static/css/ui_contract.css`。
  - 明确菜单是 6 个只读页面入口集合，不新增独立工作台页面。
  - 明确菜单不依赖外部 JS/CSS，不下发现场记录写入、Excel 导入、模板下载或表单写入地址。

## 6. requirement 回写

- 本阶段不单独回写 requirement。原因是它只补顶层入口，完整“每天打开系统先处理什么”的用户能力要等第 3 阶段 `dashboard-workbench-risk-todos` 把首页值班台落地后再一起归并。

## 7. roadmap 回写

- 已把 `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml` 中 `workbench-nav-entry` 标记为 `done`。
- 已把 roadmap 主文档第 6 节子 feature 清单第 2 条状态改为 `done`。
- 已在 roadmap 变更日志记录本阶段结果。

## 8. attention.md 候选盘点

- 本 feature 未暴露需要补入 `attention.md` 的通用启动注意事项。

## 9. 遗留

- 已知限制：顶层计划工作台菜单第一版只提供无上下文入口，不从任意当前页面自动拼当前版本、日期或方案；跨页上下文继续由第 1 阶段合同和各业务页内部链接负责。
- 后续接力：第 3 阶段 `dashboard-workbench-risk-todos` 继续升级首页值班台内容，让“计划工作台”入口进入后能看到今日待处理。
