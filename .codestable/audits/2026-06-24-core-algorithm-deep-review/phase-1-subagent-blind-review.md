---
doc_type: audit-stage
audit: 2026-06-24-core-algorithm-deep-review
stage: phase-1-subagent-blind-review
status: completed
created: 2026-06-24
---

# Phase 1：子代理盲审

本阶段按自然链路拆片。每个子代理只读代码，不修改文件。

## 子代理输出汇总

| track | 子代理 | 结论 | 主线程处理 |
|---|---|---|---|
| 探针 | 019ef9ce-53c7-7223-8aeb-4d820a8c88fc | 主入口到 `GreedyScheduler.schedule` 未发现确认问题；OR-Tools 失败不是完全静默，会有 warning 和降级事件。 | 采纳；OR-Tools 只保留为诊断粒度不足。 |
| 输入合同 | 019ef9d4-f540-7293-8804-2f68434ee93b | 停机加载失败继续排产、坏工时 fallback 为 0、`enforce_ready` 直接传未知字符串会变 no。 | 停机与坏工时升为确认问题；`enforce_ready` 限定为直接服务调用风险。 |
| 优化/候选 | 019ef9d5-1cf2-7a43-8827-5a4692c30589 | 候选对比强制 greedy，绕开 improve；balanced 可能覆盖当前目标；OR-Tools 根因不进摘要；attempts 截断缺标记。 | 全部采纳，但 OR-Tools 和 attempts 作为 P2 诊断问题。 |
| 图增强 | 019ef9d5-4ae1-7333-bec4-7c5eb5461ebc | `on + 有环 + block=no` 降级继续；balanced 覆盖局部健康。 | 图有环按架构文档降为 P2 展示弱化；balanced 与优化目标问题合并到 F-04。 |
| 派工算法 | 019ef9d5-72e6-77f2-894e-a7a5e0e7b713 | 同批次后续跳过只计数不补错误明细。 | 采纳为 P2；不升级为“失败装成功”，因为 `failed_count` 会增加。 |
| 摘要/持久化 | 019ef9d5-9c78-71c1-a960-720d4376b5e0 | 坏 `scheduled_ops` 可能在降级摘要前崩；持久化和日志裸用原始 count；底层 simulate 会写表。 | 采纳；计数单源破裂列 P1，simulate 语义冲突列 P2。 |
| 测试/架构 | 019ef9d5-c0b3-73d0-a188-c083d09e75ca | simulate 上下层含义相反；候选默认 balanced 缺完整端到端覆盖；关键合同没全部进 required。 | 采纳边界债和测试缺口；未把“缺少整体最优证明”写成源码缺陷。 |

## 重要分流说明

- “完全静默回退”与“可见降级但继续排”分开处理。停机、坏工时、OR-Tools 都不是同一类问题。
- 停机失败已有 `downtime_avoid_degraded` 可见提示，但它仍允许正式排产继续，所以问题核心是硬约束失败没有阻断。
- 坏工时已有 `input_fallback` 降级标记，但它仍可能把坏输入变成 0 小时排程，所以问题核心是坏输入进入正式结果。
- OR-Tools 预热失败已有 warning 和降级计数，所以不报“静默吞错”；只报诊断信息不足。
- 图有环且 `graph_block_on_cycle=no` 是架构文档允许的行为，所以不报“违反文档”；只报顶层状态容易弱化告警。
- `ScheduleService.run_schedule(simulate=True)` 当前不会落库；底层 `persist_schedule(... simulate=True)` 会落库，这是命名和边界风险，不是当前主入口直接落库 bug。

## 子代理覆盖文件概览

- `core/services/scheduler/schedule_service.py`
- `core/services/scheduler/run/schedule_input_collector.py`
- `core/services/scheduler/run/schedule_input_builder.py`
- `core/services/scheduler/resource_pool_builder.py`
- `core/services/scheduler/run/schedule_orchestrator.py`
- `core/services/scheduler/run/schedule_optimizer.py`
- `core/services/scheduler/run/schedule_candidate_runner.py`
- `core/services/scheduler/run/schedule_candidate_selection.py`
- `core/services/scheduler/run/schedule_graph_report.py`
- `core/services/scheduler/run/schedule_graph_dispatch_context.py`
- `core/services/scheduler/summary/schedule_summary.py`
- `core/services/scheduler/summary/schedule_summary_freeze.py`
- `core/services/scheduler/run/schedule_persistence.py`
- `core/algorithms/greedy/scheduler.py`
- `core/algorithms/greedy/dispatch/sgs.py`
- `core/algorithms/greedy/dispatch/batch_order.py`
- `core/algorithms/greedy/run_state.py`
- `tests/algorithm/`
- `tests/scheduler_graph/`
- `tests/candidate/`
- `tests/schedule/`
- `tools/test_registry_data.py`
