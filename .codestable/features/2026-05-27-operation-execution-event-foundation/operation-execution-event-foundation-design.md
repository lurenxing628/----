---
doc_type: feature-design
feature: 2026-05-27-operation-execution-event-foundation
status: approved
roadmap: aps-three-gap-directions
roadmap_item: operation-execution-event-foundation
created: 2026-05-27
retrospective_backfill: true
---

# 车间执行事件基础设计

## 背景

`Schedule` 表表示计划怎么排，不能拿来覆盖现场实际开工、暂停、完工和异常。`BatchOperations.status` 也没有事件时间、反馈人、原因和幂等信息，不能单独当现场事实源。本阶段新增只追加的执行事件表和状态读模型。

这份设计是回溯补档，用来补齐 CodeStable 事实源。它记录的边界和后续 checklist、acceptance 保持一致。

## 目标

- 新增 `OperationExecutionEvents`，现场事实只追加，不更新、不删除。
- 新增事件模型、状态模型和 repository，repository 负责所有事件 SQL。
- service 负责计划身份校验、状态版本、幂等、合法状态流转和事件写入。
- 状态读模型按事件聚合，不把写入后的 `state_revision` 回写到事件行。
- 数据库和迁移硬检测覆盖字段、外键、CHECK、UNIQUE、索引和默认值。

## 不做

- 不开放普通用户页面入口。
- 不新增 `execution/data`、`start/finish` route。
- 不接入重排护栏、执行快照或算法。
- 不实现纠错、撤销或反冲。

## 实现范围

- `schema.sql`、`core/infrastructure/migrations/v15.py`、`core/infrastructure/migrations/v16.py`、`core/infrastructure/migration_state.py`、迁移注册。
- `core/models/operation_execution_event.py`、`core/models/operation_execution_state.py`、`core/models/operation_execution_labels.py`。
- `data/repositories/operation_execution_event_repo.py`。
- `core/services/scheduler/operation_execution_feedback_service.py`。
- `web/bootstrap/request_services.py`。
- `tests/regression_operation_execution_event_foundation.py`、`tests/regression_operation_execution_state_revision.py`、`tests/regression_migrations.py`。

## 验收口径

- schema、迁移和结构检测一致。
- 幂等键同内容复用，不同内容冲突。
- 状态版本过期拒绝写入。
- 非最新正式 adopted 方案拒绝写入。
- 暂停/异常基础字段和状态聚合存在，但完整页面入口留给后续 feature。
