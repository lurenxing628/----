---
doc_type: feature-acceptance
feature: 2026-04-28-scheduler-summary-result-summary-contract
status: accepted
created: 2026-04-28
last_reviewed: 2026-04-29
roadmap: p1-scheduler-debt-cleanup
roadmap_item: scheduler-summary-result-summary-contract
---

# Summary 与历史回放合同验收

## 1. 验收结论

PR-5 已完成 summary/result_summary 合同补证。初次验收只补测试和 CodeStable 追踪文档；最终复审后，当前分支已在 `schedule_summary_assembly.py` 运行路径调用 `compact_attempts(list(ctx.attempts or []), limit=12)`，确保 rejected diagnostics 不会被普通 attempts 截断挤掉。

本次完成：

- 走通 `build_result_summary -> persist_schedule -> ScheduleHistoryRepository.get_by_version -> json.loads`，证明 `result_summary` 写入历史再读回后形状稳定。
- 读回后的 `result_summary.algo.attempts` 全量检查：不含 `candidate_rejected`，不含 `source`、`tag`、`used_params`、`algo_stats`、`origin`。
- `diagnostics.optimizer.attempts` 在正常大小下随历史 JSON 落库并读回，rejected 诊断保留 `origin.type`、`origin.field`、`origin.message`；`schedule_summary_assembly.py` 运行时先用 `compact_attempts()` 压缩 attempts，再交给公开投影。
- 构造 `INTERNAL_OPTIMIZER_SECRET` 放进内部 diagnostics 后，真实访问分析页、系统历史页、排产首页、周计划页、甘特图、资源排班页、报表入口和报表子页，这些响应均不出现这个内部词。
- PR-5 的 `web/routes/normalizers.py` 和 `web/viewmodels/scheduler_summary_display.py` 只做边界核对和静态检查，没有在页面层补二次过滤。

本次没有做：

- 没有改 `summary_schema_version=1.2`。
- 没有改 `OptimizationOutcome` 字段或优化器主逻辑。
- 没有新增 fallback、兜底、静默吞错或宽泛默认值逻辑；最终复审的 runtime 改动只复用已有 `compact_attempts()`。
- 没有在模板、route 或 viewmodel 里补过滤来掩盖上游问题。
- 没有减少 full-test-debt；active xfail 仍是 5 条 operator-machine/query service 旧登记。

## 2. 改动范围

- `tests/regression_scheduler_summary_result_summary_contract.py`：新增 summary 到历史落库读回测试，以及真实页面 HTML 不泄漏内部 diagnostics 测试。
- `codestable/features/2026-04-28-scheduler-summary-result-summary-contract/`：新增 PR-5 design、checklist、acceptance 三件套。
- `core/services/scheduler/summary/schedule_summary_assembly.py`：最终复审后在运行装配点复用 `compact_attempts()`，让公开 attempts 与 diagnostics 使用同一压缩事实源。
- `codestable/roadmap/p1-scheduler-debt-cleanup/`：回填 PR-5 执行状态、验证命令、PR-6 头部承接和 M4 完成结果。

## 3. 债务口径

| 项目 | 结果 |
|---|---|
| full-test-debt | 不减少，仍是 5 条 active xfail |
| `collected_count` | 744 |
| `unexpected_failure_count` | 0 |
| `complexity_count` | 40 |
| `silent_fallback_count` | 153 |
| schema 版本 | 仍是 `summary_schema_version=1.2` |
| 是否关闭 old P1 | 没有关联 old P1，不关闭 |

## 4. 已运行验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_summary_result_summary_contract.py`：2 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_optimizer_public_summary_projection_contract.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_schedule_summary_v11_contract.py tests/regression_schedule_service_passes_algo_stats_to_summary.py tests/regression_scheduler_summary_result_summary_contract.py`：10 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_system_history_route_contract.py tests/regression_scheduler_analysis_route_contract.py tests/regression_scheduler_batches_degraded_visibility.py tests/regression_reports_page_version_default_latest.py`：25 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_week_plan_no_reschedulable_flash.py tests/regression_dashboard_overdue_count_tolerance.py tests/regression_gantt_invalid_summary_surfaces_overdue_degraded.py`：3 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/summary/schedule_summary.py core/services/scheduler/summary/schedule_summary_assembly.py core/services/scheduler/summary/optimizer_public_summary.py core/services/scheduler/run/schedule_persistence.py web/routes/normalizers.py web/viewmodels/scheduler_summary_display.py tests/regression_optimizer_public_summary_projection_contract.py tests/regression_system_history_route_contract.py tests/regression_scheduler_summary_result_summary_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/summary/schedule_summary.py core/services/scheduler/summary/schedule_summary_assembly.py core/services/scheduler/summary/optimizer_public_summary.py core/services/scheduler/run/schedule_persistence.py web/routes/normalizers.py web/viewmodels/scheduler_summary_display.py`：0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，active xfail 仍为 5，`collected_count=744`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`complexity_count=40`，`silent_fallback_count=159`，`test_debt_count=5`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/roadmap/p1-scheduler-debt-cleanup`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/features/2026-04-28-scheduler-summary-result-summary-contract`：通过。
- `git diff --check`：通过。
- M4 完整收口后，在干净工作区复跑 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`：通过。

## 5. Subagent 复审

- 落库/历史读回复审：无阻塞；确认新增测试走了真实 `build_result_summary -> persist_schedule -> ScheduleHistoryRepository.get_by_version -> json.loads`。复审建议把公开 attempts 从第一条检查加严为全量检查，本次已修。
- 页面不泄漏复审：无阻塞；确认测试使用真实 `app.create_app()` 和真实 HTML，不是 stub `render_template`，并且 secret 先真实进入 diagnostics。
- 无新增兜底对抗复审：无阻塞；最终复审 runtime 改动只复用已有 `compact_attempts()`，没有在模板/route/viewmodel 里补过滤。
- CodeStable 回填复审：无阻塞；提醒 acceptance 必须逐条写清验证、full-test-debt 口径、PR-6 承接和 checklist 收口，本文件已回填。

## 6. 后续承接

PR-6 可以承接完整 M4 的结果：优化器输出、summary 投影、历史落库读回和页面展示均已有证据，且完整 M4 已在干净工作区通过最终质量门禁。但 PR-6 不能把这些 proof 当成落库校验和 auto-assign persist 已经稳定；PR-6 仍要自己证明落库 payload 错误优先级、simulate 行为和自动分配写回条件。
