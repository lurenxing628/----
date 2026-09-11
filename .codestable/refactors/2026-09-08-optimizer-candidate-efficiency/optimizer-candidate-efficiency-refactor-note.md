---
doc_type: refactor-note
refactor: optimizer-candidate-efficiency
date: 2026-09-08
status: done
summary: Exact SGS graph-key preorder deduplication and reserved elite repair budgets
tags: [scheduler, graph-ready, predecode, budget, python38]
---

# Scope And Approval

The 2026-09-08 user instruction explicitly approves profile deduplication and
budget allocation. The existing approved feature is
`.codestable/features/2026-09-08-graph-ready-elite-repair/graph-ready-elite-repair-design.md`.
This extends its remaining-budget scheduling rule with an explicit reservation;
it is NOT a claim of behavior-preserving search order under finite budgets.
The project `cs-refactor-ff`, AGENTS, attention and system overview were read.
The skill's single-file fast-forward threshold does not describe this task;
the user's explicit multi-file approval defines the implementation boundary.

No commit, real database, runtime SGS edits, evaluation.py edits, shared registry,
ratchet runner/baseline, frontend, installation or subagents are part of this work.
Existing dirty files, including these optimizer files, are preserved.

# Minimum Contract

1. A profile emits finite, uniform-length graph keys through the existing
   `context_for_profile`. Preserve EXACT ordered equality classes over all
   mutable operation IDs. No additional rounding, epsilon, name matching,
   approximate score, initial ready-set-only comparison or ID-tiebroken permutation.
2. The cache lives inside one evaluator closure and one phase. Operations,
   batches, seed, graph edges, readiness, calendar, downtime, strategy, resource
   pool, dispatch rule, objective and version are fixed by that closure. Order is
   part of the cache key. Never reuse across restarts, resources or repair.
3. SGS forms `(dynamic_penalty, *graph_key, *dynamic_dispatch_key)` in
   `sgs.py:_score_candidate` / `sgs_scoring.py:with_graph_priority_key`.
   Uniform graph arity within each profile means unequal graph keys decide
   comparison before the suffix; equal keys defer to the unchanged suffix.
   Equal weak orders preserve every pairwise comparison for any dynamic prefix
   and suffix, including changing resource estimates, changeovers and window
   failures. Inductively identical ready sets, selections and resource state
   transitions produce identical SGS placements or failures. Variable arity and
   nonfinite keys are rejected because this proof does not cover them.
4. Validation and full graph-key construction precede deduplication. A failed
   decode is not cached. Pruned profiles do not increment evaluated/accepted or
   output-fingerprint counters. A v2 alias may supply its already decoded
   representative to elite selection without relabeling that result.
5. Default v1/v2 profiles alternate BEFORE configured truncation. Overrides keep
   their explicit order. The v1-only list remains unchanged.
6. For candidate budget B >= 3 with repair enabled, reserve
   `min(max(1, B//4), B-2, top_k*max_neighbors_per_elite)` slots and 25% of the
   remaining phase time (bounded by explicit repair time limit). The soft cutoff
   applies only after a usable elite exists; otherwise profiles may use the
   original budget. B < 3 cannot guarantee v1 + v2 + repair. All decodes share
   the original candidate count and deadline; construction is charged to it.
7. Profile and repair construction both recheck deadline immediately before
   SGS. A started SGS is nonpreemptible and completes scoring even if it overruns.
   Reservations are opportunities, not completion guarantees or a proof of
   universally better finite-budget scores. No baseline or acceptance changes.
8. A18 handoff: `compute_metrics(res, batches,
   expected_operations=algo_ops_to_schedule, seed_results=seed_sr_list,
   failure_details=getattr(summ, "failure_details", ()))`, no legacy fallback.

# Stable Diagnostics

- `state.candidate_profile["graph_ready_optimization"]["profile_efficiency"]`.
- `attempts` item with `tag == "graph_ready_profile_efficiency"`, field
  `profile_efficiency`. It is a `phase_summary`, not a decoded candidate.
- `configured_profiles = considered_profiles + unvisited_profiles`.
- `considered_profiles = profile_decodes + predecode_pruned_profiles +
  construction_rejected_profiles + skipped_before_decode`.
- `profile_decodes` includes started SGS calls that subsequently fail. It is not
  the count of successfully scored candidates. No second rejected increment for
  a decode failure in the equation above.
- `equivalent_profiles` lists only profile/representative slugs, not raw
  operation IDs, decision hashes or resource details. It stays in diagnostics.
