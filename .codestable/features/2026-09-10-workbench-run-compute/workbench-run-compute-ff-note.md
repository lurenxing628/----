---
doc_type: feature-note
feature: workbench-run-compute
status: partial
summary: AS 严格输入和无持久化真实候选计算可接合；不代表整个 run 或密集争用容量验收完成
tags: [workbench, scheduling, candidate, readonly]
---

# AS 计算块交接

## 范围

本轮用户已批准亲自实施，只新增 `core/services/workbench/run_input*.py`、`run_compute*.py`、`core/models/workbench_run_compute.py`、`tests/workbench/test_run_compute*.py` 及本目录。没有改旧 preflight、scheduler 算法、shared 调用链、schema/registry、前端或 build。没有生产 DB 操作、commit、创建子任务。

主线程负责 schema v25/entry，AQ 提供唯一执行保护转换，AV 负责持久受理、候选结果台账和恢复。用户已确认分件与瞬时零工时列为后续兼容能力，不伪拆批、不补 epsilon、不改变旧算法合同。

## 公开接口

```python
prepare_candidate_run_input(conn, normalized_input, execution_projections) -> CandidateRunInput
compute_candidate_run(conn, normalized_input, execution_projections, *, version_override=None) -> CandidateRunComputation
compute_prepared_candidate_run(conn, schedule_input, *, version_override=None) -> CandidateRunComputation
restore_execution_projections(payload) -> List[ExecutionProjection]
```

- `run_input.py:52` 入口返回定义于该文件第30行的 `CandidateRunInput`，它是真正的 `ScheduleRunInput` 子类，额外带 `normalized_input/dispositions/facts_fingerprint`；批次和工序是严格验证原始行后直接构造的 `Batch/BatchOperation`，不用 `from_row` 补默认。
- 规范输入沿预检的六字段：`batch_refs/start_date/end_date/ready_check/missing_resource_policy/completed_policy`。空范围拒绝，不替换成全库；原选中批次集合保留，包括有解释的排除批次。
- `execution_projections` 只接 AJ `ExecutionProjection` 实例；范围必须精确等于选中全部工序加每道工序最后正式安排的全集。AS 按永久 `operation_ref` 切给 AQ `build_execution_guardrails_from_projections`，不重新聚合报工、不重算剩余量、不解释第二套 fixed/completed 状态。
- 新选中但无正式 scope 的工序只允许无执行证据的 `unreported`；有执行却丢 scope、未知投影类型/状态、缺项或重复都拒绝。执行目标数量与旧算法批次数量不同也拒绝，不能把单件目标偷偷按整批计算。
- 工序排除沿原批次单链传递；后序不能在前序被排除后继续入选。明确零数量按无需求解释；未知数量/工时不是零。明确零工时保留到真实算法输入。
- 配置只读严格快照，在内存覆盖本次齐套、自动匹配、`auto_assign_persist=no`、`graph_analysis_mode=on`；不 bootstrap 默认配置。`ready_check=False` 不用齐套日期或物料不足再次限制排产。
- 复用真实资源池、人员资格、工厂/人员日历、停机、冻结与原锁定行；已发生执行 seed 由 AQ 提供。所有真实完成候选都独立验证 scope、原 seed 不可移动、窗口及前后序；合并外协组沿用真实同起止块。

## Worker 合同

- worker 使用 `core.services.scheduler.schedule_service._RUN_SCHEDULE_LOCK`，AS 不再次 acquire；受理、事务分配、运行锁与终态持久化均不在本块。
- 计算入口使用 `PRAGMA query_only=ON` 与只读事务，结束恢复原值；不替换调用方 authorizer。已有事务只建 savepoint，不提交调用方事务。
- `CandidateRunInput` 含当前连接的日历对象，不能序列化后直接恢复，不能拿到另一个连接计算。worker 持久保存规范输入与 `Projection.to_dict()`，在事实一致的读快照内恢复 DTO 并重新 prepare。
- `facts_fingerprint` 使用预检的全表和 schema 指纹。`compute_prepared_candidate_run` 会重验，因此 worker 必须在 running/computing 状态写完后 prepare，prepare 与 compute 之间不能再写 stage。AV 自有持久受理指纹排除自己的账本表是 AV 的生命周期约定，不改变本块指纹。
- 不分配正式版本，`version_override` 仅是已有上下文编号，worker 默认不传即可。已有前版时显式传 0 会报 `version_context_unrepresentable`，因为旧编排器会将该 0 回退为前版；新入口不得默许这种改值。调用 `orchestrate_schedule_run(allocate_version=False, persist_schedule_fn=None, simulate=True)`；不调用旧 `run_schedule`，不调用正式/候选持久化助手。
- `CandidateRunComputation` 包含 `schedule_input/orchestration/candidate_payloads/dispositions/state`；`result_persisted` 固定为 false，不能初始化为 true。这里的 complete/partial 只是计算结果，不是新 run 已持久完成或方案可采用。
- `orchestration.candidate_comparison` 是完整真实 `CandidatePlan` 集合及 selection；其中 baseline 的名称是原算法，不是原正式基线。AV 应另存原正式基线。
- `candidate_payloads[candidate_key]` 是 `ValidatedSchedulePayload`：`schedule_rows` 每行带 `op_id/machine_id/operator_id/start_time/end_time/source`，并有 `scheduled_op_ids/assigned_by_op_id`。不能由摘要重造明细。
- `CandidateRunInputError` 提供 `code/reason/issues/can_adopt=False/result_persisted=False`。AQ `AppError` 与算法错误原样传播，不能包装成成功或把 failed 理解成已持久保存。

