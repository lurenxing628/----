---
doc_type: refactor-apply-notes
refactor: 2026-09-10-round1-h-process
status: completed
scope: R1-H known process and master-overview complexity failures only
---

# R1-H Process Apply Notes

## Scope And Isolation

- Explicitly authorized first-round local extraction only. No additional agents,
  stage/commit, global build, browser/server operations, production database,
  full-site acceptance, 5000-load test, Win7 release, or old-UI removal.
- Read `AGENTS.md`, `.codestable/attention.md`,
  `.codestable/reference/system-overview.md`, and project `cs-refactor` instructions.
- Existing worktree is heavily dirty. Initial sole staged path is
  `tests/gate_meta/test_frozen_bundle_contract.py`; its worktree SHA-256 is
  `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`.
  No index writes. G owns `core/models/workbench_process_commands.py`; not edited.
- Runtime: `.venv/bin/python --version` -> `Python 3.8.10`.
- Private scratch root: `/tmp/aps-r1-h.S7tptK`; `PYTHONPYCACHEPREFIX` and
  `CHECKUP_CALLGRAPH` point to its `pycache` and `callgraph` subdirectories.
- `python3 -m tools.symbol_locator {whereis,callers,callees}` ran for all seven
  target symbols. Full raw results: `/tmp/aps-r1-h.S7tptK/symbol-locator.json`.
  Ambiguous/dynamic caller counts are not a complete callgraph proof; `rg` checked
  the actual process read, route apply, file preview, and legacy hours call sites.
- Exact original pyright report filtered by the six authorized product paths:
  `output/workbench-migration/verification/point-main-20260910/stage-pyright.json`
  -> `[]`. Original complexity baseline is `round1-20260910/architecture-before.log`.
- All test databases are in-memory fixtures or private temporary file-backed
  SQLite. Process environment paths are explicitly rooted in the private scratch
  directory; pytest cache and basetemp are also private.

## Baseline Characterization

- Added `tests/workbench/test_round1_process_boundaries.py`.
- Initial run: 29 passed, 1 failed because the new SELECT-only authorizer also
  denied the domain's legitimate `BEGIN`. Corrected only this new fixture to use
  SQLite `PRAGMA query_only=ON` plus the unchanged all-table preservation oracle.
- Corrected baseline on untouched product source: **30 passed in 4.92s**.
- Command: `.venv/bin/python -m pytest -q -o cache_dir=/tmp/aps-r1-h.S7tptK/pytest-cache --basetemp=/tmp/aps-r1-h.S7tptK/before-tests-retry tests/workbench/test_round1_process_boundaries.py --junitxml=output/workbench-migration/verification/round1-20260910/r1-h-before.xml`.
  Prefix for pytest commands: `env PYTHONPYCACHEPREFIX=/tmp/aps-r1-h.S7tptK/pycache APS_DB_PATH=/tmp/aps-r1-h.S7tptK/unused.sqlite APS_LOG_DIR=/tmp/aps-r1-h.S7tptK/logs APS_BACKUP_DIR=/tmp/aps-r1-h.S7tptK/backups`.

## Closure 1: Overview And Readiness

- `core/models/workbench_master_overview.py:22`: extracted the repeated exact
  search-text contract; type, size, NUL rejection, column ownership and diagnostic
  messages retain their original order. `__post_init__`: **16 -> 10**.
- `core/services/workbench/master_overview_process.py:36`: separated workflow
  confirmation projection from active-operation traversal. `_route`: **17 -> 11**.
- `core/services/workbench/master_overview_process.py:102`: separated supplier
  capability checks and group ownership/range evidence from period projection.
  `_external`: **24 -> 10**. No external-group evidence or retained days removed.
- `core/services/workbench/resource_readiness.py:15`: separated stage-state matrix
  and confirmation evidence validation. `_checked_workflow`: **21 -> 8**. Legacy,
  managed, ready, unknown and invalid evidence remain distinct.
- Command: `.venv/bin/python -m pytest -q -o cache_dir=/tmp/aps-r1-h.S7tptK/pytest-cache --basetemp=/tmp/aps-r1-h.S7tptK/overview-tests tests/workbench/test_round1_process_boundaries.py tests/workbench/test_master_overview_reads.py tests/workbench/test_master_overview_boundaries.py tests/workbench/test_process_readiness.py tests/workbench/test_resource_readiness.py -k 'not scale and not thousand and not large_catalog' --junitxml=output/workbench-migration/verification/round1-20260910/r1-h-overview.xml`.
- Result: **101 passed, 2 deselected in 17.26s**, exit 0. Deselected only named
  large-catalog/2000-template tests, not failures or weakened assertions.
- Exact project `scan_complexity_entries` and `scan_oversize_entries` on these
  three files: **both empty**, exit 0. No threshold, ledger or allowlist edits.
- Before/after SHA-256 and Radon source lines:
  `output/workbench-migration/verification/round1-20260910/r1-h-overview-quality.json`.

## Closure 2: Route Preview, Difference And Hours

- `core/services/workbench/process_queries.py:150`: compare route operations
  independently from public projection; invalid legacy sequences still block
  confirmation without renumbering/deletion. `route_difference`: **19 -> 9**.
- `core/services/workbench/process_route_preview.py:160`: separate persisted refs,
  interpretation and diagnostic assembly, preserving raw rows/text, unknown types
  and reference-snapshot lifetime. `preview`: **27 -> 9**.
- `core/services/process/part_service.py:391`: only extract existing hours input
  normalization. `update_internal_hours`: **16 -> 12**. Existing lock protection,
  same-object check and transaction were already dirty on entry and retained.
