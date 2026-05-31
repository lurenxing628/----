---
doc_type: issue-fix
slug: resource-dispatch-query-layout
status: done
path: fast-track
created: 2026-05-31
last_reviewed: 2026-05-31
tags:
  - aps
  - frontend
  - resource-dispatch
  - layout
---

# 资源排班查询区排版修复记录

## 1. 问题

资源排班页的查询条件区原来使用通用大网格。人员和设备视角下，“班组轴”字段被隐藏但还占着一个格子，导致“人员”和“区间类型”之间出现一大块空白。

第一次把它改成自适应小格后，空白消失了，但查询和重置按钮被挤到中间窄列里，视觉上像竖排，不符合排班工具的筛选习惯。

第二次改成资源块、时间块、计划块后，按钮不再被挤到中间，但卡片被左右两大块撑开：第一行右侧空、第二行按钮孤悬在右下，整体仍然不像一个稳定的排班查询区。

## 2. 修复

- 先按 Claude Code 的方案把查询表单改成单一 12 列栅格，解决了左右大块撑开的问题。
- 继续浏览器验收后发现：12 列虽然能放下，但上下行字段边缘仍然不齐，肉眼看起来还是歪。
- 最终改成 4 列固定栅格：
  - 第一行：视角、查询对象、班组轴（仅班组视角）或区间类型、查询日期。
  - 第二行：版本、方案、查询 / 重置；方案可跨两列，按钮踩第四列。
  - 自定义区间下：开始日期、结束日期、版本、方案按同一套 4 列线排列，按钮落到下一行左侧。
- 每个字段通过 `dq-*` 类声明栅格位置，避免短字段被强行拉满，也避免上下行边缘错开。
- 人员和设备视角下，“班组轴”字段使用 `hidden` / `display: none` 离开布局，不再留下空格。
- 自定义日期下，版本和方案缩短列宽，保证开始日期、结束日期、版本、方案同排不挤压。
- 小屏下回到单列布局，按钮铺满可用宽度，避免横向溢出。
- 补测试锁住“资源排班使用单栅格布局”“按钮左对齐”“状态类随视角和区间切换”这些规则。
- 2026-05-31 晚间再次交给新的 Claude Code 会话复审。Claude Code 判断 4 列结构可以保留，但指出嵌套在“查询对象”里的 `w-240` 下拉框仍会撑破 4 列格子，导致右边界肉眼不齐。
- 按 Claude Code 的意见补了资源排班查询区的局部控件宽度规则：查询区里的 `select`、日期输入框、文本输入框，以及查询对象里的嵌套下拉框，都必须收进自己的格子宽度内；同时显式固定查询 / 重置按钮贴第二行底部对齐。
- 用户继续指出上下两行之间留白偏大。资源排班查询区的行距从 `16px` 收紧为 `10px`，让两行仍然可区分，但视觉上更像同一个查询表单。

## 3. 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_stable_form_layout_allowlist.py -q`：14 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_stable_form_layout_allowlist.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_resource_dispatch_actual_import.py -q`：55 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_resource_dispatch_site_records_frontend_contract.py -q`：9 passed。
- Claude Code 复审后再次执行：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_stable_form_layout_allowlist.py -q`：14 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_stable_form_layout_allowlist.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_resource_dispatch_actual_import.py -q`：55 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：passed。
  - `node --check static/js/resource_dispatch_core.js`：passed。
- 收紧两行留白后再次执行：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_stable_form_layout_allowlist.py -q`：14 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_stable_form_layout_allowlist.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_resource_dispatch_actual_import.py -q`：55 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：passed。
  - `node --check static/js/resource_dispatch_core.js`：passed。
- 浏览器验证：
  - 1336 x 1029，人员 + 按周：四列坐标对齐，第一行和第二行使用同一套列线。截图：`/tmp/aps-resource-dispatch-query-layout-aligned-4col.png`。
  - Claude Code 复审后重新量尺：人员下拉框从“父格子 232px、控件 240px”的越界状态，修正为父格子约 234px、控件约 234px；方案字段父格子 483px、控件 483px；查询 / 重置按钮底边与方案输入框底边一致。截图：`/tmp/aps-resource-dispatch-query-layout-final-claude-reviewed.png`。
  - 收紧留白后重新量尺：查询区两行行距为 `10px`，查询表单高度约 `135px`。截图：`/tmp/aps-resource-dispatch-query-layout-tight-gap.png`。
  - 1336 x 1029，班组 + 自定义区间：班组轴、开始日期、结束日期、版本、方案均按同一套 4 列线排列。
  - 390 x 844：查询区内可见字段无横向溢出。

## 4. 遗留

当前工作区在本轮开始前已经有较多未提交和未跟踪内容，所以本记录不声明 clean-worktree proof。
