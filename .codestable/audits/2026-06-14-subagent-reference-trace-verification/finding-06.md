---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "performance-06"
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 06：资源派工和现场任务卡缺精确条件下推

## 速答

资源派工主数据和现场记录任务卡都复用“按时间窗取派工明细”的宽查询接口，`batch_id/schedule_id/op_id` 等精确条件在 Python 里筛。

## 关键证据

- `core/services/scheduler/resource_dispatch_service.py:411-422`：查询层只传时间、版本、方案、资源范围，`batch_id` 在 `_filter_rows_by_batch()` 中 Python 过滤。
- `core/services/scheduler/resource_dispatch_execution_service.py:108-123`：执行上下文有 `batch_id` 时仍先查一批，再列表推导过滤。
- `core/services/scheduler/resource_dispatch_execution_service.py:143-160`、`:185-190`：单任务卡已有 `schedule_id/op_id/batch_id`，仍按任务时间窗查一批，再 `_matching_row()` 找单行。
- `core/services/scheduler/schedule_plan_query_service.py:389-400`：派工查询服务签名没有 `batch_id/schedule_id/op_id`。
- `data/repositories/schedule_plan_query_repo.py:431-454`：仓储 SQL 条件只有时间窗和资源过滤。

## 影响

不是全库全表，但在资源范围不窄或时间窗较大时，会多取不需要的派工行；单任务卡尤其浪费，因为本来已经有唯一身份。

## 修复方向

扩展派工查询接口，支持可选 `batch_id`、`schedule_id`、`op_id`，并在 SQL 层拼等值条件。

## 建议动作

`cs-refactor`，因为主要是查询接口参数补齐和调用点收口，用户行为不变。
