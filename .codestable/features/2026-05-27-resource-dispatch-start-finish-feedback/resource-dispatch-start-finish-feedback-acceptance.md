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

本阶段在资源派工页补了“现场反馈”任务卡，让系统能在受控条件下写入开工和完工事件，并能把当前现场状态、实际开始、实际结束、实际设备、实际人员和最近反馈展示出来。

第 9 项独立完成时，为了不让后续重排在保护规则没完成前误动现场事实，普通用户页面按钮仍默认不可写，绕过页面直接提交也会被服务端拒绝。当前工作区已经完成第 10 项最小现场护栏，所以第 9 项预备好的普通用户开工/完工写入已经按第 10 项要求放开，当前事实不能再描述成“普通用户仍被拒绝”。

## 已落地范围

- 新增 `ResourceDispatchExecutionService`，单独读取资源派工现场反馈任务卡，不改变普通资源派工 data 的脱敏规则。
- 新增 `scheduler_resource_dispatch_execution` viewmodel，固定 `execution/data` 返回结构，并统一中文禁用原因、动作中文名和错误响应细节。
- 资源派工页新增“现场反馈”标签页和任务卡容器，前端只按后端 `available_actions` 渲染按钮状态。
- 新增 `GET /scheduler/resource-dispatch/execution/data`，返回任务卡、状态版本、实际时间、实际资源和服务端可用动作。
- 新增 `POST /scheduler/resource-dispatch/execution/<op_id>/start` 和 `/finish`。第 9 项独立完成时普通用户默认 409/6003 拒绝，只有 `TESTING=True` 且带测试专用 header 时才允许写入回归验证；第 10 项完成后普通用户写入已按路线图解除保护。
- `OperationExecutionFeedbackService` 补开工和完工业务校验：操作人员、设备、设备和正式排程匹配、完成数量和报废数量格式（非负整数）；完工合计不设上限，允许报废补投后产出超过批次数量。
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
- 本轮第 4-9 项回溯整项复审使用 5 个只读子代理（`019e695f-2d19-7762-9327-cf4237002dfb`、`019e695f-2dc4-75a3-a62e-3a24a37f7dd1`、`019e695f-2e6e-76c1-baa8-b133c68a525b`、`019e695f-2f81-73b3-a25b-78ffc600b757`、`019e695f-301b-75b0-8124-c818d3d01a6b`）覆盖后端写入、任务卡/viewmodel、前端、CodeStable 产物和整体横向。已修复复审发现的事实源阻塞：第 9 项文档按独立阶段写保护中，但当前工作区已经因第 10 项解除保护；同时补充说明当前工作区混有多个条目，本轮不作为第 9 项独立提交证据。
- 修复后第二轮整项复审继续使用 5 个只读子代理（`019e696b-00ec-72e0-8822-dc320bd77321`、`019e696b-01a3-79a2-be81-156402c5b01a`、`019e696b-0257-7d52-830e-9c5356c8b538`、`019e696b-0350-71b0-b2a6-7fd99fd34ef3`、`019e696b-051f-72e1-9362-7356b482cc99`），发现状态不允许操作的错误提示缺少下一步，以及 items.yaml 第 9 项漏列任务卡读取 service 和 viewmodel。已把 `invalid_state_transition` 中文提示改成带刷新和联系计划员处理的下一步说明，补 route 测试，并回写第 9 项 `primary_paths`。
- 第三轮整项复审继续使用 5 个只读子代理（`019e6974-37cc-7503-b073-376ffc1a2651`、`019e6974-38d0-7501-81e9-74122467df3a`、`019e6974-3960-7c83-a8dd-8d53dbccdccc`、`019e6974-39ed-7d33-84d0-ceee5903dc94`、`019e6974-3b39-7b53-a09c-07f8797db348`），发现两条验收测试记录数字过期。已按当前工作区复跑结果回写为 `24 passed` 和 `55 passed`，并重新跑过对应命令。
- 第四轮整项复审继续使用 5 个只读子代理（`019e697e-1b79-7673-8d57-f341809a4cf7`、`019e697e-1c10-7762-97d6-8a82dcfe7617`、`019e697e-1cad-7cd1-b9e7-937e2cf9e7a2`、`019e697e-1dcb-71c0-854d-fd8820a00c22`、`019e697e-1eb0-78f0-9d54-17be5b68a132`），发现 roadmap 5.9 和 items 第 9 项 POST 字段清单漏 `batch_id`，以及单跑 route 测试记录仍是旧数字。已把 `batch_id` 补入 roadmap 和 items 字段清单，并把 route 测试结果回写为 `13 passed`。
- 第五轮整项复审继续使用 5 个只读子代理（`019e6988-4ec8-7211-a790-7edb2de756a8`、`019e6988-4f4f-7910-aad2-6f3302ddf67e`、`019e6988-4fdf-7cb3-b004-8c35ae659db6`、`019e6988-512a-7510-90d8-4fd982603917`、`019e6988-52de-7173-af8d-810501fd60e1`），覆盖第 9 项整项产物和当前第 10 项已解除写入保护后的边界；结论均为 OK，无阻塞项。非阻塞提醒是后续若做独立提交，需要重新分拣混合工作区并补 clean-worktree 证据。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py`
  - 结果：`13 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_resource_dispatch_contract.py`
  - 结果：`5 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_operation_execution_feedback_routes.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py`
  - 结果：`23 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_operation_execution_feedback_routes.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py`
  - 结果：`24 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/services/scheduler/resource_dispatch_execution_service.py core/services/scheduler/operation_execution_feedback_service.py web/routes/domains/scheduler/scheduler_resource_dispatch.py web/routes/domains/scheduler/scheduler_resource_dispatch_query.py web/bootstrap/request_services.py web/viewmodels/scheduler_resource_dispatch_execution.py tests/regression_operation_execution_feedback_routes.py tests/regression_scheduler_candidate_resource_dispatch_contract.py`
  - 结果：未发现 Python 3.8.10 之后才支持的语法或注解风险。

## 2026-05-27 回溯补充修复和验证

- 回溯复审发现直接 POST 的计划身份上下文缺少 `batch_id`，route 还会补默认身份字段。已改成 route 只收参传参，service 硬校验 `schedule_id / schedule_version / op_id / batch_id / requested_plan_role / source_table / effective_plan_role`，并把 `batch_id` 纳入服务端指纹。
- 回溯复审发现设备不存在、设备不匹配和数量小数的错误口径不符合第 9 项 exit checks。已统一为 `1001 / 400`、中文字段名和 `invalid_field_value`，并拒绝小数、布尔值、非整数文本。
- 回溯复审发现任务卡 `unavailable_reasons` 是列表，不利于前端按动作展示原因。已改为按动作键保存的对象，前端仍兼容旧列表展示。
- 回溯复审发现 `execution/data` 任务卡没有返回 roadmap 5.9 要求的最近异常中文字段。已补 `latest_exception_reason_label / severity_label / impact_minutes_label / affected_machine_label / affected_operator_label / handling_status_label / suggest_reschedule_label`，并补任务卡契约测试。
- 回溯补测直接 POST：缺计划身份字段返回 400；`batch_id` 不匹配返回 409；开工后早于开工时间完工返回 409；事件写入数量保持不变。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_event_foundation.py tests/regression_migrations.py`
  - 结果：`55 passed`
