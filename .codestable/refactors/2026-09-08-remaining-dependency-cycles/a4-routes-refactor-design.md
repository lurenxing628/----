---
doc_type: refactor-design
refactor: 2026-09-08-remaining-dependency-cycles
scope: web/routes backend helpers and scheduler consumers
status: approved
summary: Preserve behavior while removing the verified return dependency
---

# a4-routes design

Move form_values, history_summary_logging, navigation_utils, pagination, enum_display, excel_utils and normalizers to web.routes.helpers. Keep explicit same-object compatibility exports and existing shared hmac patch target. Switch all direct backend route consumers to the leaves; do not change route bodies, registration, templates or styles.

Callgraph refinement: after scheduler-only import changes, 161 known confident edges from root route consumers were hidden behind compatibility exports. As required by A3's direct-canonical contract, the remaining root-route imports must also point at the leaf. This is import-only inside the authorized backend write set, not permission to alter their handlers.

- Methods: M-L2-04, M-L1-01, M-L1-04.
- Start contract: existing characterization set passed 65 tests before implementation.
- Verification: focused existing tests, new identity/import-order/patch/AST boundaries, Python 3.8, Ruff and both import scopes.
- No runtime dependency added. No lazy import or dynamic module alias hides a dependency.
- Rollback: reverse only this slice against `/tmp/remaining-cycles-start-files-20260908.tar`; never restore a whole shared dirty file without reconciling concurrent changes.
- API guards: old signatures and same-object re-exports; natural canonical __module__ for moved helpers; actual route/plugin patch globals remain executable.
- Exclusions: frontend integration/templates/styles, forbidden infrastructure/algorithm/scheduler paths, baselines, roadmap, registry, governance ledger, staging/commit/push.
- Full gate and final evidence updates belong to the main agent; local checks cannot establish clean-worktree proof.
