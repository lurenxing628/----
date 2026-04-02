# 2026-04-01 core 静默回退基线裁决 / baseline reconciliation

## Decision

- Preserve the original `2026-03-31` audit artifacts as an immutable snapshot:
  - `audit/2026-03/20260331_core_静默回退_inventory_methods.csv`
  - `audit/2026-03/20260331_core_静默回退_inventory.json`
  - `audit/2026-03/20260331_core_静默回退审计.md`
- Do **not** silently rewrite the original baseline counts in place.
- Record post-baseline discoveries and remediation progress in addendum/reconciliation notes first.

## Why the original snapshot is preserved

The `2026-03-31` inventory was later found to have unresolved completeness issues, including at least these verified omissions or under-modeled chains:

- `core/services/process/part_service.py::_save_template_no_tx`
- `core/services/process/supplier_service.py::_validate_fields`
- `core/services/process/supplier_service.py::create`
- `core/services/process/supplier_service.py::update`
- `core/services/scheduler/resource_pool_builder.py::build_resource_pool`
- `core/services/scheduler/schedule_optimizer.py::optimize_schedule`
- `core/services/scheduler/schedule_summary.py` warning/degradation extraction path

Because the omission set was still moving, directly replacing `68/179` with a new number would have turned a historical snapshot into an undocumented mutable target.

## Current implementation batch linked to this reconciliation

This batch applies the first remediation slice without rewriting the original `2026-03-31` inventory baseline:

1. Route / supplier / persistence observability hardening
   - `RouteParser.parse()` now warns when an external op has no supplier mapping.
   - `RouteParser._build_supplier_map()` now preserves supplier default-days fallback evidence for used op types.
   - `PartService._save_template_no_tx()` now traces `default_days -> ext_days` fallback at persistence time.
   - `SupplierService` create/update write paths now log invalid `default_days` fallback instead of silently swallowing it.

2. Warning / summary pipeline hardening
   - `build_result_summary(..., algo_warnings=..., warning_merge_status=...)`
   - result summary now unions `summary.warnings` with independent `algo_warnings`
   - freeze degradation extraction now reads from the unioned warning list
   - warning merge failure is recorded structurally in `result_summary_obj["algo"]["warning_pipeline"]`

3. Resource-pool degradation observability
   - `build_resource_pool(..., meta=...)`
   - result summary now exposes `result_summary_obj["algo"]["resource_pool"]`

4. Weighted-optimizer falsy-weight fix
   - `optimize_schedule()` / `_run_multi_start()` / `_run_ortools_warmstart()` now preserve configured `0.0` weights instead of coercing them back to `0.4` / `0.5` via `or` fallback.

## Follow-up requirement

Only after the remaining rescan / traceability work is complete should the project publish either:

- a formal `inventory_version=2`, or
- an explicit addendum with revised counts and scope deltas.
