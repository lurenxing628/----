---
doc_type: refactor-apply-notes
refactor: 2026-05-07-scheduler-perf-cache
status: completed
tags: [scheduler, performance, cache, quality-gate]
---

# scheduler-perf-cache apply notes

## Step 0: baseline and docs

- Status: completed.
- Changed files:
  - `.codestable/refactors/2026-05-07-scheduler-perf-cache/scheduler-perf-cache-scan.md`
  - `.codestable/refactors/2026-05-07-scheduler-perf-cache/scheduler-perf-cache-refactor-design.md`
  - `.codestable/refactors/2026-05-07-scheduler-perf-cache/scheduler-perf-cache-checklist.yaml`
  - `.codestable/refactors/2026-05-07-scheduler-perf-cache/scheduler-perf-cache-apply-notes.md`
  - `tests/regression_freeze_window_fail_closed_contract.py`
  - `tests/regression_schedule_summary_freeze_state_contract.py`
- Notes:
  - Existing dirty file `evidence/ArchAudit/arch_audit_report.md` remains untouched and unstaged.
  - Freeze-window stale wording assertions now use `FREEZE_WINDOW_DEGRADED_MESSAGE` as the source of truth.
  - `tools/check_full_test_debt.py` now reports `status=passed`, `collected_count=972`, `unexpected_failure_count=0`.
- Validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_freeze_window_fail_closed_contract.py tests/regression_schedule_summary_freeze_state_contract.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tests/regression_freeze_window_fail_closed_contract.py tests/regression_schedule_summary_freeze_state_contract.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`

## Benchmark baseline

- The repo has two scheduler benchmark entry points:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode full`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/benchmark_sgs_large_resource_pool.py`
- These runs write scheduler evidence reports under `evidence/Benchmark/`.
- They are part of the final verification for this refactor.

## Step 1: strict_mode signature cache

- Status: completed.
- Changed files:
  - `core/services/scheduler/run/schedule_signature_support.py`
  - `core/services/scheduler/run/schedule_optimizer_steps.py`
  - `tests/test_schedule_optimizer_strict_mode_signature_cache.py`
- Notes:
  - Stable bound-method signatures are cached by the underlying function object.
  - Unhashable callable objects are not cached.
  - Unknown signatures are not cached and still use the existing TypeError fallback.
  - `_schedule_supports_strict_mode` remains available from `schedule_optimizer_steps.py` through an import alias.
- Validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_optimizer_steps.py core/services/scheduler/run/schedule_signature_support.py tests/test_schedule_optimizer_strict_mode_signature_cache.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_schedule_optimizer_strict_mode_signature_cache.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_improve_dispatch_modes.py tests/test_optimizer_local_search_neighbor_dedup.py tests/test_optimizer_build_order_once_per_strategy.py::test_ortools_strict_mode_raises_candidate_validation_error tests/regression_warmstart_failure_surfaces_degradation.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold --tb=short`

## Step 2: freeze-window prefix grouping

- Status: completed.
- Changed files:
  - `core/services/scheduler/run/freeze_window_prefixes.py`
  - `core/services/scheduler/run/freeze_window.py`
  - `tests/regression_freeze_window_fail_closed_contract.py`
- Notes:
  - Prefix helpers were moved out of `freeze_window.py`; the main file is now 481 lines.
  - Prefix grouping is built only from the active `seed_operations`.
  - Explicit `reschedulable_operations` subsets do not get expanded back to full `operations`.
  - Batch-local prefix order follows the original seed operation list.
- Validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/freeze_window.py core/services/scheduler/run/freeze_window_prefixes.py tests/regression_freeze_window_fail_closed_contract.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_freeze_window_fail_closed_contract.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_freeze_window_fail_closed_contract.py tests/regression_schedule_summary_freeze_state_contract.py tests/regression_schedule_input_collector_contract.py tests/regression_schedule_service_all_frozen_short_circuit.py tests/regression_analysis_page_version_default_latest.py tests/regression_scheduler_analysis_observability.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold --tb=short`

## Step 3: SGS total-hours cache

- Status: completed.
- Changed files:
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py`
  - `tests/test_sgs_total_hours_cache.py`
  - `tests/benchmark_sgs_large_resource_pool.py`
  - `evidence/Benchmark/sgs_large_resource_pool_report.md`
- Notes:
  - SGS now creates a local `op_id -> total_hours` cache inside one `dispatch_sgs()` run.
  - Only successfully validated internal operation hours are cached.
  - Invalid hours still fall through to the original scoring validation path and raise `ValidationError(field="setup_hours")`.
  - Auto-assign choices, slot estimates, formal scheduling validation, and external operations are not cached.
  - The SGS benchmark script was made compatible with the current `greedy.scheduler` module before running it.
- Benchmark note:
  - Pre-change SGS benchmark sample: large-pool estimator calls `601`, result count `1`, failed ops `0`; seed-fragment estimator calls `1`, result count `1201`, failed ops `0`.
  - Post-change SGS benchmark sample: large-pool estimator calls `601`, result count `1`, failed ops `0`; seed-fragment estimator calls `1`, result count `1201`, failed ops `0`.
- Validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py tests/test_sgs_total_hours_cache.py tests/benchmark_sgs_large_resource_pool.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sgs_total_hours_cache.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sgs_total_hours_cache.py tests/test_greedy_refactor_contracts.py tests/test_sgs_internal_scoring_matches_execution.py tests/regression_sgs_scoring_fallback_unscorable.py tests/regression_sgs_pre_sort_strict_nonfinite_rejected.py tests/regression_sgs_atc_penalize_missing_resources.py tests/regression_sgs_penalize_nonfinite_proc_hours.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/benchmark_sgs_large_resource_pool.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold --tb=short`

## Step 4: compute_metrics aggregation

- Status: completed.
- Changed files:
  - `core/algorithms/evaluation.py`
  - `tests/test_compute_metrics_contract.py`
- Notes:
  - Result rows are collected once into `_ResultMetricState`.
  - Batch due-date and unscheduled accounting still walks `batches` separately.
  - Machine changeover sorting stays per machine with the same `(start_time, end_time, op_id)` ordering.
  - `ScheduleMetrics.to_dict()` and `objective_score()` were not changed.
  - `compute_metrics()` radon complexity is now `A (3)`; `evaluation.py` is 349 lines.
- Validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/algorithms/evaluation.py tests/test_compute_metrics_contract.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_compute_metrics_contract.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_compute_metrics_contract.py tests/regression_metrics_horizon_semantics.py tests/regression_metrics_to_dict_nonfinite_safe.py tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py tests/regression_due_exclusive_consistency.py tests/regression_priority_weight_case_insensitive.py tests/regression_objective_projection_contract.py tests/regression_weighted_tardiness_objective.py tests/regression_optimizer_public_summary_projection_contract.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_schedule_summary_v11_contract.py --tb=short`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m radon cc -s core/algorithms/evaluation.py`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold --tb=short`

## Review follow-up: SGS non-positive op_id cache boundary

- Status: completed.
- Changed files:
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/sgs_scoring.py`
  - `tests/test_sgs_total_hours_cache.py`
  - `evidence/Benchmark/sgs_large_resource_pool_report.md`
- Notes:
  - Review found that `id=0` or missing operation ids could share cache key `0` in the SGS `total_hours` cache.
  - SGS now only caches `total_hours` for positive integer operation ids.
  - `id=0`, negative, missing, or non-integer ids stay on the original per-candidate validation path.
  - Positive database operation ids keep the existing single-run derived cache benefit.
  - Auto-assign choices, slot estimates, formal scheduling validation, and external operations remain uncached.
- 10-run SGS benchmark:
  - Warmup run was excluded from the formal statistics.
  - Formal large-pool runs had median `0.010044s`, mean `0.010387s`, min `0.009663s`, max `0.012004s`.
  - Formal 1000+ seed runs had median `0.108936s`, mean `0.109574s`, min `0.106659s`, max `0.118183s`.
  - Compared with the earlier single pre-change sample, this is about `24.41%` faster for the large-pool scenario and about `10.34%` faster for the 1000+ seed scenario.
  - This is post-change 10-run evidence compared with a single pre-change sample, not a strict 10-run baseline-vs-10-run-after experiment.
- Validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sgs_total_hours_cache.py --tb=short` -> `4 passed`.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_greedy_refactor_contracts.py tests/test_sgs_internal_scoring_matches_execution.py tests/regression_sgs_scoring_fallback_unscorable.py tests/regression_sgs_pre_sort_strict_nonfinite_rejected.py tests/regression_sgs_atc_penalize_missing_resources.py tests/regression_sgs_penalize_nonfinite_proc_hours.py --tb=short` -> `37 passed`.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py tests/test_sgs_total_hours_cache.py` -> passed.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold --tb=short` -> `2 passed`.
  - `git diff --check` -> passed.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py` -> `status=passed`, `collected_count=982`, `unexpected_failure_count=0`.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check` -> passed.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree` -> `质量门禁通过`.

## Final verification

- Status: completed with clean proof.
- Benchmark validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .limcode/skills/aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py --mode full`
  - Result: `runs=20 valid=20`.
  - Report: `evidence/Benchmark/fjsp_benchmark_report.md`.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/benchmark_sgs_large_resource_pool.py`
  - Result: large-pool estimator calls `601`, scheduled ops `1`, failed ops `0`; seed-fragment estimator calls `1`, scheduled ops `1201`, failed ops `0`.
  - Report: `evidence/Benchmark/sgs_large_resource_pool_report.md`.
- Governance validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`
  - Result: `status=passed`, `collected_count=980`, `unexpected_failure_count=0`.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`
  - Result: passed.
- Quality gate validation:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py`
  - Result: exited before running gate because the worktree was dirty.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree`
  - Result: gate completed, but manifest was marked `passed_but_unbound`; return code was `2`, so this is not a clean proof.
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`
  - Initial result: blocked by dirty worktree before running gate.
  - Follow-up result after committing the refreshed architecture audit report: `质量门禁通过`.
- Blocker resolution:
  - `evidence/ArchAudit/arch_audit_report.md` had pre-existing staged refresh content and two trailing spaces.
  - The trailing spaces were removed and the refreshed report was committed separately from scheduler performance code.
  - Full `git diff --check` passes after that cleanup.
