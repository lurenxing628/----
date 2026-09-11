---
doc_type: refactor-design
refactor: 2026-09-08-remaining-dependency-cycles
scope: core/plugins/manager.py import only
status: approved
summary: Preserve behavior while removing the verified return dependency
---

# a5-plugins design

Change the manager normalizer import to the existing core.shared.boolean_normalize leaf. Preserve _normalize_yes_no, PluginManager, state ownership, public package identities, registry behavior and the pre-existing registration rollback fix.

- Methods: M-L3-06, M-L1-04.
- Start contract: existing characterization set passed 65 tests before implementation.
- Verification: focused existing tests, new identity/import-order/patch/AST boundaries, Python 3.8, Ruff and both import scopes.
- No runtime dependency added. No lazy import or dynamic module alias hides a dependency.
- Rollback: reverse only this slice against `/tmp/remaining-cycles-start-files-20260908.tar`; never restore a whole shared dirty file without reconciling concurrent changes.
- API guards: old signatures and same-object re-exports; natural canonical __module__ for moved helpers; actual route/plugin patch globals remain executable.
- Exclusions: frontend integration/templates/styles, forbidden infrastructure/algorithm/scheduler paths, baselines, roadmap, registry, governance ledger, staging/commit/push.
- Full gate and final evidence updates belong to the main agent; local checks cannot establish clean-worktree proof.
