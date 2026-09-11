---
doc_type: refactor-scan
refactor: 2026-09-08-remaining-dependency-cycles
scope: web/routes backend helpers and scheduler consumers
status: user-reviewed
---

# a4-routes scan

Route assembly and seven reusable helper modules share web/routes; scheduler consumers point back to that directory. The start graph also includes bootstrap/config edges owned by the main agent.

- Evidence: `/tmp/remaining-cycles-before-production-20260908.json` and `/tmp/remaining-cycles-before-tests-20260908.json`; explicit hard file SCC = 0, parse errors = 0. Directory SCC is not proof of an ImportError.
- Category: structure. One root-cause slice, not cosmetic cleanup.
- Prechecks: behavior unchanged; characterization first; existing roadmap supplies boundaries; scope split into four independent slices; no generated/vendor edits; no extra candidates invented.
- Authorization: current request expressly authorizes all four scan/design/apply slices without repeated checkpoints.
- Risk: medium for moved helpers and patch state; low for import-only plugin change.
- Methods: M-L2-04, M-L1-01, M-L1-04.
