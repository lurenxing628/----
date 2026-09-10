# R1-D Execution Contract and Dependency Fix

- Date: 2026-09-10. Product/test source frozen at 18:17 +08:00.
- Scope: the assigned five-file 19-error subset, execution adapter/guard complexity, neutral execution and shared plan reads, and the separately approved explicit SGS piece-scope condition.
- This is scoped dirty/unbound evidence. No stage, commit, full gate/build, preview operation, production database, dependency upgrade, Win7 release or next round.

## Implementation

- `core/models/workbench_execution_input.py:18`: `reject` returns `NoReturn`; reference/time parsing has explicit non-optional returns. This fixes 14 nullable-flow diagnostics without weakening runtime rejection.
- `core/services/workbench/production_report_prepare.py:25`: report-batch rejection owns typed row/conflict metadata; code/status/cause and atomic failure are retained. Five attribute diagnostics are removed without changing the generic command error class.
- `core/services/execution/ledger_reader.py:27`: the SELECT-only reader takes an explicit current-plan provider and validated optional clock. It imports no scheduler/workbench/report service. Pure projection, legacy interpretation, quality and totals each have one neutral owner.
- `core/services/workbench/execution_ledger.py:44`: the original service inherits the same load/snapshot methods and adds only original public queries and write contexts. Old helper imports re-export the same objects.
- `core/services/scheduler/execution/execution_plan_identity.py:10`: scheduler supplies the unchanged official identity reader. Shared bounded/query/identity implementation now lives in `core/services/common/{bounded_plan_query,plan_query,plan_identity}.py`.
- Original scheduler query/identity/page modules preserve all original public names and the contract-protected `_normalize_role`, with identical objects. Strict, permissive, scenario, comparison and history semantics are unchanged.
- `execution_ledger_adapter.py:147`: scope selection, projection loading and adaptation are separated, complexity 25 -> 11. `execution_ledger_guard.py:79`: evidence applicability, status and interval checks are separated, complexity 19 -> 5. Protection reasons and stored facts are unchanged.
- `core/algorithms/greedy/dispatch/sgs.py:202`: only explicit `piece_scope` enables per-operation end-time readiness. The graph/type guards remain. No persistence guard or original fixture was edited.
- The assigned `production_report_validation.py` and `workbench_execution_repo.py` did not need edits; `NoReturn` fixes their nullable-flow diagnostics naturally.

## SGS Evidence and Corrected Conclusion

The original legacy fixture retains OP10 `(B1, piece-a, seq10)` and OP20 `(B1, piece-b, seq20)`. A real private run preserved OP10 actual 08:20-08:50 but proposed OP20 at 08:00. The persistence guard uses batch/seq downstream checks and rejected the proposal before writing a new schedule; old formal rows remained identical.

An empty optimizer predecessor set does NOT prove that different pieces are naturally independent: completed operations may have been removed before building that graph. The earlier independence inference is withdrawn. No fixture labels were cleared and no persistence guard was weakened.

The verified cause is the implicit `any(piece_id is not None)` branch enabling the newer ready-time mechanism on that legacy graph without its complete-piece contract. A process-only AST experiment removed only that inference: all three failing completion cases and the real piece collection passed (83 cases), while the SGS source hash remained unchanged. Real workbench piece preparation explicitly sets `piece_scope=True` after validating its complete scope and building its common/piece edges. The approved source fix matches this exact experiment.

## Verification

| Check | Result | Evidence |
| --- | --- | --- |
| Original five-file Pyright reproduction | 19 errors, then 0 | Original `stage-pyright.json`; first handoff |
| Final product Pyright | 25 files, 0 errors / warnings | `pyright-freeze-final.json` |
| Final Ruff and Python 3.8 syntax | 33 files passed | `ruff-freeze-final.log`, `source-proof.json` |
| Original execution plus new error/callback contracts | 90 passed | `type-focused.xml` |
| Neutral boundary, aliases, WAL, 10000-task bounded read and original service-cycle contract | 67 passed | `freeze-focused.xml` |
| Corrected same-domain plan fixture and all public alias contracts | 12 passed | `plan-contract-final-retry.xml` |
| Final plan-query + SGS negatives + original three failures + real piece + point API + candidate query contracts | 141 passed | `plan-sgs-union.xml` |
| Original adapter/guard vs same private facts | 12 passed | `equivalence.xml` |
| Moved-source AST and exact SGS conditional delta | 9 checks passed | `source-proof.json` |
| Formal product import gate | Exit 0, no new cycles/edges/unresolved imports | `imports-product-lock.json`, `cycle-delta-final.json` |
| Formal import gate including tests | Exit 1 in the last R1-D snapshot; subsequent verification belongs to main | `imports-tests-lock.json`, `cycle-delta-final.json` |
| Scoped tracked whitespace diff | Passed | `git diff --check` |

Test collections overlap and are not additive. The 10000-task test is the existing bounded SELECT/query-count contract, not the excluded 5000-operation scheduler load test. All tests used private temporary SQLite or in-memory connections, a private `PYTHONPYCACHEPREFIX` and `PYTHONDONTWRITEBYTECODE=1`. Shared bytecode was not removed.

The old 457-pass/4-failure intermediate collection and original-source replay are retained in `facts-final.xml` / `before-replay4.xml`. Three completion failures are now covered by the final successful SGS run. The fourth candidate-kind storage assertion was assigned to I; R1-D did not change it or claim I's verification as its own.

## Remaining and Handoff

- The last R1-D including-tests snapshot reported `tests/gantt|tests/operation_execution|tests/web_pages|tests/workbench` as a new directory SCC, with no new file cycles, cycle-internal module edges or unresolved imports. Main subsequently reported eliminating that SCC by moving the shared SQLite snapshot helper to `tests/_support/sqlite_snapshot`, with no R1-D source/test changes. Main owns the fresh scan and combined run; R1-D did not rerun or claim those results. No baseline/ignore was changed.
- No execution/scheduler/common-plan service hard or delayed directory cycle remains. The temporary scheduler subdirectory hard SCC introduced during extraction was removed by the shared plan-read boundary, not by narrowing tests or using lazy imports.
- The two intermediate dynamic imports in the new dependency test now use explicit module objects. Its original strict graph assertions remain intact. The temporary plan-fixture shadowing error was corrected with `seed_scenario`, preserving every business assertion.
- Four new test files require main-owned registry/scope integration: `test_round1_execution_contract.py`, `test_round1_execution_dependency_contract.py`, `test_round1_plan_query_dependency_contract.py`, and `tests/algorithm/test_sgs_explicit_piece_scope.py`.
- Source receipt lists all 33 checked paths and SHA256 values. The staged patch remains `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`; the uniquely staged frozen-bundle test was untouched.
- Before-source snapshots and process-only experiment scripts remain under `/tmp/aps-r1-d.UUOpVC/`. Final evidence copies accompany this note. R1-D stops after this handoff.
