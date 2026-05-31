---
doc_type: refactor-apply-notes
refactor: 2026-05-29-resource-dispatch-js-split
status: applied
tags: [resource-dispatch, frontend, js-split]
---

# resource-dispatch-js-split apply notes

## 步骤 1：先改测试读取口径

- 完成时间：2026-05-29
- 改动文件：
  - `tests/resource_dispatch_frontend_support.py`
  - `tests/operation_execution_feedback_test_support.py`
  - `tests/regression_resource_dispatch_site_records_frontend_contract.py`
  - `tests/regression_table_layout_readability_contract.py`
  - `tests/regression_scheduler_ui_range_feedback_contract.py`
  - `tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py`
  - `tests/regression_frontend_ui_language_polish.py`
- 验证结果：前端合约测试改为按模板顺序读取资源排班脚本束；`namedResourceInfo`、`resourceInfoHtml`、`calendarTaskHtml` 的 `完整身份：` 断言改为逐个提取函数体，没有降级成全文搜索。
- 偏离：无。

## 步骤 2：建立 shared 命名空间和 boot 启动边界

- 完成时间：2026-05-29
- 改动文件：
  - `static/js/resource_dispatch_shared.js`
  - `static/js/resource_dispatch_boot.js`
  - `templates/scheduler/resource_dispatch.html`
- 验证结果：模板在 `has_history` 条件块外按 `shared -> core -> execution -> boot` 顺序加载，四个脚本都使用 `defer`，旧 `resource_dispatch.js` 不再作为模板入口。
- 偏离：`sourceLabel`、`lockStatusLabel`、`relationBadge`、`codeCell`、日历范围辅助函数、`renderFlags`、`affectedResourceSummary`、`affectedResourceCell`、`affectedResourcePopupHtml` 当前也放在 shared 中；它们属于资源排班页的显示口径工具层，当前主要由 core 消费，execution 只复用其中少量通用显示函数。这个归属微调没有改变页面行为。

## 步骤 3：拆出 execution 子域

- 完成时间：2026-05-29
- 改动文件：
  - `static/js/resource_execution.js`
- 验证结果：现场记录任务卡、填写、查看记录、实际情况导入逻辑迁入 execution 文件；跨域调用通过 `window.__APS_RESOURCE_DISPATCH__` 调用 core 的 `currentQueryString()` 与 `loadData()`。
- 偏离：无。

## 步骤 4：拆出 core 子域并收束原文件

- 完成时间：2026-05-29
- 改动文件：
  - `static/js/resource_dispatch_core.js`
  - `static/js/resource_dispatch.js`
- 验证结果：排班查询、汇总、任务明细、日历、甘特、班组表逻辑迁入 core 文件；旧单文件已删除，模板不再引用。
- 偏离：无。

## 步骤 5：回归验证和范围守护

- 完成时间：2026-05-29
- 验证结果：
  - `node --check static/js/resource_dispatch_shared.js`
  - `node --check static/js/resource_dispatch_core.js`
  - `node --check static/js/resource_execution.js`
  - `node --check static/js/resource_dispatch_boot.js`
  - `.venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py`
  - `.venv/bin/python -m pytest tests/regression_table_layout_readability_contract.py`
  - `.venv/bin/python -m pytest tests/regression_scheduler_ui_range_feedback_contract.py`
  - `.venv/bin/python -m pytest tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py`
  - `.venv/bin/python -m pytest tests/regression_frontend_ui_language_polish.py`
  - `.venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_table_layout_readability_contract.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py tests/regression_frontend_ui_language_polish.py`
  - `.venv/bin/python scripts/run_quality_gate.py --fast-precheck`
  - Node VM 无历史页面启动烟测通过：无 `rdPage` 场景不误触发请求，视角和区间下拉绑定存在。
  - Sub Agent 对抗审查发现脚本 `async` 属性检查存在空洞，已改为读取完整 `<script ...></script>` 标签后检查；同时补强日历资源展示链路的 `完整身份：` 断言，避免测试变松。
- 聚焦测试总结果：52 passed。
- 范围守护：未新增 `/scheduler/resource-execution` 路由、`scheduler_resource_execution.py`、排产主导航现场记录入口、Win7 hidden-import、`OperationExecutionEvents` schema 改动。
- 浏览器点验：
  - 本地服务：`http://127.0.0.1:5017/scheduler/resource-dispatch`
  - 查询按钮：点击后页面刷新到带完整查询参数的 URL，任务数仍为 3，明细行 3 条，现场记录任务卡 3 张。
  - 现场记录 tab：面板正常显示；下载填写模板、导入实际情况 Excel、3 张任务卡正常出现。
  - 实际导入入口：未选择文件直接点击导入，页面提示“请先选择要导入的 Excel 文件。”，没有控制台错误。
  - 填写实际情况：第 1 张任务卡能展开填写表单，实际开工、实际完工、数量、暂停、异常、备注、保存、取消控件正常出现；未提交写入。
  - 日历矩阵 tab：日历表渲染成功，任务卡数量为 9。
  - 甘特图 tab：甘特 SVG 渲染成功，检测到 1 个 SVG 与甘特条元素。
  - 筛选联动：视角切到班组时班组选项和班组轴启用，切回人员时人员选项启用且班组轴禁用；区间切自定义时开始/结束日期显示，切回按周时查询日期显示。
  - 连续轻压：连续 5 轮切换 `任务明细 -> 现场记录 -> 日历矩阵 -> 甘特图`，明细 3 行、任务卡 3 张、日历任务 9 个、甘特 SVG 1 个与条元素 22 个保持稳定。
  - 浏览器控制台：上述操作后未发现 error 级别日志。
  - 截图证据：`/tmp/aps-resource-dispatch-execution.png`、`/tmp/aps-resource-dispatch-calendar.png`、`/tmp/aps-resource-dispatch-gantt.png`。
- 偏离：未提交任何会写入数据库的现场记录动作；填写表单只展开不保存，导入入口只验证无文件提示。
