---
doc_type: issue-fix
issue: 2026-05-28-resource-dispatch-resource-identity-fields
path: standard
fix_date: 2026-05-28
status: completed
severity: P1
tags:
  - scheduler
  - resource-dispatch
  - execution-feedback
  - report
  - frontend
---

# 资源排班资源身份字段修复记录

## 问题

资源排班、现场反馈、甘特弹窗、Excel 导出和计划实际复盘里，设备和人员原来经常显示成一个长字符串。

用户看到时分不清哪部分是编号、哪部分是名称，也不容易判断计划资源和实际资源是不是同一个。

## 根因

资源身份原来只有一个 `label` 字段，编号、名称、用户主显示文本和完整身份文本都挤在一起。

这样会导致两个问题：

- 页面想显示得清楚，只能靠前端猜字符串。
- 导出和报表想换成更好读的文案，也没有稳定字段可用。

## 修复

- 新增 `core/models/resource_identity.py`，统一生成资源编号、名称、主显示文本、完整身份文本。
- 执行事件状态读模型补齐实际设备、实际人员、异常影响设备、异常影响人员的干净字段。
- 资源排班任务明细、日历、甘特弹窗和现场反馈卡片改为主文本显示名称，第二行显示“完整身份”。
- Excel 导出和计划实际复盘导出使用中文可读文本，并在需要时补“完整身份”。
- 对“名称本身已经重复带编号”的压测数据做清理：主显示去掉重复编号，完整身份保留编号。
- 保留旧 `label` 字段作为完整身份，避免已有调用丢信息。

## 第一轮 SubAgent 复审

- `019e6e4f-d6f0-7093-ae6a-58ef9cee7df1`：检查执行事件写入、聚合、路由和响应链路，结论 OK，无阻塞；提醒新增文件必须纳入提交。
- `019e6e50-32fa-7be0-8a5e-ebd09f76ddf9`：检查资源排班页面、导出和前端链路，发现新增文件未跟踪是阻塞；这个会在提交前通过提交清单解决。
- `019e6e50-3369-7583-8fc0-9ba98aa53a09`：检查报表、导出、测试和 CodeStable 闭环，发现旧公开输出契约未更新、甘特弹窗影响资源缺完整身份、缺 fix-note。

## 第一轮阻塞修复

- 更新 `tests/regression_resource_dispatch_viewmodel_public_output_contract.py`：公开主文本接受只显示名称，完整身份字段继续保留编号和名称。
- 更新 `static/js/resource_dispatch.js`：甘特弹窗的异常影响设备、影响人员也显示主文本和“完整身份”。
- 更新 `tests/regression_table_layout_readability_contract.py`：锁住甘特弹窗不再只拼 display 文本。
- 新增本 fix-note，补齐 CodeStable issue 闭环记录。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_resource_identity.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/test_resource_dispatch_viewmodel.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_table_layout_readability_contract.py tests/regression_plan_vs_actual_review.py tests/regression_resource_dispatch_viewmodel_public_output_contract.py tests/regression_resource_dispatch_task_id_encoding.py`
  - 结果：`89 passed`
- `node --check static/js/resource_dispatch.js`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit ...`
  - 结果：未发现 Python 3.8.10 之后才支持的语法或注解兼容风险。
- `git diff --check -- ...`
  - 结果：通过。
- CodeStable frontmatter 校验：
  - report / analysis 通过。

## 浏览器复查

浏览器保持打开在：

`http://127.0.0.1:61731/scheduler/resource-dispatch?version=8&start_date=2026-06-01&end_date=2026-06-30&plan_role=adopted&period_preset=custom`

已刷新同一页面并检查现场反馈卡片：

- 主文本显示资源名称。
- 第二行显示 `完整身份：编号 名称`。
- 护眼模式下仍使用当前页面主题。

## 遗留说明

当前工作区仍有本轮之前的设备 Excel 导入、现场反馈点击和文案修复相关未提交改动。本次没有回退或清理这些已有改动。

新增文件 `core/models/resource_identity.py`、`tests/test_resource_identity.py` 和本 issue 目录需要纳入最终提交范围，避免干净环境缺文件。