- Budget fields: `max_candidates`, `reserved_repair_candidates`,
  `reserved_repair_time_ms`, `stop_reason`. Repair keeps its existing report.

# Verification

Evidence is dirty/unbound and does not claim clean-worktree proof. All pytest
runs used the repository `.venv/bin/python`, verified as Python 3.8.10. The
`.venv/bin/pytest` launcher still points to an old Documents path; invoking
`python -m pytest` avoids that unrelated launcher problem without editing it.

- New independent tests: 52 passed. Exact preorder comparison, ties/near-floats,
  invalid key domains, all 19 profiles through real SGS for each of 4 scenarios
  (plain, seed/dependencies/downtime, automatic resources, failed window) and all
  3 dispatch rules (slack/cr/atc), full result/summary/metric/score equality for
  every pruned profile. Trace through the real SGS confirms dynamic penalties
  include both 0 and 1. Resource-pool isolation, distinct-decision/same-output
  fingerprint rejection, aliases, A18 argument identity, count conservation,
  construction failures, real SGS with controlled clocks, soft reservation and
  nonpreemptible overrun are covered.
- New tests plus existing runtime-tiebreak and repair-neighbor tests: 65 passed.
  Reproduction and machine-readable evidence:
  `.venv/bin/python -m pytest -q tests/algorithm/test_optimizer_profile_predecode_dedup.py
  tests/algorithm/test_optimizer_profile_budget.py
  tests/algorithm/test_optimizer_graph_ready_runtime_tiebreak_contract.py
  tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_neighbors.py
  --junitxml=.codestable/refactors/2026-09-08-optimizer-candidate-efficiency/targeted-tests.xml`.
- Ruff on all 7 changed/new product and test files: passed. Python 3.8 syntax
  scan: 7 files, 0 findings. The benchmark evidence script also passes Ruff.
- `python -m pyright -p pyrightconfig.gate.json`: 0 errors, 15 warnings in
  pre-existing scheduler export declarations, outside this write set.
- Targeted architecture gate: file size and runtime asserts passed. Complexity
  failed on the following outside-write-set functions (not modified here):
  `optimizer_graph_ready_repair_neighbors.py:27 build_repair_neighborhood` (17),
  `schedule_input_seed_metadata.py:18 with_frozen_external_seed_metadata` (27),
  `schedule_seed_contracts.py:60 coerce_seed_result_item` (16).
- Targeted `git diff --check`: passed. Product files remain under 500 lines
  (entry 447, candidates 479, profiles 226, predecode 116, budget 51).
- No full quality gate was run: the approved feature explicitly excludes the
  long whole-repository gate, the worktree is shared/dirty, and registry/legacy
  benchmark contract migration belongs to the coordinating agent.

# Same-Budget Benchmark

The independent benchmark compares the original local entry/profile source
snapshots with the new implementation, using the SAME current evaluator, A18
and SGS in both arms. The snapshots are `before_optimizer_graph_ready.txt` and
`before_optimizer_graph_ready_profiles.txt`; they are evidence, not runtime code.
The current candidate evaluator is intentionally shared so A18 changes cannot be
mistaken for deduplication gains. No shared ratchet files are edited.

Run `.venv/bin/python .codestable/refactors/2026-09-08-optimizer-candidate-efficiency/benchmark_evidence.py`.
`before-after.json` records per-seed full score, baseline score, actual decode
starts, count, repair count, wall-clock time, profile report, source SHA-256 and
source-stability checks. The final recorded run was not concurrent with this
agent's type/architecture checks. Other host activity is not controlled; timings
are observations, not a regression threshold.

Each suite has seeds 0..4, exactly 100ms configured phase time per arm, the same
count cap and the same input dataset. Runtime uses real `time.perf_counter`,
with alternating arm order. All schedules use real production SGS, no fabricated
results or decode-duration mocks.

| Case | Cap | Wins/ties/losses | Mean total decodes before/after | Mean repair before/after | Median ms before/after |
| --- | --- | --- | --- | --- | --- |
| tiny | 6 | 5/0/0 | 6 / 6 | 0 / 2 | 5.27 / 5.84 |
| tiny | 19 | 0/5/0 | 19 / 19 | 0 / 10.4 | 16.30 / 17.06 |
| tiny | 60 | 0/5/0 | 33.4 / 23 | 14.4 / 14.4 | 28.56 / 21.69 |
| smtwt40 instance 0 | 19 | 0/5/0 | 3 / 3 | 0 / 1 | 129.72 / 129.82 |
| smtwt40 instance 1 | 60 | 0/5/0 | 3 / 3 | 0 / 1 | 129.30 / 130.82 |

