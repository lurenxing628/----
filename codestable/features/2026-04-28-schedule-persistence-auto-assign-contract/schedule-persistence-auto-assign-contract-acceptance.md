---
doc_type: feature-acceptance
feature: 2026-04-28-schedule-persistence-auto-assign-contract
status: accepted
created: 2026-04-28
last_reviewed: 2026-04-28
roadmap: p1-scheduler-debt-cleanup
roadmap_item: schedule-persistence-auto-assign-contract
---

# 落库校验与自动分配写回合同验收

## 1. 验收结论

PR-6 已完成落库校验与自动分配写回合同收口。本次只处理 `schedule_persistence.py`：先用专项测试固定错误优先级、模拟排产和资源写回边界，再把 `build_validated_schedule_payload()` 里的既有判断原样搬到私有 helper，行为不变但复杂度登记关闭。

本次完成：

- 新增 `tests/regression_schedule_persistence_auto_assign_contract.py`，覆盖 `out_of_scope_schedule_rows > invalid_schedule_rows > no_actionable_schedule_rows`、全部非法无可落库行、`simulate=True`、`auto_assign_persist=no`、外协隔离、已有资源不覆盖、只补空字段和 missing set 门控。
- `simulate=True` 保持现有语义：仍写 Schedule 和 ScheduleHistory 用于追溯，但不改 Batches/BatchOperations 状态，也不持久化自动分配资源。
- 正式排产时，`auto_assign_persist=no` 不补资源；`auto_assign_persist=yes` 也只补内部工序原本缺失的字段，不覆盖已有 machine/operator。
- `build_validated_schedule_payload()` 复杂度登记已由受控脚本移除，技术债台账高复杂度登记从 40 降到 39。

本次没有做：

- 没有新增写前重读数据库工序的特殊检查；旧对象覆盖风险保留为观察项。
- 没有改 summary、result_summary、schema、页面、route、viewmodel、repo、质量门禁脚本、full-test-debt 脚本或台账脚本运行逻辑。
- 没有新增 fallback、兜底、静默吞错、新 reason、新 details 或宽泛默认值逻辑。
- 没有减少 full-test-debt；active xfail 仍是 5 条 operator-machine/query service 旧登记。

## 2. 改动范围

- `core/services/scheduler/run/schedule_persistence.py`：把落库行校验的既有判断搬到 `_build_validated_schedule_row()`，保持错误原因和输出形状不变。
- `tests/regression_schedule_persistence_auto_assign_contract.py`：新增 PR-6 专项合同测试。
- `开发文档/技术债务治理台账.md`：用受控脚本刷新复杂度登记，移除 P1-11 对应的 `build_validated_schedule_payload` 高复杂度登记。
- `codestable/features/2026-04-28-schedule-persistence-auto-assign-contract/` 和 `codestable/roadmap/p1-scheduler-debt-cleanup/`：回填 PR-6 验收、items、source-map 和 PR-7 承接边界。

## 3. 债务口径

| 项目 | 结果 |
|---|---|
| full-test-debt | 不减少，仍是 5 条 active xfail |
| `collected_count` | 744 |
| `unexpected_failure_count` | 0 |
| `complexity_count` | 39 |
| `silent_fallback_count` | 159 |
| P1-11 | complexity fixed，复杂度登记已移除 |
| P1-12 | test_coverage evidence-locked，错误优先级合同已补证 |
| P1-13 | test_coverage evidence-locked，simulate/auto-assign persist 合同已补证 |

## 4. 已运行验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_schedule_persistence_auto_assign_contract.py`：4 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_schedule_persistence_reschedulable_contract.py tests/regression_schedule_persistence_reject_empty_actionable_schedule.py tests/regression_auto_assign_persist_truthy_variants.py tests/regression_schedule_orchestrator_contract.py tests/regression_schedule_service_reject_no_actionable_schedule_rows.py tests/regression_schedule_service_empty_reschedulable_rejected.py tests/regression_schedule_history_not_created_for_empty_schedule.py`：8 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_system_history_route_contract.py tests/regression_scheduler_analysis_route_contract.py tests/regression_scheduler_batches_degraded_visibility.py tests/regression_reports_page_version_default_latest.py tests/regression_scheduler_week_plan_no_reschedulable_flash.py tests/regression_dashboard_overdue_count_tolerance.py tests/regression_gantt_invalid_summary_surfaces_overdue_degraded.py tests/test_scheduler_resource_dispatch_smoke.py`：29 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold`：1 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_persistence.py tests/regression_schedule_persistence_auto_assign_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_persistence.py`：0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`：通过，`complexity_count=39`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`complexity_count=39`，`silent_fallback_count=159`，`test_debt_count=5`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，active xfail 仍为 5，`collected_count=744`。
- `git diff --check`：通过。

## 5. 复审结论

- 落库合同复审重点：错误优先级没有改变；全部非法但无可落库行仍走 no-actionable 并带 validation_errors。
- 自动分配写回复审重点：测试直接查数据库，证明 simulate、配置关闭、外协、已有资源和只补空字段都符合合同。
- 无新增兜底复审重点：运行代码只搬移既有判断，没有新增 fallback、兜底、静默吞错、新 reason 或新 details。
- 下游影响复审重点：历史、分析页、批次页、报表、甘特图、资源派工等现有读取测试已复跑通过。

## 6. 后续承接

PR-7 可以承接 PR-6 已证明的稳定落库输出：落库前脏结果会被拒绝，模拟排产不会污染真实工序，自动分配资源只补空字段。但 PR-7 不能把 PR-6 的证明当成 `/scheduler/run` route、view result、flash 和跳转已经完成；页面展示合同仍要自己补测试和验收。
