---
doc_type: refactor-apply-notes
refactor: 2026-09-08-remaining-dependency-cycles
scope: web/routes backend helpers and scheduler consumers
status: completed
---

# a4-routes apply

- Start: shared dirty worktree; pre-existing modifications preserved.
- Characterization: 65 passed in 1.11s; `/tmp/remaining-cycles-characterization-20260908.log`.
- Seven helper implementations moved to `web/routes/helpers/`; old module attributes explicitly re-export the same objects. Fourteen scheduler and 28 root route modules change imports only, preserving their pre-existing dirty code. The private `_normalized_form_values` return annotation changes from list[str] to typing.List[str] for the Python 3.8 gate; its body is unchanged.
- Tests: 81 passed in 5.03s, including new fresh-process forward/reverse imports, all moved function/class identities, shared hmac patch execution and existing route patch contracts. Log: `/tmp/remaining-cycles-a4-tests-final-20260908.log`.
- Both scopes: scheduler directory leaves the A4 SCC. The remaining `.` / `web/bootstrap` / `web/routes` SCC has 13 edges caused by startup/config ownership outside this helper slice; no helper is in it. A5/A6/tests unchanged, explicit hard file SCC remains zero. JSON: `/tmp/remaining-cycles-a4-{production,tests}-20260908.json`.
- Adjustment: one new test initially named a nonexistent `ImportMode.MERGE`; changed test data to existing APPEND. Existing 80 tests passed before that correction. Ruff only sorted compatibility imports.
- Tool incident: pre-implementation symbol_locator noticed changing sources and auto-rebuilt `.codestable/checkup/latest/callgraph/`, despite the intended read-only use; concurrent invocations produced one transient JSON read failure. No preimage was available and no unsafe restore was attempted. All later locator calls set `CHECKUP_CALLGRAPH=/tmp/remaining-cycles-locator-20260908`. The main agent must re-seal the shared callgraph; these are not controlled final snapshots.
- Proof boundary: dirty targeted proof only; no staging or commit.

## Final direct-canonical verification

- The first candidate hid 161 known confident incoming edges because root route consumers still imported compatibility wrappers. Updated all 28 direct root consumers to canonical helper imports inside the same authorized backend scope; no handler or registration body changed.
- Expanded integration: 1071 passed in 93.20s, covering all web_pages, excel_data_io, route_view, selected safe-next/summary contracts and all four new boundary test modules. Log: `/tmp/remaining-cycles-integration-final-20260908.log`.
- Callgraph: 56 moved callable identities all map; all 278 related old confident edges are present after mapping. Two independent final graphs in `/tmp/remaining-cycles-direct-callgraph-{1,2}-20260908` have identical SHA256 for all 10 JSON files. No claim is made that unrelated concurrent callable changes are this slice's work.
- Final scans are `/tmp/remaining-cycles-direct-{production,tests}-20260908.json`; both scopes retain only the unrelated startup/config directory SCC. No new hard SCC edge or unresolved callsite relative to the saved dirty start.
- Governance handoff, not a behavior change: migrate `fallback:web-routes-excel_utils-read_uploaded_xlsx-fef185cd8db6` to `fallback:web-routes-helpers-excel_utils-read_uploaded_xlsx-fef185cd8db6`. Existing cleanup exception behavior was kept; the main agent owns ledger updates.
