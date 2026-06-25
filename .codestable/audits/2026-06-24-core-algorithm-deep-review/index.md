---
doc_type: audit-index
audit: 2026-06-24-core-algorithm-deep-review
scope: core/services/scheduler 与 core/algorithms 排产主链、图增强、优化搜索、派工、摘要和持久化边界
created: 2026-06-24
status: completed
total_findings: 12
---

# core 和算法层分阶段深度 Review

## 任务边界

- 本轮只做 review，不修改业务代码。
- 允许写入审计 Markdown、调用链证据和必要的只读分析产物。
- 核心范围：
  - `core/services/scheduler/`
  - `core/algorithms/`
- 重点问题：
  - 调用链是否真实闭合。
  - 算法失败、图增强失败、候选方案失败时，是否有静默回退或假装正常。
  - 是否存在过度防御性编程、过度兜底、吞错。
  - 局部修补是否破坏整体最优。
  - 测试和门禁是否真的覆盖关键合同。

## 当前阶段

- Phase 0：范围、工具、调用链摸底，已完成。
- Phase 1：第一轮子代理盲审，已完成。
- Phase 2：主线程逐条复核，已完成第一版。
- Phase 3：对抗复审，已完成。
- Phase 4：完整报告和下一步建议，已完成。

## 调用链工具证据

- `python3 -m tools.symbol_locator callers run_schedule --deep`
- `python3 -m tools.symbol_locator callees run_schedule --deep`
- `python3 -m tools.symbol_locator callers _run_schedule_impl --deep`
- `python3 -m tools.symbol_locator callees _run_schedule_impl --deep`
- `python3 -m tools.symbol_locator callers orchestrate_schedule_run --deep`
- `python3 -m tools.symbol_locator callees orchestrate_schedule_run --deep`
- `python3 -m tools.symbol_locator callers optimize_schedule --deep`
- `python3 -m tools.symbol_locator callees optimize_schedule --deep`
- `python3 .limcode/skills/aps-deep-review/scripts/reference_tracer.py --file ...`

自动报告位置：

- `evidence/DeepReview/reference_trace.md`

注意：`reference_tracer.py` 自身声明它只是启发式线索，最终发现必须回源码核对行号。

## 主调用链速览

```text
web route / tests / tools
  -> core/services/scheduler/schedule_service.py::ScheduleService.run_schedule
  -> ScheduleService._run_schedule_impl
  -> core/services/scheduler/run/schedule_input_collector.py::collect_schedule_run_input
  -> core/services/scheduler/run/schedule_orchestrator.py::orchestrate_schedule_run
  -> schedule_orchestrator._run_plan_selection
  -> schedule_orchestrator._run_optimizer_once 或 schedule_candidate_runner.run_candidate_comparison
  -> core/services/scheduler/run/schedule_optimizer.py::optimize_schedule
  -> core/services/scheduler/run/schedule_signature_support.py::schedule_with_optional_strict_mode
  -> core/algorithms/greedy/scheduler.py::GreedyScheduler.schedule
  -> core/algorithms/greedy/dispatch/sgs.py / batch_order.py
  -> core/algorithms/greedy/internal_operation.py / external_groups.py
```

## 子代理矩阵

| round_id | track | slice | agent_id | 是否盲审 | 状态 | 阻塞数 | 证据 |
|---|---|---|---|---|---|---|---|
| probe | 探针 | 主入口到 GreedyScheduler.schedule | 019ef9ce-53c7-7223-8aeb-4d820a8c88fc | 是 | completed | 0 | 子代理通知 |
| blind-1A | 输入合同 | run_schedule 输入、齐套、停机、资源池 | 019ef9d4-f540-7293-8804-2f68434ee93b | 是 | completed | 3 | 子代理通知 |
| blind-1B | 优化/候选 | optimizer、candidate comparison、selection | 019ef9d5-1cf2-7a43-8827-5a4692c30589 | 是 | completed | 4 | 子代理通知 |
| blind-1C | 图增强 | graph report/on/ready queue/resource matching | 019ef9d5-4ae1-7333-bec4-7c5eb5461ebc | 是 | completed | 2 | 子代理通知 |
| blind-1D | 派工算法 | GreedyScheduler、SGS、batch_order | 019ef9d5-72e6-77f2-894e-a7a5e0e7b713 | 是 | completed | 1 | 子代理通知 |
| blind-1E | 摘要/持久化 | result_summary、ScheduleHistory、candidate persistence | 019ef9d5-9c78-71c1-a960-720d4376b5e0 | 是 | completed | 3 | 子代理通知 |
| blind-1F | 测试/架构 | tests、quality gate、architecture parity | 019ef9d5-c0b3-73d0-a188-c083d09e75ca | 是 | completed | 3 | 子代理通知 |
| adv-1A | 对抗复核 | 主线程结论反证检查 | 019ef9df-60b1-7900-80ca-5ddb9764b2c2 | 否 | completed | 0 | phase-3-adversarial-review.md |
| adv-1B | 对抗盲审 | 主链重新盲扫 | 019ef9df-611a-7b93-94f7-5ea91f3898c1 | 是 | completed | 4 | phase-3-adversarial-review.md |

## 当前确认发现

| id | severity | 结论 |
|---|---|---|
| F-01 | P1 | 部分失败会写入正式版本并自动跳到甘特图；这是当前测试锁定的产品合同，但和“失败不应直接成为可用正式结果”的审查口径冲突。 |
| F-02 | P1 | 停机约束加载或扩展失败后只降级提示，仍可能生成正式排产；停机避让不再是完整硬约束。 |
| F-03 | P1 | 非 strict 模式下坏内部工时会 fallback 成 0.0 并进入算法层；持久化前有时间段校验，不能说一定落库，但坏输入被过度兜底是真的。 |
| F-04 | P1 | 候选对比会强制候选试跑使用 `algo_mode="greedy"`，绕开用户原本可能选择的 `improve` 优化链。 |
| F-05 | P1 | 默认 `balanced` 候选选择允许关键链健康更好的方案覆盖原始总分最佳，且没有校验当前优化目标不变差。 |
| F-06 | P1 | 摘要计数解析没有单源收口：部分路径仍裸 `int(summary.*_ops)`，坏计数可能先崩或让历史/日志和可见摘要不一致。 |
| F-07 | P2 | `graph_analysis_mode=on` 且有环、`graph_block_on_cycle=no` 时按文档允许降级，但顶层 `status="available"` 会弱化告警。 |
| F-08 | P2 | 底层 `simulate=True` 持久化接口会写 `Schedule`/`ScheduleHistory`/候选表，和服务入口“模拟不落库”的含义相反。 |
| F-09 | P2 | 同批次前序失败后，后续被连带跳过的工序只计数，没有逐条错误明细。 |
| F-10 | P2 | 未知派工异常和 OR-Tools 失败的根因在历史摘要/操作日志里会被压成泛化文案，后续只能靠运行日志排查。 |
| F-11 | P2 | 服务层直接调用时，`enforce_ready` 未知字符串会被归一成 `no`，可能关闭齐套门禁；Web 表单入口已有保护。 |
| F-12 | P2 | 关键算法合同多在 full pytest 中，但不少没有进入 required 强保护列表。 |

## 阶段报告

- [phase-0-scope-and-callchain.md](phase-0-scope-and-callchain.md)
- [phase-1-subagent-blind-review.md](phase-1-subagent-blind-review.md)
- [phase-2-main-verification.md](phase-2-main-verification.md)
- [phase-3-adversarial-review.md](phase-3-adversarial-review.md)
- [final-report.md](final-report.md)
