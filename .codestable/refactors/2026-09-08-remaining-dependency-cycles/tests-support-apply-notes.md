---
doc_type: refactor-apply-notes
refactor: 2026-09-08-remaining-dependency-cycles
scope: shared test infrastructure only
status: completed
---

# tests-support apply

- Start: shared dirty worktree; pre-existing modifications preserved.
- Characterization: 65 passed in 1.11s; `/tmp/remaining-cycles-characterization-20260908.log`.
- Moved shared resource-dispatch script support unchanged to `tests/_support/`; extracted four scenario fixture functions and two constants from the collected gantt test. All old function identities, test names/assertions, SQL seed rows and app lifecycle behavior remain.
- Direct consumers adjusted: operation_execution support, scenario secondary-output test and frontend-language test import the shared leaves. No frontend code or assertion changed.
- Initial 155-test pass exposed a remaining 3-directory / 8-edge SCC: the frontend-language test still imported the old resource-dispatch support path. Switching that one missed consumer removed the remaining test SCC without moving additional fixture code.
- Final focused tests: 178 passed in 28.63s. Includes full resource_dispatch suite, gantt scenario tests, scenario secondary outputs, identity guard, task detail, language contracts and three new identity/import-isolation/seed tests. Log: `/tmp/remaining-cycles-tests-support-final-20260908.log`.
- Final dual-scope snapshots: `/tmp/remaining-cycles-final-{production,tests}-20260908.json`. Tests SCC absent. The unrelated startup/config production SCC remains, explicit hard file SCC zero, parse errors zero, unresolved 6 / 45.
- Ruff import ordering only; shared fixture import does not load a collected test or app. Dirty targeted proof, no registry or Git index changes.
