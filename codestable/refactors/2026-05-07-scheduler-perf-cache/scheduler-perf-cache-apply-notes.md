---
doc_type: refactor-apply-notes
refactor: 2026-05-07-scheduler-perf-cache
status: in_progress
tags: [scheduler, performance, cache, quality-gate]
---

# scheduler-perf-cache apply notes

## Step 0: baseline and docs

- Status: completed.
- Changed files:
  - `codestable/refactors/2026-05-07-scheduler-perf-cache/scheduler-perf-cache-scan.md`
  - `codestable/refactors/2026-05-07-scheduler-perf-cache/scheduler-perf-cache-refactor-design.md`
  - `codestable/refactors/2026-05-07-scheduler-perf-cache/scheduler-perf-cache-checklist.yaml`
  - `codestable/refactors/2026-05-07-scheduler-perf-cache/scheduler-perf-cache-apply-notes.md`
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
