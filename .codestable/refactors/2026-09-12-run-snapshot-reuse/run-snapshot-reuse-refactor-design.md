---
doc_type: refactor-design
refactor: 2026-09-12-run-snapshot-reuse
status: approved
scope: Workbench combined candidate preparation and computation
summary: Remove a duplicate full input fingerprint scan inside one continuous read transaction.
---

# Run snapshot reuse

## Authorization and scope

The user authorized implementing the algorithm study's improvements. Main assigned
this bounded input/runtime change and explicitly chose a private continuous helper
over a reusable token or a new transaction-capability system. Use project
cs-refactor methods M-L4-01 (reuse unchanged work), M-L2-01 (extract the shared
computation body), and M-L1-04 (characterization and boundary tests).

Before editing, the working tree was clean. Symbol-locator callers for
prepare_candidate_run_input and compute_prepared_candidate_run identified the
combined service and worker entrypoints; independent admission/adoption input
preparation remains unchanged. No schema, dependencies, algorithms, execution
seeds, output-validation rules, business database, commit, full gate or large
performance run belongs to this change.

## Design

1. Keep compute_prepared_candidate_run's connection/version checks and complete
   full_facts_fingerprint comparison. An input kept by a caller across transactions
   must still be rejected after any fact changes, including unselected tables.
2. Make the combined entrypoint invoke a private prepare-then-compute helper inside
   the existing candidate_read_snapshot. Preparation still reads the identical
   full fingerprint through PreflightFacts.snapshot. It passes its local result
   directly to the private computation body with no caller callback, returned
   prepared input, stored cache or independently reusable bypass flag between
   those operations. SQLite query_only and the outer read transaction cover both.
3. Preserve same-connection/version validation and explicitly require the private
   computation body to remain inside an active query_only transaction. These
   checks verify the internal scope, not a conn-id/counter-based cache validity
   claim. The proof is the continuous owned control flow and existing read scope.
4. Route the worker through the same combined entrypoint, retaining its private
   in-memory database snapshot and pre-computation/final-persistence fact checks.
   Existing test/profiling hooks attached to the old split worker calls must be
   migrated without weakening concurrent-write, lock, recovery or timing checks.
5. Share the computation body after freshness has been established; keep all
   candidate payload, seed, window, chain and piece validations unchanged.

## Selected payload disposition

Do not introduce a cache keyed by mutable results/input identity. The selected
candidate currently crosses summary-building before its second payload validation;
safe reuse requires proof of unchanged source values and validator inputs. Inspect
the isolated current-source profile before deciding whether that one avoided
validation justifies a new proof surface. Record the measured disposition in the
apply notes; this optimization is not silently counted as implemented.

## Verification

- Count full fingerprint calls: combined preparation/computation reduces from two
  to one; separately prepared computation still performs its own full check.
- Compare complete candidate payload rows, states, metrics and protected input
  contents between combined and independent entrypoints.
- Prove stale selected/unselected facts still reject at the independent boundary;
  preserve caller transaction, query_only state and authorizer, including failures.
- Run focused real worker tests for concurrent original-database writes, final
  revalidation, shared run lock and restart retention. Avoid large capacity tests.
- Run scoped Ruff and Python 3.8 type checks. This is scoped dirty-worktree proof,
  not a full quality gate, clean-worktree proof or a claimed total speedup.
