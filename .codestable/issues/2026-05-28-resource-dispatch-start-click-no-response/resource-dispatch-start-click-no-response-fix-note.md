---
doc_type: issue-fix
issue: 2026-05-28-resource-dispatch-start-click-no-response
path: fast-track
fix_date: 2026-05-28
status: completed
severity: P1
tags:
  - scheduler
  - resource-dispatch
  - execution-feedback
  - frontend
---

# 资源排班现场反馈点击无反应修复记录

## 问题

资源排班页进入“现场反馈”后，填写反馈人并点击“开工”，页面没有明显反应，实际开始时间仍显示“暂无”。

修复开工后继续检查，又发现两个连带的用户可见问题：

- 完工填写区在护眼模式下使用了偏亮背景，看起来不像同一个主题。
- 开工后的实际设备、实际人员只显示名称，不显示编号；计划设备、计划人员显示“编号 + 名称”，两边看起来像不是同一个资源。

## 根因

- 前端点击“开工”后先调用浏览器原生 `confirm()`，再用原生 `prompt()` 收集实际设备和实际人员。内置浏览器里这类系统弹窗可能被吞掉或不明显，用户点击后没有后续提示，也没有 POST 到后端。
- 完工输入区使用了不存在的主题变量 `--ui-bg-subtle`，护眼模式下回退成浅色背景。
- 执行事件读模型生成实际资源标签时只返回资源名称，没有像计划资源一样拼上资源编号。

## 修复

- 开工不再依赖系统确认框和输入框。点击“开工”后，前端直接使用当前任务卡上的计划设备和计划人员作为实际设备、实际人员提交。
- 完工不再依赖系统输入框。点击“完工”后，在当前任务卡内展开“完成数量 / 报废数量”输入区，再提交完工。
- 完工输入区背景改用 `--ui-surface-muted`，跟护眼模式主题变量走。
- 执行事件聚合读模型和事件详情标签都统一输出“编号 + 名称”，让计划设备/实际设备、计划人员/实际人员显示口径一致。

## 改动文件

- `static/js/resource_dispatch.js`
- `static/css/ui_contract.css`
- `data/repositories/operation_execution_event_repo.py`
- `core/services/scheduler/operation_execution_feedback_actions.py`
- `tests/regression_operation_execution_feedback_routes.py`
- `tests/regression_operation_execution_exception_feedback.py`
- `tests/regression_operation_execution_event_foundation.py`
- `tests/regression_operation_execution_state_revision.py`

## 验证

- 浏览器实测：填写反馈人后点击第一张卡“开工”，页面显示“开工反馈已提交”，实际开始时间出现，状态变为“生产中”。
- 浏览器实测：点击“完工”后，卡片内出现完成数量输入区；填写 `1` 并提交后，页面显示“完工反馈已提交”，实际结束时间出现，状态变为“已完工”。
- 浏览器复查：第一张卡的计划设备和实际设备都显示 `PX0528A-MILL-MC-02 PX0528A压测MILL-MC-02`，计划人员和实际人员也都显示“编号 + 名称”。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py -q`
  - 结果：`50 passed`
- `git diff --check -- static/js/resource_dispatch.js static/css/ui_contract.css tests/regression_operation_execution_feedback_routes.py data/repositories/operation_execution_event_repo.py core/services/scheduler/operation_execution_feedback_actions.py tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit data/repositories/operation_execution_event_repo.py core/services/scheduler/operation_execution_feedback_actions.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py`
  - 结果：未发现 Python 3.8.10 之后才支持的语法或注解兼容风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 遗留说明

当前工作区在本次修复前已有设备 Excel 导入相关未提交改动、现场反馈文案修复记录和一份未跟踪探索记录。本次没有清理或回退那些已有改动，因此这不是 clean-worktree proof。
