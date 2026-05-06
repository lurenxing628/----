---
doc_type: refactor-scan
refactor: 2026-05-07-scheduler-perf-cache
status: completed
scope: scheduler run-time derived caches and hot-path repeated computation
summary: Reduce repeated pure computation inside one schedule run without changing scheduling semantics.
tags: [scheduler, performance, cache, quality-gate]
---

# scheduler-perf-cache scan

## 1. Overview

This scan is for scheduler performance cleanup only. The selected targets are read-only derived values inside a single schedule run, not cross-run business cache.

Findings:

- S1: `schedule_optimizer_steps.py` repeats `inspect.signature()` whenever optimizer candidates call scheduler `schedule()`.
- S2: `freeze_window.py` repeatedly scans all seed operations per batch prefix and is close to the 500-line file limit.
- S3: SGS scoring validates the same internal operation hours during average calculation and candidate scoring.
- S4: `compute_metrics()` scans `results` multiple times and has very high complexity.

Baseline blockers seen before implementation:

- `evidence/ArchAudit/arch_audit_report.md` already has user-side dirty changes.
- `tools/check_full_test_debt.py` was reported as a blocker before this run; after updating stale freeze-window wording assertions, it now passes with no unexpected failures.
- Freeze-window regression tests contained stale wording assertions around degraded/unapplied public messages.
- Benchmark verification is available through `tests/benchmark_fjsp.py` and `tests/benchmark_sgs_large_resource_pool.py`; final verification should run the FJSP full matrix and the SGS benchmark report.

## 2. Selected Items

### S1: strict-mode signature cache

- Category: performance.
- Risk: low.
- Method: Extract Helper + Memoize Pure Inspection.
- Change: move schedule signature support detection into a small helper module and cache stable callable signatures.
- Acceptance: supported schedulers still receive `strict_mode=True/False`; unsupported schedulers still do not receive the keyword; unknown signatures keep the current TypeError fallback.

### S2: freeze-window prefix grouping

- Category: performance and file-size control.
- Risk: medium.
- Method: Extract Module + Preserve Ordering.
- Change: group current `seed_operations` by batch once, then use the batch-local list for prefix lookup.
- Acceptance: `frozen_op_ids`, `seed_results`, `freeze_meta`, warning order, and strict-mode first failure behavior stay unchanged.

### S3: SGS total-hours cache

- Category: performance.
- Risk: medium.
- Method: Local Derived Cache.
- Change: cache only successfully validated `op_id -> total_hours` for SGS scoring.
- Acceptance: invalid-hour semantics stay unchanged; auto-assign final machine/operator is not cached.

### S4: compute-metrics traversal reduction

- Category: performance and complexity cleanup.
- Risk: medium.
- Method: Extract Helper + Single-Pass Aggregation.
- Change: collect result-derived metric state in one pass, then keep machine changeover sorting as a separate per-machine step.
- Acceptance: `ScheduleMetrics.to_dict()` and `objective_score()` outputs remain byte-for-byte equivalent for contract scenarios.

## 3. Explicit Non-Goals

- No cross-run or disk cache.
- No new dependency.
- No OR-Tools requirement change.
- No quality-gate script change.
- No new xfail.
- No fallback branch that hides scheduler data errors.
