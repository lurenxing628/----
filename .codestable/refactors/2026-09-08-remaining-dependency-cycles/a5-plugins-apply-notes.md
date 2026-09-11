---
doc_type: refactor-apply-notes
refactor: 2026-09-08-remaining-dependency-cycles
scope: core/plugins/manager.py import only
status: completed
---

# a5-plugins apply

- Start: shared dirty worktree; pre-existing modifications preserved.
- Characterization: 65 passed in 1.11s; `/tmp/remaining-cycles-characterization-20260908.log`.
- One production import changed: `core.plugins.manager.normalize_yes_no_wide` now imports the established `core.shared.boolean_normalize` policy. No function body or rollback statement changed.
- Tests: 39 passed in 0.58s; includes seven defaults against service policy, plugin public identities and import order, executable manager patch, failed registration rollback, conflicts, telemetry and Excel backend fallback. Log: `/tmp/remaining-cycles-a5-tests-20260908.log`.
- Both scopes: the 2-directory / 2-edge A5 SCC disappears; other directory SCCs unchanged. Existing parent-package-only `core.plugins` / `core.plugins.manager` file SCC remains intentionally: eager public PluginManager export, no explicit hard file SCC and both import orders pass. Do not rewrite this API for a zero count.
- Scan JSON: `/tmp/remaining-cycles-a5-{production,tests}-20260908.json`; unresolved stays 6 / 45, parse errors zero. Module totals can drift due to the other agents in this shared worktree.
- Ruff passed. Dirty targeted proof only; no baseline change or staging/commit.

## Python 3.8 final scope check

- The 78-file final compatibility scan exposed the pre-existing public `reset_plugin_state(base_dir: str | None = None)` annotation. Changed only the equivalent annotation to `Optional[str]`; parameter name/default, public object identity and function body remain unchanged.
- Added a Python 3.8 `typing.get_type_hints` assertion. This is a platform-compatibility correction, not a change to plugin behavior or registry state.