- AST comparison against private entry snapshot: all other `part_service.py`
  content unchanged; hours `with` transaction subtree unchanged (line 412).
  Evidence: `output/workbench-migration/verification/round1-20260910/r1-h-hours-preservation.json`.
- Command: `.venv/bin/python -m pytest -q -o cache_dir=/tmp/aps-r1-h.S7tptK/pytest-cache --basetemp=/tmp/aps-r1-h.S7tptK/process-tests tests/workbench/test_round1_process_boundaries.py tests/workbench/test_process_route_preview.py tests/workbench/test_process_queries.py tests/workbench/test_process_read_api.py tests/workbench/test_process_route_confirm.py tests/workbench/test_process_stage_commands.py tests/workbench/test_process_stage_api.py tests/workbench/test_process_workflow_state.py tests/workbench/test_process_quota_protection.py tests/workbench/test_process_quota_protection_routes.py tests/workbench/test_process_quota_protection_transactions.py tests/workbench/test_process_quota_protection_stage_regressions.py -k 'not scale and not thousand and not full_existing_stage_collections and not exact_2000' --junitxml=output/workbench-migration/verification/round1-20260910/r1-h-process.xml`.
- Result: **536 passed, 7 deselected in 181.15s**, exit 0. Existing assertions and
  contracts unchanged; exclusions are named large-input tests outside this round.
- Seven-file `ruff check`: **All checks passed**, exit 0.
- Direct `.venv/bin/pyright` failed with exit 127 because its existing shebang
  references the old `Documents/GitHub` interpreter. No launcher or dependency
  changed. `.venv/bin/python -m pyright --outputjson` on the six product files and
  new test succeeded: **7 analyzed, 0 errors, 0 warnings**, Pyright 1.1.406, exit 0.
- Six-file project complexity/size scan: **both empty**; Python 3.8 AST parsing
  passed. All target and newly extracted helpers are within the existing limit.
  Exact hashes and source metrics: `round1-20260910/r1-h-quality.json`.

## Closure 3: Direct Hours Request Boundaries

- `tests/workbench/test_round1_process_boundaries.py:221`: real legacy hours view
  through an in-process Flask request. A locked unit-hours change raises the
  original `WorkbenchCommandRejected`; every table and the request input remain
  unchanged. Keeping the locked quota while changing setup hours returns 302;
  private BLOB, all unrelated rows and lock/audit history remain unchanged.
- `tests/workbench/test_round1_process_boundaries.py:242`: registered production
  workbench read/write endpoints return **HTTP 409 / calibration_quota_locked**
  for a locked change, with the complete private database snapshot unchanged.
- The new API fixture initially omitted `DATABASE_PATH`; 31 passed and 1 failed
  before a business call. Set it to the existing private fixture database. No
  response-code or data-preservation assertion was changed.
- Command: `.venv/bin/python -m pytest -q -o cache_dir=/tmp/aps-r1-h.S7tptK/pytest-cache --basetemp=/tmp/aps-r1-h.S7tptK/final-boundaries-retry tests/workbench/test_round1_process_boundaries.py --junitxml=output/workbench-migration/verification/round1-20260910/r1-h-final-boundaries.xml`.
  Result: **32 passed in 7.80s**, exit 0.
- Isolated baseline comparison: load the entry snapshot
  `/tmp/aps-r1-h.S7tptK/part_service.py` as a separate module and temporarily bind
  only its original `PartService.update_internal_hours` in the pytest process.
  Run the same two tests using `-k 'legacy_hours_request or workbench_hours_api'`,
  private basetemp `http-before`, JUnit `r1-h-http-baseline.xml`.
  Result: **2 passed, 30 deselected in 2.98s**, exit 0. No repository source swap.
- Boundary: the legacy view is not `api_endpoint`-wrapped and propagates the
  domain error in this TESTING app. This proves the rejection/data boundary, not
  a friendly legacy HTTP error response. The same behavior occurs with entry
  source; no old-route error-handler change is authorized or made here.

## Final Evidence And Stop

- `r1-h-final-evidence.json`: final seven-file SHA-256, source lines, exact Ruff
  and Pyright commands/results, Python 3.8 syntax checks, three JUnit summaries,
  protected file hash and staged path list. All filenames below are relative to
  `output/workbench-migration/verification/round1-20260910/`.
- Final test file SHA-256:
  `44a94e41ade303fe91d6ad2d62c9efa95a4baf7bd834362ea7be13b04b96fcbc`.
- The three final selected runs contain **609 distinct test cases** after JUnit
  classname/name deduplication: overview 101, process 536, boundaries 32. All
  selected cases passed; this is not a claim to cover excluded scale cases.
- `r1-h-pyright.json`: 7 files, 0 errors, 0 warnings, exit 0.
- `r1-h-ruff.log`: all checks passed, exit 0. Existing configuration unchanged.
- Final project `scan_complexity_entries` / `scan_oversize_entries` on the six
  authorized product files: both empty. Source hashes match the earlier scoped
  quality run. `r1-h-product.patch` is generated against entry snapshots, so it
  separates this extraction from the existing dirty lock-protection changes.
- Final sole staged file and protected SHA-256 still match the entry record.
  All six product paths, the new test, and this note remain uncommitted; preexisting
  unrelated dirty/untracked files are preserved. G's file was never edited.
- No required R1-H extraction or selected verification remains. Final handoff to
  the main task, then stop. Full architecture/full quality gate, browser acceptance,
  5000 load test, Win7 release and old-UI removal were not run, per authorization.
- This is dirty-worktree local evidence, not clean-worktree or full-gate proof.
