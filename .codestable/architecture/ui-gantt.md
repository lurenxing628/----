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

## 2. 前端职责拆分

- `static/js/gantt_zoom.js`：只放时间粒度规格、URL 稳定值、范围保护和估算节点数。
- `static/js/gantt_ui.js`：读取页面控件、读取 URL、把当前状态写回 URL，并同步加载表单和视图切换链接。
- `static/js/gantt_render.js`：过滤任务、做范围保护、创建 Frappe Gantt、挂接点击弹窗和视觉标记。
- `static/js/gantt_contract.js`：集中维护页面帮助、状态文案和任务弹窗里对用户可见的说明。
- `static/js/frappe-gantt.min.js`：本地 vendor 文件，只保留必须落在 Frappe 内部的补丁。

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

## 5. vendor 补丁治理

`static/js/frappe-gantt.min.js` 当前本地补丁说明见 `.codestable/vendor/frappe-gantt-local-patches.md`。后续只有 Frappe 内部时间尺、任务条几何、命中区或事件绑定确实需要改时，才允许继续改 vendor 文件；业务规则优先放到 APS 自己的 `gantt_zoom.js` / `gantt_ui.js` / `gantt_render.js`。
