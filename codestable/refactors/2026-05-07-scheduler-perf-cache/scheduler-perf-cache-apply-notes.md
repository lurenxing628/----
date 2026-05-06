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
