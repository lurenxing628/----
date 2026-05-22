---
doc_type: architecture
slug: ui-gantt
status: current
created: 2026-05-22
last_reviewed: 2026-05-22
tags: [scheduler, gantt, frontend, readonly, vendor]
---

# 甘特图结果查看架构现状

## 1. 页面入口

- 页面路由：`web/routes/domains/scheduler/scheduler_gantt.py` 的 `/scheduler/gantt`。
- 数据接口：`/scheduler/gantt/data`。
- 经典模板：`templates/scheduler/gantt.html`。
- 现代模板镜像：`web_new_test/templates/scheduler/gantt.html`。

页面把 `data-gantt-mode="view"` 和 `data-zoom-level` 下发给前端。第一版只读甘特图不提供保存按钮，也不调用任何正式写库接口。

页面顶部现在有 `ganttSimulationEntryShell`。它只显示灰色禁用按钮 `模拟调整（后续开放）`，用于告诉用户后续入口位置；当前不会切换 `simulate`，不会发保存请求，也不会产生草稿、模拟方案或正式新版本。

## 2. 前端职责拆分

- `static/js/gantt_zoom.js`：只放时间粒度规格、URL 稳定值、范围保护和估算节点数。
- `static/js/gantt_adapter.js`：把 APS 的查看/模拟模式、缩放等级和回调翻译成 Frappe Gantt options，并负责创建 Gantt 实例。
- `static/js/gantt_ui.js`：读取页面控件、读取 URL、把当前状态写回 URL，并同步加载表单和视图切换链接。
- `static/js/gantt_render.js`：过滤任务、做范围保护、通过适配层创建 Frappe Gantt、挂接点击弹窗和视觉标记。
- `static/js/gantt_contract.js`：集中维护页面帮助、状态文案和任务弹窗里对用户可见的说明。
- `static/js/frappe-gantt.min.js`：本地 vendor 文件，只保留必须落在 Frappe 内部的补丁。
- `static/css/aps_gantt_simulation.css`：只放模拟调整入口壳样式，避免继续扩大主甘特图样式文件职责。

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

真实拖动调整入口尚未开放。当前页面上的 `ganttSimulationEntry` 按钮是 disabled 占位按钮。后端已经有保存模拟方案的接口，但模板仍不注入保存按钮，也不打开拖拽编辑；用户必须通过后续模拟调整入口创建 Draft 后，才能保存 Scenario。

## 5. Draft 草稿模型与校验试算

后端已经有 `ScheduleAdjustmentDraft` 和 `ScheduleAdjustmentChange` 两张表，用来记录后续模拟调整里“用户想怎么改”。它们不属于正式排产结果：

- 不写 `Schedule`。
- 不写 `ScheduleHistory`。
- 不写 `ScheduleVersionSeq`。
- 不改变甘特图、周计划、资源排班和报表默认读取的正式版本。

`GanttAdjustmentDraftService` 创建草稿前会确认基准正式版本存在，要求调用方显式传入 `base_plan_role`，并用无回退的方案解析确认这个角色有真实排程明细。当前页面入口仍禁用；本阶段只是模型能力，不是用户可点击的模拟调整功能。

后端现在已有 `GanttAdjustmentValidationService` 和 `POST /scheduler/gantt/adjustments/validate-simulate`。这条链路只读取 Draft 和基准排产，把调整项叠到内存里的临时排程上，然后返回 `valid` / `warning` / `blocked` 以及中文原因。它会检查设备重叠、人员重叠、前后工序倒挂、工作日历、停机、交期和物料齐套，但不会写 `Schedule`、`ScheduleHistory`、`ScheduleVersionSeq`、`ScheduleCandidate*`，也不会调用正式排产或发布流程。

当前页面模板仍没有注入 `validate-simulate` 地址，也没有 `data-adjustment-url`。因此这条接口只是后续模拟调整入口的后端合同，还不是用户可点击功能。

## 6. Scenario 模拟方案保存与只读预览

后端现在已有 `ScheduleAdjustmentScenario` 和 `ScheduleAdjustmentScenarioRow` 两张表，用来保存通过校验后的模拟方案。Scenario 不是正式排产版本：

- 不写 `Schedule`。
- 不写 `ScheduleHistory`。
- 不写 `ScheduleVersionSeq`。
- 不写 `ScheduleCandidate*`。
- 不改变默认甘特图、周计划、资源排班和报表的正式结果口径。

`POST /scheduler/gantt/adjustments/save-scenario` 会重新执行 Draft 校验。只有 `valid` 和 `warning` 可以保存；`blocked` 会被拒绝。保存成功后 Draft 状态变成 `saved_scenario`，返回 `scenario_id` 和只读甘特图预览链接。

只读甘特图支持显式 `scenario_id` 预览：

- `SchedulePlanQueryService.resolve_plan_view()` 在有 `scenario_id` 时读取 `ScheduleAdjustmentScenarioRow`。
- 找不到 Scenario、版本不匹配、方案角色不匹配或 Scenario 明细缺失时直接报错，不回退到 `adopted`。
- 时间范围、任务明细、超期标记和关键工序都按 Scenario 行计算。
- 页面、`/scheduler/gantt/data`、视图切换、周切换、查询表单和 `static/js/gantt_boot.js` 都会保留 `scenario_id`。
- 页面显示“当前正在预览模拟方案，正式计划还没有改变”。

## 7. vendor 补丁治理

`static/js/frappe-gantt.min.js` 当前本地补丁说明见 `.codestable/vendor/frappe-gantt-local-patches.md`。后续只有 Frappe 内部时间尺、任务条几何、命中区或事件绑定确实需要改时，才允许继续改 vendor 文件；业务规则优先放到 APS 自己的 `gantt_zoom.js` / `gantt_adapter.js` / `gantt_ui.js` / `gantt_render.js`。
