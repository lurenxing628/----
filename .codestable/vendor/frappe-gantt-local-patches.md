---
doc_type: vendor-patch
slug: frappe-gantt-local-patches
status: current
created: 2026-05-22
last_reviewed: 2026-05-22
tags: [scheduler, gantt, vendor, win7]
---

# Frappe Gantt 本地补丁说明

## 为什么要有这份说明

项目当前在 Win7 x64 离线部署边界内使用本地 `static/js/frappe-gantt.min.js`，页面不能依赖外部 CDN。这个文件是压缩后的第三方脚本，后续如果直接散改，很难知道哪些地方是 APS 必须保留的本地补丁。

所以任何修改 `static/js/frappe-gantt.min.js` 的动作，都必须同步写清楚原因、改了什么、用什么测试锁住。

## 当前本地补丁点

1. 短工序毫秒宽度
   - 条形宽度按真实开始/结束时间的毫秒差计算。
   - 不再用整小时向下取整，否则 36 分钟、51 分钟这类工序会变成空条。

2. `bar-hit` 透明命中区
   - 很短的工序真实条形仍按真实时长显示。
   - 额外保留最小 12px 透明点击区，方便点击详情。
   - 透明点击区不代表工序时长被放大。

3. 显式午夜结束时间
   - `2026-05-12` 这种纯日期仍可按整天处理。
   - `2026-05-12 00:00:00` 这种明确写出时间的结束点，不能再自动加 24 小时。
   - 这个补丁用于避免 `23:24 -> 次日 00:00` 这类短跨天工序被画成 24 小时以上。

4. 只读模式禁拖
   - `readonly=true` 或 `readonly_dates=true` 时，不绑定任务条拖动和左右拉伸事件。
   - `readonly=true` 或 `readonly_progress=true` 时，不绑定进度拖动事件。
   - 查看模式仍保留点击、弹窗和批次聚焦。
   - 只读模式下没有拖拽手柄，内部条形重算时也会跳过手柄位置更新，避免空节点报错。

5. 点击事件保留
   - 只读模式下不绑定拖动事件，但点击透明命中区仍能打开弹窗并触发页面的任务点击回调。
   - 这用于保留点击详情、批次聚焦这类查看能力。

6. 小时和分钟级 view mode
   - 新增 `Hour`、`Fifteen Minute`、`Five Minute`、`One Minute`。
   - 新增 `step_minutes` / `step_ms`，避免用小数小时走旧的 `h.add(..., "hour")` 后被 `parseInt` 截断。
   - 日期数组、条形宽度、时间反算、今天高亮、滚动定位都按 `step_ms` 计算。
   - 小时/分钟视图里，任务最晚结束点如果刚好是次日 `00:00:00`，时间尺按前一天自然日边界收口；真实任务时长不改，避免单日 1 分钟视图被误扩成两天。

7. 弹窗节点创建
   - 默认弹窗的标题、副标题和箭头节点改为用 DOM API 创建。
   - 这不改变页面显示效果，只是避免本地测试环境或旧浏览器边界下依赖 `innerHTML` 解析空壳标签。
   - 查看模式点击任务条时，弹窗仍应正常打开。

## 不得删除的合同测试

- `tests/regression_frappe_gantt_short_task_contract.py`
  - 短工序宽度
  - 透明点击区
  - 显式 `00:00:00` 结束不扩整天
  - 小时/分钟级宽度和日期步进

- `tests/regression_gantt_readonly_mode_contract.py`
  - 只读模式下用户拖动不改变条形位置
  - 只读模式下用户拉伸不改变条形宽度
  - 只读模式下不触发 `date_change` / `progress_change`
  - 点击任务条仍能触发详情/弹窗

- `tests/regression_gantt_zoom_contract.py`
  - 9 个缩放层级
  - 12 小时、6 小时、小时、15 分钟、5 分钟、1 分钟的步长
  - 分钟级日期数组递增，不死循环

## 后续维护规则

- 优先在 `static/js/gantt_zoom.js` 和 APS 自己的渲染代码里加业务规则。
- 只有确实属于 Frappe 内部时间尺、任务条几何、事件绑定的问题，才允许改 `static/js/frappe-gantt.min.js`。
- 改 vendor 文件时必须同步补测试；没有测试的 vendor 改动不得进入主线。
- 不引入外部 CDN，不要求目标机安装 Python 或联网前端资源。
