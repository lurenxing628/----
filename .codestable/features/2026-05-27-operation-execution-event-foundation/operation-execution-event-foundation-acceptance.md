---
doc_type: feature-acceptance
feature: 2026-05-27-operation-execution-event-foundation
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: operation-execution-event-foundation
created: 2026-05-27
---

# 车间执行事件基础验收

## 验收结论

已完成。

本阶段新增车间执行事件基础，把现场事实从计划行里分出来。计划行继续表示“系统原来怎么排”，执行事件表示“现场后来怎么做”。本阶段只做表结构、迁移、仓储、状态聚合、幂等写入、状态版本和服务层合法状态流转；没有新增普通用户的开工、完工、暂停、继续生产或报异常页面入口。

## 已落地范围

- 新增 `OperationExecutionEvents` 表、v15 建表迁移和 v16 修复迁移，字段覆盖计划身份、工序、批次、动作、反馈时间、实际资源、异常信息、幂等键、服务端指纹、写入前状态版本和反馈人。
- `detect_schema_is_current` 同步检测新表、必填字段、默认值、外键、CHECK、UNIQUE、索引列和索引唯一性；缺设备/人员外键也会判定为非当前结构。
- 新增 `OperationExecutionEvent` 和 `OperationExecutionState`，把事件行和聚合状态分开。
- 新增 `OperationExecutionEventRepo`，统一负责执行事件 SQL 和状态聚合。
- 新增 `OperationExecutionFeedbackService`，负责正式计划身份校验、幂等键优先判断、状态版本校验、合法状态流转和事件写入。
- 新增执行动作和状态中文映射，状态“异常中”和动作“报异常”分开处理。
- `request_services` 挂载执行反馈服务，供后续受控 route 使用。
- 新增回归测试覆盖 schema、迁移、仓储、聚合、幂等、状态版本、非正式方案拒绝、合法状态流转和 Python 3.8 兼容。

## 对抗性审核闭环