- 第 4-9 项整段回归组合结果：`104 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-27-resource-dispatch-start-finish-feedback --require doc_type --require status`
  - 结果：`3 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/infrastructure/migration_state.py core/infrastructure/migrations/v15.py core/models/operation_execution_event.py core/models/operation_execution_labels.py core/services/report/report_engine.py core/services/scheduler/operation_execution_feedback_service.py core/services/scheduler/operation_execution_labels.py core/services/scheduler/schedule_delay_diagnosis_service.py data/repositories/operation_execution_event_repo.py web/routes/domains/scheduler/scheduler_resource_dispatch.py web/viewmodels/scheduler_resource_dispatch_execution.py tests/regression_migrations.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_state_revision.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py`
  - 结果：本阶段相关 Python 文件未发现 Python 3.8.10 之后才支持的语法或注解风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 未做

- 第 9 项独立完成时不对普通用户放开开工/完工真实提交；当前第 10 项已经按路线图同批解除该保护，并由最小现场护栏承接。
- 不新增暂停、继续生产、报异常入口。
- 不新增异常原因、严重程度、处理状态或建议重排页面能力。
- 不接入重排输入、执行快照、冻结窗口或算法。
- 不修改历史 `Schedule.start_time/end_time`。
- 不把 `BatchOperations.status` 当成现场事实源。
- 不新增撤销开工或撤销完工事件。
- 本轮回溯复审不做第 9 项单独提交；当前工作区同时包含第 10 项和其他条目改动，最终提交前必须重新分拣暂存区和未暂存内容，不能把混合工作区当成第 9 项独立提交证据。