## 待兼容能力

| 能力 | 当前明确行为 | 具体边界 |
| --- | --- | --- |
| 多分件前后序 | `piece_precedence_adapter_unavailable` | 同一批次出现多个 `piece_id` 时阻断，不改 batch_id 伪拆 |
| 单件/整批目标不一致 | `piece_quantity_adapter_unavailable` | AJ 的 piece 目标为 1，而旧算法从 Batch.quantity 计算时，拒绝错误放大工时 |
| 瞬时零工时 | `zero_duration_candidate_unsupported`，issues 含具体 op_id/operation_ref/batch_id/起止 | prepare 保留 0；真实引擎产出 start=end 后明确不可采用，不丢成无任务，不补 epsilon |
| 密集单资源 5000 工序 | 未通过容量目标 | 340.33 秒未完成并人工中断；100 资源组结果不能替代，见独立证据 |

## 分件专项入口

最小反例固定在 `tests/workbench/test_run_compute_contracts.py:102`：同批 `piece-a/seq=1` 和 `piece-b/seq=2`，真实旧图仍生成一条跨分件边；新适配明确拒绝。

- 上游 `schedule_input_builder.py:23` 的 `OpForScheduleAlgo` 有 piece_id；`graph/input_adapter.py:340` 的 `_raw_snapshot` 没有保留它。
- 根边界 `graph/precedence_builder.py:14` 的 `build_linear_edges_by_batch` 仅按 batch_id 分组。symbol_locator 确认直接调用方是 `graph/analysis_service.py:18` 和 `run/schedule_graph_report.py:151`。
- 下游 `run/schedule_graph_dispatch_context.py:226` 的 `build_graph_ready_context` 将图边交给 ready 队列；`greedy/dispatch/sgs.py:129` 的 `_group_sgs_ops`、`greedy/dispatch/batch_order.py:14` 按批次推进。
- 外协 `greedy/external_groups.py:115` 的 `schedule_external` 使用批次进度和 `(batch_id, ext_group_id)` 缓存；不能仅改图边就宣称真实分件兼容。
- 原执行/锁定影响面还包括 `run/freeze_window_prefixes.py:6` 和 `run/schedule_input_runtime_support.py:241` 的 `_downstream_operations`；后者同样只按 batch_id 与 seq 判断后序。专项不得与 AQ 或 AS 在途文件冲突。
- 零工时的共享拦截点是 `run/schedule_payload_contract.py:152` 的 `_build_validated_schedule_row`，要求 start<end；本块包装真实优化输出，只增加明确不可采用错误，不更改该合同。

## 验证结果

全部测试使用临时 SQLite，运行环境为本机 `.venv/bin/python` **Python 3.8.10**，非 Win7 真机。成功和常规失败均用 `unchanged()` 在 finally 中比对所有 SQLite 表的每一行，并要求 `total_changes` 不变；另测只读 authorizer、外层事务保留、优化中误写及优化后摘要失败。

```text
首轮小规模：45 passed in 5.49s
投影类型收紧后：49 passed in 7.47s
最终小规模（含显式0版本上下文护栏）：50 passed in 1.54s
分散资源容量：1 passed in 109.53s；pytest call 108.63s
单资源压力：no tests ran in 340.33s；KeyboardInterrupt，未通过
AS 全部新产品/测试文件 Ruff：All checks passed!
AS 新产品文件 pyright：0 errors, 0 warnings, 0 informations
```

小规模命令：`.venv/bin/python -m pytest -q tests/workbench/test_run_compute.py tests/workbench/test_run_compute_contracts.py tests/workbench/test_run_compute_execution.py tests/workbench/test_run_compute_integration.py tests/workbench/test_run_compute_readonly.py --disable-warnings --durations=3`。

容量两种负载分开记录在 `evidence/dense-resource-pressure.md` 和 `evidence/distributed-resource-capacity.md`，不合并成“全部容量通过”。用户明确要求不再长时间重复单资源场景。

`scripts/run_quality_gate.py --fast-precheck` 已实际运行，因其他并行文件的 Ruff 检查项失败，例如 `workbench_run_schema.py` 的 UP031、`preflight_execution.py` / `report_facts.py` 的 import 排序。本块未越权修改它们。未跑完整门禁：工作区有大量并行改动，非最终 HEAD，完整门禁不在本次独占计算块的验证承诺内；没有 clean-worktree proof。

全部 AS 文件未提交；原有暂存、未暂存及未跟踪文件保留。下一步由 AV 接合运行生命周期，本块完成不能宣称整个 run/采用流程完成。
