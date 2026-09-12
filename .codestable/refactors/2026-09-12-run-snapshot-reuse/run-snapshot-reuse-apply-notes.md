---
doc_type: refactor-apply-notes
refactor: 2026-09-12-run-snapshot-reuse
status: completed
summary: One complete fingerprint for continuous preparation/computation; standalone prepared inputs remain fully checked.
---

# Implemented

- `run_compute.py` has a private continuous prepare/compute path inside the
  existing `candidate_read_snapshot`. It performs the existing same-connection and
  version validation, then enters the shared private computation body directly.
  No prepared object is exposed to a caller between preparation and computation.
  The body explicitly requires an active query_only transaction.
- Standalone `compute_prepared_candidate_run` still computes the complete current
  fingerprint and rejects stale inputs before entering that shared body. Returned
  combined-run input carries no cache flag or reusable freshness capability.
- `run_worker.py` calls the combined entrypoint under its original private SQLite
  backup and read snapshot. Worker ownership, original-database writer freedom,
  final fact revalidation, persistence, restart and execution protections remain.
- The unchanged full fingerprint still scans exactly the same schema/tables/rows.
  Only its second invocation on the continuous path is removed. No revision-table
  scheme, global cache, connection-id/total_changes heuristic or token protocol
  was introduced. `run_input.py`, `preflight_facts.py`, `run_input_readonly.py` and
  all payload/seed/window/chain/piece validators are byte-unchanged by this work.

# Structural and behavioral verification

- Real SQLite/real scheduler test: combined preparation+computation performs
  **one** full_facts_fingerprint call, where the previous implementation performed
  two. Independent preparation followed by standalone computation still performs
  **two** calls. Their complete candidate payloads, result rows, scores, metrics,
  dispositions and completion state match with an unselected batch present.
- SQLite tracing records one outer BEGIN and COMMIT across both operations.
  Existing tests retain caller-owned transactions, authorizers and query_only
  restoration, including attempted writes and late failures.
- Standalone stale checks cover selected operations, resources, configuration,
  schema additions and changed rows in an unrelated table outside selected scope.
  Reusing the input returned by an earlier combined run after a fact change is
  rejected normally. A foreign calendar connection and a lost/private read scope
  are rejected before scheduling.
- Candidate seed, chain/window, point-event and execution tests remain active.
  The existing exact projection-scope check caught an invalid new test fixture on
  the first run: one failure and 59 passes in `input-tests.xml`. The fixture was
  corrected to supply selected projections; the production scope check was not
  changed. This failed receipt is preserved.

# Test and observation seams

- Migrated pause/concurrent-write hooks in `test_run_entrypoint.py`,
  `run_runtime_support.py`, `test_run_jobs_concurrency.py` and
  `system_restore_entrypoint_process_support.py` to the worker's combined call.
  All existing lock, wait, late-fact-rejection and data-retention assertions remain.
- `final_capacity_observation.py` still separates preparation and engine. It now
  hooks the preparation function and private compute continuation in run_compute,
  and writes `measurement_scope_version=2` plus the observed function name.
  Version 1 engine included standalone freshness validation; version 2 measures the
  continuation after preparation. **Do not use v1/v2 engine ratios as identical
  scope comparisons.** Admission-to-terminal is still the comparable whole-run
  measure and the existing 180-second limit is unchanged. No large timing run or
  threshold change was made; `profile_dense_resources.py` was not edited.
- A real one-operation worker test verifies one full fingerprint, complete
  prepare/engine/serialization/persistence observations, ordering, profiler output
  and successful persisted state.

# Selected payload cache: measured disposition

This part was studied and deliberately **not implemented**, rather than counted
as a completed cache optimization. See `payload-cache-study.json` for the archived
profile hash and exact source comparison. The archived 5,000-operation
native-timing profile's `run_compute.py` is byte-identical to this task's prechange
HEAD (`0cdc2c3c13189632b54f3dd90814763cc0946a4ab2fb89964f8bf8391a03c35e`).

- Profile total self time: 164.248633584 seconds.
- All five `build_validated_schedule_payload` calls together: 0.292056041 seconds
  cumulative, less than 0.18 percent of that profile. Eliminating only the selected
  candidate's one call has a still smaller upper bound for this fixture.
- The removable full fingerprint invocation was 0.102125042 cumulative seconds
  in that fresh 5,000-operation database. No end-to-end speedup percentage is
  claimed; the duplicate scan's cost also depends on retained historical rows.
- A selected-payload cache keyed merely by results/input identity would be unsafe:
  the data and validator inputs remain mutable, and summary generation lies
  between validations. Proving their complete unchanged content adds another
  scan/proof surface. The measured small bound does not justify that complexity.
  Existing selected and per-candidate validations all remain in place.

# Final scoped checks

- `final-tests.xml`: **163 passed in 10.10s**, covering the 14 relevant input,
  compute, worker-concurrency, entrypoint and runtime files.
- `process-tests.xml`: **2 passed, 4 deselected in 3.49s**, exercising real process
  stop/restore with an active paused worker and retained original locks.
- Earlier receipts `targeted-tests.xml` (73 passes) and `runtime-tests.xml`
  (98 passes) are retained; these overlap and must not be added to the final count.
- Scoped Ruff: all eight product/test files passed. Scoped Pyright with
  `--pythonversion 3.8`: 0 errors, 0 warnings. It initially reported an existing
  dynamic BackupManager test double in the migrated entrypoint test; an `Any`
  annotation fixed the test-only typing without changing its execution/assertions.
- Scoped `git diff --check` passed. `source-binding.json` records the eight owned
  product/test file hashes and HEAD. The shared working tree contains other
  agents' changes, so this is scoped dirty-worktree evidence, not a full gate or
  clean-worktree proof.

No business database was opened, no commit/push/cleanup was performed, no full
quality gate or large performance run was started, and no Win7 timing claim is
made. Main owns aggregate verification and registration of the new test file
`tests/workbench/test_run_snapshot_reuse.py`.
