---
doc_type: issue-fix-note
status: fixed
date: 2026-09-14
title: 现场甘特文字层级与现场记录筛选分页对齐
---

## 根因与修复

- 实际甘特 `.fg-wait` 和左侧 `.fg-frozen` 都使用 frozen 层级，轨道没有独立堆叠上下文。横向滚动时提示文字与固定列重叠，`elementFromPoint()` 返回 fg-wait，验证了真实遮挡。
- 为 `frontend/workbench/app/styles/33-gantt-foundation.css` 的 `.fg-live .fg-track` 设置 z-index:0，将轨道内文字和图形限制在固定列下层。
- 现场页通用 `.field-workspace label` 使用 flex-direction:column，导致筛选条件和按钮中心错位，也把共享分页控件里的“每页”文字堆到下拉框上方。
- 在 `frontend/workbench/app/styles/35-field.css` 对筛选标签、分页数量标签明确使用横排居中，报工状态独占一行；其他编辑表单保留原布局。
- 重新离线构建同步 static 下对应两份 CSS 和 asset-manifest.json；没有修改业务算法或数据库。

## 验证与限制

- 构建通过，目标仍为 Chrome109，build_id: `8618529d34d704a68ae3650456908606fba30514a7aaf9bb6c5d4bbb96b78c56`。
- `.venv/bin/python -m pytest -q tests/workbench/test_actual_gantt_ui.py`：2 passed in 7.21s，包含模型及真实 Chrome109 浏览器测试。
- 实际本地页面复现相同横向滚动：同一重叠坐标的顶部元素从 fg-wait 变为 fg-frozen，提示文字不再覆盖冻结列。
- 实际现场页读取元素矩形：搜索框、两日期框、查询和清除按钮均 y=163、height=32；分页数量下拉框与上一页、下一页均 y=574、height=32。截图核对同排显示。
- `git diff --check` 通过。用户明确要求不跑门禁，本轮未运行门禁；不声称整仓通过。
- symbol_locator 不索引上述 JSX 组件，使用 rg 和实际 DOM 定位；其自动重建的 8 份调用图快照本轮起步时干净，已仅恢复这些自动生成的无关变动。
- 保留前轮未提交的图标、菜单名称、相关测试和修复记录、数据库备份。新增本记录及本轮样式/构建变更未提交。项目服务保持运行。
