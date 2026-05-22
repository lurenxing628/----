---
doc_type: audit-finding
audit: 2026-05-21-networkx-full-browser-stress
finding_id: missing-resource-message-op-id-only
nature: ux-copy
severity: P1
confidence: high
status: open
suggested_action: cs-issue
last_deep_trace: 2026-05-21
---

# Finding 02：缺资源报错只给内部工序编号，不告诉调度员是哪一批哪道工序

## 现象

排产时选中故意缺设备/人员的批次 `BNX-MISS-101`，页面能正确阻止排产，但提示只显示内部工序编号。

## 操作步骤

1. 打开批次排产页面。
2. 选择 `BNX-MISS-101`。
3. 执行模拟排产。

## 输入数据

- 批次：`BNX-MISS-101`
- 故意留空部分自制工序的设备/人员。

## 实际表现

页面提示：

```text
智能派工计算时发现自制工序缺少设备或人员：工序编号=131
```

## 期望表现

提示应该让调度员能直接去修数据，例如：

```text
批次 BNX-MISS-101 的工序 BNX-MISS-101_10（压测数车）缺少设备或人员，请到批次详情补齐后再排产。
```

## 问题类型

文案难懂。

## 严重程度

明显影响使用。调度员不知道 `工序编号=131` 对应哪个批次、哪个工序、缺什么字段。

## 证据

- 浏览器边界测试已复现。
- 临时库中 `BNX-MISS-101..111` 是本轮故意构造的缺资源批次。

## 追加根因追踪（2026-05-21）

根因不是后端拿不到业务信息。后端当时能拿到批次号、工序号、工种名和缺设备/人员，但 SGS 智能派工评分阶段抛错时，只把内部 `op_id` 拼进了给用户看的报错。

调用链：

- 页面按钮在 [templates/scheduler/_run_panel.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/_run_panel.html:41)，正式排产提交到 `/scheduler/run`，模拟排产提交到 `/scheduler/simulate`。
- 正式排产入口 [web/routes/domains/scheduler/scheduler_run.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_run.py:37) 调 `schedule_service.run_schedule()`。
- 模拟排产入口 [web/routes/domains/scheduler/scheduler_week_plan.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_week_plan.py:389) 也调同一个服务。
- 服务入口 [core/services/scheduler/schedule_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/schedule_service.py:192) 进入 `_run_schedule_impl()`。
- 输入收集阶段 [core/services/scheduler/run/schedule_input_collector.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/run/schedule_input_collector.py:161) 已经记录 `missing_internal_resource_op_ids`，判断逻辑在 [core/services/scheduler/run/schedule_input_collector.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/run/schedule_input_collector.py:169)。
- 但这一步没有直接拦停，真正冒到页面的是 SGS 评分阶段：[core/algorithms/greedy/dispatch/sgs.py](/Users/lurenxing/Documents/GitHub/----/core/algorithms/greedy/dispatch/sgs.py:218) 进入 `_score_candidates()`，再到 [core/algorithms/greedy/dispatch/sgs_scoring.py](/Users/lurenxing/Documents/GitHub/----/core/algorithms/greedy/dispatch/sgs_scoring.py:145) 的 `_score_internal_candidate()`。
- 坏点在 [core/algorithms/greedy/dispatch/sgs_scoring.py](/Users/lurenxing/Documents/GitHub/----/core/algorithms/greedy/dispatch/sgs_scoring.py:164)：`machine_id` 或 `operator_id` 为空时，直接抛 `ValidationError(... 工序编号={meta['op_id']!r})`。
- 页面提示链路在 [web/routes/domains/scheduler/scheduler_user_messages.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_user_messages.py:17) 和 [web/error_boundary.py](/Users/lurenxing/Documents/GitHub/----/web/error_boundary.py:182)。因为这个异常没有 `details.user_message`，最后页面把原始中文异常展示出来。

关键变量：

- `op_id` 来自 [core/algorithms/greedy/dispatch/sgs_scoring.py](/Users/lurenxing/Documents/GitHub/----/core/algorithms/greedy/dispatch/sgs_scoring.py:185) 的 `_candidate_meta()`。
- 批次字段是 `op.batch_id`，本轮样例为 `BNX-MISS-101`。
- 工序字段包括 `op.op_code`、`op.seq`、`op.op_type_id`、`op.op_type_name`，在 [core/services/scheduler/run/schedule_input_builder.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/run/schedule_input_builder.py:190) 已经复制进算法输入。
- 缺失字段是 `op.machine_id`、`op.operator_id`。
- 临时库只读核对：`BatchOperations.id=131` 对应 `BNX-MISS-101_10`，`batch_id=BNX-MISS-101`，`seq=10`，`op_type_id=OTNX-TURN`，`op_type_name=压测数车`，`machine_id/operator_id` 都为空。
- 仓库查询 [data/repositories/batch_operation_repo.py](/Users/lurenxing/Documents/GitHub/----/data/repositories/batch_operation_repo.py:37) 已经 SELECT 了这些字段，模型映射在 [core/models/batch_operation.py](/Users/lurenxing/Documents/GitHub/----/core/models/batch_operation.py:69)。

## 建议修复方向

最小修复点应放在 [core/algorithms/greedy/dispatch/sgs_scoring.py](/Users/lurenxing/Documents/GitHub/----/core/algorithms/greedy/dispatch/sgs_scoring.py:164) 附近。抛 `ValidationError` 前，用 `op.batch_id`、`op.op_code`、`op.seq`、`op.op_type_name`、`op.machine_id/operator_id` 组一条调度员能看懂的消息，并放进 `details["user_message"]`。内部 `op_id` 可以保留在 details 或日志里，但不要作为唯一前台提示。

需要补回归：构造缺设备/人员的 SGS 评分异常，断言 `ValidationError.details["user_message"]` 包含批次、工序、工种、缺设备/人员，并且 `/scheduler/run`、`/scheduler/simulate` 的 flash 展示这条可读消息。
