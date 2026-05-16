---
doc_type: issue-fix
issue: gantt-popup-readable-width
status: fixed
severity: medium
root_cause_type: ui-contract
tags:
  - scheduler
  - gantt
  - frontend
---

# 甘特图任务弹窗过窄修复记录

## 问题背景

用户在甘特图点击任务条后，任务详情弹窗会显示批次、设备、人员、工序、时间等信息。某些任务条靠近当前可视区域右侧时，弹窗标题被挤成很窄的一列，长标题只能竖着显示，基本没法阅读。

## 根因

这个问题不在后端排产数据，也不在任务名称生成逻辑。任务名称本身包含批次、设备、人员等业务信息，是应该展示给用户看的。

真正的问题在前端弹窗盒子：

- Frappe Gantt 会把弹窗放在任务条右侧，位置按 SVG 内部横坐标计算。
- 我们自己的弹窗样式只有 `max-width`，没有稳定的 `width` 或 `min-width`。
- 弹窗内容又允许 `overflow-wrap: anywhere`，盒子一旦被浏览器压窄，长标题就会被拆成一小段一小段，最终看起来像竖条。

## 修复内容

- 给主甘特图 `#gantt` 里的弹窗增加稳定宽度和最小宽度，让标题和明细先按可读宽度展示。
- 保留长文字换行能力，避免超长批次号、设备名或人员名撑破页面。
- 增加弹窗打开后的可见区域修正：如果 Frappe Gantt 把弹窗放得太靠右，前端会把弹窗往当前可见区域内收回来。
- 主甘特图 `#gantt` 和资源排班页 `#rdGantt` 都使用同一套可读弹窗宽度，避免同类弹窗在不同页面表现不一致。
- 补充静态回归测试，锁住“弹窗必须有可读宽度”和“打开后会按容器可见区域修正位置”这两个合同。

## 验证结果

- 已用浏览器打开 `/scheduler/gantt?view=machine`，点击用户反馈的同类任务条，确认弹窗已经变成正常宽度，不再被挤成竖条。
- 已执行 `node --check static/js/gantt_render.js`，确认新增前端脚本语法正确。
- 已执行 `node --check static/js/resource_dispatch.js`，确认资源排班页甘特弹窗脚本语法正确。
- 已执行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_layout_contract.py`，结果 3 个测试通过。
- 已执行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_critical_outline_sync.py`，结果 15 个测试通过。
- 已执行 `git diff --check`，没有发现空白格式问题。
