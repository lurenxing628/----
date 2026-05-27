---
doc_type: architecture
slug: ui-gantt
status: current
created: 2026-05-22
last_reviewed: 2026-05-27
tags: [scheduler, gantt, frontend, readonly, vendor, scenario-preview]
---

# 甘特图结果查看架构现状

## 1. 页面入口

- 页面路由：`web/routes/domains/scheduler/scheduler_gantt.py` 的 `/scheduler/gantt`。
- 数据接口：`/scheduler/gantt/data`。
- 经典模板：`templates/scheduler/gantt.html`。
- 现代模板镜像：`web_new_test/templates/scheduler/gantt.html`。

页面把 `data-gantt-mode="view"` 和 `data-zoom-level` 下发给前端。第一版只读甘特图不提供保存按钮，也不调用任何正式写库接口。

页面顶部现在有 `ganttSimulationEntryShell`。它只显示灰色禁用按钮 `模拟调整（后续开放）`；当前点击不了，不会切换 `simulate`，不会发保存请求，也不会产生草稿、模拟方案或正式新版本。

## 2. 前端职责拆分

- `static/js/gantt_zoom.js`：只放时间粒度规格、URL 稳定值、范围保护和估算节点数。
- `static/js/gantt_adapter.js`：把 APS 的查看/模拟模式、缩放等级和回调翻译成 Frappe Gantt options，并负责创建 Gantt 实例。
- `static/js/gantt_ui.js`：读取页面控件、读取 URL、把当前状态写回 URL，并同步加载表单和视图切换链接。
- `static/js/gantt_contract.js`：集中维护甘特图数据合同、关键链状态、公开标签、任务数据转换和降级提示。
- `static/js/gantt_help.js`：生成页面帮助列表，只负责用户能直接看到的查看说明。
- `static/js/gantt_popup.js`：生成任务弹窗 HTML，只拼接已经转义后的公开字段。
- `static/js/gantt_legend.js`：生成图例、关键工序状态、配色说明和假期背景说明。
- `static/js/gantt_holidays.js`：管理后端日历或周末弱兜底的假期/停工背景标注，并保证周、月视图下单日背景只占一天宽度。
- `static/js/gantt_decorations.js`：管理条形圆角、外协虚线、超期红框、关键工序外框、聚焦高亮和装饰缓存。
- `static/js/gantt_render.js`：过滤任务、做范围保护、通过适配层创建 Frappe Gantt，并串联弹窗、假期、图例和视觉装饰模块。
- `static/js/frappe-gantt.min.js`：本地 vendor 文件，只保留必须落在 Frappe 内部的补丁。
- `static/css/aps_gantt_simulation.css`：只放模拟调整入口壳样式，避免继续扩大主甘特图样式文件职责。

脚本加载顺序必须保持为 `gantt.js`、`gantt_zoom.js`、`gantt_adapter.js`、`gantt_color.js`、`gantt_outline.js`、`gantt_contract.js`、`gantt_help.js`、`gantt_popup_fit.js`、`gantt_popup.js`、`gantt_legend.js`、`gantt_holidays.js`、`gantt_decorations.js`、`gantt_render.js`、`gantt_ui.js`、`gantt_boot.js`。`gantt_boot.js` 负责请求数据和阻塞式错误展示：HTTP 错误会优先显示后端 JSON 里的业务错误，成功响应必须满足 `success=true` 且 `data.tasks` 是数组；渲染前准备、渲染或适配层异常会显示到页面错误区，不再伪装成空数据，也不会把内部英文错误直接展示给用户。

## 3. 时间和缩放合同

- 页面日期按本地自然日解释。
- `start_date` 表示当天 `00:00:00`。
- `end_date` 对用户表示当天 `23:59:59`。
- 后端查询可以继续使用次日 `00:00:00` 作为 end-exclusive 边界，但页面、提示和测试都按自然日口径解释。
- URL 里的缩放稳定值是：`month`、`week`、`day`、`half-day`、`quarter-day`、`hour`、`fifteen-minute`、`five-minute`、`one-minute`。

## 4. 只读边界

渲染 Frappe Gantt 时固定传入：

- `readonly: true`
- `readonly_dates: true`
- `readonly_progress: true`

这会禁掉拖动、左右拉伸和进度拖动，但保留点击任务条、弹窗、批次聚焦、筛选、配色、关键工序外框和依赖线查看。

`simulate` 模式目前只在 `gantt_adapter.js` 中保留事件出口，不连接保存接口，不创建草稿，也不写正式排产数据。

