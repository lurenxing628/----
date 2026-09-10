---
doc_type: issue-fix
status: completed
date: 2026-09-10
scope: R1-C known batch gaps only
---

# R1-C Batch Round 1

Result: **207 unique scoped tests passed**, no failures/errors/skips. All 17 changed product/test files pass Pyright, Ruff and native Python 3.8.10 parsing. All six assigned complexity violations are closed. This round stops here.

## Boundaries

- Shared worktree was already dirty. No staging, commit, global build, preview operation, production DB, dependency upgrade, threshold change or allowlist change.
- The only staged path at entry was `tests/gate_meta/test_frozen_bundle_contract.py`; it is not an edit target.
- Test runtime: repository Python 3.8.10, private SQLite fixtures and `/tmp/aps-r1c-ow1OHI` environment. Every verification uses a fresh `PYTHONPYCACHEPREFIX` and `PYTHONDONTWRITEBYTECODE=1`; shared caches are not deleted.
- Stop after this round. No whole-site acceptance, 5000-load test, Win7 release or old UI retirement.

## Closed: Legacy Copy And Transaction Errors

- Reproduced the three requested original failures: `legacy-before.xml`, 3 failed.
- `WorkbenchTemplateLineageRepository.insert_instance` now uses inherited `BaseRepository.execute`, preserving the existing `DUPLICATE_ENTRY` mapping, original SQLite cause and details. No writer, source, revision, copy payload or transaction changes.
- The duplicate-code test keeps its exact domain error assertion and adds a later-operation collision, full schema/table/sequence equality and no-open-transaction assertion. Both first and later collisions roll back automatic templates, batch rows and metadata completely.
- The copy preservation oracle now counts the exact delivery/material pair per new batch identity and validates unique 48-hex item identities. Old rows and exact total counts remain required for every table.
- Once the dashboard omission was fixed, current schema revealed another existing append trigger: `wb_outsourcing_operation_born`. Its new origin rows are checked one-for-one against new operation refs and their actual new batch refs, not skipped. No outsourcing source/schema was changed.
- Empty copy uses the same full-table preservation oracle. The 50-batch/150-operation copy case retains real nonempty plans, execution, materials, identity and origin history.
- Command: isolated `.venv/bin/python -m pytest -q -p no:cacheprovider` over `tests/workbench/test_legacy_batch_lineage_copy.py`, `tests/web_pages/test_batch_template_autobuild_same_tx.py`, `tests/workbench/test_template_lineage_writes.py`, `tests/workbench/test_template_lineage_integrity.py`.
- First closure: **53 passed in 17.31s**, `legacy-closed.xml`. The following hashes belong to that first handoff, not the later final source set.

| Source | SHA-256 at closure |
| --- | --- |
| data/repositories/workbench_template_lineage_repo.py | 41f7d0b965e10b31a82d2443d9593ee1b06e232d96b5a758b3115893d462a85f |
| tests/workbench/legacy_batch_lineage_copy_support.py | 083cdfbc1758c33267b7d55547b3528df026904b5086e972293d750fd3067f70 |
| tests/workbench/test_legacy_batch_lineage_copy.py | ea8f95d73607ddbe20bd04acd4941549997ec4becf823f3f3494f4364a1b98b0 |
| tests/web_pages/test_batch_template_autobuild_same_tx.py | bb6b2a51257b91798ceed08f6fcf87a1f08cf763dc32bbb8fcc11fbfbc818ad6 |

## Closed: Types And Complexity

- Baseline: `output/workbench-migration/verification/point-main-20260910/stage-pyright.json`, exactly 19 errors in the seven assigned files.
- Baseline complexity: `output/workbench-migration/verification/round1-20260910/architecture-before.log`: batch_scope 28, read_batch_file 26, preview 33, sync_preview 27, update 17, _validate 17.
- Final scoped Pyright: **17 files, 0 errors/warnings**. The seven original product files account for exactly 19 baseline diagnostics. Expanding the check to edited tests exposed four pre-existing `Workbook.active` optional accesses in `test_batch_files.py`; explicit nonempty-sheet assertions close these too. No test expectation is removed.
- `normalize_batch_input` now constructs its actual heterogeneous result from separately normalized fields. `BatchFacts.load` similarly keeps table rows separate from workflow/ref/execution metadata until assembly. These remove incorrect homogeneous-dictionary inference without widening to `Any`.
- `operation_execution_fields` explicitly handles unavailable execution state by retaining stored status. File preview branches directly on actual batch absence/replacement before accessing existing batch fields. GET scope keeps raw request text separate from parsed integer values. Non-create commands require the existing public-ref contract before using the subject.
- Excel reading is split into workbook lifetime/format validation, first-sheet/header iteration and row parsing; export uses the known first worksheet of the newly constructed workbook.
- Import row normalization and replacement deletion guards live in `core/services/workbench/batch_file_preview.py:12`. Template identity/source/hour/group validation lives in `core/services/workbench/batch_template_validation.py:8`. Resource activity, internal qualification and external period/capability checks stay within their owning operation service.
- No `Any` casts, type ignores, new suppressions, global configuration, thresholds, allowlists or dependencies were introduced.

