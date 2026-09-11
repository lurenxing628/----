---
doc_type: refactor-apply-notes
refactor: 2026-09-11-capacity-calendar-hot-path
status: completed
summary: Remove repeated calendar scalar normalization and fixed enum lookup without changing schedule semantics.
---

# Capacity Calendar Hot Path

- Authorization: user requested performance optimization after remaining migration delivery completed.
- Scope: `core/services/scheduler/calendar_engine.py` and focused characterization tests. Existing user changes remain untouched. No automatic commit or remote operation.
- Baseline: `b614631018cbd5ad767c90602c11feae600078ba`; the original 5000-operation timing remains failed at 182.305726833 engine seconds against the unchanged 180-second acceptance target.
- Fresh exploration: `/private/tmp/aps-capacity-opt-b614631-ZarMkO/baseline-profile-1000`, 100 batches x 10 operations, existing real worker profiler, 4 candidates, complete payload/replay/restart checks. This is not the formal 5000-operation acceptance.
- Profile: engine 41.275462917 seconds with cProfile; 2,598,380 `_policy_for_date` calls and 2,008,434 `is_priority_allowed` calls. Calendar text normalization and repeated enum property lookup are measured repeated work. Profile elapsed time must not be compared directly with unprofiled formal timing.
- Planned change: exact built-in strings use the same strip/blank semantics directly; all other values and string subclasses retain the general normalization path. Fixed enum values are resolved once, while priority text and policy permission fields are still evaluated on every call.
- Explicitly unchanged: candidate count, weights, search strategy, segment snapshots, invalidation rules, date/shift boundaries, errors, public APIs, Python 3.8/Win7 compatibility and 180-second acceptance.
- Validation plan: characterization and work-elimination assertions; existing calendar and SGS/busy-block regressions; matched 1000-operation profile/result comparison; unprofiled 5000-operation full functional/timing acceptance in a fresh isolated fixture.
- The user's no-full-gate-rerun instruction remains in force. Focused checks will not be reported as final-HEAD full-gate or clean-worktree proof.
- Original business database and both existing preview services are not optimization fixtures and must not be altered.

## Results

- Product delta: one file, 10 insertions and 5 deletions. No public interface, search, cache, timeline or acceptance-threshold change.
- Characterization before implementation: 122 passed; the two deliberate work-elimination checks failed. After implementation: 344 focused tests passed, including calendar rollover, operator overrides, busy-block boundaries and SGS equivalence. Scoped Ruff and Python-3.8 Pyright checks passed with no reported errors or warnings.
- Matched 1000-operation profile: engine 41.275462917 -> 30.368226375 seconds. General text normalization calls fell from 2,598,480 to 100; enum value reads fell from 4,027,376 to 10,508. Full candidate payload files were byte-identical. These profiled times are exploratory, not the formal capacity result.
- First unprofiled 5000-operation acceptance: admission-to-terminal 177.055147083 seconds; engine 172.063225250 seconds. Full functional acceptance passed.
- One repeatability check: admission-to-terminal 171.386780875 seconds; engine 166.936380000 seconds. Full functional acceptance passed again. Both used 100 batches x 50 operations, 4 candidates, the same resource pair and the unchanged 180-second target.
- Both 5000-operation payload files are byte-identical to the original failed run's full validated payloads. All 20,000 persisted task rows, integrity/FK checks, same-request replay and restart retention passed. All benchmark-owned processes, listeners and locks were released.
- Real data: all 40 original business files retained the same hash, size, mode, inode and modification time. No original database connection or restoration was performed.
- Evidence: `/Users/lurenxing/GitHub/----/output/workbench-migration/performance/20260911-calendar-hot-path/optimization-result.json`, SHA-256 `2f334bc062da208da9df7c6a975ada129abd2ad8838106bdb5be8729558b49da`. The archive contains 7,862 byte-verified regular files, 1,338,165,841 bytes; duplicate temporary aliases are recorded separately without following external paths.
- Optimized preview: `http://127.0.0.1:55597/workbench`, PID 30235, fresh sample database `/private/tmp/aps-workbench-live-ec4jxvei/db/aps-live.db`. The exact optimized source was bound and all 226 served assets were checked. Existing previews on 53144 and 61301 were preserved.
- Source boundary: the tested source is the complete `b614631018cbd5ad767c90602c11feae600078ba` Git tree plus the explicit, uncommitted product patch and new test. Original unrelated working-tree changes were not copied into the acceptance snapshot or modified. No commit, push, PR, full-gate rerun, Win7 package or real-machine acceptance was performed.
- Remaining limit: observed end-to-end headroom was 2.945 and 8.613 seconds. Two local passes do not guarantee timing under arbitrary host load or on a Win7 target machine. The original 182.305726833-second engine failure remains preserved as historical evidence.
