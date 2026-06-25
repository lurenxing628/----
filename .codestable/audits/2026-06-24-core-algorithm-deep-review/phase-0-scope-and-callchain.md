---
doc_type: audit-stage
audit: 2026-06-24-core-algorithm-deep-review
stage: phase-0-scope-and-callchain
status: completed
created: 2026-06-24
---

# Phase 0：范围和调用链摸底

## 已确认事实

- 当前分支：`ci/install-networkx-win`。
- 起步时 `git status --short` 无业务代码未提交改动。
- 运行调用链工具后，`.codestable/checkup/latest/callgraph/*.json` 被重建，`evidence/DeepReview/reference_trace.md` 被更新。
- 本轮不会修改业务代码；上述变化属于审计工具产物。

## 真实主链

| 顺序 | 位置 | 说明 |
|---|---|---|
| 1 | `core/services/scheduler/schedule_service.py:197` | `ScheduleService.run_schedule()` 是服务层入口。 |
| 2 | `core/services/scheduler/schedule_service.py:212` | 加锁后进入 `_run_schedule_impl()`。 |
| 3 | `core/services/scheduler/schedule_service.py:253` | 调 `collect_schedule_run_input()` 收集排产输入。 |
| 4 | `core/services/scheduler/schedule_service.py:319` | 调 `orchestrate_schedule_run()` 进入编排。 |
| 5 | `core/services/scheduler/run/schedule_orchestrator.py:288` | 编排入口先调 `_run_plan_selection()`。 |
| 6 | `core/services/scheduler/run/schedule_orchestrator.py:236` | 非候选或候选内部会进入 `_run_optimizer_once()`。 |
| 7 | `core/services/scheduler/run/schedule_orchestrator.py:151` | `_run_optimizer_once()` 调 `optimize_schedule_fn()`。 |
| 8 | `core/services/scheduler/run/schedule_optimizer.py:60` | 默认运行时用 `GreedyScheduler`。 |
| 9 | `core/services/scheduler/run/schedule_signature_support.py:151` | 通过 `schedule_with_optional_strict_mode()` 调度算法。 |
| 10 | `core/algorithms/greedy/scheduler.py:70` | 算法落点是 `GreedyScheduler.schedule()`。 |

## 调用链工具观察

- `run_schedule` 同名函数有两个定义：服务层 `ScheduleService.run_schedule()` 和 route 层 `scheduler_run.run_schedule()`。
- `schedule_service` 这个名字会误命中 `web/bootstrap/request_services.py` 的属性方法，不是排产服务入口。
- `schedule` 同名定义有 `GreedyScheduler.schedule` 和 `SchedulerLike.schedule`，需要结合文件上下文确认。
- 因此本轮不能只靠裸函数名，要把工具结果和源码行号一起核对。

## 阶段结论

- Phase 0 已经确认主链路。
- 探针子代理已完成主链入口审查，未发现可确认问题。
- 仍需对输入收集、候选优化、图增强、SGS 派工、摘要持久化和测试覆盖做分片深读。
