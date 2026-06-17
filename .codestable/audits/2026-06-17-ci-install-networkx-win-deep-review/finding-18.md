# Finding 18：现场记录任务卡丢弃降级事件，页面会显示“暂无任务卡”

- 优先级：P2
- 结论：资源派工的现场记录链路底层会产出 `degradation_events`，但 viewmodel payload 没有带给前端。当前端没有任务卡时，只能显示“当前查询范围内暂无现场记录任务卡”，无法告诉用户是数据异常导致任务不可用。

## 根因

service 层已经把 `prepare_dispatch_rows()` 的降级事件放进上下文，但 `build_execution_payload()` 重新组装公开 payload 时只保留计划身份、是否可写和任务卡，丢掉了降级事件。

大白话说：后端已经知道“有些数据不对”，但传给页面时把这句话漏掉了，页面只能装作真的没有任务。

## 调用链

- `ResourceDispatchExecutionService.execution_context()`
- `prepare_dispatch_rows(...).events`
- `web/viewmodels/scheduler_resource_dispatch_execution.py::build_execution_payload()`
- `static/js/resource_execution_cards.js`

## 证据

- `core/services/scheduler/resource_dispatch_execution_service.py:125-134`：service context 包含 `degradation_events`。
- `web/viewmodels/scheduler_resource_dispatch_execution.py:339-379`：payload 只返回 `plan_identity`、`plan_identity_label`、`can_write_feedback`、`disabled_reason`、`tasks`。
- `static/js/resource_execution_cards.js:145-147`：没有任务时直接显示“当前查询范围内暂无现场记录任务卡。”
- 主线程只读复现：传入带 `degradation_events` 的 context 后，`build_execution_payload()` 输出 key 为 `['can_write_feedback', 'disabled_reason', 'plan_identity', 'plan_identity_label', 'tasks']`，不含 `degradation_events`。

## 影响

- 用户可能把“数据坏了导致无法生成任务卡”理解成“这个范围本来就没有任务”。
- 这是静默降级，不利于排查现场记录缺失原因。

## 建议

- payload 保留降级事件或整理成用户可读提示。
- 前端无任务卡时优先显示数据异常原因，其次才显示真的无任务。
- 增加测试：有 degradation_events 且 tasks 为空时，页面必须出现异常提示。