Total: 25 pairs, 5 wins / 20 ties / 0 losses. All baseline comparisons and count
budgets passed; source hashes stayed stable during the run. Every new decode
started before the global deadline. 40-operation cases overran the 100ms budget
because the already-started SGS is nonpreemptible; this is NOT a hard realtime
claim. Repair receives more opportunities but does not always improve quality
or reduce elapsed time. These finite fixtures do not prove universal quality
improvement or global optimality.

# Integration Handoff

Historical snapshot before the subsequent explicit test-migration approval:
the two legacy contract files had 87 passed / 8 failed, with migration initially
assigned to the coordinating agent. Earlier combined run including runtime and
neighbor contracts: 100 passed / 8 failed. These failures are resolved by the
authorized migration below; the list is retained to explain the changed tests.

- `test_optimizer_graph_ready_candidate_contract.py`:
  `test_graph_ready_candidates_run_real_sgs_weight_grid` (minimum decode count),
  `test_graph_ready_v2_missing_due_date_keeps_v2_production_candidates_even_in_strict_mode`
  (expects a decoded v1-grid alias; also indexes candidate_origin on a phase-summary),
  `test_graph_ready_v2_runs_real_sgs_and_keeps_repair_attribution_separate`
  (old v2 helper count threshold),
  `test_graph_ready_candidates_deduplicate_same_output_fingerprint`
  (an equal graph decision now stops before output fingerprint evaluation).
- `test_optimizer_graph_ready_v2_elite_repair_contract.py`:
  `test_remaining_profile_candidate_budget_blocks_repair` (19 decoded profiles),
  `test_no_v2_elites_due_to_profile_cap_is_explicit` (all first 9 were v1),
  `test_global_deadline_blocks_all_repairs` (clock advances only at decode 19),
  `test_disabled_repair_keeps_production_profile_search` (19 decoded profiles).

Do not migrate these by inventing evaluated/rejected candidates. The stable
conservation equations above distinguish considered profiles from actual SGS
calls. The new independent real-chain test still locks output-fingerprint
rejection for genuinely different graph decisions that decode identically.

# Changed Paths

- `core/services/scheduler/run/optimizer_graph_ready.py`
- `core/services/scheduler/run/optimizer_graph_ready_candidates.py`
- `core/services/scheduler/run/optimizer_graph_ready_profiles.py`
- `core/services/scheduler/run/optimizer_graph_ready_predecode.py` (new)
- `core/services/scheduler/run/optimizer_graph_ready_budget.py` (new)
- `tests/algorithm/test_optimizer_profile_predecode_dedup.py` (new)
- `tests/algorithm/test_optimizer_profile_budget.py` (new)
- This record directory, benchmark runner/snapshots/JSON and targeted test XML.

`optimizer_graph_ready_repair.py` was NOT edited: initial and final SHA-256 are
both `e76ba9a4b8b413253c1cfc5d989862225a13e9d7147f4ab2ff4a74092bcd643c`.
All existing and new changes remain uncommitted; no staging, commit or cleanup.

# Authorized Contract Migration (2026-09-08)

The user subsequently authorized narrowly migrating the eight legacy failures.
This follow-up changed only these test/support files plus this record:

- `tests/algorithm/test_optimizer_graph_ready_candidate_contract.py`:
  the v1 fixture still requires all 9 configured profiles, real improvement,
  diversity and a changed output; actual decode count now closes with predecode
  prunes and the one baseline evaluation. The missing-due fixture requires all
  19 configured profiles to be decoded or represented by a proven alias, with
  every alias referencing an actually decoded representative. The v2 real-SGS
  test retains ALL quality, origin, oracle-boundary and repair assertions while
  adding accounting and count-budget checks. The same-output test uses distinct
  graph decisions, so it still requires actual `same_fingerprint` rejection;
  only one improvement event is accepted, and predecode aliases are not counted
  as evaluations or acceptances.
- `tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_contract.py`:
  a 19-call cap now validates that profiles and repair share the cap, that repair
  gets positive capacity and that excess neighbors are skipped. Cap 9 requires
  early v1/v2 coverage and real repair; an additional cap-1 case preserves the
  explicit no-elite boundary. The controlled deadline now expires on the first
  actual v2 decode, independent of obsolete ordinal 19, and still requires no
  repair SGS starts, zero repair time/calls and a marked global deadline. When
  repair is disabled, all 19 profiles are covered by decodes plus exact prunes;
  no repair time/slots/calls are reserved or used. Baseline and budget assertions
  remain in each migrated case.
