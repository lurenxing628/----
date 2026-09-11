---
doc_type: refactor-apply-notes
refactor: 2026-09-08-remaining-dependency-cycles
scope: report numeric value leaf and its consumers
status: completed
---

# a6-reports apply

- Start: shared dirty worktree; pre-existing modifications preserved.
- Characterization: 65 passed in 1.11s; `/tmp/remaining-cycles-characterization-20260908.log`.
- Number parsing moved byte-for-byte into `core/services/report/values/number_parsing.py`; old exports preserve identities and __all__. Five direct consumers now import canonical functions. Report orchestration, degradation changes already in the worktree and exporters' execution bodies are untouched.
- Tests: 47 passed in 5.02s; old/new and ReportEngine import order/identity, numeric validation/field/message, ordinary/write-only XLSX sheet/cell equivalence, executable exporter parser patch, existing degradation, date and size contracts. Log: `/tmp/remaining-cycles-a6-tests-final-20260908.log`.
- Both scopes: A6 2-directory / 3-edge SCC removed; parent-aware report file SCC retained because ReportEngine remains an eager public API. Explicit hard file SCC still zero. JSON: `/tmp/remaining-cycles-a6-{production,tests}-20260908.json`; unresolved 6 / 45, parse errors zero.
- Test-only adjustment: Python 3.8 SpooledTemporaryFile lacks the seekable attribute expected by the XLSX reader; verification now reads the returned bytes through BytesIO. Product buffer type is unchanged.
- Ruff import ordering fixed; no baseline, frontend or Git index changes. Dirty targeted proof only.
