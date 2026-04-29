---
doc_type: feature-acceptance
feature: 2026-04-28-schedule-persistence-auto-assign-contract
status: accepted
created: 2026-04-28
last_reviewed: 2026-04-29
roadmap: p1-scheduler-debt-cleanup
roadmap_item: schedule-persistence-auto-assign-contract
---

# 落库校验与自动分配写回合同验收

## 1. 验收结论

PR-6 已完成落库校验与自动分配写回合同收口。最终复审后，本合同正式吸收 `duplicate_schedule_rows` 与 schema v7 / `idx_schedule_version_op_unique`：先在 payload 层拒绝重复有效 `op_id`，再用数据库唯一索引保护同一版本同一工序不会落入重复 Schedule 行。

本次完成：

- 新增 `tests/test_schedule_persistence_auto_assign_contract.py`，覆盖 `out_of_scope_schedule_rows > duplicate_schedule_rows > invalid_schedule_rows > no_actionable_schedule_rows`、全部非法无可落库行、`simulate=True`、`auto_assign_persist=no`、外协隔离、已有资源不覆盖、只补空字段、missing set 门控，以及 v7 唯一索引正向/负向迁移。
- `simulate=True` 保持现有语义：仍写 Schedule 和 ScheduleHistory 用于追溯，但不改 Batches/BatchOperations 状态，也不持久化自动分配资源。
- 正式排产时，`auto_assign_persist=no` 不补资源；`auto_assign_persist=yes` 也只补内部工序原本缺失的字段，不覆盖已有 machine/operator。
- `build_validated_schedule_payload()` 复杂度登记已由受控脚本移除，技术债台账高复杂度登记从 40 降到 39；最终复审补充的 `duplicate_schedule_rows` 是显式数据完整性合同，不记 full-test-debt 减少。

本次没有做：

- 没有新增写前重读数据库工序的特殊检查；旧对象覆盖风险保留为观察项。
- 没有改 summary、result_summary、页面、route、viewmodel、repo、质量门禁脚本、full-test-debt 脚本或台账脚本运行逻辑；schema 只按本补充记录升到 v7 并新增唯一索引。
- 没有新增 fallback、兜底、静默吞错或宽泛默认值逻辑；唯一新增 public reason 是已记录的 `duplicate_schedule_rows`。
- 没有减少 full-test-debt；active xfail 仍是 5 条 operator-machine/query service 旧登记。

## 2. 改动范围

- `core/services/scheduler/run/schedule_persistence.py`：把落库行校验的既有判断搬到 `_build_validated_schedule_row()`，并显式拒绝重复有效 `op_id`。
- `core/infrastructure/database.py`、`core/infrastructure/migrations/v7.py`、`schema.sql`：纳入 `CURRENT_SCHEMA_VERSION=7` 和 `idx_schedule_version_op_unique`。
- `tests/test_schedule_persistence_auto_assign_contract.py`：新增 PR-6 专项合同测试、schema 唯一索引测试和 v7 迁移正/负向测试。
- `开发文档/技术债务治理台账.md`：用受控脚本刷新复杂度登记，移除 P1-11 对应的 `build_validated_schedule_payload` 高复杂度登记。
- `codestable/features/2026-04-28-schedule-persistence-auto-assign-contract/` 和 `codestable/roadmap/p1-scheduler-debt-cleanup/`：回填 PR-6 验收、items、source-map 和 PR-7 承接边界。

## 3. 债务口径

| 项目 | 结果 |
|---|---|
| full-test-debt | 不减少，仍是 5 条 active xfail |
| `collected_count` | 792 |
| `unexpected_failure_count` | 0 |
| `complexity_count` | 31 |
| `silent_fallback_count` | 153 |
| P1-11 | complexity fixed，复杂度登记已移除 |
| P1-12 | test_coverage evidence-locked，错误优先级与重复排程拒绝合同已补证 |
| P1-13 | test_coverage evidence-locked，simulate/auto-assign persist 合同已补证 |

## 4. 已运行验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_schedule_persistence_auto_assign_contract.py`：8 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --collect-only -q tests | grep -E "tests/test_schedule_persistence_auto_assign_contract.py|tests collected"`：默认收集已包含 8 个 PR-6 专项测试，`792 tests collected`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_schedule_persistence_reschedulable_contract.py tests/regression_schedule_persistence_reject_empty_actionable_schedule.py tests/regression_auto_assign_persist_truthy_variants.py tests/regression_schedule_orchestrator_contract.py tests/regression_schedule_service_reject_no_actionable_schedule_rows.py tests/regression_schedule_service_empty_reschedulable_rejected.py tests/regression_schedule_history_not_created_for_empty_schedule.py`：8 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_system_history_route_contract.py tests/regression_scheduler_analysis_route_contract.py tests/regression_scheduler_batches_degraded_visibility.py tests/regression_reports_page_version_default_latest.py tests/regression_scheduler_week_plan_no_reschedulable_flash.py tests/regression_dashboard_overdue_count_tolerance.py tests/regression_gantt_invalid_summary_surfaces_overdue_degraded.py tests/test_scheduler_resource_dispatch_smoke.py`：29 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold`：1 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_persistence.py tests/test_schedule_persistence_auto_assign_contract.py core/infrastructure/migrations/v7.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_persistence.py core/infrastructure/database.py core/infrastructure/migrations/v7.py`：0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`：通过，`complexity_count=39`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：最终复审通过，`complexity_count=31`，`oversize_count=8`，`silent_fallback_count=153`，`test_debt_count=5`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：最终复审通过，active xfail 仍为 5，`collected_count=792`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/features/2026-04-28-schedule-persistence-auto-assign-contract`：3 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/roadmap/p1-scheduler-debt-cleanup`：3 passed。
- `git diff --check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`：需要在最终提交工作区干净后复跑，当前文档不提前声明 clean proof。

## 5. 复审结论

- 对抗性复审共 8 路：落库合同、测试强度、下游影响、CodeStable 回填、债务证明、无新增兜底、提交边界和总反方。
- 复审确认的问题已修正：删除 `row is None` 静默跳过分支；新增测试改为默认门禁可收集的 `test_*.py`；simulate 增补批次状态断言；外协结果即使在 missing set 中也不写 internal 资源；补齐 YAML 和最终 clean gate 证据。
- 落库合同复审重点：当前错误优先级为 out-of-scope > duplicate > invalid > no-actionable；全部非法但无可落库行仍走 no-actionable 并带 validation_errors。
- 自动分配写回复审重点：测试直接查数据库，证明 simulate、配置关闭、外协、已有资源和只补空字段都符合合同。
- 无新增兜底复审重点：运行代码没有新增 fallback、兜底或静默吞错；`duplicate_schedule_rows` 是本次正式记录的 public reason，不作为隐藏兜底处理。
- 下游影响复审重点：历史、分析页、批次页、报表、甘特图、资源派工等现有读取测试已复跑通过。

## 6. 后续承接

PR-7 可以承接 PR-6 已证明的稳定落库输出：落库前脏结果会被拒绝，模拟排产不会污染真实工序，自动分配资源只补空字段。但 PR-7 不能把 PR-6 的证明当成 `/scheduler/run` route、view result、flash 和跳转已经完成；页面展示合同仍要自己补测试和验收。
