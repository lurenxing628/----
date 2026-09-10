# FJ / FE-04 Scoped Fix

- Date: 2026-09-10. Product/test source frozen at 16:27:48 +08:00.
- Scope: FE-04 only, plus the 21 explicitly approved mechanical import consumers. No next batch.
- Result: shared ownership and the four assigned reverse imports fixed; whole-repository gates remain red.
- Runtime: repository `.venv/bin/python`, Python 3.8.10. No dependency installation, schema/DLL changes, stage, commit, build, or preview reload.

## Implementation

- `core/services/process/quota_protection.py` owns `ProcessQuotaProtection`, `quota_skip`, and `quota_skip_summary`.
- `core/services/scheduler/template_lineage.py` owns `TemplateLineageWriter`; `template_lineage_query.py` owns `TemplateLineageQuery` and origin validation.
- The three previous workbench modules explicitly re-export the same objects; no wrappers, duplicate business implementations, dynamic exports, or scanner exclusions.
- `process/part_service.py`, `process/part_operation_hours_excel_import_service.py`, `scheduler/batch_copy.py`, and `scheduler/batch_template_ops.py` import the neutral owners directly.
- `core/services/process/__init__.py` is now a documentation-only package entry. The former 12 symbols remain at their explicit leaf paths. Cold imports and object identity are tested.
- Transactions, BEGIN IMMEDIATE/savepoints, same-key/revision checks, lock ownership, permanent refs, origin history, raw source values, and all business method bodies are unchanged. Final AST comparison proves all 28 moved/import-only modules match their pre-FJ non-import bodies.

## Approved Consumers

Only imports were changed in these 21 files:

```text
web/routes/process_parts.py
web/routes/equipment_pages.py
web/routes/process_suppliers.py
web/routes/process_excel_suppliers.py
web/routes/process_excel_routes.py
web/routes/domains/scheduler/scheduler_batch_detail.py
web/bootstrap/request_services.py
web/routes/equipment_excel_machines.py
web/routes/process_op_types.py
web/routes/process_excel_route_apply.py
web/routes/process_excel_op_types.py
scripts/convert_rotary_shell_unit_excel.py
tests/_scripts_e2e/smoke_phase5.py
tests/excel_data_io/test_unit_excel_converter_diagnostics_visible.py
tests/excel_data_io/test_unit_excel_station_block_dropped_visible.py
tests/excel_data_io/test_unit_excel_first_sheet_and_sheet_not_found.py
tests/excel_data_io/test_unit_excel_converter_duplicate_part_rows_no_override.py
tests/excel_data_io/test_unit_excel_date_coerced_cells_diagnosed.py
tests/excel_data_io/test_unit_excel_converter_merge_steps_and_classify.py
tests/excel_data_io/test_excel_conversion_output_contract.py
tests/excel_data_io/test_unit_excel_route_map_degradations_visible.py
```

Repository AST/import/string searches, product dynamic loader tables, `plugins/`, and plugin documentation found no package-level dynamic attribute consumer or documented external public contract for the removed convenience exports. The existing string patch targets `core.services.process.workflow_state.record_confirmation`, which is unchanged. This is a repository evidence boundary, not a claim about unknown external plugins.

## Verification

| Run | Result | Evidence in this directory |
| --- | --- | --- |
| Pre-edit FE-04 five groups | 79 passed | Initial terminal run |
| Final five groups + new dependency contract | 94 passed | `fj-fe04-focused-final.xml` |
| Legacy copy/template/protection/adoption | 198 passed, 3 failed | `fj-fe04-legacy-protection.xml` |
| Real zero-duration and piece engine/adoption chains | 228 passed | `fj-fe04-zero-piece.xml` |
| Import consumers, plugin boundary, factory | 63 passed | `fj-fe04-import-consumers.xml` |
| Original eight source modules replay, same three failing nodes | 3 failed identically | `fj-fe04-before-replay.xml` |
| Architecture fitness | 17 passed, 4 failed | `fj-fe04-architecture.xml` |
| All 33 FJ code/test files: Ruff and Python 3.8 syntax | Passed | `fj-fe04-ruff.log`, `fj-fe04-py38.log` |
| Scoped Pyright | 23 analyzed, 0 errors/warnings | `fj-fe04-pyright.json` |
| Tracked scoped diff whitespace | Passed | `git diff --check` |

The final focused run and baseline replay used an unused `PYTHONPYCACHEPREFIX` plus `PYTHONDONTWRITEBYTECODE=1`; no existing bytecode or preview state was deleted. Baseline replay loaded the exact eight pre-FJ files from `/tmp/aps-fj-fe04-before-MLFhKa` through a test-process-only loader. It did not restore or modify the shared worktree.

## Retained Red Results

1. `tests/workbench/test_legacy_batch_lineage_copy.py:57` and `:261`: preservation expectations omit dashboard item additions. `core/infrastructure/workbench_dashboard_schema.py:39` installs the existing batch-ref insert trigger, which adds delivery/material rows. Both fail with the exact pre-FJ copy implementation as well.
2. `tests/web_pages/test_batch_template_autobuild_same_tx.py:38`: duplicate `BatchOperations.op_code` raises raw `sqlite3.IntegrityError` from `data/repositories/workbench_template_lineage_repo.py:88`, while the legacy test expects `AppError`. The identical error is reproduced through the pre-FJ writer at its original workbench path; no exception contract was changed by FJ.
3. Architecture fitness still detects the existing lazy reverse edge at `core/services/scheduler/execution/execution_ledger_adapter.py:49`. The other three failures are silent-fallback ledger drift, startup sample drift, and existing complexity (including unchanged `PartService.update_internal_hours`). User explicitly requested retaining all four failures and that adapter without expanding scope.
4. Both formal import commands still return 1. Captured graphs have one hard directory cycle in web/bootstrap/routes, and nine hard file cycles. The process package-root SCC and assigned service hard SCC are absent, but the smaller `core.services.process.unit_excel` package SCC remains. Baseline comparison also retains the web cycle and, for the tests scan, the same three pre-existing unresolved dynamic imports recorded by FE. No baseline or scanner was changed. See `fj-fe04-imports-product.json`, `fj-fe04-imports-tests.json`, and the comparisons in `fj-fe04-receipt.json`.

## Handoff

- New dedicated test: `tests/workbench/test_fe04_shared_service_dependency_contract.py` (15 cases). FD was notified through the main task, including exact helper paths and scope advice.
- Its whole-graph dependency checks need the scanner's product roots plus tests. Existing `_LINEAGE_SCOPES` and batch scopes need `core/services/scheduler/template_lineage*.py`; process scopes already include `core/services/process/**/*.py`. FJ did not edit the registry.
- `fj-fe04-receipt.json` records all 33 final source hashes, 29 before hashes, 28 non-import AST proofs, test evidence hashes, and checks. Schema, frozen v24..31, both cycle baselines, and the staged diff hash match the pre-edit state.
- All FJ changes are left unstaged/uncommitted. The shared worktree was already dirty and is not an atomic repository snapshot. These are scoped dirty/unbound checks, not full quality-gate or clean-worktree proof.
- The existing worker/preview remains on its previously loaded source. Main task owns the final unified reload. FJ stops after this stage.
