---
doc_type: refactor-apply-notes
refactor: 2026-09-11-capacity-index-reuse
status: completed
summary: Reuse validated immutable overlap-index arrays for a single appended segment.
---

# Capacity Index Reuse

- Authorization: user requested deeper performance optimization and explicitly allowed multiple subagents for research. The previous calendar optimization remains intact and uncommitted.
- Four real subagents analyzed scoring/error ordering, timeline ownership, native calendar fusion and numerical optimization bounds. Main retains implementation and measured acceptance responsibility.
- Baseline diagnostic profile: `/private/tmp/aps-capacity-deep-opt-K64fOb/baseline-profile-5000`, exact previous optimized source, 100 x 50 operations, all 4 candidates, cProfile enabled. The 900-second diagnostic watchdog is not the unchanged 180-second acceptance threshold; this run explicitly does not evaluate or claim timed acceptance.
- Measured profile: 1,485,150 SGS scores, 4,500,450 overlap-cache lookups, 30,294 materializations. Cache lookup self time was 25.675 seconds; materialization self time was 15.652 seconds. Parent cumulative times are not additive. The full output payloads matched the prior formal run byte-for-byte.
- Rejected shortcuts: caching whole scores by operation id, discarding candidates by graph key before penalty/errors, and relying on mutable-list identity/length/version alone. These do not preserve current contracts.
- Selected implementation: retain exact per-call content snapshots and ordinary dict/list interfaces. When an already materialized immutable snapshot gains exactly one native naive-datetime segment with the same prefix and valid sorted position, derive new prefix-max and cached covered-block tuples. The old index remains immutable. All other changes retain lazy rebuilding and existing error timing.
- Scope: `core/algorithm_runtime/downtime.py`, `slot_overlap_reuse.py`, focused tests and this record. No candidate/weight/search/quality/timeout change, no real data access, no full-gate rerun, no automatic Git commit.
- Validation plan: independent constructor oracle for positive/zero/reversed queries, nested/touching/micro-gap coverage, snapshot retention, every non-append invalidation, delayed unsorted errors, mutable/aware/subclass inputs, and structural build counts; existing SGS/busy-block tests; then matched profiling and full 5000-operation functional/timing acceptance.

## Implemented Contract

- `SegmentOverlapIndex.with_appended_segment()` preserves the parent index and immutable query arrays. Valid positive appends extend the sorted starts, prefix maxima and any existing covered-block arrays; invalid appended segments increase the original segment count without changing those arrays.
- Old and new prefixes must contain exact tuples of two exact naive datetimes. The shared-identity prefix check avoids repeated type validation; equal copied native prefixes remain eligible after validation. Subclasses, aware datetimes, malformed rows, changed prefixes, bulk appends, gap inserts and cold indexes use the existing lazy constructor path.
- Three initial boundary failures exposed equal-valued tuple/datetime subclasses and a comparison exception. The native-prefix guard was tightened before source freeze. The failed run is preserved, not replaced by the later pass.
- Ordinary dict/list interfaces, content-based invalidation, old snapshots, unsorted 0-hop behavior and query/error timing remain covered. No mutable-container version shortcut, whole-score cache, early candidate pruning, dependency upgrade or front-end change was introduced.

## Verification

- Final source checks: **367 targeted tests passed**, Ruff passed, and Pyright with `--pythonversion 3.8` reported zero errors and warnings. This is scoped validation, not a full quality-gate pass.
- Final executable snapshot: 5,104 files, a complete `b614631018cbd5ad767c90602c11feae600078ba` tree plus the explicit uncommitted calendar/index changes and their tests. Source-binding SHA-256: `17c090ae4aa71d40badc631bad00563d1eb1f7467bd4968c0ad286ab7e08713b`.
- The new phase changes two product files, adds one focused test file and updates this record. The earlier calendar optimization remains unchanged and uncommitted. Existing unrelated dirty files and the empty Git index were preserved.

## Formal Timing

All formal runs use 100 batches x 50 operations, four candidates and 20,000 persisted task rows. The original 180-second admission-to-terminal threshold, objective weights and search settings are unchanged. Profiling is disabled and each run uses a separately declared exclusive local timing window.

| Snapshot | Run | Admission To Terminal | Engine |
| --- | --- | --- | --- |
| Previous calendar optimization | 1 | 177.055147083 s | 172.063225250 s |
| Previous calendar optimization | 2 | 171.386780875 s | 166.936380000 s |
| Calendar plus index optimization | 1 | 134.051188208 s | 129.444383916 s |
| Calendar plus index optimization | 2 | 135.450551583 s | 131.207380375 s |

- Both new formal attempts passed. Mean admission-to-terminal time decreased by about 22.7% relative to the two previous runs; the smaller new headroom is 44.55 seconds. Two measurements are not a statistical guarantee or a worst-case bound.
- Both new runs produced byte-identical complete candidate payloads compared with the original pre-optimization 5000-operation output. All four workspaces were read in full, admission replay preserved the same request/run/receipt, and restart preserved all candidate tasks and business rows.
- Owned benchmark processes stopped normally, six benchmark ports were verified closed and locks absent. The fresh preview is deliberately left running separately.

## Measured Cause And Remaining Limit

- Matched 5000-operation diagnostics with cProfile: engine time changed from 250.463242333 s to 225.308999958 s. These are diagnostic times, not the unprofiled acceptance times above; the separate 900-second diagnostic watchdog does not change the 180-second acceptance rule.
- Full index materializations fell from **30,294 to 306**. `covered_end` still ran 6,321,705 times, but its self time fell from 12.410724181 s to 2.067746365 s. `find_overlap_shift_end` calls fell from 46,203 to 15,927. The new append derivation was attempted 29,994 times.
- Work was not skipped at the scoring or calendar level: both diagnostics performed 1,485,150 SGS scores, 1,505,150 internal-slot estimates, 4,500,450 overlap-cache lookups and 16,725,775 date-policy lookups. All four complete payloads were identical.
- The remaining profile still shows about 26.56 s of self time in snapshot/cache lookup and repeated native calendar work. Parent cumulative times overlap and must not be added together. These costs are not all removable: content mutations, callbacks, abort ordering, cross-midnight rules and exceptions still matter.
- No global speed limit, 60/100-second target, universal 5000-operation bound or Win7 speed is established. Results apply to this local fixture and hardware. Reducing further repeated work requires another validated design; changing candidate quality or the acceptance threshold is not an optimization.

## Retention And Delivery

- A read-only comparison of all 40 protected real business files confirmed unchanged SHA-256, size, mode, inode and modification time, with no original database connection opened or original application started.
- Evidence archive: `output/workbench-migration/performance/20260911-index-reuse/raw/`, 7,817 regular files / 1,572,931,837 bytes, individually copied and verified by hash, size and mode. Temporary aliases were recorded separately; previous timing failures and the first optimization archive were preserved.
- Result: `output/workbench-migration/performance/20260911-index-reuse/optimization-result.json`, SHA-256 `c1f8df9c22e548cf6446c79c3ec110616699401cfe8e9973345adbc38eff3d5f`. The result links source binding, raw requests, both profiles, both formal attempts, test/lint/type receipts and protected-data checks.
- Current sample-only preview: <http://127.0.0.1:56699/workbench>, PID 77945, fresh database `/private/tmp/aps-workbench-live-_et1xiu5/db/aps-live.db`. All 226 delivered assets passed HTTP/hash/size verification. Previous previews were not modified. This is a source-bound boot/asset check, not a repeated full-site visual acceptance.
- No full quality-gate rerun, clean-worktree proof, Win7 real-machine validation, Git commit, push or release was performed in this phase.