真实拖动调整入口尚未开放。当前页面上的 `ganttSimulationEntry` 按钮是 disabled 占位按钮。后端已经有保存模拟方案的接口，但模板仍不注入保存按钮，也不打开拖拽编辑；当前页面不能创建 Draft，也不能保存 Scenario。

## 5. Draft 草稿模型与校验试算

后端已经有 `ScheduleAdjustmentDraft` 和 `ScheduleAdjustmentChange` 两张表，用来记录模拟调整草稿里“用户想怎么改”。它们不属于正式排产结果：

- 不写 `Schedule`。
- 不写 `ScheduleHistory`。
- 不写 `ScheduleVersionSeq`。
- 不改变甘特图、周计划、资源排班和报表默认读取的正式版本。

`GanttAdjustmentDraftService` 创建草稿前会确认基准正式版本存在，要求调用方显式传入 `base_plan_role`，并用无回退的方案解析确认这个角色有真实排程明细。当前页面入口仍禁用；本阶段只是模型能力，不是用户可点击的模拟调整功能。

后端现在已有 `GanttAdjustmentValidationService` 和 `POST /scheduler/gantt/adjustments/validate-simulate`。这条链路只读取 Draft 和基准排产，把调整项叠到内存里的临时排程上，然后返回 `valid` / `warning` / `blocked` 以及中文原因。它会检查设备重叠、人员重叠、前后工序倒挂、工作日历、停机、交期和物料齐套，但不会写 `Schedule`、`ScheduleHistory`、`ScheduleVersionSeq`、`ScheduleCandidate*`，也不会调用正式排产或发布流程。

当前页面模板仍没有注入 `validate-simulate` 地址，也没有 `data-adjustment-url`。因此这条接口只是后端能力，页面上没有按钮，用户看不到也点不到。

## 6. Scenario 模拟方案保存与只读预览

后端现在已有 `ScheduleAdjustmentScenario` 和 `ScheduleAdjustmentScenarioRow` 两张表，用来保存通过校验后的模拟方案。Scenario 不是正式排产版本：

- 不写 `Schedule`。
- 不写 `ScheduleHistory`。
- 不写 `ScheduleVersionSeq`。
- 不写 `ScheduleCandidate*`。
- 不改变默认甘特图、周计划、资源排班和报表的正式结果口径。

`POST /scheduler/gantt/adjustments/save-scenario` 会重新执行 Draft 校验。只有 `valid` 和 `warning` 可以保存；`blocked` 会被拒绝。保存成功后 Draft 状态变成 `saved_scenario`，接口只返回模拟方案名称、服务端确认的保存人、中文消息和只读甘特图预览链接；`scenario_id` 只保留在预览链接里作为程序传参，不作为普通 JSON 字段直接暴露。

只读甘特图支持显式 `scenario_id` 预览：

- `SchedulePlanQueryService.resolve_plan_view()` 在有 `scenario_id` 时读取 `ScheduleAdjustmentScenarioRow`。
- 找不到 Scenario、版本不匹配、方案角色不匹配或 Scenario 明细缺失时直接报错，不回退到 `adopted`。
- 时间范围、任务明细、超期标记和关键工序都按 Scenario 行计算。
- 页面、`/scheduler/gantt/data`、视图切换、周切换、查询表单和 `static/js/gantt_boot.js` 会在 URL、隐藏字段和服务端参数里保留 `scenario_id`，用来保证跨页仍查看同一个模拟预览；`scenario_id` 是程序内部身份，不是用户可见名称。
- 页面显示“当前正在预览模拟方案，正式计划还没有改变”。

周计划、资源排班和报表也支持显式 `scenario_id` 预览，但必须区分“程序内部传参”和“用户能看到的文案”：

