---
doc_type: refactor-scan
refactor: 2026-09-08-remaining-dependency-cycles
scope: core/plugins/manager.py import only
status: user-reviewed
---

# a5-plugins scan

manager imports service enum_normalizers only for wide yes/no; common.excel_backend_factory imports the plugin API. core.shared.boolean_normalize already has the same policy and a lockstep test.

- Evidence: `/tmp/remaining-cycles-before-production-20260908.json` and `/tmp/remaining-cycles-before-tests-20260908.json`; explicit hard file SCC = 0, parse errors = 0. Directory SCC is not proof of an ImportError.
- Category: structure. One root-cause slice, not cosmetic cleanup.
- Prechecks: behavior unchanged; characterization first; existing roadmap supplies boundaries; scope split into four independent slices; no generated/vendor edits; no extra candidates invented.
- Authorization: current request expressly authorizes all four scan/design/apply slices without repeated checkpoints.
- Risk: medium for moved helpers and patch state; low for import-only plugin change.
- Methods: M-L3-06, M-L1-04.