- `tests/_support/optimizer_graph_ready_v2_benchmark.py`:
  `candidate_profile_count` now means configured profiles, matching the v1
  helper's coordinating-agent update. `decoded_profile_count` counts actual
  non-repair attempts. `profile_efficiency`, `configured_profile_slugs` and
  `covered_profile_slugs` expose actual-or-proven coverage. The pass predicate
  requires complete 19-profile coverage, no construction rejection or budget
  skip, exact decode/prune accounting and actual profile+repair evaluations
  within the cap. All prior quality, diversity, baseline and v1-improvement
  checks remain. New negative tests reject incorrect counters, missing v2
  coverage and total-budget overspending.

Verification immediately before migration: 152 passed / 8 failed across the
six dedicated files. After migration, including nine extra parameterized cases:
**169 passed, 0 failed**, executed with Python 3.8.10. The result is saved as
`integration-tests.xml`; the previous `targeted-tests.xml` remains unchanged.

Reproduction:

```bash
.venv/bin/python -m pytest -q \
  tests/algorithm/test_optimizer_graph_ready_candidate_contract.py \
  tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_contract.py \
  tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_neighbors.py \
  tests/algorithm/test_optimizer_graph_ready_runtime_tiebreak_contract.py \
  tests/algorithm/test_optimizer_profile_predecode_dedup.py \
  tests/algorithm/test_optimizer_profile_budget.py \
  --junitxml=.codestable/refactors/2026-09-08-optimizer-candidate-efficiency/integration-tests.xml
```

Ruff, Python 3.8 syntax scan and `git diff --check` passed for the three migrated
test/support files. No product code was changed in this follow-up. Public
projection tests (including those inside the migrated files) were not edited;
the shared ratchet test, v1 benchmark helper, A18 VNS/GRASP/build_order fixtures
and the three other agents' complexity findings were not modified. No full gate,
real database, subagent, staging or commit; this remains dirty/unbound evidence.

# Authorized Repair-Neighbor Extraction (2026-09-08)

The user subsequently assigned the existing repair-neighbor CC17 integration
tail to this task, with behavior-preserving helper extraction only. No new
operator, ordering policy, whitelist entry or unrelated complexity fix.

- Product change: `core/services/scheduler/run/optimizer_graph_ready_repair_neighbors.py`.
  `build_repair_neighborhood` retains mutable-scope validation, signal collection
  and the original `zip_longest` interleaving. Extracted unchanged expressions
  into `_risky_batch_indices`, `_adjacent_swap_moves` and `_single_insert_moves`.
  Risk ranking/top-3, stable seeded shuffle, insertion targets, boundary moves,
  duplicate moves and evaluation order are unchanged.
- Tests: `tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_neighbors.py`.
  Kept all 11 existing tests; added a full pre-extraction seed-7 move sequence
  and three zero-signal boundary cases (empty, single batch, two batches).
- Original module is preserved as `before_repair_neighbors.txt`. A differential
  run loaded that snapshot and compared batch order, exact ordered move tuples
  and materialized neighbors against the extracted implementation for 180 cases:
  sizes 0..8, four risk/order patterns (including no risk and filtered fixed
  batches), seeds -7/0/1/7/123. All comparisons passed; global RNG state stayed
  unchanged. This is finite characterization, not a new neighborhood policy.
- The gate's `tools.quality_gate_scan.complexity_scan_map(..., include_all=True)`
  measured the snapshot entry at CC17 and the new entry at **CC9**. Helpers are
  CC4/CC3/CC4; all functions/classes in this module are <=9, below threshold 15.
- Full dedicated six-file regression: **173 passed, 0 failed**, saved as
  `neighbor-extraction-tests.xml` using the same six-file command as the previous
  section with the new XML filename. Existing integration XML is preserved.
- `tests/gate_meta/test_architecture_fitness.py -k
  'file_size_limit or cyclomatic_complexity_threshold'`: **2 passed** on the
  current shared worktree. Other agents' complexity changes are not attributed
  to this task. No allowlist/ledger changes were made here.
- Ruff and the Python 3.8 compatibility scan passed for the module and its
  neighbor tests. No real DB, subagent, commit or full quality-gate run.

All evidence remains dirty/unbound. Previous "not owned/not modified" statements
above describe the earlier approval boundary; only this explicitly authorized
repair-neighbor module is newly included, not the other complexity items.
