---
doc_type: issue-fix
issue: 2026-05-28-resource-dispatch-pause-exception-inline-feedback
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

# 资源排班暂停和报异常按钮无反应修复记录

## 1. 问题描述

在资源排班页进入“现场反馈”后，用户填写反馈人，再点击“暂停”或“报异常”，页面看起来没有任何反应。因为暂停不能顺利提交，用户也无法确认“继续生产”是否可用。

## 2. 根因

“开工”和“完工”已经改成了任务卡内可见的填写方式，但“暂停”“继续生产”“报异常”还在使用浏览器原生输入弹窗收集原因、严重程度、情况说明等字段。

内置浏览器里这类系统弹窗不明显，用户点击按钮后看不到页面内的填写区，也看不到下一步该怎么填，于是表现成“点了没反应”。

## 3. 修复方案

- “暂停”改为在当前任务卡里展开“暂停原因 / 情况说明”表单，提交后再调用原来的后端接口。
- “继续生产”改为在当前任务卡里展开“情况说明”表单，说明可以留空，提交后再调用原来的后端接口。
- “报异常”改为在当前任务卡里展开完整异常表单，字段包括异常原因、严重程度、预计影响分钟、影响设备编号、影响人员工号、处理状态、是否建议重排、情况说明。
- 删除这三类动作对 `window.prompt` 的依赖，保留后端原有字段校验、状态流转、幂等和 `state_revision` 校验。
- 表单样式继续使用护眼模式已有主题变量，避免再次出现亮色块。

## 4. 改动文件清单

- `static/js/resource_dispatch.js`
- `static/css/ui_contract.css`
- `tests/regression_operation_execution_feedback_routes.py`
- `tests/regression_operation_execution_exception_feedback.py`

## 5. 验证结果

- 浏览器实测：在用户当前打开的资源排班页面填写反馈人 `tester`，点击生产中任务卡的“暂停”，页面展开“填写暂停反馈”表单。
- 浏览器实测：选择暂停原因 `设备问题`，填写情况说明 `pause`，提交后任务卡刷新为“已暂停”，最近反馈显示“暂停，pause”。
- 浏览器实测：点击同一任务卡的“继续生产”，页面展开“填写继续生产反馈”表单；提交后任务卡刷新为“生产中”，最近反馈显示“继续生产，resume”。
- 浏览器实测：点击同一任务卡的“报异常”，页面展开“填写异常反馈”表单；填写原因、严重程度、处理状态、建议重排和情况说明后提交，任务卡刷新为“异常中”，最近异常区显示原因、严重程度、预计影响时间、处理状态、建议重排和情况说明。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py`
  - 结果：`20 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py`
  - 结果：`30 passed`
- `node --check static/js/resource_dispatch.js`
  - 结果：通过
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py`
  - 结果：未发现 Python 3.8.10 之后才支持的语法或注解兼容风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 6. SubAgent 对抗性复审

- `019e6e73-ff7a-7d72-8d58-65144843a2d2`（Rawls）：检查前端交互、样式、护眼模式、离线静态资源和 Chrome 109 兼容性；结论 OK，无阻塞问题。
- `019e6e74-2fd0-7703-b25b-9c119f7993a9`（Hilbert）：检查 route、service、repository、读模型、身份护栏、幂等和 `state_revision`；结论 OK，无阻塞问题。
- `019e6e74-55da-7e93-b031-7c6455ab751c`（Godel）：检查测试覆盖和 CodeStable 落档准备；结论 OK，无阻塞问题。
- `019e6e79-4cd2-7520-a275-dd6187f61685`（Gibbs）：检查本轮最终提交包，包括实现、测试、fix-note、文案、兼容性、离线资源和 frontmatter；结论 OK，无阻塞问题。

四位子代理都已关闭。两轮对抗性复审阻塞项为 0，因此不需要修复后再复审。

## 7. 遗留事项

- 本次修复保留了 route 层和 service 层对“最新正式采用方案才可写现场反馈”的双层校验。子代理指出它不够纯粹，但不会放开错误写入，属于非阻塞观察。
- 整个 `.codestable` 目录校验会被 11 个历史无 frontmatter 文件拦住；本次新增 fix-note 已用单文件严格校验通过。
- 本次没有关闭用户当前打开的浏览器页面，方便用户继续批注。
