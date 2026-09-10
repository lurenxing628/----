---
doc_type: issue-fix-note
status: fixed
date: 2026-09-10
scope: preflight business status only
---

# EY Preflight Run Status

## Root Cause And Change

- Evidence: `output/playwright/main-integrated-20260910/page-2026-09-10T07-08-06-623Z.yml:192-202` shows an unavailable-worker status beside an enabled real run action.
- `core/services/workbench/preflight_result.py:57` unconditionally reported `run_worker_not_connected` despite having no host capability input.
- Replace only that retained reason with `schedule_not_computed` and the short business message meaning no schedule result has been generated. Keep `run_blocked=True`, blockers, calendar warnings, input tokens and all write-admission behavior unchanged.
- The existing frontend accepts string issue codes and displays the backend message directly. No frontend, model, API, runtime, worker, registry or build changes are needed.
- `tests/workbench/test_preflight_api.py:27` changes only the corresponding reason-code assertion. All no-write/no-authorization assertions remain intact.

## Verification

- New dedicated file: `tests/workbench/test_preflight_run_status.py` (3 tests).
- RED: all 3 tests reproduced the old incorrect reason, including the production factory with an actual managed runtime reporting ready.
- GREEN: service-only evaluation plus real factory/HTTP service-present and service-absent passed. Every database, launcher lock and server belongs to temporary fixtures; no existing preview was accessed.
- The HTTP requests run with SQLite `query_only` and a write-denying authorizer. No write attempts occurred; all tables and schema remained identical. Preflight never returns a write token or run capability; only the separate run preview grants a token when the actual runtime is ready. Absent service still reports `run_worker_not_connected` through that preview. No run is submitted.
- `.venv/bin/python -m pytest -q tests/workbench/test_preflight_run_status.py tests/workbench/test_preflight_api.py tests/workbench/test_preflight_ledger.py tests/workbench/test_preflight_capacity.py tests/workbench/test_run_jobs_api.py`: 63 passed, 1 failed.
- The sole failure is the existing `test_known_zero_quantity_not_unknown` at line 95 (empty issues, `IndexError`). Repeating it with the original reason restored in memory fails identically. It is outside this status-only fix and was not modified.
- The same suite with `-k 'not test_known_zero_quantity_not_unknown'`: 63 passed, 1 deselected.
- Ruff on the 3 touched Python files: passed. Python 3.8.10 executed the tests; Python 3.8 AST checks passed.

## Handoff And Limits

- EX owns test registration and was notified before test edits; no registry files were modified by EY.
- Product change is one line. Restart/rebuild and live Chrome109 verification remain with the main owner; ports 53144 and all old previews were untouched.
- This is a dirty shared-worktree local proof, not a full gate or clean-worktree proof. No commit or staging performed.
