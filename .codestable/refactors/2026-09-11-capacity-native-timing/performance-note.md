---
doc_type: refactor-apply-notes
refactor: 2026-09-11-capacity-native-timing
status: completed
summary: Reduce native calendar and scalar parsing repetition without changing scheduling results.
---

# Native Timing Optimization

- Authorization: continue optimization and extract as much remaining performance as is supported by equivalent behavior and measurements. Existing calendar/index optimizations and all unrelated dirty content remain untouched.
- Baseline: the previous explicit uncommitted source completed two full 5000-operation, four-candidate runs in 134.051188208 and 135.450551583 seconds. The original 180-second requirement, weights and candidate/search settings remain unchanged.
- Main evaluated attempt-local native calendar timing reuse. Separate agents prepared independent callback/exception equivalence tests, implemented bounded scalar parsing fast paths, and assessed whether a safe scoring-round snapshot reuse proof exists.
- The fully frozen 1000-operation trial completed with identical payloads. Engine times: previous source 16.990555041 s, fusion plus scalar/certificate changes 15.628094333 s, and identical scalar/certificate changes without fusion 14.730801459 s. These are sequential exploratory measurements, not 5000-operation acceptance.
- Fusion was rejected because it did not demonstrate a net benefit over the unfused variant. Its new runtime API, context helper, estimator changes and context-only tests were removed from the working source; the complete experimental source and tests remain in immutable trial snapshots. The original estimator file was verified byte-identical to the prior source afterward.
- Retained candidates: bounded native-integer parsing; strict native due-date parsing; canonical priority handling without repeated normalization; native method identity proof with the original reflected-method proof as fallback; and a bounded pure native-date formatter cache. Work-calendar policies themselves are still looked up on every call.
- The date formatter experiment used five alternating pairs of 500,000 calls: median 0.172954166 s uncached and 0.106586083 s cached. The cache is limited to 4096 native date keys. Date subclasses and their formatting callbacks remain on the original path; no business data is cached by this helper.
- No real database is opened, no original business data is written, no full quality-gate rerun or Git commit is authorized by this phase. Verification remains targeted plus isolated full-capacity runs; no clean-worktree or Win7 real-machine claim is implied.

## Selected Changes

- `core/shared/strict_parse.py`: only exact native integers within `[-2**53, 2**53]`, with `min_value is None` and `reject_integer_float is False`, bypass the old conversion path. Booleans, subclasses, larger integers and non-default option objects retain legacy conversion, error and callback behavior.
- `core/algorithms/greedy/dispatch/sgs_scoring.py`: strict due-date parsing returns only `None` and exact native dates directly. Datetime/date subclasses, text and non-strict calls retain the existing parsers. Per-candidate input reads, first errors and scoring order remain unchanged.
- `core/services/scheduler/calendar_engine.py`: avoid canonical-priority normalization; use a 4096-entry cache for pure native-date ISO formatting. Calendar policy reads, policy-cache replacement visibility, flags, work windows and subclass callbacks remain on their existing paths; the formatter adds no business-policy cache.
- `core/services/scheduler/calendar_native_timing.py` and `calendar_service.py`: prove unchanged native methods using exact class, MRO, descriptor and instance-override checks. When this proof is unavailable, retain the original reflected-method checks. No business-policy snapshot is reused by this guard.
- The previous append-index optimization is retained. The attempted calendar timing context and its runtime API are absent from the selected working source; `internal_slot.py` remains byte-identical to the previous version.
- Three new test files cover scalar parsing, native certificate guards and date-key caching. The existing calendar equivalence suite also covers the canonical-priority path.

## Full Capacity Results

Each row below is a separate unprofiled, Main-exclusive run with 100 batches, 50 operations per batch, four complete candidates and the unchanged 180-second requirement. There were no concurrent agent tests, builds or other benchmark runs in either selected timing window.

| Source | Accepted to terminal (s) | Engine (s) | Result |
| --- | ---: | ---: | --- |
| Previous append-index source, first | 134.051188208 | 129.444383916 | Passed |
| Previous append-index source, confirmation | 135.450551583 | 131.207380375 | Passed |
| Selected native optimization, first | 116.441791208 | 112.062647250 | Passed |
| Selected native optimization, confirmation | 115.538071917 | 111.242470334 | Passed |

