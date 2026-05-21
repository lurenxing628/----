---
doc_type: audit-finding
audit: 2026-05-21-networkx-full-browser-stress
finding_id: gantt-short-task-zero-width
nature: frontend-interaction
severity: P1
confidence: high
status: open
suggested_action: cs-issue
last_deep_trace: 2026-05-21
---

# Finding 05：甘特图短任务真实条宽为 0 或极窄，文字看得到但不能正常拖拽

## 现象

用户在设备甘特图 v15 上指出：大部分任务条可以拖宽拖窄，但少数看起来像“空的”任务条不能正常拖。现场最明显的例子包括 `BNX-LONG-036_60 MCNX-Q1 压测检验1 OPNX-E 压测人员E`。

## 操作步骤

1. 打开 `/scheduler/gantt?view=machine&version=15`。
2. 查看 `BNX-LONG-036_60` 附近的任务条。
3. 尝试像普通任务条一样拖拽调整宽度。

## 实际表现

文字和外框看起来有一整条胶囊，但真正的 `rect.bar` 宽度是 `0`。鼠标点在文字区域并不能拖拽，导致用户感觉“这条是空的，不能拉”。

浏览器 DOM 证据：

```json
{
  "id": "BNX-LONG-036_60",
  "bar.width": "0",
  "bar-progress.width": "0",
  "label.width": 340.4765625,
  "handle.left.width": 8,
  "handle.right.width": 8
}
```

## 期望表现

短工序也应该有一个清楚、可点、可拖的最小可视宽度。tooltip 里仍显示真实开始结束时间，不能把真实工时改长。

## 根因

不是排程数据 0 分钟。临时库只读 SQL 复核：

```text
BNX-LONG-036_60
start = 2026-05-11 08:51:36
end = 2026-05-11 09:27:36
duration = 36.0 分钟
setup_hours = 0.15
unit_hours = 0.15
quantity = 3
```

工时计算也对得上：

```text
(0.15 + 0.15 * 3) * 60 = 36 分钟
```

前端根因是本地 Frappe Gantt 用整小时向下取整算条宽。日视图列宽是 38px/24h：

- 小于 1 小时会被算成 0 小时，所以条宽是 0。
- 1 到 2 小时会被算成 1 小时，所以条宽是 `38 / 24 = 1.583px`。

相关代码链路：

- 后端输出真实分钟数：[core/services/scheduler/gantt_tasks.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/gantt_tasks.py:162)
- 前端直接创建 Gantt：[static/js/gantt_render.js](/Users/lurenxing/Documents/GitHub/----/static/js/gantt_render.js:857)
- Frappe Gantt 用小时差计算宽度：[static/js/frappe-gantt.min.js](/Users/lurenxing/Documents/GitHub/----/static/js/frappe-gantt.min.js:1)
- 文字标签不可作为拖拽命中区：[static/css/aps_gantt.css](/Users/lurenxing/Documents/GitHub/----/static/css/aps_gantt.css:70)

## 追加根因追踪（2026-05-21，4 个子代理交叉核对）

本轮又沿“后端取数 -> API 合同 -> 前端状态 -> Frappe Gantt 内部计算 -> 测试覆盖”完整追了一遍。结论一致：问题不在排产结果本身，而在甘特图显示层把短工序压成了 0px 或极窄区域。

### 后端链路

- 页面入口：[web/routes/domains/scheduler/scheduler_gantt.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_gantt.py:105) 解析 `view/version/start_date/end_date/plan_role`，并渲染甘特图模板。
- 数据入口：[web/routes/domains/scheduler/scheduler_gantt.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_gantt.py:169) 调用 `GanttService.get_gantt_tasks()` 返回 JSON。
- 服务取数：[core/services/scheduler/gantt_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/gantt_service.py:271) 解析版本和方案；[core/services/scheduler/gantt_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/gantt_service.py:322) 调 `list_plan_detail_rows_between()` 按时间重叠取任务。
- 方案明细查询：[core/services/scheduler/schedule_plan_query_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/schedule_plan_query_service.py:167) 先解析 `adopted/baseline_best/critical_best`，再进 repository 查询明细。
- 单任务构造：[core/services/scheduler/gantt_tasks.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/gantt_tasks.py:123) 生成 task；[core/services/scheduler/gantt_tasks.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/gantt_tasks.py:162) 计算 `duration_minutes`；[core/services/scheduler/gantt_tasks.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/gantt_tasks.py:201) 按同批次、同件号、`seq` 补工艺依赖。

后端变量结论：

- `start`、`end`、`duration_minutes`、`schedule_id`、`op_id`、`machine_id`、`operator_id`、`dependencies` 都正常。
- `BNX-LONG-036_50`：`schedule_id=1307`，`op_id=121`，`2026-05-11 08:00:00` 到 `08:51:36`，实际 51 分 36 秒，接口给 `duration_minutes=51`。
- `BNX-LONG-036_60`：`schedule_id=1314`，`op_id=122`，`2026-05-11 08:51:36` 到 `09:27:36`，实际 36 分钟，接口给 `duration_minutes=36`。
- 依赖正常：`BNX-LONG-036_50.dependencies = BNX-LONG-036_40`，`BNX-LONG-036_60.dependencies = BNX-LONG-036_50`。
- v15 adopted 明细 24 行，空时间 0 行，非正时长 0 行。
- 小修正：`duration_minutes` 是按分钟向下取整后的整数，不是带小数的精确分钟；但 `start/end` 是秒级真实时间，所以这不是 0 宽根因。

