---
doc_type: refactor-design
refactor: 2026-05-07-scheduler-perf-cache
status: approved
scope: scheduler run-time derived caches and hot-path repeated computation
summary: Apply four small behavior-preserving scheduler performance refactors with targeted contract tests.
tags: [scheduler, performance, cache, quality-gate]
---

# scheduler-perf-cache refactor design

## 1. Scope

- Implement S1 through S4 from the scan.
- Preserve scheduler strategy, dispatch rule, candidate ordering, objective scoring, random neighbor generation, and public result fields.
- Keep Win7 and Python 3.8 compatibility.
- Keep existing user dirty file `evidence/ArchAudit/arch_audit_report.md` untouched.

## 2. Preconditions

- Create branch `codex/scheduler-perf-cache`.
- Repair or clearly isolate existing baseline blockers before claiming clean proof.
- Use `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python` for verification.
- Do not run formatters that rewrite unrelated files.

## 3. Execution Order

### Step 1: strict-mode signature cache

- Method: Extract Helper + Memoize Pure Inspection.
- Files: `core/services/scheduler/run/schedule_signature_support.py`, `core/services/scheduler/run/schedule_optimizer_steps.py`, `tests/test_schedule_optimizer_strict_mode_signature_cache.py`.
- Exit signal: strict-mode signature tests, optimizer strict regressions, ruff, architecture checks, and diff check pass.
- Rollback: revert this step commit.

### Step 2: freeze-window prefix grouping

- Method: Extract Module + Preserve Ordering.
- Files: `core/services/scheduler/run/freeze_window_prefixes.py`, `core/services/scheduler/run/freeze_window.py`, freeze-window tests.
- Exit signal: freeze-window contracts and downstream summary/view tests pass; `freeze_window.py` stays under 500 lines.
- Rollback: revert this step commit.

### Step 3: SGS total-hours cache

- Method: Local Derived Cache.
- Files: `core/algorithms/greedy/dispatch/sgs.py`, `core/algorithms/greedy/dispatch/sgs_scoring.py`, SGS tests.
- Exit signal: SGS result fields stay unchanged; invalid-hour errors stay on the same contract path; greedy complexity gates pass.
- Rollback: revert this step commit.

### Step 4: compute_metrics aggregation

- Method: Extract Helper + Single-Pass Aggregation.
- Files: `core/algorithms/evaluation.py`, metrics tests.
- Exit signal: metrics contract outputs and optimizer summary projections remain unchanged; `compute_metrics()` complexity drops below threshold.
- Rollback: revert this step commit.

## 4. Risks And Stop Lines

- Stop if any change needs new fallback, silent swallow, or wider compatibility branch.
- Stop if tests show public result summary fields changed.
- Stop if `tools/check_full_test_debt.py` finds new candidate debt.
- Stop if any touched file exceeds 500 lines or creates new complexity debt.
- Stop if `evidence/ArchAudit/arch_audit_report.md` would be overwritten.
