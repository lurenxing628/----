---
doc_type: feature-acceptance
feature: 2026-04-28-optimizer-result-contract-evidence
status: accepted
created: 2026-04-28
last_reviewed: 2026-04-28
roadmap: p1-scheduler-debt-cleanup
roadmap_item: optimizer-result-contract-evidence
---

# 优化器结果合同补证验收

## 1. 验收结论

PR-4 已完成优化器结果合同补证。本次没有改运行代码，只补测试和 CodeStable 追踪文档，用来证明近期优化器输出的外形已经被锁住。

本次完成：

- `12` 条普通 attempt 加 `1` 条 rejected attempt 进入 `build_result_summary` 后，公开 attempts 只保留页面可展示字段，不含 `source`、`tag`、`used_params`、`algo_stats`、`origin`，rejected 诊断留在 `diagnostics.optimizer.attempts`。
- rejected 诊断继续用现有 `origin.type`、`origin.field`、`origin.message` 表达，不新增独立 `reason` 字段，也不伪造 `score`。
- 已有 `state.best is None` 路径仍返回真实 `OptimizationOutcome`，并固定 `summary`、`used_strategy`、`used_params`、`best_score`、`best_order`、`algo_stats`、`attempts` 外形。
- strict/non-strict 坏数据相关旧测试继续通过，说明本次没有把坏候选改成静默成功。
- PR-4 文件边界已补准：rejected 诊断入口、候选分流和 local search 相关文件纳入 primary_paths 与静态检查。

本次没有做：

- 没有新增 `if`、fallback、兜底、静默吞错或宽泛默认值逻辑。
- 没有改 summary、页面、落库、冻结窗口、停机资源池、runtime/plugin 或质量门禁工具运行逻辑。
- 没有新增独立 `reason` 字段；后续如果必须新增，需要先停下来说明。
- 没有减少 full-test-debt；active xfail 仍是 5 条 operator-machine/query service 旧登记。

## 2. 改动范围

- `tests/regression_optimizer_public_summary_projection_contract.py`：新增 rejected 诊断穿过 attempts 压缩和 summary 投影后的分层测试。
- `tests/regression_ortools_budget_guard_skip_when_no_time.py`：加严已有 `state.best is None` 路径的返回外形断言。
- `codestable/features/2026-04-28-optimizer-result-contract-evidence/`：新增 PR-4 design、checklist、acceptance 三件套。
- `codestable/roadmap/p1-scheduler-debt-cleanup/`：回填 PR-4 执行计划、文件边界、退出检查和 PR-5 承接说明。

## 3. 债务口径

| 项目 | 结果 |
|---|---|
| full-test-debt | 不减少，仍是 5 条 active xfail |
| `collected_count` | 744 |
| `unexpected_failure_count` | 0 |
| `complexity_count` | 40 |
| `silent_fallback_count` | 159 |
| 是否关闭 old P1 | 没有关联 old P1，不关闭 |

## 4. 已运行验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_optimizer_attempt_compaction_contract.py tests/test_optimizer_local_search_neighbor_dedup.py tests/test_optimizer_build_order_once_per_strategy.py tests/regression_optimizer_public_summary_projection_contract.py`：22 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_schedule_optimizer_cfg_snapshot_contract.py tests/test_schedule_params_direct_call_contract.py tests/regression_optimizer_zero_weight_cfg_preserved.py tests/regression_optimizer_outcome_type_contract.py tests/regression_optimizer_runtime_seam_contract.py tests/regression_optimizer_seed_boundary_contract.py`：32 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_ortools_budget_guard_skip_when_no_time.py`：OK。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_warmstart_failure_surfaces_degradation.py`：OK。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_optimizer.py core/services/scheduler/run/optimizer_search_state.py core/services/scheduler/run/optimizer_attempt_records.py core/services/scheduler/run/schedule_optimizer_steps.py core/services/scheduler/run/optimizer_local_search.py core/services/scheduler/summary/optimizer_public_summary.py tests/test_optimizer_attempt_compaction_contract.py tests/test_optimizer_local_search_neighbor_dedup.py tests/test_optimizer_build_order_once_per_strategy.py tests/regression_optimizer_public_summary_projection_contract.py tests/regression_ortools_budget_guard_skip_when_no_time.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_optimizer.py core/services/scheduler/run/optimizer_search_state.py core/services/scheduler/run/optimizer_attempt_records.py core/services/scheduler/run/schedule_optimizer_steps.py core/services/scheduler/run/optimizer_local_search.py core/services/scheduler/summary/optimizer_public_summary.py`：0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，active xfail 仍为 5，`collected_count=744`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`complexity_count=40`，`silent_fallback_count=159`，`test_debt_count=5`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/roadmap/p1-scheduler-debt-cleanup`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/features/2026-04-28-optimizer-result-contract-evidence`：通过。
- `git diff --check`：通过。

## 5. Subagent 复审

- 计划落盘后对抗复审指出：不能新增 `reason` 字段，不能把已有 `state.best is None` 路径写成新增 fallback，不能在 summary/page 层补二次兜底；文案已修正。
- CodeStable 回填复审指出：acceptance 阶段需要把 checklist 的 checks 标成真实状态，PR-6 需要先放承接占位；本次已修正。
- 优化器边界复审指出：PR-4 primary_paths 少列 rejected 诊断入口和候选分流文件；本次已补进 items.yaml 和静态检查。

## 6. 后续承接

PR-5 只能承接“优化器输出已经有证据”这个事实，不能把 PR-4 的通过结果当成 summary、历史落库、页面展示已经稳定。PR-5 仍要自己证明 `result_summary` 写入、读回和页面展示不泄漏内部诊断。