- 阶段前调查使用 4 个子代理，分别检查 schema/迁移、repository/聚合、service/幂等身份、测试落点。
- 第一轮对抗审核使用 5 个子代理，分别检查迁移结构、repository、service、兼容/测试和越界边界；发现迁移硬检测和包导出问题后已修复。
- 第一轮修复后再审核使用 3 个子代理，分别复查迁移硬检测、导出注册和越界边界；发现合法状态流转没有服务层阻挡后已修复。
- 状态流转修复后使用 3 个子代理复审，分别检查状态流转/幂等、迁移结构和越界边界；发现设备/人员外键检测不足后已修复。
- 外键修复后使用 2 个子代理复审，分别检查状态流转和外键检测、越界和测试覆盖；发现暂停/继续/报异常基础流转测试不足后已补测试。
- 此前复审使用 2 个子代理，分别检查状态流转聚合边界和越界/质量；当时结论均为 OK。
- 本轮按第 4-9 项回溯要求重新打开第 8 项整项复审。已修复新发现阻塞项，最新整项复审阻塞项为 0。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_migrations.py`
  - 结果：`42 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/infrastructure/migration_state.py core/infrastructure/migrations/__init__.py core/infrastructure/migrations/v15.py core/models/__init__.py core/models/operation_execution_event.py core/models/operation_execution_state.py core/services/scheduler/__init__.py core/services/scheduler/operation_execution_feedback_service.py core/services/scheduler/operation_execution_labels.py data/repositories/__init__.py data/repositories/operation_execution_event_repo.py web/bootstrap/request_services.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_migrations.py`
  - 结果：未发现 Python 3.8.10 之后才支持的语法或注解风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 2026-05-27 回溯补充修复和验证

- 回溯复审发现 roadmap 5.6、schema 和实现口径不完全一致：文档写 `machine_id / operator_id`，实现已经按实际资源落到 `actual_machine_id / actual_operator_id`。已回写 roadmap，明确前端提交仍用 `machine_id / operator_id`，service 校验后入库为实际资源字段。
- 回溯复审发现 `suggest_reschedule` 契约应为 `INTEGER NOT NULL DEFAULT 0`，结构检测仍按旧 `yes/no` 判断。已统一 `schema.sql`、v15 迁移、模型、仓储、迁移检测和测试为 `0 / 1`。
- 回溯复审发现暂停/异常基础约束不足。已补数据库结构检测、DB 约束测试和 service 测试：暂停和报异常必须有原因，报异常必须有严重程度。
- 回溯复审发现仓储层倒依赖 service 层中文标签。已把执行状态/动作标签搬到 `core.models.operation_execution_labels`，service 侧保留兼容 re-export，repository 只依赖模型层。
- 回溯复审发现事件时间可倒退。已补 service 校验：同一工序后续事件不能早于上一条事件，完工时间不能早于实际开工时间。
- 回溯复审发现幂等并发窗口：事务外第一次查不到同 key，但事务内状态版本已经被同一次提交消费时，会误报状态过期。已在事务内、状态版本判断前二次查询幂等键，并补测试锁住“同 key 同内容重复提交”必须复用已有事件。
- 本轮整项复审继续发现早期 v15 老库不会自动修到当前执行事件契约。已新增 v16 迁移、升级 `CURRENT_SCHEMA_VERSION=16` 并补老 v15 升级测试。
- 本轮整项复审发现无异常时 `latest_exception_impact_minutes_label / latest_exception_suggest_reschedule_label` 会显示默认文案。已改为空值，布尔字段仍保持 `False`，并补初始、开工后、无异常完工测试。
- 本轮整项复审发现异常字段非法值会漏到底层 DB 约束。已在 service 校验 `reason_code / severity / impact_minutes / affected_machine_id / affected_operator_id / handling_status / suggest_reschedule`，统一返回 `1001` 和中文字段名，不暴露 `db_message`。
- 修复后整项复审继续发现结构检测没有确认索引属于 `OperationExecutionEvents`。已让结构检测按索引名回查归属表，并补“假表同名索引不能通过检测”的迁移测试。
- 修复后整项复审继续发现 `schedule_id / op_id` 外键带级联删除，会把现场事实一起删掉。已移除新库 schema 和迁移里的级联删除，v16 会把早期 v15 表重建到非级联结构，并补“删除父计划行会被阻止，事件仍保留”的测试。
- 修复后整项复审继续发现现场反馈失败 JSON 缺 `details.can_retry`。已在资源派工反馈路由统一补 `can_retry`，并用路由测试锁住常见 400/409 错误。
- 修复后整项复审继续发现架构文档没有记录执行事件现状。已更新 `.codestable/architecture/ARCHITECTURE.md`，补执行事件表、仓储、反馈服务和状态读模型。
- 再次复审发现 v16 老库迁移会被早期 v15 允许但当前不允许的暂停/异常旧行卡死。已让 v16 对这类旧行做有痕修正：缺原因补“其他”、缺严重程度补“一般”、失效资源引用清空并写入迁移说明，保留事件本身，并补老库升级测试。
- 第三轮复审继续发现早期 v15 资源字段为空字符串时仍会触发新外键失败。已让 v16 把旧资源空字符串转成 NULL，并用同一条老库升级测试覆盖空字符串和失效资源引用。
- 第四轮复审发现执行状态读模型按整数分钟截断，和 roadmap 的浮点分钟契约不一致。已把实际耗时和暂停耗时改为浮点分钟，并补 0.5 分钟聚合测试。
- 第四轮复审发现两个连接并发提交同一旧状态时可能漏出数据库锁错误。已让执行反馈写入事务使用 `BEGIN IMMEDIATE` 先拿写锁，并补同幂等键并发复用、不同幂等键并发返回状态过期的测试。
- 第四轮复审提醒第 8 项“未做 route”是当时边界，而当前工作区已有第 9/10 项 route。已确认这是后续条目承接，不属于第 8 项越界。
- 第五轮复审发现结构检测没有确认 `OperationExecutionEvents.id` 是 `INTEGER PRIMARY KEY AUTOINCREMENT`。已补结构检测和反向迁移测试，普通 `id INTEGER` 坏表不能再误判为当前结构。
- 第六轮整项复审发现 v16 对“只缺严重程度”的旧异常行补值时没有留下说明。已让 v16 在 `reason_detail` 写入“严重程度”迁移说明，并补资源正常、仅缺严重程度的老库升级测试。
- 第六轮整项复审发现“暂停中报异常再继续”会把异常处理时间也算进暂停时长。已让异常事件关闭当前暂停段，并补暂停 08:20、异常 08:30、继续 09:00 后暂停时长仍为 10 分钟的测试。
- 第七轮整项复审使用 5 个子代理（`019e6947-5bd0-7d72-9811-733a8304aaba`、`019e6947-5c54-7f41-bbea-d7ee9e63c7b7`、`019e6947-5cfe-7f13-813f-0c1f56e821d2`、`019e6947-5d6c-71c2-b6f1-93b221657f4c`、`019e6947-5e18-7082-af8b-e120c61a6a65`），发现 `handling_status` 为空时中文标签不符合 roadmap 契约，以及 roadmap 第 3.4 节仍描述“没有执行事件”。已把空处理状态展示为“刚上报”，补显式空值测试，并回写 roadmap 当前事实。
- 第八轮整项复审使用 5 个只读子代理（`019e6954-0e79-7d60-b020-e0771817d603`、`019e6954-0efe-7550-9ca9-feee3abaeb3c`、`019e6954-0f7a-7563-b5f0-0b5467722554`、`019e6954-104d-74d0-a7d4-ce55278fdcd6`、`019e6954-115a-7eb1-9ed1-42d1e8d5e33c`）覆盖数据库迁移、模型仓储、服务路由、CodeStable 产物和整体横向；5 个结论均为 OK，阻塞项为 0。非阻塞建议中的 roadmap 行号和组合回归命令记录已补准。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_event_foundation.py tests/regression_migrations.py tests/regression_scheduler_candidate_reports_contract.py`
  - 结果：`63 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_feedback_routes.py tests/regression_migrations.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes`
  - 结果：第 4-9 项整段回归组合 `129 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-27-operation-execution-event-foundation --require doc_type --require status`
  - 结果：`3 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/infrastructure/migration_state.py core/infrastructure/migrations/v15.py core/infrastructure/migrations/v16.py core/models/operation_execution_event.py core/models/operation_execution_labels.py core/models/operation_execution_state.py core/services/report/report_engine.py core/services/scheduler/operation_execution_feedback_service.py core/services/scheduler/operation_execution_labels.py core/services/scheduler/schedule_delay_diagnosis_service.py data/repositories/operation_execution_event_repo.py web/routes/domains/scheduler/scheduler_resource_dispatch.py web/viewmodels/scheduler_resource_dispatch_execution.py tests/regression_migrations.py tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_state_revision.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py`
  - 结果：本阶段相关 Python 文件未发现 Python 3.8.10 之后才支持的语法或注解风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 未做

- 不新增 `/scheduler/resource-dispatch/execution/data`。
- 不新增普通用户 `start`、`finish`、`pause`、`resume`、`report-exception` route。
- 不开放资源派工页面按钮。
- 不接入重排护栏、执行快照或算法。
- 不修改历史 `Schedule.start_time/end_time`。
- 不把 `BatchOperations.status` 当成现场事实源。
- 不实现纠错、撤销或反冲事件。
