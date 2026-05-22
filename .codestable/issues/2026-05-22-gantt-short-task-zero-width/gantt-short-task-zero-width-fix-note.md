---
doc_type: issue-fix
issue: 2026-05-22-gantt-short-task-zero-width
path: fast-track
fix_date: 2026-05-22
tags: [scheduler, gantt, frontend, frappe-gantt]
---

# 甘特图短工序条形变空修复记录

## 1. 问题描述

在排产甘特图页面，真实存在小于 1 小时的工序时，页面上少数条形会显示成几乎空白，用户很难点中，也不能正常拉宽或缩窄。

压测版本 v15 里确认过的短工序包括：

- `BNX-LONG-036_60`：约 36 分钟。
- `BNX-SHORT-024_10`：约 35.4 分钟。
- `BNX-LONG-036_30`：约 73.2 分钟。

## 2. 根因

后端接口保留了真实 `start` / `end`，没有把短工序裁成 0。

真正问题在本地 Frappe Gantt 前端库：条形宽度原来使用 `diff(end, start, "hour")`，而这个 `diff` 会对小时差执行 `Math.floor(...)`。所以 36 分钟、51 分钟这类工序会被算成 0 小时，最终 SVG 条形宽度变成 `0px`。

同时，拖拽后的时间反算也走整小时加减，短工序即使能被拖动，也可能丢掉分钟级时间。

## 3. 修复方案

修复限定在 Frappe Gantt 本地静态资源内部：

- 条形 `x` 坐标按真实毫秒差计算。
- 条形 `width` 按真实毫秒差计算。
- 拖拽后把像素反算回时间时，继续按同一套毫秒比例计算，避免丢分钟。
- 允许小于一个时间列宽的条形更新宽度。
- 在 Frappe Gantt 的条形内部增加透明命中区 `.bar-hit`，让极短工序能被鼠标稳定点中；真实可见条形宽度仍保持真实时间比例。

没有修改后端排程时间，也没有在 `gantt_render.js` 里做渲染后强撑宽度的补丁。

## 4. 改动文件清单

- `static/js/frappe-gantt.min.js`
  - 修正 Frappe Gantt 内部条形时间到像素、像素到时间的换算。
  - 增加短条透明命中区。
  - 调整左右拖拽手柄位置，避免短条时左右手柄反向。

- `tests/regression_frappe_gantt_short_task_contract.py`
  - 新增短工序回归测试。
  - 覆盖 36 分钟、51 分钟、73 分钟任务的真实条宽。
  - 覆盖小于一天列宽时仍能更新宽度。
  - 锁住修复必须留在 Frappe Gantt 内部，不能退化成外层渲染后补丁。

## 5. 验证结果

- `.venv/bin/python -m pytest tests/regression_frappe_gantt_short_task_contract.py`：通过，2 个用例全部通过。
- `.venv/bin/python tests/regression_frappe_gantt_short_task_contract.py`：通过。
- `.venv/bin/python tests/regression_gantt_critical_outline_sync.py`：通过。
- `.venv/bin/python tests/regression_gantt_layout_contract.py`：通过。
- `git diff --check`：通过。
- 浏览器实测当前页面 `http://127.0.0.1:61661/scheduler/gantt?view=machine&version=15`：
  - `#gantt .bar-wrapper` 数量为 24。
  - `.bar-hit` 数量为 24。
  - `BNX-LONG-036_60` 条形宽度为 `0.95px`，不再是 `0px`。
  - `BNX-SHORT-024_10` 条形宽度为 `0.9341666666666666px`，不再是 `0px`。
  - 短条命中区宽度为 `12px`，方便鼠标点中。

受环境影响未完成的验证：

- `python tests/regression_gantt_contract_snapshot.py` 未通过，阻塞点是临时排产时缺少可选依赖 `networkx==3.1`，报错要求安装 `requirements-optimizer-lite-win7.txt`。这个失败发生在后端排产准备阶段，不是本次 Frappe Gantt 前端修复引起。
- 未运行完整质量门禁；本次只做短工序甘特图修复和路线图文档收口，提交前已跑针对性前端合同测试和文档校验。

## 6. 遗留事项

- 当前修复已经解决短工序条形被算成 `0px` 的根因。
- 后端 `duration_minutes` 仍会把秒级小数向下取整到整分钟，例如 35.4 分钟显示为 35 分钟；这不是本次空条问题的根因，可单独评估是否需要更精细显示。
