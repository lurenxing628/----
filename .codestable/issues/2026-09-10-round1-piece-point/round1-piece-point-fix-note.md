---
doc_type: issue
date: 2026-09-10
status: fixed
scope: R1-A known first-round piece-point completion
---

# R1-A Piece Point Completion

## Outcome

- The real managed worker, candidate adoption, official read, trial move/save,
  second adoption, fresh production DATE connection and receipt replay all pass.
- Exact original piece work targets one item. Common work keeps batch quantity.
- No schema, dependency, epsilon, expanded calendar, public DTO or runtime flag
  change was made. Existing point-rendering admission remains mandatory.
- Product and focused tests are frozen at the hashes below. No next-round work.

## Implementation Evidence

- `core/services/workbench/zero_duration.py:19`: bind original operation ID,
  batch, piece, permanent operation ref and ledger target/basis before a witness.
- `core/services/workbench/zero_duration.py:111`: candidate points use that
  exact target plus real shift/efficiency rules. Positive work still cannot be a point.
- `core/services/workbench/zero_duration_evidence.py:11`: captured candidate
  evidence binds the exact ref and target, not current master hours.
- `core/services/workbench/zero_duration_evidence.py:60`: frozen trial evidence
  must retain execution, original piece/batch/ref and exact basis value types.
  Common-point basis format is unchanged; piece basis adds its original identity.
- `core/services/workbench/run_input_piece.py:9`: complete piece scope replaces
  the obsolete blanket zero-work prohibition. Full target/graph guards remain.
- `core/services/workbench/trial_calendar.py:27`: witnessed piece points enter
  normal trial calculation; calendar-only opt-in is not an adoption permission.
- `core/services/workbench/piece_adoption.py:77`: rebuilt validated payload
  proves every zero interval; complete scope and fork/join precedence remain.
- `core/services/workbench/piece_adoption.py:108`: current resources, readiness,
  scheduling bounds and duration stay mandatory; complexity 23 -> 11.
- `core/services/workbench/piece_adoption_execution.py:28`: ledger equality,
  complete execution snapshot, seeds, locks and outside reservations retained;
  complexity 23 -> 7. `trial_calendar.original_duration`: 21 -> 12.
- `core/services/workbench/point_plan_query.py:11`: lossless interval parsing
  rejects invalid times and narrows before min/max; both reported type errors fixed.
- `core/algorithm_runtime/piece_input.py` and `plan_point_evidence.py` were
  reused unchanged. No other owner's product file was edited.

## Tests

- New: `tests/workbench/test_round1_piece_point_chain.py`,
  `test_round1_piece_point_constraints.py`, `test_round1_piece_point_evidence.py`,
  `test_round1_piece_point_protection.py`, `test_round1_piece_point_support.py`.
- Updated old contracts: `tests/workbench/test_piece_chain_boundaries.py:39`,
  `test_piece_chain_input.py:37`, `test_piece_adoption_boundaries.py:51` and `:68`.
  Blanket rejection was replaced by real witnessed success plus no-witness,
  nonzero-work and wrong-target rejection; incomplete-stage rejection remains.
- Full chain: `test_round1_piece_point_chain.py:22` uses the real managed
  background worker and `get_connection` DATE conversion against a private DB.
- Occupancy/calendar/DAG: points can coexist with common points and positive
  intervals without occupied time; predecessors still constrain them. Off-shift
  moves reject without writes. The engine's existing conservative downtime slot
  choice is unchanged; a witnessed in-shift point can be trial-moved inside downtime.
- Protection: locks/freeze survive the next managed run; started work cannot move;
  a real positive execution interval for nominal zero work is preserved through
  subsequent candidate/trial adoption, without rewriting original reports.
- Historical master hours do not rewrite witnesses. Changed piece identity fails
  closed instead of borrowing an old witness. Bare legacy zero, wrong ref/target,
  missing execution, boolean/float basis quantity and tiny positive work reject.

## Verification

Runtime: `.venv/bin/python --version` -> Python 3.8.10.

```bash
env PYTHONPYCACHEPREFIX=/tmp/aps-r1a-pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/workbench/test_round1_piece_point*.py tests/workbench/test_piece_adoption*.py tests/workbench/test_piece_chain*.py tests/workbench/test_zero_duration*.py tests/workbench/test_ea_zero_duration*.py --basetemp=/tmp/aps-r1a-frozen-tests --junitxml=output/workbench-migration/verification/round1-20260910/r1a-point-regression.xml
```

Result: **240 passed in 124.15s**. All test databases and runtime ownership were
private temporary resources; no live database or preview service was accessed.

- Ruff check on all 15 changed product/test paths: `All checks passed!`.
- Pyright on the same paths: `0 errors, 0 warnings, 0 informations`.
- Radon on the seven product files: every function complexity <= 13;
  no allowlist or global configuration changes.
- Evidence: `output/workbench-migration/verification/round1-20260910/r1a-point-regression.xml`.
- Final SHA-256 manifest: `output/workbench-migration/verification/round1-20260910/r1a-source-sha256.txt`.
- Worktree HEAD: `de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`.
- This is dirty/unbound scoped proof, not clean-worktree or full-gate proof.
  Existing staged `tests/gate_meta/test_frozen_bundle_contract.py` remains the
  sole staged path; no staging, commit or removal of shared caches was performed.
- Out of scope and not run: global build, full-site acceptance, 5000-load test,
  Win7 release, old UI removal and mainline frontend/integration acceptance.