### 前端链路

- 模板注入 `#gantt` 的 `data-url/view/start/end/version/plan-role`，并按顺序加载脚本：[templates/scheduler/gantt.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/gantt.html:233)。
- 页面初始化读配置并请求 `/scheduler/gantt/data`：[static/js/gantt_boot.js](/Users/lurenxing/Documents/GitHub/----/static/js/gantt_boot.js:183)。
- 接口返回的 `payload.data.tasks` 直接进入 `state.allTasks`：[static/js/gantt_boot.js](/Users/lurenxing/Documents/GitHub/----/static/js/gantt_boot.js:323)。
- 渲染时 `state.filteredTasks = applyFilters(state.allTasks)`，再 `buildRenderTasks()`，最后 `new Gantt("#gantt", tasks, ...)`：[static/js/gantt_render.js](/Users/lurenxing/Documents/GitHub/----/static/js/gantt_render.js:825)。
- `gantt_contract.js` 只克隆任务、转义 `name`、重算依赖，不改 `start/end/duration_minutes/custom_class`：[static/js/gantt_contract.js](/Users/lurenxing/Documents/GitHub/----/static/js/gantt_contract.js:201)。

前端变量结论：

- `task.duration_minutes` 到前端后仍在，但 Frappe Gantt 画条宽时不使用这个字段。
- `task.name` 很长，所以条宽过小时 Frappe 会把文字移到条右侧并加 `.bar-label.big`。
- `.bar-label` 在本项目 CSS 里是 `pointer-events: none`，所以用户点到文字不会命中拖拽区域。

### Frappe Gantt 内部公式

关键代码在本地第三方文件 [static/js/frappe-gantt.min.js](/Users/lurenxing/Documents/GitHub/----/static/js/frappe-gantt.min.js:1)：

```js
diff(t,e,i=s){ ... Math.floor({ ... hours:o ... }[i]) }
this.duration = h.diff(this.task._end, this.task._start, "hour") / this.gantt.options.step
this.width = this.gantt.options.column_width * this.duration
t===w.DAY ? (this.options.step=24, this.options.column_width=38) : ...
```

大白话就是：

- 日视图把 1 天画成 38px。
- 它先把真实时间差换成“整小时数”，不足 1 小时直接向下取整成 0 小时。
- 再用 `38px * 整小时数 / 24` 算条宽。
- 所以 36 分钟是 0px，51 分 36 秒也是 0px；60 到 119 分钟也只有约 1.58px。

这解释了用户指出的现象：屏幕上看见的是很长的文字标签，不是真实可拖拽条。真实可拖区域仍然是 `rect.bar`，宽度是 0 或极窄。

### 为什么现有测试没挡住

已有测试覆盖了甘特图数据合同、版本范围、关键链字段、脚本加载顺序和关键链描边同步，例如：

- [tests/regression_gantt_contract_snapshot.py](/Users/lurenxing/Documents/GitHub/----/tests/regression_gantt_contract_snapshot.py:97)
- [tests/regression_scheduler_candidate_gantt_plan_role_contract.py](/Users/lurenxing/Documents/GitHub/----/tests/regression_scheduler_candidate_gantt_plan_role_contract.py:218)
- [tests/regression_gantt_critical_outline_sync.py](/Users/lurenxing/Documents/GitHub/----/tests/regression_gantt_critical_outline_sync.py:902)
- [tests/regression_scheduler_ui_range_feedback_contract.py](/Users/lurenxing/Documents/GitHub/----/tests/regression_scheduler_ui_range_feedback_contract.py:57)

但缺少两类回归：

- 没有断言“30 到 60 分钟这种短工序在 Day 视图下至少有可点击宽度”。
- 没有真实浏览器拖拽 `.handle.left/.handle.right` 的测试，所以没检查用户能不能真的拖动。

对抗复核补充：Frappe 不只初始宽度会算成 0 或 1.58px，拖拽更新也围绕列宽和条宽计算；所以修复不能只让文字看起来更宽，必须同步真实条、进度条、左右 handle、label 和关键链外框的几何位置。

## 问题类型

前端交互、排版误导。

## 严重程度

明显影响使用。调度员看到任务文字，却点不到真正任务条。

## 证据

- 截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/gantt-current-after-user-comment.png`
- v15 只读 SQL 统计：24 条任务中，小于 60 分钟 6 条，60 到 119 分钟 7 条。
- 典型 0 宽任务：`BNX-SHORT-024_10 35.4m`、`BNX-LONG-036_60 36.0m`、`BNX-LONG-036_50 51.6m`、`BNX-LONG-036_10 55.8m`、`BNX-SHORT-025_10 56.4m`。

## 建议修复方向

最小修复应放在甘特图前端显示层：

- 使用真实分钟数重新同步 SVG 条的 `x/width`，不要让整小时取整决定最终宽度。
- 对短任务增加“最小可视宽度/最小可拖命中宽度”。
- 标签、拖拽手柄、关键链外框要跟着同一个显示宽度同步。
- tooltip 继续显示真实开始时间、结束时间和真实分钟数。

建议补回归：

- 后端合同测试：36 分钟任务 JSON 仍返回真实 `duration_minutes=36`。
- 前端几何测试：36 分钟任务渲染后 `.bar.width` 不再是 `0`。
- 浏览器回归：短任务可以像普通任务一样拖拽。
- 测试数据至少包含小于 1 小时、正好 1 小时、60 到 119 分钟三类任务，避免只修 0px 没修 1.58px。
