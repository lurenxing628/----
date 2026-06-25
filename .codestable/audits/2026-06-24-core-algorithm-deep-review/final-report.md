---
doc_type: audit-report
audit: 2026-06-24-core-algorithm-deep-review
status: completed
created: 2026-06-24
---

# core 和算法层深度 Review 总报告

## 一句话结论

本轮没有发现“排产主链完全不可用”这种整体崩坏问题，但确认存在 6 个 P1 和 6 个 P2。最需要先处理的是：部分失败仍生成可打开正式版本、停机硬约束失败仍继续排产、坏工时被过度兜底进算法层、候选对比绕开 improve、默认 balanced 可能偏离当前优化目标、摘要计数解析没有单源收口。

## 审查范围

- 服务入口：`ScheduleService.run_schedule`
- 输入收集：批次、工序、齐套、停机、资源池、冻结窗口
- 编排：`orchestrate_schedule_run`
- 优化：`optimize_schedule`、OR-Tools 预热、多起点、本地搜索
- 候选方案：图权重候选、自动选择、候选落库
- 算法：`GreedyScheduler.schedule`、SGS、batch order、内部/外协派工
- 摘要和持久化：`result_summary`、`ScheduleHistory`、OperationLogs
- 测试和门禁：关键合同测试、required 守护清单

## 调用链确认

```text
ScheduleService.run_schedule
  -> _run_schedule_impl
  -> collect_schedule_run_input
  -> orchestrate_schedule_run
  -> _run_plan_selection
  -> _run_optimizer_once 或 run_candidate_comparison
  -> optimize_schedule
  -> schedule_with_optional_strict_mode
  -> GreedyScheduler.schedule
  -> dispatch_sgs / dispatch_batch_order
  -> summary / persistence
```

## P1：优先修

1. 部分失败会生成可打开正式版本
   - 位置：`core/services/scheduler/summary/schedule_summary_freeze.py:72`、`core/services/scheduler/run/schedule_payload_contract.py:203`、`core/services/scheduler/run/schedule_persistence.py:287`、`web/routes/domains/scheduler/scheduler_run.py:60`
   - 大白话：如果一部分工序失败、一部分排出来，系统会写正式版本，并自动跳到甘特图。它会标成“部分成功”，不是假装全成功；但按“失败不应直接成为可用正式结果”的口径，这是高风险合同。
   - 建议：明确 partial 是正式版本还是待确认版本。若不是正式可用结果，改成确认页；若继续允许，结果页、历史页和导出入口必须强提示失败范围。

2. 停机约束失败后继续正式排产
   - 位置：`core/services/scheduler/resource_pool_builder.py:225-236`、`core/services/scheduler/resource_pool_builder.py:351-361`、`core/algorithms/greedy/internal_slot.py:287-313`
   - 大白话：停机表读失败后，系统会提示“停机避让降级”，但仍继续排正式计划。这样可能把任务排到真实停机时间里。
   - 建议：正式排产遇到停机总加载失败直接停；部分失败时阻断受影响设备或相关工序。

3. 坏内部工时 fallback 成 0.0
   - 位置：`core/services/scheduler/run/schedule_input_builder.py:234-253`、`core/shared/field_parse.py:82-93`、`core/algorithms/greedy/internal_slot.py:176-226`、`core/services/scheduler/run/schedule_payload_contract.py:169-176`
   - 大白话：工时写错时，默认模式会当成 0 小时继续送进算法。持久化前有时间段校验，所以不能说一定会落库成零时长排程；问题是坏输入不该先被兜底成算法结果。
   - 建议：正式排产入口拒绝坏工时；兼容 fallback 只放在导入预览或模拟诊断里。

4. 候选对比绕开 improve
   - 位置：`core/services/scheduler/run/schedule_candidate_runtime_helpers.py:33-42`、`core/services/scheduler/run/schedule_candidate_runner.py:97-104`、`core/services/scheduler/run/schedule_orchestrator.py:235-256`、`core/services/scheduler/run/schedule_optimizer_steps.py:215-216`
   - 大白话：用户如果选择了更精细的 improve，候选对比实际会把候选强制改成 greedy 快速排，再把候选结果当正式采用方案。
   - 建议：候选也继承原始 `algo_mode`；如果只跑 greedy，要在页面和摘要里明说。

5. 默认 balanced 可能偏离当前优化目标
   - 位置：`core/services/scheduler/run/schedule_candidate_selection.py:56-90`、`core/services/scheduler/run/schedule_candidate_selection.py:156-169`、`core/models/objective.py:18-45`
   - 大白话：系统默认会“综合判断”，可能为了重点工序更好，选择一个不是当前目标总分最好的方案。比如用户要最少换型，系统却可能因为关键链更健康而选了换型更差的方案。
   - 建议：默认改 `score_only`，或 balanced 覆盖时要求当前目标不变差。

6. 摘要计数解析没有单源收口
   - 位置：`core/services/scheduler/summary/schedule_summary_freeze.py:72-79`、`core/services/scheduler/run/schedule_persistence.py:123-130`、`core/services/scheduler/run/schedule_persistence.py:152-163`
   - 大白话：系统已经有安全解析坏数量的逻辑，但部分地方还直接 `int()` 原始数量。坏数量可能导致摘要还没来得及提示就先崩，或者历史/日志和用户看到的摘要不一致。
   - 建议：完工状态、历史表、操作日志都改用同一份解析后的 count。

## P2：排障和边界收紧

1. 图有环且配置允许继续时，顶层仍是 `status="available"`，容易弱化“本次没用图增强”的提示。
2. 服务层 `simulate=True` 是“不落库”，底层持久化 `simulate=True` 是“写模拟版本但不改正式状态”，同名不同义，容易误用。
3. 同批次后续被连带跳过的工序只增加失败数量，没有错误明细。
4. 未知派工异常和 OR-Tools 预热失败会被压成泛化文案，历史摘要/操作日志里没有结构化根因。
5. 服务层直接调用时，`enforce_ready` 未知字符串会被归一成 `no`，可能关闭齐套门禁；Web 表单入口已有保护。
6. 一些关键算法合同没有进入 required 强保护列表，未来门禁分组变化时保护偏弱。

## 不作为缺陷

- OR-Tools 失败不是完全静默：已有 warning 和 `ortools_warmstart_failed` 降级事件。
- 图有环降级不违反当前架构：文档允许 `graph_block_on_cycle=no` 继续旧 SGS。
- 服务入口模拟不会落库：`ScheduleService.run_schedule(simulate=True)` 没有传持久化函数。
- 停机和坏工时不是“完全无提示”：它们有降级标记；真正问题是提示后仍继续正式排产。
- 多个 rejected attempts 截断没有作为正式缺陷：目前只证明 public attempts 有 12 条上限，未证明关键根因一定丢失。

## 当前状态

- Phase 0 调用链确认：完成。
- Phase 1 子代理盲审：完成。
- Phase 2 主线程复核：完成第一版。
- Phase 3 对抗复审：完成，已按反证修订。
- 业务代码：未修改。
- 本地变更：只有审计 Markdown、调用链工具生成的 callgraph JSON、`evidence/DeepReview/reference_trace.md`。
