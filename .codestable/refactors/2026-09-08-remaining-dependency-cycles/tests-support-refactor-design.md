---
doc_type: refactor-design
refactor: 2026-09-08-remaining-dependency-cycles
scope: shared test infrastructure only
status: approved
summary: Preserve behavior while removing the verified return dependency
---

# tests-support design

Move resource_dispatch_frontend_support unchanged to tests._support. Extract VERSION, SCHEMA_PATH, _connect, _seed_base, _draft_with_change and _build_app from the collected gantt test into tests._support.gantt_scenario. Keep old helper identities, SQL data, fixture behavior, test names and assertions; update only direct cyclic consumers.

- Methods: M-L2-04, M-L1-01, M-L1-04.
- Start contract: existing characterization set passed 65 tests before implementation.
- Verification: focused existing tests, new identity/import-order/patch/AST boundaries, Python 3.8, Ruff and both import scopes.
- No runtime dependency added. No lazy import or dynamic module alias hides a dependency.
- Rollback: reverse only this slice against `/tmp/remaining-cycles-start-files-20260908.tar`; never restore a whole shared dirty file without reconciling concurrent changes.
- API guards: old signatures and same-object re-exports; natural canonical __module__ for moved helpers; actual route/plugin patch globals remain executable.
- Exclusions: frontend integration/templates/styles, forbidden infrastructure/algorithm/scheduler paths, baselines, roadmap, registry, governance ledger, staging/commit/push.
- Full gate and final evidence updates belong to the main agent; local checks cannot establish clean-worktree proof.
