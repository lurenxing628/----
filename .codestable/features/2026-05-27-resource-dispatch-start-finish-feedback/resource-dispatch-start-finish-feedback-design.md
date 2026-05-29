---
doc_type: feature-design
feature: 2026-05-27-resource-dispatch-start-finish-feedback
status: approved
roadmap: aps-three-gap-directions
roadmap_item: resource-dispatch-start-finish-feedback
created: 2026-05-27
retrospective_backfill: true
---

# 资源派工开工完工反馈设计

## 背景

执行事件基础完成后，资源派工页需要先有任务卡和受控开工/完工写入，方便后续最小重排护栏上线后放开普通用户操作。在第 10 项完成前，普通用户按钮和直接 POST 必须继续被后端拒绝。

这份设计是回溯补档，用来补齐 CodeStable 事实源。它记录的边界和后续 checklist、acceptance 保持一致。

当前工作区已经完成第 10 项最小现场护栏，所以第 9 项预备好的普通用户开工/完工写入已经按第 10 项要求放开。第 9 项本身的历史边界仍然是“先做任务卡和受控写入，不单独放开普通用户写入”。

## 目标

- 新增现场反馈任务卡读取接口，返回计划身份、状态版本、实际时间、实际资源、最近反馈和可用动作。
- 资源派工页增加“现场反馈”标签页和任务卡容器。
- 新增受控 `start`、`finish` route，用测试专用 header 验证写入链路。
- 第 9 项独立完成时普通用户默认 409/6003 拒绝直接 POST，不写事件；第 10 项完成后，这个保护已经被解除，普通用户开工/完工写入由最小现场护栏承接。
- 候选方案、模拟预览、历史正式方案、非最新正式方案全部拒绝写入。
- 成功写入后返回事件、当前状态、`state_revision` 和刷新后的任务卡。

## 不做

- 第 9 项独立完成时不对普通用户放开开工/完工真实提交；当前第 10 项已经按路线图同批解除该保护。
- 不新增暂停、继续生产、报异常页面入口。
- 不接入重排输入、执行快照、冻结窗口或算法。
- 不改 `Schedule.start_time/end_time`，不把 `BatchOperations.status` 当现场事实。

## 实现范围

- `core/services/scheduler/resource_dispatch_execution_service.py`：读取现场反馈任务卡。
- `web/viewmodels/scheduler_resource_dispatch_execution.py`：整理任务卡和成功响应数据。
- `web/routes/domains/scheduler/scheduler_resource_dispatch.py`：新增 execution data/start/finish route 和错误响应。
- `templates/scheduler/resource_dispatch.html`、`static/js/resource_dispatch.js`：展示现场反馈标签页和任务卡。
- `tests/regression_operation_execution_feedback_routes.py`、`tests/regression_scheduler_candidate_resource_dispatch_contract.py`、`tests/regression_scheduler_dispatch_plan_identity_guardrails.py`。

## 验收口径

- 普通用户按钮和直接 POST 默认不可写。
- 测试专用 header 只在 `TESTING=True` 时放行。
- 开工校验人员和设备，设备必须匹配当前正式排程记录。
- 完工校验完成数量、报废数量格式（非负整数）；不限制合计上限，允许报废补投后产出超过批次数量。
- 页面和错误提示只显示中文字段名。
- 普通资源派工 data 继续脱敏。