- 周计划页面和导出复用 `GanttService.get_week_plan_rows(..., scenario_id=...)`，页面表单、导出 URL 和服务端日志可以保留 Scenario 身份；用户可见位置使用 `scenario_display_name`、`scenario_name` 或“模拟预览（未命名）”，不把 `scenario_id` 拼到页面或文件名里。当前证据在 `templates/scheduler/week_plan.html:16`、`templates/scheduler/week_plan.html:96` 和 `core/services/scheduler/week_plan_excel.py:70`。
- 资源排班页面、`/scheduler/resource-dispatch/data` 和导出会把 `scenario_id` 传到 `ResourceDispatchService`，明细行和超期标记都按同一份 Scenario 解析结果计算。
- 资源排班页面和 Excel 摘要会写明模拟预览名称或“模拟预览（未命名）”，并提示“正式计划还没有改变”，不把内部编号当作名称展示。当前证据在 `templates/scheduler/resource_dispatch.html:59`、`templates/scheduler/resource_dispatch.html:160` 和 `core/services/scheduler/resource_dispatch_excel.py:170`。
- 报表页面的超期清单、资源负荷与利用率、停机影响统计会按 Scenario 行计算；对应 Excel 导出也按同一份模拟方案生成，并在摘要里使用模拟预览名称或“模拟预览（未命名）”，不把内部编号当作文件名或表头展示。当前页面提示使用“模拟预览（未命名）”兜底，证据在 `templates/reports/overdue.html:56`、`templates/reports/utilization.html:70`、`templates/reports/downtime.html:77`、`web/routes/reports.py` 的对应报表导出路由和 `tests/regression_scenario_preview_secondary_outputs.py`。
- 计划和现场实际复盘页第一版只复盘“正式采用方案”，不支持模拟预览和对比参考方案。报表页导航跳到 `/reports/execution-review` 时只保留 `version`、`date_from`、`date_to` 和 `batch_id`，不携带 `plan_role` 或 `scenario_id`，避免用户误以为现场事实复盘支持模拟方案。
- Scheduler 主导航和普通报表页导航在预览态会在 URL / 查询参数中保留 `version`、`plan_role` 和 `scenario_id`，避免用户点跨页导航后悄悄掉回正式计划；这些字段不能直接当页面文案、按钮文案、导出列名或导出文件名展示。
- 非法 Scenario 在页面、data 接口和导出入口都必须报错，不允许清掉 `scenario_id` 后展示正式计划。

## 7. Scenario 正式采用

后端现在已有 `GanttAdjustmentPublishService` 和 `POST /scheduler/gantt/adjustments/publish-scenario`。这条链路把已保存的 Scenario 正式采用为新的官方排产版本：

- 必须传入二次确认文本 `正式采用`。
- 必须填写正式采用原因。
- 发布前重新校验来源 Draft，且只允许 `saved_scenario` 状态。
- 发布前要求 Scenario 的基准版本仍然是当前最新正式版本。
- 发布前用保存 Scenario 时的同一批工序复算执行快照；现场状态已经变化时，拒绝发布并回滚。
- 同一事务里分配新版本号、复制 Scenario 行到 `Schedule`、写 `ScheduleHistory`、把 Scenario 和 Draft 标为 `published`。
- 同一事务里写 `OperationLogs`，记录基准版本、新版本、Scenario、Draft、发布人、原因、调整数量和校验结果。
- 发布人来自服务端可信上下文；不会接受客户端自报姓名作为审计身份。
- `OperationLogs` 写入属于发布事务；日志失败时整次发布回滚。
- 不原地修改旧 `Schedule` 版本，不复用版本号，不写 `ScheduleCandidate*`。
- 成功响应只返回新正式版本、服务端确认的发布人、采用原因、中文消息和正式版本查看链接，不返回 `scenario_id`、`source_draft_id` 或执行快照字段。

当前页面仍不开放可点击的正式采用按钮；接口只作为后端能力存在，页面没有正式采用按钮。正式采用成功后调用方应跳转到 `/scheduler/gantt?version=<new_version>&plan_role=adopted`，不要继续携带 `scenario_id`。

## 8. vendor 补丁治理

`static/js/frappe-gantt.min.js` 当前本地补丁说明见 `.codestable/vendor/frappe-gantt-local-patches.md`。vendor 文件当前维护规则是：只有 Frappe 内部时间尺、任务条几何、命中区或事件绑定确实需要改时，才允许继续改 vendor 文件；业务规则优先放到 APS 自己的 `gantt_zoom.js` / `gantt_adapter.js` / `gantt_ui.js` / `gantt_render.js`。

## 9. 变更日志

- 2026-05-25：刷新 Scenario 预览的用户可见口径，明确 `scenario_id / plan_role` 等字段只作为 URL、隐藏字段和服务端参数使用；页面、导出文件名、工作簿摘要和提示语使用模拟预览名称或“模拟预览（未命名）”，不直接展示内部编号。
- 2026-05-27：补充 Scenario 保存和正式采用的执行快照边界；保存和发布成功响应改为用户可见白名单字段，内部追踪字段只留在链接、日志和开发测试追溯里。