| Assigned Function | Before | After | Current Definition |
| --- | --- | --- | --- |
| batch_scope | 28 | 2 | core/models/workbench_batch_query.py:9 |
| read_batch_file | 26 | 10 | core/services/workbench/batch_file_codec.py:21 |
| WorkbenchBatchFileService.preview | 33 | 5 | core/services/workbench/batch_files.py:20 |
| WorkbenchBatchOperationService.sync_preview | 27 | 8 | core/services/workbench/batch_operations.py:38 |
| WorkbenchBatchOperationService.update | 17 | 10 | core/services/workbench/batch_operations.py:70 |
| WorkbenchBatchOperationService._validate | 17 | 7 | core/services/workbench/batch_operations.py:103 |

`source-complexity.json` records before/after hashes, all function scores and line counts. The existing shared scanners report no scoped product complexity or size violation at the unchanged threshold 15. Every scoped product function was also checked directly, including the extracted helpers.

## Closed: Import And Protection Regression

- Original batch file tests exposed two more instances of the same dashboard omission at `tests/workbench/test_batch_files.py:54` in the initial source. Both reproduce identically with the exact pre-edit product modules loaded in a private process; `batch-file-before-replay.xml` and `batch-file-before-replay-sources.json` retain the failure and loaded-source hashes. No shared file was restored during replay.
- That test now calls the exact dashboard pair/identity/count oracle at `tests/workbench/legacy_batch_lineage_copy_support.py:126`; other unchanged tables still require full equality. It does not simply skip the dashboard table.
- `tests/workbench/test_batch_round1_boundaries.py` adds 43 cases for strict query values, GET integer parsing, invalid-first-row duplicate reservations, validation-before-append, each import mode's second-insert rollback, raw source and hidden values, and complete external-group period validation.
- `tests/workbench/test_legacy_batch_lineage_copy.py:92` adds a second-operation code collision through real `copy_instance`, requiring exact `DUPLICATE_ENTRY`, original SQLite cause and complete rollback.
- Existing copy/overwrite/append/replace, hidden fields, source/revision history, same-key replay, protected plan/freeze/execution facts and stale-context tests remain enabled. The new rollback tests use real SQLite triggers, not mocked successful writes.

## Final Verification

| Check | Result | Evidence |
| --- | --- | --- |
| Legacy copy, template writes/integrity, strict mode, due-date validation | 60 passed, 29.34s | legacy-final.xml / legacy-final.log |
| Original batch file/actions/commands/transport, execution boundaries/guards/projection/atomicity, lineage schema/calibration, new boundaries | 147 passed, 19.61s | batch-final.xml / batch-final.log |
| Pyright, all 17 changed source/test files | 0 errors, 0 warnings | pyright.json |
| Ruff, all 17 changed source/test files | Passed | ruff.log |
| Native Python 3.8.10 parsing, all 17 files | Passed | python38.log |
| Existing scoped complexity/size scanners | No violations | source-complexity.json |
| Tracked scoped git diff and all 17 files including untracked whitespace | Passed | final-receipt.json |

Each `*-receipt.json` records the exact command, private environment, exit status, output hash and every scoped source hash before/after that run. `final-receipt.json` verifies all final runs used the same 17-file source set, all 207 test identities are unique, and the staged patch stayed unchanged. `round1-source.patch` captures only R1-C edits against the saved pre-edit source, including files already untracked at entry.

## Handoff And Stop

- All 17 changed product/test files are listed with full SHA-256 in `final-receipt.json`. Three new files: the two product helpers above and `tests/workbench/test_batch_round1_boundaries.py`; the other 14 paths already existed at entry.
- `core/services/scheduler/template_lineage.py` remained byte-identical to its saved entry source. The repository insertion change is the only product edit in the legacy lineage path.
- Mainline received each closed stage. Registry ownership stays with mainline: include the two new helpers and new test in the batch source/test scopes; batch file tests now reuse `tests/workbench/legacy_batch_lineage_copy_support.py`.
- All edits remain unstaged/uncommitted. The only staged path is still `tests/gate_meta/test_frozen_bundle_contract.py`, and no changes were made to it.
- No assigned R1-C item remains open. Full quality gate and the four whole-repository architecture failures are not re-judged here; they remain mainline scope. No preview reload or later stage is started.

## Evidence Boundary

These are scoped dirty/unbound checks. Other agents may edit other files concurrently. No clean-worktree proof or full gate claim is made.
