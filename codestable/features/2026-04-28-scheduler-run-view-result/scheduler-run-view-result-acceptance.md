---
doc_type: feature-acceptance
feature: 2026-04-28-scheduler-run-view-result
status: accepted
created: 2026-04-28
last_reviewed: 2026-04-28
roadmap: p1-scheduler-debt-cleanup
roadmap_item: scheduler-run-view-result
---

# /scheduler/run ViewResult 验收

## 1. 验收结论

PR-7 已完成 `/scheduler/run` 页面提示收口。本次把原来散在 route 里的展示判断搬到 `RunScheduleViewResult`，让 route 只负责接表单、调用排产服务、构建页面展示结果、flash、异常提示和跳转。

本次完成：

- 新增 `web/viewmodels/scheduler_run_view_result.py`，只消费 `ScheduleService.run_schedule()` 返回的公开 dict，并复用 `build_summary_display_state()`。
- `web/routes/domains/scheduler/scheduler_run.py` 不再直接拆 `summary_display`、`summary` 或 `overdue_batches` 来拼展示细节。
- 新增默认可收集的 `tests/test_scheduler_run_view_result_contract.py`，覆盖成功、失败、公开降级提示、超期样本最多 10 个、跳转目标、普通异常通用提示和 `AppError` 用户文案。
- 复跑已有 `/scheduler/run` 回归，确认部分成功、告警数量、错误预览、无可重排工序错误和 checkbox 三态仍稳定。
- 用受控脚本刷新技术债台账，移除 `run_schedule` 复杂度登记，高复杂度登记从 39 降到 38。

本次没有做：

- 没有做 PR-8 的 `batches_page()`，也没有证明批次筛选、批次行、配置面板或最新历史面板。
- 没有改 `ScheduleService`、summary、result_summary、落库、模板、`scheduler_week_plan.py`、`scheduler_batches.py` 或 `scheduler_bp.py`。
- 没有新增 fallback、兜底、静默吞错、新 reason、新 details 或宽泛默认值逻辑；复审指出的重复消息整理已删除。
- 没有减少 full-test-debt；active xfail 仍是 5 条 operator-machine/query service 旧登记。

## 2. 改动范围

- `web/viewmodels/scheduler_run_view_result.py`：新增 `/scheduler/run` 专用展示结果对象。
- `web/routes/domains/scheduler/scheduler_run.py`：收薄 route，让它只消费 ViewResult。
- `tests/test_scheduler_run_view_result_contract.py`：新增 PR-7 用户可见合同测试。
- `开发文档/技术债务治理台账.md`：由 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 刷新，移除 P1-18 对应复杂度登记。
- `codestable/features/2026-04-28-scheduler-run-view-result/` 和 `codestable/roadmap/p1-scheduler-debt-cleanup/`：回填 PR-7 验收、items、source-map 和 PR-8 承接边界。

## 3. 债务口径

| 项目 | 结果 |
|---|---|
| full-test-debt | 不减少，仍是 5 条 active xfail |
| `collected_count` | 755 |
| `unexpected_failure_count` | 0 |
| `complexity_count` | 38 |
| `silent_fallback_count` | 159 |
| P1-18 | complexity fixed，ui_contract/test_coverage evidence-locked |

## 4. 已运行验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_scheduler_run_view_result_contract.py tests/regression_scheduler_run_no_reschedulable_flash.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py tests/regression_scheduler_route_enforce_ready_tristate.py`：18 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_summary_result_summary_contract.py tests/regression_system_history_route_contract.py tests/regression_scheduler_analysis_route_contract.py tests/regression_scheduler_batches_degraded_visibility.py`：24 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold tests/test_architecture_fitness.py::test_known_complexity_entries_still_exceed_threshold`：2 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check web/routes/domains/scheduler/scheduler_run.py web/viewmodels/scheduler_run_view_result.py tests/test_scheduler_run_view_result_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright web/routes/domains/scheduler/scheduler_run.py web/viewmodels/scheduler_run_view_result.py`：0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`：通过，`complexity_count=38`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`complexity_count=38`，`silent_fallback_count=159`，`test_debt_count=5`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，active xfail 仍为 5，`collected_count=755`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/roadmap/p1-scheduler-debt-cleanup`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/features/2026-04-28-scheduler-run-view-result`：通过。
- `git diff --check`：通过。

## 5. 复审结论

- PR-7 合同复审：无阻塞；确认 `run_schedule()` 只剩表单、服务调用、ViewResult、flash、异常边界和跳转。
- 无新增兜底复审：发现 ViewResult 里多了一层消息默认整理；本轮已删除并复跑目标测试、ruff 和 pyright。
- 共享层影响复审：无阻塞；分析页、系统历史页、排产首页和批次页仍走原共享展示链。
- 测试覆盖复审：无阻塞；按建议补了最小成功态 ViewResult 测试，把 `AppError` flash 改成精确用户文案断言。二次对抗审查后又补了跳转目标断言和普通异常通用提示测试，并把源码字符串守护收窄为“route 不直接拆展示状态”。
- CodeStable 与债务口径复审：确认不能提前写完成；本文件回填时已把 source-map 的 P1-18 改成真实完成口径。
- Python 3.8 与导入顺序复审：无阻塞；目标文件能在 Python 3.8 下解析和导入，wrapper 导入顺序测试通过。

## 6. 后续承接

PR-8 可以承接 PR-7 的结论：`/scheduler/run` 的表单、服务调用、ViewResult、flash、异常边界和跳转已经有测试和复审证据。但 PR-8 不能把这些 proof 当成 `batches_page()` 已经稳定；批次筛选、批次行、配置面板、最新历史面板、latest summary 解析和页面快照仍要在 PR-8 自己证明。