- Mean accepted-to-terminal time fell from 134.750869896 to 115.989931563 seconds, a further 13.92% reduction. The smaller observed margin below 180 seconds is 63.558208792 seconds, not a worst-case bound.
- All four complete persisted candidate payloads, totaling 20,000 task rows per run, were byte-identical to the original failed-run payloads and the previous successful optimization results. Full HTTP candidate reads, same-request-key replay, restart reads, integrity and foreign-key checks passed.
- The three 1000-operation comparison runs are exploratory only. Each preserved all 4000 task rows and passed its own replay/restart checks. They are not counted as formal 5000-operation acceptance.

## Matched Profile

- A separate full-5000 diagnostic used cProfile with a 900-second observation watchdog. It did not evaluate or change the 180-second requirement and is not marked as a formal capacity pass.
- Its profiled engine time was 169.538609875 seconds versus 225.308999958 seconds for the previous matched profile. Profiler overhead means these times must not be substituted for the unprofiled timing results above.
- Total calls fell from 594,799,575 to 489,262,107. Candidate scoring remained 1,485,150 calls; slot estimation remained 1,505,150; overlap-index reads remained 4,500,450; date-policy reads remained 16,725,775. Full persisted outputs were byte-identical.
- The bounded native-date formatter had only two cache misses in this fixture. This is fixture-specific, not a promise that every dataset has two calendar dates.
- The largest remaining self-time was `slot_overlap_reuse.index` at 24.111226921 profiled seconds. It still compares snapshots of mutable occupancy lists. Removing those reads needs an explicit mutation/ownership contract; length-only or object-identity-only reuse would miss in-place changes.
- Reusing scores between rounds was not adopted: resource availability, previous operation completion, first-error order and mutable input visibility need a sufficient invalidation proof. No global or theoretical performance minimum is claimed.

## Verification and Provenance

- Selected new/equivalence tests: 468 passed. The final broader scoped run covered the algorithm, calendar-maintenance and domain-model suites plus related numeric/calendar integration contracts: 2105 passed, no failures, errors or skips. Ruff and Pyright with Python 3.8 settings passed on all 12 optimized product/test paths.
- The first broad run already passed all 2105 tests, but Pyright reported 24 errors in deliberately dynamic test fixtures. Only test annotations were then corrected; the same 2105 tests and both static checks passed again. The initial failed typing receipt is retained.
- The measured source is the complete `b614631018cbd5ad767c90602c11feae600078ba` tree plus explicit uncommitted runtime changes, frozen under `selected-v4/source` with 5108 files. Source-binding SHA-256: `9d666e929ea9c974ff317977f4a6e8f2e4c1c580fb39cb6b30f21f88c0e8b79d`.
- Factory manifest SHA-256: `bc79c61f202df7095ecd7984d6abc5430d87728e1aeb45db82e72213988ff80c`. Runtime loaded-source guards, before/after product-input hashes and restart source checks passed.
- The post-timing test-only annotation delta is recorded separately in `raw/verification-source-binding.json`, its final source copy and `raw/verification-final/test-annotations.patch`. Every product byte remained unchanged; the amended test module was not loaded by any timed or diagnostic runtime. The frozen measured tree was not overwritten.
- The 40 protected original business files retain their original hashes, sizes, modes, inodes and modification times. The check used filesystem reads, not an SQLite connection. Benchmark and preview databases are isolated temporary samples.
- Raw trial sources, rejected code/tests, all six run directories, request records, payloads, profiles, checks and verification scripts are archived with independently checked file hashes: 19,776 regular files, 2,254,498,151 bytes. All owned benchmark processes stopped; their ports and lock files were verified closed/absent.
- Durable receipt: `output/workbench-migration/performance/20260912-native-timing/optimization-result.json`; SHA-256: `9995253d747e8dc508088d29ed5b10ddf589699ca57879d58261f87e95fc1743`.
- New sample preview: `http://127.0.0.1:59856/workbench`, PID 28052, bound to the measured source with a fresh sample database. All 226 served static payloads were verified by size/hash. Older previews were left untouched. This is startup/asset verification, not a new full visual acceptance run.
- Changes remain uncommitted. Existing unrelated dirty files and staged-state boundaries were preserved. No full quality-gate rerun, clean-worktree proof, release package, or Win7 real-machine verification was performed in this phase.
