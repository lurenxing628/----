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

- 新增 `OperationExecutionEvents` 表和 v15 迁移，字段覆盖计划身份、工序、批次、动作、反馈时间、实际资源、异常信息、幂等键、服务端指纹、写入前状态版本和反馈人。
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
- 最终复审使用 2 个子代理，分别检查状态流转聚合边界和越界/质量；结论均为 OK，无阻塞项。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_migrations.py`
  - 结果：`22 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/infrastructure/migration_state.py core/infrastructure/migrations/__init__.py core/infrastructure/migrations/v15.py core/models/__init__.py core/models/operation_execution_event.py core/models/operation_execution_state.py core/services/scheduler/__init__.py core/services/scheduler/operation_execution_feedback_service.py core/services/scheduler/operation_execution_labels.py data/repositories/__init__.py data/repositories/operation_execution_event_repo.py web/bootstrap/request_services.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_migrations.py`
  - 结果：未发现 Python 3.8.10 之后才支持的语法或注解风险。
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
