---
doc_type: feature-acceptance
feature: 2026-05-27-shop-exception-feedback
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: shop-exception-feedback
accepted: 2026-05-27
---

# 车间暂停继续和异常反馈验收

## 完成范围

- 资源派工现场反馈任务卡开放“暂停”“继续生产”“报异常”，并保留“开工”“完工”。
- 新增 `POST /pause`、`POST /resume`、`POST /report-exception` 和 `GET /events`。
- `report_exception` 入库仍转成 `event_type=exception`，读回给前端时转成 `action=report_exception`、`action_label=报异常`。
- 页面、任务卡、任务明细、甘特弹窗和导出展示异常原因、严重程度、预计影响时间、影响设备、影响人员、处理状态、是否建议重排和情况说明。
- 普通自动重排遇到异常中工序时返回 `6003 / 409`，中文提示先处理现场异常，并且不写新排程。
- `paused` 状态纳入第 10 项最小重排护栏，普通重排不会随意移动已暂停工序。

## 验收结果

- `processing` 支持暂停、完工、报异常。
- `paused` 支持继续生产、完工、报异常。
- `exception` 支持继续生产、完工。
- `not_started` 不允许直接报异常。
- 暂停和报异常都要求原因和情况说明；报异常要求严重程度。
- 影响时间必须是非负整数；为空时显示“暂时不知道影响多久”。
- 影响设备和影响人员可空；填写时必须能查到，页面和导出显示中文名称。
- 紧急异常会提示“紧急异常，请计划员尽快处理。”，不会自动触发重排。
- 候选方案、模拟预览、历史正式方案、非最新正式方案继续拒绝现场反馈写入。
- 事件列表按每条事件自己的影响时间和影响资源展示，不串用最新异常信息。
- 用户可见文案不显示 `reason_code / severity / handling_status / event_type / report_exception / op_id` 等内部字段或内部编号。

## SubAgent 复审闭环

- 第一轮只读调查 4 个 SubAgent：
  - `019e69a2-5a25-7ba3-9aa0-3836e8f2960f`：后端事件和 service，发现 route/test/异常重排仍缺。
  - `019e69a2-5ac8-79b3-82d7-e92056482e04`：资源派工页面链路，发现 pause/resume/report-exception 未接通。
  - `019e69a2-5b79-77b2-80d7-9a109ad95b68`：普通重排，发现 exception 未阻止自动重排。
  - `019e69a2-5c4f-76f0-8c27-f485f4aeb1d5`：测试夹具和 request service，确认可复用夹具并指出新增测试缺口。
- 第一轮对抗复审 5 个 SubAgent：
  - `019e69b6-5432-7b71-91b9-96bcf5f0d93b`：阻塞 0。
  - `019e69b6-54b4-77e2-a2e4-798db8997e56`：阻塞 1，前端报异常未收集影响设备/影响人员。
  - `019e69b6-5555-7320-9f23-5280f0190245`：阻塞 0。
  - `019e69b6-55f5-7730-a4e5-3d450133f27b`：阻塞 0。
  - `019e69b6-5719-7713-9ea2-4f6215e9166c`：阻塞 0。
- 第二轮复审 2 个 SubAgent：
  - `019e69bd-8c15-7683-a4a1-edb5dc91e839`：阻塞 1，缺 `GET /events`。
  - `019e69bd-8c86-75a1-96d3-af566ae59b3f`：阻塞 2，缺 `GET /events`，且 `reason_detail` 单独填写时不会显示为情况说明。
- 第三轮复审 3 个 SubAgent：
  - `019e69c9-ead3-7701-a290-657756c2f0dd`、`019e69c9-eb69-7a92-ae9e-dca8df5db6e3`、`019e69c9-ec32-7450-a725-5dfd67462905` 都指出同一阻塞：事件列表的历史异常会串用最新异常影响信息。
- 第四轮复审 3 个 SubAgent：
  - `019e69d6-a4cf-7472-bd30-97f2f08687c4`：阻塞 2，ruff import 排序失败、紧急异常缺少“尽快处理”提示。
  - `019e69d6-a557-72b0-a4b1-bf23d4fea84f`：阻塞 0。
  - `019e69d6-a5dd-7e71-b0a8-6efa6571d547`：阻塞 0。
- 第五轮复审 3 个 SubAgent：
  - `019e69e0-408a-77f3-bf93-1e5207bdafef`：阻塞 1，异常中重排拒绝 message 暴露内部 `op_id`。
  - `019e69e0-4143-7231-923f-054720526a7a`：阻塞 0。
  - `019e69e0-41b7-7a21-87e0-0c08f567e08c`：阻塞 0。
- 第六轮复审 3 个 SubAgent：
  - `019e69ea-9e10-7143-96fb-181e242f7e2e`：阻塞 0。
  - `019e69ea-9e96-7cf2-8068-10e4d1303fb6`：阻塞 0。
  - `019e69ea-9f30-7470-b881-1737bd842ea4`：阻塞 0。

最终结论：第 11 项整体复审阻塞项为 0，所有已发现阻塞项均已修复并复审通过。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_feedback_routes.py tests/regression_scheduler_exception_blocks_auto_reschedule.py tests/regression_frontend_offline_static_assets.py`：`26 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_exception_feedback.py tests/regression_operation_execution_feedback_routes.py tests/regression_scheduler_exception_blocks_auto_reschedule.py tests/regression_scheduler_reschedule_execution_minimum_guardrails.py tests/regression_resource_dispatch_public_output_contract.py tests/regression_resource_dispatch_viewmodel_public_output_contract.py tests/regression_resource_dispatch_export_surfaces_degraded.py tests/regression_resource_dispatch_task_id_encoding.py tests/regression_frontend_offline_static_assets.py`：`86 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`：通过。
- CodeStable YAML 校验：feature 目录、roadmap items、roadmap 主文档均通过。
- Python 3.8 语法扫描：通过。
- `git diff --check`：通过。
