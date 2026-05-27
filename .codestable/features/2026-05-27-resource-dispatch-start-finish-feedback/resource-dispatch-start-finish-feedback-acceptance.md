---
doc_type: feature-acceptance
feature: 2026-05-27-resource-dispatch-start-finish-feedback
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: resource-dispatch-start-finish-feedback
created: 2026-05-27
---

# 资源派工开工完工反馈验收

## 验收结论

已完成。

本阶段在资源派工页补了“现场反馈”任务卡，让系统能在受控条件下写入开工和完工事件，并能把当前现场状态、实际开始、实际结束、实际设备、实际人员和最近反馈展示出来。为了不让后续重排在保护规则没完成前误动现场事实，普通用户页面按钮仍默认不可写，绕过页面直接提交也会被服务端拒绝。

## 已落地范围

- 新增 `ResourceDispatchExecutionService`，单独读取资源派工现场反馈任务卡，不改变普通资源派工 data 的脱敏规则。
- 新增 `scheduler_resource_dispatch_execution` viewmodel，固定 `execution/data` 返回结构，并统一中文禁用原因、动作中文名和错误响应细节。
- 资源派工页新增“现场反馈”标签页和任务卡容器，前端只按后端 `available_actions` 渲染按钮状态。
- 新增 `GET /scheduler/resource-dispatch/execution/data`，返回任务卡、状态版本、实际时间、实际资源和服务端可用动作。
- 新增 `POST /scheduler/resource-dispatch/execution/<op_id>/start` 和 `/finish`，但普通用户默认 409/6003 拒绝；只有 `TESTING=True` 且带测试专用 header 时才允许写入回归验证。
- `OperationExecutionFeedbackService` 补开工和完工业务校验：操作人员、设备、设备和正式排程匹配、完成数量、报废数量和批次数量上限。
- 普通资源派工 data 增加递归脱敏测试，锁住 `schedule_id / op_id / _row_identity / source_table` 不回流到普通公开 JSON。

## 对抗性审核闭环

- 阶段前调查使用 5 个子代理，分别检查 route/service/repository/viewmodel/template/static/js/test 链路、普通 data 脱敏边界、执行反馈服务校验、前端中文和离线资源、是否越界提前做后续重排或异常反馈。
- 实现后第一轮对抗审核使用 5 个子代理，分别检查写入口保护、任务卡字段和脱敏、开工完工业务校验、前端兼容和越界边界。
- 第一轮发现 1 个阻塞项：正式 `Schedule.machine_id` 为空时，开工校验会跳过设备匹配。已修复为计划设备为空也返回 `schedule_mismatch`，并补回归测试。
- 第一轮还给出若干非阻塞增强，已补成功返回结构、数量非法值、测试 header 只在测试环境有效、普通 data 递归脱敏等测试。
- 修复后复审使用 2 个子代理，分别复查开工/完工校验和普通 data 脱敏/页面边界；结论均为 OK，无阻塞项。
- 第一次推送前门禁又发现 1 个架构阻塞：`web/viewmodels` 层不应导入 service、错误基础设施或共享字段映射；上一版把现场反馈错误响应包装、HTTP 状态码和字段中文名放进了 viewmodel，越过了 ViewModel 只整理页面数据的边界。
- 该架构阻塞已在提交 `673bb066 修复第9项现场反馈视图层边界` 中修复：错误响应包装移回 `scheduler_resource_dispatch` route 层，`scheduler_resource_dispatch_execution` viewmodel 只保留任务卡、动作标签和成功返回数据整理。
- 架构阻塞修复后已再次派子代理 `019e6724-4211-7bb1-b73b-6d76b3a23265` 做同范围复审，重点检查 viewmodel 边界、反馈 route、资源派工契约和页面数据脱敏；结论 OK，无阻塞项。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py`
  - 结果：`11 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_resource_dispatch_contract.py`
  - 结果：`5 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_operation_execution_feedback_routes.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py`
  - 结果：`21 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_operation_execution_feedback_routes.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py`
  - 结果：`22 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/services/scheduler/resource_dispatch_execution_service.py core/services/scheduler/operation_execution_feedback_service.py web/routes/domains/scheduler/scheduler_resource_dispatch.py web/routes/domains/scheduler/scheduler_resource_dispatch_query.py web/bootstrap/request_services.py web/viewmodels/scheduler_resource_dispatch_execution.py tests/regression_operation_execution_feedback_routes.py tests/regression_scheduler_candidate_resource_dispatch_contract.py`
  - 结果：未发现 Python 3.8.10 之后才支持的语法或注解风险。

## 未做

- 不对普通用户放开开工/完工真实提交；按钮放开留给 `reschedule-minimum-execution-guardrails` 同批验收。
- 不新增暂停、继续生产、报异常入口。
- 不新增异常原因、严重程度、处理状态或建议重排页面能力。
- 不接入重排输入、执行快照、冻结窗口或算法。
- 不修改历史 `Schedule.start_time/end_time`。
- 不把 `BatchOperations.status` 当成现场事实源。
- 不新增撤销开工或撤销完工事件。
