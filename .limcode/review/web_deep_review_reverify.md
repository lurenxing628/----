# web/web_new_test full deep re-verification review
- Date: 2026-04-02
- Overview: Three-round re-verification review of web/ and web_new_test/, with a focused remediation closeout pass for F002-F007 re-checked from current code and tests.
- Status: completed
- Overall decision: accepted

## Review Scope
---
title: web/web_new_test full deep re-verification review
date: 2026-04-02
status: completed
review_scope:
  - web/
  - web_new_test/
review_mode: read_only
rounds_planned: 3
previous_review_status: pending_reverification
---

# Review Overview

This review restarts the deep review of `web/` and `web_new_test/` from scratch.
All prior conclusions are treated as **pending verification** until re-validated from the current workspace state.

Planned verification rounds:
1. Bootstrap and cross-layer entrypoints
2. Routes and call-chain behavior
3. ViewModels, `web_new_test/`, and regression/test corroboration

Review focus:
- real bugs
- silent fallbacks that may hide bugs
- unnecessary defensive fallbacks / catch-alls
- function/variable/call-chain verification

## Review Summary
<!-- LIMCODE_REVIEW_SUMMARY_START -->
- Current status: completed
- Reviewed modules: app.py, app_new_ui.py, web/bootstrap/factory.py, web/error_handlers.py, web/ui_mode.py, core/services/system/system_maintenance_service.py, core/services/system/maintenance/throttle.py, tests/regression_system_maintenance_throttle_short_circuit.py, tests/regression_system_maintenance_jobstate_commit.py, web/routes/dashboard.py, web/routes/scheduler_batches.py, web/routes/system_history.py, web/routes/equipment_pages.py, web/routes/personnel_pages.py, web/routes/process_parts.py, web/routes/process_suppliers.py, web/routes/excel_utils.py, web/routes/scheduler_calendar_pages.py, web/routes/scheduler_excel_calendar.py, web/routes/personnel_calendar_pages.py, web/routes/personnel_excel_operator_calendar.py, web/routes/system_backup.py, web/routes/scheduler_resource_dispatch.py, web/routes/reports.py, web/routes/system_ui_mode.py, web/routes/system_health.py, web/routes/scheduler_batch_detail.py, tests/regression_dashboard_overdue_count_tolerance.py, web/viewmodels/scheduler_analysis_vm.py, web/viewmodels/system_logs_vm.py, tests/regression_scheduler_analysis_observability.py, tests/test_ui_mode.py, web_new_test/templates/base.html, web_new_test/templates/dashboard.html, web_new_test/templates/scheduler/batches_manage.html, web_new_test/templates/scheduler/batches.html, web_new_test/templates/scheduler/config_manual.html, web_new_test/templates/scheduler/config.html, web_new_test/templates/scheduler/gantt.html, web_new_test/static/css/style.css, web_new_test/static/docs/scheduler_manual.md, web/routes/equipment_excel_machines.py, web/routes/equipment_excel_links.py, web/routes/personnel_excel_operators.py, web/routes/personnel_excel_links.py, web/routes/process_excel_suppliers.py, web/routes/process_excel_routes.py, web/routes/process_excel_part_operation_hours.py, web/routes/process_excel_op_types.py, web/routes/scheduler_config.py, web/routes/scheduler_excel_batches.py, web/routes/scheduler_gantt.py, web/routes/scheduler_run.py, web/routes/scheduler_week_plan.py, web/routes/system_logs.py, web/routes/equipment_downtimes.py, web/routes/excel_demo.py, web/routes/material.py, web/routes/system_utils.py, web/routes/scheduler_utils.py, web/routes/process_bp.py, web/routes/personnel_bp.py, web/routes/equipment_bp.py, web/routes/process_excel_part_operations.py, web/routes/scheduler_pages.py, web/routes/equipment.py, web/routes/personnel.py, web/routes/process.py, web/routes/scheduler.py, web/routes/system.py, web/routes/system_bp.py, web/routes/scheduler_bp.py, web/routes/enum_display.py, web/routes/pagination.py, web/routes/normalizers.py, web/routes/personnel_teams.py, web/routes/process_op_types.py, web/routes/scheduler_ops.py, web/routes/system_plugins.py, web/routes/team_view_helpers.py, tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py, tests/regression_part_service_external_default_days_fallback.py, tests/regression_supplier_service_invalid_default_days_not_silent.py, tests/test_supplier_excel_import_remark_normalization.py, tests/regression_process_excel_part_operation_hours_import.py, tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py, tests/regression_personnel_excel_links_header_aliases.py, tests/test_operator_machine_excel_route_error_handling.py, tests/regression_excel_preview_confirm_baseline_guard.py, tests/regression_excel_preview_confirm_extra_state_guard.py, tests/regression_system_logs_delete_no_clamp.py, tests/regression_system_health_route.py, tests/regression_excel_normalizers_mixed_case.py, tests/regression_page_manual_registry.py, tests/regression_safe_next_url_hardening.py, tests/regression_config_manual_markdown.py
- Current progress: 6 milestones recorded; latest: focused-remediation-reverify-closeout
- Total milestones: 6
- Completed milestones: 6
- Total findings: 6
- Findings by severity: high 0 / medium 4 / low 2
- Latest conclusion: Focused remediation re-verification is stable on the current workspace state. The previously active findings `F002`-`F007` are now remediated by code plus regression evidence, and no replacement high-confidence issue was found in the touched scope during this pass. The six findings remain below as historical audit trace, but they are no longer active blockers for acceptance.
- Recommended next action: If this change set is going to be packaged or merged immediately, perform one final lightweight manual smoke on the affected pages and then split commits by finding cluster for cleaner history.
- Overall decision: accepted
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
- [medium] maintainability: `render_ui_template()` silently degrades V2 requests back to the V1 Jinja environment
  - ID: F002
  - Description: `web/ui_mode.py:305-307` renders with `app.jinja_env` whenever `mode == "v2"` but `_get_v2_env(app)` is `None`. Startup initialization already emits a warning at `web/ui_mode.py:152-158`, but the render-time path itself adds no one-time warning/metric and still injects `ui_mode="v2"` into the template context. Packaging or overlay regressions can therefore leave the request logically in V2 mode while the actual template resolution has already degraded to the V1 environment. Because `web/error_handlers.py:9` imports `render_ui_template`, the same silent degradation also affects HTML error pages.
  - Evidence Files:
    - `web/ui_mode.py`
    - `web/error_handlers.py`
    - `app.py`
    - `app_new_ui.py`
    - `web/bootstrap/factory.py`
    - `core/services/system/system_maintenance_service.py`
    - `core/services/system/maintenance/throttle.py`
    - `tests/regression_system_maintenance_throttle_short_circuit.py`
    - `tests/regression_system_maintenance_jobstate_commit.py`
  - Related Milestones: round1-bootstrap-reverify
  - Recommendation: Keep the non-fatal fallback if required for availability, but emit a one-time runtime warning/metric whenever `mode == "v2"` and `_get_v2_env(app)` is missing, and consider exposing a visible diagnostics flag on the page or health endpoint.

- [low] maintainability: Dashboard/history landing pages drop malformed schedule-summary state without telemetry
  - ID: F003
  - Description: `web/routes/dashboard.py:27-38`, `web/routes/scheduler_batches.py:61-73`, and `web/routes/system_history.py:35-48` all preserve page availability by converting malformed `result_summary` payloads (or, in `scheduler_batches.py`, any exception inside the latest-history load block) into `None`/empty state without a warning log. `tests/regression_dashboard_overdue_count_tolerance.py:84-121` confirms that dirty summary tolerance is intentionally preserved for compatibility, so the defect is the missing observability: corrupted or partially unreadable history data becomes invisible to operators and reviewers.
  - Evidence Files:
    - `web/routes/dashboard.py`
    - `web/routes/scheduler_batches.py`
    - `web/routes/system_history.py`
    - `tests/regression_dashboard_overdue_count_tolerance.py`
    - `web/routes/equipment_pages.py`
    - `web/routes/personnel_pages.py`
    - `web/routes/process_parts.py`
    - `web/routes/process_suppliers.py`
    - `web/routes/excel_utils.py`
    - `web/routes/scheduler_calendar_pages.py`
    - `web/routes/scheduler_excel_calendar.py`
    - `web/routes/personnel_calendar_pages.py`
    - `web/routes/personnel_excel_operator_calendar.py`
    - `web/routes/system_backup.py`
    - `web/routes/scheduler_resource_dispatch.py`
    - `web/routes/reports.py`
    - `web/routes/system_ui_mode.py`
    - `web/routes/system_health.py`
    - `web/routes/scheduler_batch_detail.py`
  - Related Milestones: routes-silent-fallback-cluster
  - Recommendation: Keep tolerant rendering if required, but log a warning with the affected version/id when `result_summary` parsing fails, and in `scheduler_batches.py` isolate summary parsing from `list_recent()` failures so a bad summary does not erase the whole latest-history card.

- [low] other: `preview_baseline_matches()` downgrades token comparison to plain `==` on unexpected `compare_digest()` failure
  - ID: F004
  - Description: `web/routes/excel_utils.py:61-73` normalizes both tokens to strings and then calls `hmac.compare_digest(...)`, but still catches any exception and falls back to `provided == expected`. On the supported Python 3.8 runtime, `compare_digest()` is available and the current call site already feeds it string inputs, so the fallback is unnecessary defensive code on a token-validation path and hides unexpected runtime problems.
  - Evidence Files:
    - `web/routes/excel_utils.py`
    - `web/routes/dashboard.py`
    - `web/routes/scheduler_batches.py`
    - `web/routes/system_history.py`
    - `web/routes/equipment_pages.py`
    - `web/routes/personnel_pages.py`
    - `web/routes/process_parts.py`
    - `web/routes/process_suppliers.py`
    - `web/routes/scheduler_calendar_pages.py`
    - `web/routes/scheduler_excel_calendar.py`
    - `web/routes/personnel_calendar_pages.py`
    - `web/routes/personnel_excel_operator_calendar.py`
    - `web/routes/system_backup.py`
    - `web/routes/scheduler_resource_dispatch.py`
    - `web/routes/reports.py`
    - `web/routes/system_ui_mode.py`
    - `web/routes/system_health.py`
    - `web/routes/scheduler_batch_detail.py`
    - `tests/regression_dashboard_overdue_count_tolerance.py`
  - Related Milestones: routes-silent-fallback-cluster
  - Recommendation: Remove the `==` fallback, or at minimum log the exception and return `False` so runtime anomalies are visible instead of silently reclassifying the comparison path.

- [medium] other: `_load_active_downtime_machine_ids()` silently hides downtime-query failures by returning an empty set
  - ID: F005
  - Description: `web/routes/equipment_pages.py:61-67` catches every exception from `MachineDowntimeQueryService.list_active_machine_ids_at(...)` and returns `set()`. When that path fails, `web/routes/equipment_pages.py:134-144` and `84-114` build the equipment list without the active-downtime overlay, so machines that should render as `停机（计划）` silently fall back to plain `MachineStatus` labels. This is a real masking bug, not just a tolerance preference.
  - Evidence Files:
    - `web/routes/equipment_pages.py`
    - `web/routes/dashboard.py`
    - `web/routes/scheduler_batches.py`
    - `web/routes/system_history.py`
    - `web/routes/personnel_pages.py`
    - `web/routes/process_parts.py`
    - `web/routes/process_suppliers.py`
    - `web/routes/excel_utils.py`
    - `web/routes/scheduler_calendar_pages.py`
    - `web/routes/scheduler_excel_calendar.py`
    - `web/routes/personnel_calendar_pages.py`
    - `web/routes/personnel_excel_operator_calendar.py`
    - `web/routes/system_backup.py`
    - `web/routes/scheduler_resource_dispatch.py`
    - `web/routes/reports.py`
    - `web/routes/system_ui_mode.py`
    - `web/routes/system_health.py`
    - `web/routes/scheduler_batch_detail.py`
    - `tests/regression_dashboard_overdue_count_tolerance.py`
  - Related Milestones: routes-silent-fallback-cluster
  - Recommendation: Log the exception and surface a degraded-state marker to the template, or fail the downtime overlay separately while preserving the base list so operators can distinguish query failure from `no active downtimes`.

- [medium] maintainability: Multiple bulk-management routes still swallow per-item exceptions without logging or per-item reason
  - ID: F006
  - Description: The currently verified routes `web/routes/equipment_pages.py:293-307`, `321-335`, `web/routes/personnel_pages.py:203-217`, `231-245`, `web/routes/scheduler_batches.py:199-213`, `web/routes/process_parts.py:157-171`, and `web/routes/system_backup.py:147-183` all convert per-item failures into an ID-only failed list. These handlers do not preserve `AppError.message` per item and, for the verified sites above, also skip `current_app.logger.exception(...)`, so reference-protection failures and true crashes are flattened into the same UI outcome.
  - Evidence Files:
    - `web/routes/equipment_pages.py`
    - `web/routes/personnel_pages.py`
    - `web/routes/scheduler_batches.py`
    - `web/routes/process_parts.py`
    - `web/routes/system_backup.py`
    - `web/routes/dashboard.py`
    - `web/routes/system_history.py`
    - `web/routes/process_suppliers.py`
    - `web/routes/excel_utils.py`
    - `web/routes/scheduler_calendar_pages.py`
    - `web/routes/scheduler_excel_calendar.py`
    - `web/routes/personnel_calendar_pages.py`
    - `web/routes/personnel_excel_operator_calendar.py`
    - `web/routes/scheduler_resource_dispatch.py`
    - `web/routes/reports.py`
    - `web/routes/system_ui_mode.py`
    - `web/routes/system_health.py`
    - `web/routes/scheduler_batch_detail.py`
    - `tests/regression_dashboard_overdue_count_tolerance.py`
  - Related Milestones: routes-silent-fallback-cluster
  - Recommendation: Handle `AppError` separately so the user sees concrete per-item reasons, and log unexpected exceptions with the affected ID so partial bulk failures remain diagnosable.

- [medium] other: Calendar pages and Excel imports silently coerce invalid `holiday_default_efficiency` to `0.8`
  - ID: F007
  - Description: `web/routes/scheduler_calendar_pages.py:17-24`, `web/routes/scheduler_excel_calendar.py:123-129` and `241-247`, `web/routes/personnel_calendar_pages.py:35-43`, and `web/routes/personnel_excel_operator_calendar.py:93-99` and `221-226` all replace malformed/missing/non-positive `holiday_default_efficiency` config values with `0.8` without warning. Because the same fallback is reused in both page rendering and preview/confirm extra-state construction, a broken config can silently change the default efficiency applied to blank holiday rows and still look internally consistent during preview confirmation.
  - Evidence Files:
    - `web/routes/scheduler_calendar_pages.py`
    - `web/routes/scheduler_excel_calendar.py`
    - `web/routes/personnel_calendar_pages.py`
    - `web/routes/personnel_excel_operator_calendar.py`
    - `web/routes/dashboard.py`
    - `web/routes/scheduler_batches.py`
    - `web/routes/system_history.py`
    - `web/routes/equipment_pages.py`
    - `web/routes/personnel_pages.py`
    - `web/routes/process_parts.py`
    - `web/routes/process_suppliers.py`
    - `web/routes/excel_utils.py`
    - `web/routes/system_backup.py`
    - `web/routes/scheduler_resource_dispatch.py`
    - `web/routes/reports.py`
    - `web/routes/system_ui_mode.py`
    - `web/routes/system_health.py`
    - `web/routes/scheduler_batch_detail.py`
    - `tests/regression_dashboard_overdue_count_tolerance.py`
  - Related Milestones: routes-silent-fallback-cluster
  - Recommendation: Validate `holiday_default_efficiency` centrally in `ConfigService` (or at startup) and log/surface a degraded-state warning whenever the route layer has to fall back to `0.8`, especially on Excel import paths that can persist derived values.
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
### round1-bootstrap-reverify · Round 1 bootstrap and cross-layer entrypoints re-verified
- Status: completed
- Recorded At: 2026-04-02T07:10:01.788Z
- Reviewed Modules: app.py, app_new_ui.py, web/bootstrap/factory.py, web/error_handlers.py, web/ui_mode.py, core/services/system/system_maintenance_service.py, core/services/system/maintenance/throttle.py, tests/regression_system_maintenance_throttle_short_circuit.py, tests/regression_system_maintenance_jobstate_commit.py
- Summary:
Re-verified the bootstrap/request chain across `app.py:42-48`, `app_new_ui.py:42-49`, `web/bootstrap/factory.py:184-368`, `web/error_handlers.py:24-63`, and `web/ui_mode.py:117-323`.

Confirmed the main call chain is still:
`create_app()` -> `web.bootstrap.factory.create_app_core()` -> `@app.before_request _open_db()` -> `SystemMaintenanceService.run_if_due(...)`.

The previous maintenance-loop finding is **not reproduced as originally stated** on the current codebase:
- `core/services/system/system_maintenance_service.py:58-60` now defines `CHECK_THROTTLE_SECONDS = 10`.
- `core/services/system/system_maintenance_service.py:70-83` now short-circuits through `MaintenanceThrottle.allow_run(...)`.
- `core/services/system/maintenance/throttle.py:11-18` implements the in-process throttle gate.
- `tests/regression_system_maintenance_throttle_short_circuit.py:77-100` explicitly asserts that the second `run_if_due(...)` call is throttled.
- `tests/regression_system_maintenance_jobstate_commit.py:53-156` also shows current maintenance telemetry persistence/failure-isolation behavior.

Conclusion for the stale prior finding: the old "every request repeats failure with no cooldown" claim should be closed, not carried forward unchanged.

A separate UI-mode degradation issue remains live: when `get_ui_mode()` resolves to `"v2"`, `web/ui_mode.py:305-307` still executes `env = _get_v2_env(app) or app.jinja_env`. `init_ui_mode()` does log startup warnings on overlay creation failure at `web/ui_mode.py:152-158`, but render-time fallback itself is not separately surfaced and the same behavior also affects error-page rendering because `web/error_handlers.py:9` imports `render_ui_template` directly.
- Conclusion: Round 1 completed. Old F001 is stale on current code and should be retired; the remaining bootstrap-layer issue is the V2-to-V1 render fallback path in `web/ui_mode.py`.
- Evidence Files:
  - `app.py`
  - `app_new_ui.py`
  - `web/bootstrap/factory.py`
  - `web/error_handlers.py`
  - `web/ui_mode.py`
  - `core/services/system/system_maintenance_service.py`
  - `core/services/system/maintenance/throttle.py`
  - `tests/regression_system_maintenance_throttle_short_circuit.py`
  - `tests/regression_system_maintenance_jobstate_commit.py`
- Recommended Next Action: Continue route-by-route re-verification and convert the already collected route evidence into formal findings, especially silent summary fallbacks, bulk-operation catch-alls, and `holiday_default_efficiency` coercion paths.
- Findings:
  - [medium] maintainability: `render_ui_template()` silently degrades V2 requests back to the V1 Jinja environment

### routes-silent-fallback-cluster · Route-level silent fallback cluster re-verified
- Status: completed
- Recorded At: 2026-04-02T07:11:05.610Z
- Reviewed Modules: web/routes/dashboard.py, web/routes/scheduler_batches.py, web/routes/system_history.py, web/routes/equipment_pages.py, web/routes/personnel_pages.py, web/routes/process_parts.py, web/routes/process_suppliers.py, web/routes/excel_utils.py, web/routes/scheduler_calendar_pages.py, web/routes/scheduler_excel_calendar.py, web/routes/personnel_calendar_pages.py, web/routes/personnel_excel_operator_calendar.py, web/routes/system_backup.py, web/routes/scheduler_resource_dispatch.py, web/routes/reports.py, web/routes/system_ui_mode.py, web/routes/system_health.py, web/routes/scheduler_batch_detail.py, tests/regression_dashboard_overdue_count_tolerance.py
- Summary:
Deep re-read and cross-checked the current route behavior in:
- `web/routes/dashboard.py`
- `web/routes/scheduler_batches.py`
- `web/routes/system_history.py`
- `web/routes/equipment_pages.py`
- `web/routes/personnel_pages.py`
- `web/routes/process_parts.py`
- `web/routes/process_suppliers.py`
- `web/routes/excel_utils.py`
- `web/routes/scheduler_calendar_pages.py`
- `web/routes/scheduler_excel_calendar.py`
- `web/routes/personnel_calendar_pages.py`
- `web/routes/personnel_excel_operator_calendar.py`
- `web/routes/system_backup.py`
- `web/routes/scheduler_resource_dispatch.py`
- `web/routes/reports.py`
- `web/routes/system_ui_mode.py`
- `web/routes/system_health.py`
- `web/routes/scheduler_batch_detail.py`

Current route-level evidence falls into four live clusters:

1. **Schedule summary / recent-history fallback remains too silent on read paths**
- `web/routes/dashboard.py:27-38` converts `latest.result_summary` parse failures into `latest_summary = None` with no warning.
- `web/routes/scheduler_batches.py:61-73` clears both `latest_history` and `latest_summary` on any exception in the whole recent-history block.
- `web/routes/system_history.py:35-48` converts per-item `result_summary` parse failures to `None` with no warning.
- `tests/regression_dashboard_overdue_count_tolerance.py:84-121` confirms that keeping the page alive on dirty summary data is intentional compatibility behavior, so the remaining issue is **observability**, not availability.

2. **A real user-visible masking bug remains in equipment downtime status loading**
- `web/routes/equipment_pages.py:61-67` returns `set()` on any exception from `MachineDowntimeQueryService.list_active_machine_ids_at(...)`.
- This means the equipment list page will silently drop the planned-downtime overlay and fall back to plain `MachineStatus` rendering when the downtime read path breaks.

3. **Bulk-management routes still swallow per-item failures without reason or logging**
Verified current silent per-item catch-all sites:
- `web/routes/equipment_pages.py:293-307`, `321-335`
- `web/routes/personnel_pages.py:203-217`, `231-245`
- `web/routes/scheduler_batches.py:199-213`
- `web/routes/process_parts.py:157-171`
- `web/routes/system_backup.py:147-183`
These routes still collapse both business-rule failures and unexpected exceptions into a failed-ID list with no per-item message and, for the verified sites above, no `current_app.logger.exception(...)` trace.

4. **`holiday_default_efficiency` still silently collapses to `0.8` across both page and Excel import paths**
Verified current scope:
- `web/routes/scheduler_calendar_pages.py:17-24`
- `web/routes/scheduler_excel_calendar.py:123-129`, `241-247`
- `web/routes/personnel_calendar_pages.py:35-43`
- `web/routes/personnel_excel_operator_calendar.py:93-99`, `221-226`
Malformed/missing/non-positive config values are silently coerced to `0.8`, which directly affects page defaults and the preview/confirm baseline state used when blank holiday efficiency cells are imported.

Additional narrowing decisions from the current pass:
- `web/routes/excel_utils.py:61-73` still contains the unnecessary `compare_digest(...)` -> `==` fallback.
- The old broad `op_logger` claim should **not** be carried forward unchanged. The remaining omissions found in this pass are read-side helpers only: `web/routes/process_parts.py:98`, `web/routes/process_suppliers.py:29`, and `web/routes/process_suppliers.py:79`.
- `web/routes/reports.py` and `web/routes/scheduler_resource_dispatch.py` mainly use explicit user-visible fallback/redirect behavior; no new high-confidence silent-failure bug from those files was promoted in this milestone.
- Conclusion: Round-2 route evidence now points to a narrower but still real set of silent-fallback problems: summary/read-path observability gaps, equipment downtime masking, bulk-operation exception swallowing, and `holiday_default_efficiency` coercion.
- Evidence Files:
  - `web/routes/dashboard.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/system_history.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/process_parts.py`
  - `web/routes/process_suppliers.py`
  - `web/routes/excel_utils.py`
  - `web/routes/scheduler_calendar_pages.py`
  - `web/routes/scheduler_excel_calendar.py`
  - `web/routes/personnel_calendar_pages.py`
  - `web/routes/personnel_excel_operator_calendar.py`
  - `web/routes/system_backup.py`
  - `web/routes/scheduler_resource_dispatch.py`
  - `web/routes/reports.py`
  - `web/routes/system_ui_mode.py`
  - `web/routes/system_health.py`
  - `web/routes/scheduler_batch_detail.py`
  - `tests/regression_dashboard_overdue_count_tolerance.py`
- Recommended Next Action: Finish Round 3 consolidation: record the viewmodel/test corroboration, explicitly close the old broad F009/F010 claims, and summarize the `web_new_test/` compatibility result before recalculating the interim finding counts.
- Findings:
  - [low] maintainability: Dashboard/history landing pages drop malformed schedule-summary state without telemetry
  - [low] other: `preview_baseline_matches()` downgrades token comparison to plain `==` on unexpected `compare_digest()` failure
  - [medium] other: `_load_active_downtime_machine_ids()` silently hides downtime-query failures by returning an empty set
  - [medium] maintainability: Multiple bulk-management routes still swallow per-item exceptions without logging or per-item reason
  - [medium] other: Calendar pages and Excel imports silently coerce invalid `holiday_default_efficiency` to `0.8`

### round3-viewmodels-webnewtest-corroboration · Round 3 viewmodels, web_new_test, and regression corroboration consolidated
- Status: completed
- Recorded At: 2026-04-02T07:11:29.640Z
- Reviewed Modules: web/viewmodels/scheduler_analysis_vm.py, web/viewmodels/system_logs_vm.py, tests/regression_scheduler_analysis_observability.py, tests/test_ui_mode.py, web_new_test/templates/base.html, web_new_test/templates/dashboard.html, web_new_test/templates/scheduler/batches_manage.html, web_new_test/templates/scheduler/batches.html, web_new_test/templates/scheduler/config_manual.html, web_new_test/templates/scheduler/config.html, web_new_test/templates/scheduler/gantt.html, web_new_test/static/css/style.css, web_new_test/static/docs/scheduler_manual.md
- Summary:
Deep re-read and corroborated:
- `web/viewmodels/scheduler_analysis_vm.py`
- `web/viewmodels/system_logs_vm.py`
- `tests/regression_scheduler_analysis_observability.py`
- `tests/test_ui_mode.py`
- all `web_new_test/` files currently present in scope:
  - `web_new_test/templates/base.html`
  - `web_new_test/templates/dashboard.html`
  - `web_new_test/templates/scheduler/batches_manage.html`
  - `web_new_test/templates/scheduler/batches.html`
  - `web_new_test/templates/scheduler/config_manual.html`
  - `web_new_test/templates/scheduler/config.html`
  - `web_new_test/templates/scheduler/gantt.html`
  - `web_new_test/static/css/style.css`
  - `web_new_test/static/docs/scheduler_manual.md`

Current Round-3 conclusions:

1. **Old F010 should not be carried forward as a current bug**
- `web/viewmodels/scheduler_analysis_vm.py:7-23`, `95-105`, and `243-253` still use tolerant helpers such as `safe_float()`, `safe_int()`, and `_safe_load_json()`.
- `tests/regression_scheduler_analysis_observability.py:145-209` explicitly verifies that old/new summary formats, truncated summaries, degraded observability flags, and missing attempt fields are rendered through those tolerant paths without breaking the analysis page.
- On current evidence, this is an intentional display-layer compatibility contract, not a newly discovered defect.

2. **No new high-confidence silent-fallback bug was reproduced inside `web_new_test/` itself**
- `web_new_test/templates/base.html:42-45` always loads `static/css/ui_contract.css`, which defines the `--ui-*` variables consumed by `web_new_test/templates/scheduler/config.html:4-172`; there is no unresolved custom-property regression in that template stack.
- `web_new_test/templates/scheduler/batches.html:40-74` and `web_new_test/templates/scheduler/config.html:194-261` use `safe_url_for(...)` plus explicit downgrade/debug copy when optional endpoints are unavailable, which is visible degradation rather than silent breakage.
- `web_new_test/templates/scheduler/gantt.html:174-205` also keeps empty/error containers explicit instead of swallowing the state in the template layer.

3. **The current Chrome 109+ compatibility assumption is not contradicted by the reviewed V2 CSS**
- `web_new_test/static/css/style.css:160-165` uses `:has()` for legacy-card padding logic.
- External compatibility reference (`https://caniuse.com/css-has`) shows Chrome support from version 105 onward, so this specific selector is compatible with the declared Chrome 109+ runtime assumption.
- No stronger browser-compatibility regression was identified from the currently reviewed V2 CSS/templates.

4. **`system_logs_vm` tolerance remains bounded and template-contract-oriented**
- `web/viewmodels/system_logs_vm.py:7-33` degrades invalid JSON detail payloads to `detail_obj=None`, which matches the documented route/view fallback behavior and did not surface a new high-risk issue in this pass.

Net result: Round 3 corroborates that the currently strongest remaining issues are still in the route/bootstrap layers, not in the already-reviewed `web_new_test/` template set or the analysis/system-log viewmodels.
- Conclusion: Round 3 corroboration did not add a new high-confidence `web_new_test/` or viewmodel defect. Old F010 should be treated as accepted compatibility behavior, while the active review focus stays on the route/bootstrap findings already recorded.
- Evidence Files:
  - `web/viewmodels/scheduler_analysis_vm.py`
  - `web/viewmodels/system_logs_vm.py`
  - `tests/regression_scheduler_analysis_observability.py`
  - `tests/test_ui_mode.py`
  - `web_new_test/templates/base.html`
  - `web_new_test/templates/dashboard.html`
  - `web_new_test/templates/scheduler/batches_manage.html`
  - `web_new_test/templates/scheduler/batches.html`
  - `web_new_test/templates/scheduler/config_manual.html`
  - `web_new_test/templates/scheduler/config.html`
  - `web_new_test/templates/scheduler/gantt.html`
  - `web_new_test/static/css/style.css`
  - `web_new_test/static/docs/scheduler_manual.md`
- Recommended Next Action: Continue remaining route-file coverage and then recalculate the interim finding set and interim decision.

### routes-excel-remaining-cluster · Remaining Excel route cluster and scheduler export/control routes re-verification
- Status: completed
- Recorded At: 2026-04-02T07:22:42.102Z
- Reviewed Modules: web/routes/equipment_excel_machines.py, web/routes/equipment_excel_links.py, web/routes/personnel_excel_operators.py, web/routes/personnel_excel_links.py, web/routes/process_excel_suppliers.py, web/routes/process_excel_routes.py, web/routes/process_excel_part_operation_hours.py, web/routes/process_excel_op_types.py, web/routes/scheduler_config.py, web/routes/scheduler_excel_batches.py, web/routes/scheduler_gantt.py, web/routes/scheduler_run.py, web/routes/scheduler_week_plan.py, web/routes/system_logs.py, web/routes/equipment_downtimes.py, web/routes/excel_demo.py, web/routes/material.py
- Summary:
Reviewed the remaining Excel-heavy route cluster and adjacent scheduler/control routes with focus on silent fallbacks, broad catch-alls, and preview/confirm drift guards.

Reviewed modules:
- `web/routes/equipment_excel_machines.py`
- `web/routes/equipment_excel_links.py`
- `web/routes/personnel_excel_operators.py`
- `web/routes/personnel_excel_links.py`
- `web/routes/process_excel_suppliers.py`
- `web/routes/process_excel_routes.py`
- `web/routes/process_excel_part_operation_hours.py`
- `web/routes/process_excel_op_types.py`
- `web/routes/scheduler_config.py`
- `web/routes/scheduler_excel_batches.py`
- `web/routes/scheduler_gantt.py`
- `web/routes/scheduler_run.py`
- `web/routes/scheduler_week_plan.py`
- `web/routes/system_logs.py`
- `web/routes/equipment_downtimes.py`
- `web/routes/excel_demo.py`
- `web/routes/material.py`

Corroborating tests re-read in this step:
- `tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`
- `tests/regression_part_service_external_default_days_fallback.py`
- `tests/regression_supplier_service_invalid_default_days_not_silent.py`
- `tests/test_supplier_excel_import_remark_normalization.py`
- `tests/regression_process_excel_part_operation_hours_import.py`
- `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`
- `tests/regression_personnel_excel_links_header_aliases.py`
- `tests/test_operator_machine_excel_route_error_handling.py`
- `tests/regression_excel_preview_confirm_baseline_guard.py`
- `tests/regression_excel_preview_confirm_extra_state_guard.py`
- `tests/regression_system_logs_delete_no_clamp.py`
- `tests/regression_system_health_route.py`

Conclusions from this cluster:
- `web/routes/process_excel_suppliers.py` still normalizes blank `默认周期` to `1.0`, but this behavior is intentional and currently regression-backed rather than an untracked silent route bug. The current test suite explicitly accepts blank Excel `默认周期` importing as `default_days=1.0` in `tests/test_supplier_excel_import_remark_normalization.py`, while service-level fallback observability is separately covered by `tests/regression_supplier_service_invalid_default_days_not_silent.py`.
- `web/routes/process_excel_routes.py` and `web/routes/scheduler_excel_batches.py` now expose strict-mode/baseline-guard behavior instead of silently continuing through hidden template drift. This is corroborated by `tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`, `tests/regression_excel_preview_confirm_baseline_guard.py`, and `tests/regression_excel_preview_confirm_extra_state_guard.py`.
- `web/routes/process_excel_part_operation_hours.py` rejects external rows and non-finite numeric values during both preview and confirm; append semantics are explicit rather than silently overwriting non-empty rows. This is covered by `tests/regression_process_excel_part_operation_hours_import.py` and `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`.
- `web/routes/personnel_excel_links.py`/`web/routes/equipment_excel_links.py` accept alias headers, but invalid downstream normalization/runtime failures are not silently swallowed at route level; `tests/test_operator_machine_excel_route_error_handling.py` confirms internal runtime errors still surface as HTTP 500 instead of being downgraded into false-success pages.
- `web/routes/equipment_downtimes.py` batch creation routes use a broad final catch-all, but the underlying `core/services/equipment/machine_downtime_service.py:create_by_scope()` executes inside `self.tx_manager.transaction()` and reports overlap skips structurally, so this route was not promoted into the current bulk-swallow finding set.
- `web/routes/system_logs.py` deletion behavior remains narrowed and guarded (`log_id <= 0` is rejected rather than clamped), matching `tests/regression_system_logs_delete_no_clamp.py`.
- `web/routes/scheduler_config.py`, `web/routes/scheduler_gantt.py`, `web/routes/scheduler_run.py`, `web/routes/scheduler_week_plan.py`, `web/routes/excel_demo.py`, and `web/routes/material.py` contain availability-preserving generic error handling, but this pass did not find a new high-confidence silent fallback/catch-all bug strong enough to add beyond the existing active finding set.

Result: no new active findings were added from this route cluster; active findings remain `F002`-`F007`, while the unresolved `F008` decision still needs explicit disposition against `web/routes/system_utils.py:_normalize_time_range()`.
- Conclusion: Remaining Excel-centric route coverage narrowed several suspected fallback patterns but did not justify expanding the active finding set. The next high-value step is to resolve `F008` explicitly and then close out the remaining helper/blueprint route coverage.
- Evidence Files:
  - `web/routes/equipment_excel_machines.py`
  - `web/routes/equipment_excel_links.py`
  - `web/routes/personnel_excel_operators.py`
  - `web/routes/personnel_excel_links.py`
  - `web/routes/process_excel_suppliers.py`
  - `web/routes/process_excel_routes.py`
  - `web/routes/process_excel_part_operation_hours.py`
  - `web/routes/process_excel_op_types.py`
  - `web/routes/scheduler_config.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_gantt.py`
  - `web/routes/scheduler_run.py`
  - `web/routes/scheduler_week_plan.py`
  - `web/routes/system_logs.py`
  - `web/routes/equipment_downtimes.py`
  - `web/routes/excel_demo.py`
  - `web/routes/material.py`
  - `core/services/equipment/machine_downtime_service.py`
  - `tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`
  - `tests/regression_part_service_external_default_days_fallback.py`
  - `tests/regression_supplier_service_invalid_default_days_not_silent.py`
  - `tests/test_supplier_excel_import_remark_normalization.py`
  - `tests/regression_process_excel_part_operation_hours_import.py`
  - `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`
  - `tests/regression_personnel_excel_links_header_aliases.py`
  - `tests/test_operator_machine_excel_route_error_handling.py`
  - `tests/regression_excel_preview_confirm_baseline_guard.py`
  - `tests/regression_excel_preview_confirm_extra_state_guard.py`
  - `tests/regression_system_logs_delete_no_clamp.py`
  - `tests/regression_system_health_route.py`
- Recommended Next Action: Resolve the pending `F008` disposition for `web/routes/system_utils.py:_normalize_time_range()`, then finish the remaining helper/blueprint route sweep before recalculating the interim review decision.

### routes-helper-blueprint-closeout · Route helper/blueprint sweep completed and old F008 disposition resolved
- Status: completed
- Recorded At: 2026-04-02T07:25:42.290Z
- Reviewed Modules: web/routes/system_utils.py, web/routes/scheduler_utils.py, web/routes/process_bp.py, web/routes/personnel_bp.py, web/routes/equipment_bp.py, web/routes/process_excel_part_operations.py, web/routes/scheduler_pages.py, web/routes/equipment.py, web/routes/personnel.py, web/routes/process.py, web/routes/scheduler.py, web/routes/system.py, web/routes/system_bp.py, web/routes/scheduler_bp.py, web/routes/enum_display.py, web/routes/pagination.py, web/routes/normalizers.py, web/routes/personnel_teams.py, web/routes/process_op_types.py, web/routes/scheduler_ops.py, web/routes/system_plugins.py, web/routes/team_view_helpers.py
- Summary:
Completed the remaining helper/blueprint route sweep and resolved the pending `F008` disposition.

Reviewed modules in this closeout step:
- `web/routes/system_utils.py`
- `web/routes/scheduler_utils.py`
- `web/routes/process_bp.py`
- `web/routes/personnel_bp.py`
- `web/routes/equipment_bp.py`
- `web/routes/process_excel_part_operations.py`
- `web/routes/scheduler_pages.py`
- `web/routes/equipment.py`
- `web/routes/personnel.py`
- `web/routes/process.py`
- `web/routes/scheduler.py`
- `web/routes/system.py`
- `web/routes/system_bp.py`
- `web/routes/scheduler_bp.py`
- `web/routes/enum_display.py`
- `web/routes/pagination.py`
- `web/routes/normalizers.py`
- `web/routes/personnel_teams.py`
- `web/routes/process_op_types.py`
- `web/routes/scheduler_ops.py`
- `web/routes/system_plugins.py`
- `web/routes/team_view_helpers.py`

Corroborating tests/doc checks re-read in this step:
- `tests/regression_excel_normalizers_mixed_case.py`
- `tests/regression_page_manual_registry.py`
- `tests/regression_safe_next_url_hardening.py`
- `tests/regression_config_manual_markdown.py`

`F008` disposition:
- Old `F008` targeted `web/routes/system_utils.py:_normalize_time_range()` because lines `97-105` still contain `except Exception: _ = None` around the final `start_norm <= end_norm` comparison.
- After re-verification, this is **not promoted as an active finding** in the current review run. The swallowed branch sits after both `start_norm` and `end_norm` have already been produced by `_parse_dt()` plus `strftime("%Y-%m-%d %H:%M:%S")`, so user-controlled parse failures are already surfaced earlier as `ValidationError`, while the remaining swallowed branch is effectively dead defensive code around reparsing self-generated canonical timestamps.
- In other words: the code is slightly messy and arguably unnecessary, but it is not a meaningful current silent user-facing fallback on the supported runtime. Old `F008` is therefore closed as a narrowed non-active note, not carried into the active finding set.

Additional helper-route conclusions:
- `web/routes/normalizers.py` route-side defaults (`blank -> normal/yes/workday`) are intentional and regression-backed by `tests/regression_excel_normalizers_mixed_case.py`, and the calendar-day blank default is also documented in `tests/regression_page_manual_registry.py` (`"leave blank -> workday"`). These were not promoted as new findings.
- `web/routes/system_utils.py:_safe_next_url()` and scheduler manual source filtering are explicitly hardened and covered by `tests/regression_safe_next_url_hardening.py`.
- `web/routes/scheduler_config.py` manual-page/manual-download fallback behavior is availability-preserving and test-backed by `tests/regression_config_manual_markdown.py`; this pass did not find a new silent-failure bug there.
- The remaining barrel/helper files (`equipment.py`, `personnel.py`, `process.py`, `scheduler.py`, `system.py`, `*_bp.py`, `team_view_helpers.py`) are registration/adapter shells only and did not introduce new catch-all or silent-fallback defects.
- `web/routes/personnel_teams.py`, `web/routes/process_op_types.py`, `web/routes/scheduler_ops.py`, and `web/routes/system_plugins.py` did not add a new high-confidence active finding in this pass.

Result: route/helper coverage is now effectively complete for the current `web/` re-verification scope. The active finding set remains exactly `F002`-`F007`; old `F001`, `F008`, `F009`, and `F010` are not active in the re-verified state.
- Conclusion: The remaining helper sweep closed the last unresolved old-finding placeholder (`F008`) without expanding the active defect set. The re-verification now supports an interim overall decision based on six active low/medium findings and no reproduced high-severity web-layer regressions.
- Evidence Files:
  - `web/routes/system_utils.py`
  - `web/routes/scheduler_utils.py`
  - `web/routes/process_bp.py`
  - `web/routes/personnel_bp.py`
  - `web/routes/equipment_bp.py`
  - `web/routes/process_excel_part_operations.py`
  - `web/routes/scheduler_pages.py`
  - `web/routes/equipment.py`
  - `web/routes/personnel.py`
  - `web/routes/process.py`
  - `web/routes/scheduler.py`
  - `web/routes/system.py`
  - `web/routes/system_bp.py`
  - `web/routes/scheduler_bp.py`
  - `web/routes/enum_display.py`
  - `web/routes/pagination.py`
  - `web/routes/normalizers.py`
  - `web/routes/personnel_teams.py`
  - `web/routes/process_op_types.py`
  - `web/routes/scheduler_ops.py`
  - `web/routes/system_plugins.py`
  - `web/routes/team_view_helpers.py`
  - `tests/regression_excel_normalizers_mixed_case.py`
  - `tests/regression_page_manual_registry.py`
  - `tests/regression_safe_next_url_hardening.py`
  - `tests/regression_config_manual_markdown.py`
- Recommended Next Action: Recalculate the interim review outcome from the fully re-verified scope and close the review with the active set `F002`-`F007` only.

### focused-remediation-reverify-closeout · Focused remediation re-verification for F002-F007 completed
- Status: completed
- Recorded At: 2026-04-02T08:23:00.000Z
- Reviewed Modules: core/services/scheduler/config_service.py, core/services/scheduler/calendar_admin.py, core/services/common/excel_validators.py, web/routes/equipment_pages.py, templates/equipment/list.html, web/routes/personnel_pages.py, web/routes/scheduler_batches.py, web/routes/process_parts.py, web/routes/system_backup.py, web/routes/scheduler_calendar_pages.py, templates/scheduler/calendar.html, web/routes/scheduler_excel_calendar.py, web/routes/personnel_calendar_pages.py, templates/personnel/calendar.html, web/routes/personnel_excel_operator_calendar.py, web/ui_mode.py, templates/base.html, web_new_test/templates/base.html, web/routes/dashboard.py, web/routes/system_history.py, web/routes/excel_utils.py, tests/test_ui_mode.py, tests/test_equipment_page_downtime_overlay_degraded.py, tests/test_bulk_route_error_visibility.py, tests/test_holiday_default_efficiency_read_guard.py, tests/test_schedule_summary_observability.py, tests/test_excel_utils_compare_digest_guard.py, tests/regression_dashboard_overdue_count_tolerance.py, tests/regression_excel_preview_confirm_baseline_guard.py, tests/regression_excel_preview_confirm_extra_state_guard.py, tests/regression_scheduler_reject_nonfinite_and_invalid_status.py, tests/regression_scheduler_apply_preset_reject_invalid_numeric.py, tests/regression_calendar_pages_readside_normalization.py, tests/regression_system_health_route.py, tests/regression_system_logs_delete_no_clamp.py
- Summary:
Focused re-verification was rerun against the implemented remediation set for the previously active findings `F002`-`F007`.

Verified current code state:
- `F005`: `web/routes/equipment_pages.py` now returns structured downtime-overlay state, logs read failures, and `templates/equipment/list.html` shows a persistent degraded banner instead of silently pretending there is no planned downtime overlay.
- `F006`: bulk-management routes in `web/routes/equipment_pages.py`, `web/routes/personnel_pages.py`, `web/routes/scheduler_batches.py`, `web/routes/process_parts.py`, and `web/routes/system_backup.py` now preserve per-item business reasons, log unexpected exceptions with item identifiers, and keep partial-success redirect/flash behavior.
- `F007`: `core/services/scheduler/config_service.py` now centralizes strict `holiday_default_efficiency` reading; GET pages in `web/routes/scheduler_calendar_pages.py` and `web/routes/personnel_calendar_pages.py` degrade visibly with warnings, while Excel preview/confirm flows in `web/routes/scheduler_excel_calendar.py` and `web/routes/personnel_excel_operator_calendar.py` now refuse to continue on invalid config instead of silently using `0.8`. Downstream alignment was also rechecked in `core/services/scheduler/calendar_admin.py` and `core/services/common/excel_validators.py`.
- `F002`: `web/ui_mode.py` now emits a one-time runtime warning for V2 render fallback, exposes `ui_template_env` / `ui_template_env_degraded` in request/template context, and both `templates/base.html` and `web_new_test/templates/base.html` expose low-risk diagnostic meta tags.
- `F003`: tolerant rendering remains intact in `web/routes/dashboard.py`, `web/routes/scheduler_batches.py`, and `web/routes/system_history.py`, but malformed `result_summary` payloads are now logged and `scheduler_batches.py` no longer erases the whole latest-history card when only summary parsing fails.
- `F004`: `web/routes/excel_utils.py` now logs unexpected `compare_digest()` failures and returns `False` instead of downgrading to plain `==`.

Automated verification completed in this pass:
- `python -m pytest tests/test_ui_mode.py tests/test_equipment_page_downtime_overlay_degraded.py tests/test_bulk_route_error_visibility.py tests/test_holiday_default_efficiency_read_guard.py tests/test_schedule_summary_observability.py tests/test_excel_utils_compare_digest_guard.py -q` -> `21 passed`
- `python -m pytest tests/regression_dashboard_overdue_count_tolerance.py tests/regression_excel_preview_confirm_baseline_guard.py tests/regression_excel_preview_confirm_extra_state_guard.py tests/regression_scheduler_reject_nonfinite_and_invalid_status.py tests/regression_scheduler_apply_preset_reject_invalid_numeric.py tests/regression_calendar_pages_readside_normalization.py -q` -> `6 passed`
- Optional regressions re-run successfully: `python tests/regression_system_health_route.py` and `python tests/regression_system_logs_delete_no_clamp.py` -> `OK`
- Targeted lint recheck: `python -m ruff check ...` on the modified code/tests -> `All checks passed!`

This pass did not perform a human visual/manual page smoke session; however, the affected route/template behaviors were re-checked through targeted tests and focused source inspection.
- Conclusion: Focused remediation re-verification is stable on the current workspace state. The previously active findings `F002`-`F007` are now remediated by code plus regression evidence, and no replacement high-confidence issue was found in the touched scope during this pass.
- Evidence Files:
  - `core/services/scheduler/config_service.py`
  - `core/services/scheduler/calendar_admin.py`
  - `core/services/common/excel_validators.py`
  - `web/routes/equipment_pages.py`
  - `templates/equipment/list.html`
  - `web/routes/personnel_pages.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/process_parts.py`
  - `web/routes/system_backup.py`
  - `web/routes/scheduler_calendar_pages.py`
  - `templates/scheduler/calendar.html`
  - `web/routes/scheduler_excel_calendar.py`
  - `web/routes/personnel_calendar_pages.py`
  - `templates/personnel/calendar.html`
  - `web/routes/personnel_excel_operator_calendar.py`
  - `web/ui_mode.py`
  - `templates/base.html`
  - `web_new_test/templates/base.html`
  - `web/routes/dashboard.py`
  - `web/routes/system_history.py`
  - `web/routes/excel_utils.py`
  - `tests/test_ui_mode.py`
  - `tests/test_equipment_page_downtime_overlay_degraded.py`
  - `tests/test_bulk_route_error_visibility.py`
  - `tests/test_holiday_default_efficiency_read_guard.py`
  - `tests/test_schedule_summary_observability.py`
  - `tests/test_excel_utils_compare_digest_guard.py`
  - `tests/regression_dashboard_overdue_count_tolerance.py`
  - `tests/regression_excel_preview_confirm_baseline_guard.py`
  - `tests/regression_excel_preview_confirm_extra_state_guard.py`
  - `tests/regression_scheduler_reject_nonfinite_and_invalid_status.py`
  - `tests/regression_scheduler_apply_preset_reject_invalid_numeric.py`
  - `tests/regression_calendar_pages_readside_normalization.py`
  - `tests/regression_system_health_route.py`
  - `tests/regression_system_logs_delete_no_clamp.py`
- Recommended Next Action: If this change set is going to be packaged or merged immediately, perform one final lightweight manual smoke on the affected pages and then split commits by finding cluster for cleaner history.

<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mnh4i4u3-yfc30y",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "finalizedAt": "2026-04-02T08:23:30.000Z",
  "status": "completed",
  "overallDecision": "accepted",
  "latestConclusion": "Focused remediation re-verification is stable on the current workspace state. The previously active findings `F002`-`F007` are now remediated by code plus regression evidence, and no replacement high-confidence issue was found in the touched scope during this pass. The six findings remain below as historical audit trace, but they are no longer active blockers for acceptance.",
  "recommendedNextAction": "If this change set is going to be packaged or merged immediately, perform one final lightweight manual smoke on the affected pages and then split commits by finding cluster for cleaner history.",
  "reviewedModules": [
    "app.py",
    "app_new_ui.py",
    "web/bootstrap/factory.py",
    "web/error_handlers.py",
    "web/ui_mode.py",
    "core/services/system/system_maintenance_service.py",
    "core/services/system/maintenance/throttle.py",
    "tests/regression_system_maintenance_throttle_short_circuit.py",
    "tests/regression_system_maintenance_jobstate_commit.py",
    "web/routes/dashboard.py",
    "web/routes/scheduler_batches.py",
    "web/routes/system_history.py",
    "web/routes/equipment_pages.py",
    "web/routes/personnel_pages.py",
    "web/routes/process_parts.py",
    "web/routes/process_suppliers.py",
    "web/routes/excel_utils.py",
    "web/routes/scheduler_calendar_pages.py",
    "web/routes/scheduler_excel_calendar.py",
    "web/routes/personnel_calendar_pages.py",
    "web/routes/personnel_excel_operator_calendar.py",
    "web/routes/system_backup.py",
    "web/routes/scheduler_resource_dispatch.py",
    "web/routes/reports.py",
    "web/routes/system_ui_mode.py",
    "web/routes/system_health.py",
    "web/routes/scheduler_batch_detail.py",
    "tests/regression_dashboard_overdue_count_tolerance.py",
    "web/viewmodels/scheduler_analysis_vm.py",
    "web/viewmodels/system_logs_vm.py",
    "tests/regression_scheduler_analysis_observability.py",
    "tests/test_ui_mode.py",
    "web_new_test/templates/base.html",
    "web_new_test/templates/dashboard.html",
    "web_new_test/templates/scheduler/batches_manage.html",
    "web_new_test/templates/scheduler/batches.html",
    "web_new_test/templates/scheduler/config_manual.html",
    "web_new_test/templates/scheduler/config.html",
    "web_new_test/templates/scheduler/gantt.html",
    "web_new_test/static/css/style.css",
    "web_new_test/static/docs/scheduler_manual.md",
    "web/routes/equipment_excel_machines.py",
    "web/routes/equipment_excel_links.py",
    "web/routes/personnel_excel_operators.py",
    "web/routes/personnel_excel_links.py",
    "web/routes/process_excel_suppliers.py",
    "web/routes/process_excel_routes.py",
    "web/routes/process_excel_part_operation_hours.py",
    "web/routes/process_excel_op_types.py",
    "web/routes/scheduler_config.py",
    "web/routes/scheduler_excel_batches.py",
    "web/routes/scheduler_gantt.py",
    "web/routes/scheduler_run.py",
    "web/routes/scheduler_week_plan.py",
    "web/routes/system_logs.py",
    "web/routes/equipment_downtimes.py",
    "web/routes/excel_demo.py",
    "web/routes/material.py",
    "web/routes/system_utils.py",
    "web/routes/scheduler_utils.py",
    "web/routes/process_bp.py",
    "web/routes/personnel_bp.py",
    "web/routes/equipment_bp.py",
    "web/routes/process_excel_part_operations.py",
    "web/routes/scheduler_pages.py",
    "web/routes/equipment.py",
    "web/routes/personnel.py",
    "web/routes/process.py",
    "web/routes/scheduler.py",
    "web/routes/system.py",
    "web/routes/system_bp.py",
    "web/routes/scheduler_bp.py",
    "web/routes/enum_display.py",
    "web/routes/pagination.py",
    "web/routes/normalizers.py",
    "web/routes/personnel_teams.py",
    "web/routes/process_op_types.py",
    "web/routes/scheduler_ops.py",
    "web/routes/system_plugins.py",
    "web/routes/team_view_helpers.py",
    "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py",
    "tests/regression_part_service_external_default_days_fallback.py",
    "tests/regression_supplier_service_invalid_default_days_not_silent.py",
    "tests/test_supplier_excel_import_remark_normalization.py",
    "tests/regression_process_excel_part_operation_hours_import.py",
    "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py",
    "tests/regression_personnel_excel_links_header_aliases.py",
    "tests/test_operator_machine_excel_route_error_handling.py",
    "tests/regression_excel_preview_confirm_baseline_guard.py",
    "tests/regression_excel_preview_confirm_extra_state_guard.py",
    "tests/regression_system_logs_delete_no_clamp.py",
    "tests/regression_system_health_route.py",
    "tests/regression_excel_normalizers_mixed_case.py",
    "tests/regression_page_manual_registry.py",
    "tests/regression_safe_next_url_hardening.py",
    "tests/regression_config_manual_markdown.py",
    "core/services/scheduler/config_service.py",
    "core/services/scheduler/calendar_admin.py",
    "core/services/common/excel_validators.py",
    "templates/equipment/list.html",
    "templates/scheduler/calendar.html",
    "templates/personnel/calendar.html",
    "tests/test_equipment_page_downtime_overlay_degraded.py",
    "tests/test_bulk_route_error_visibility.py",
    "tests/test_holiday_default_efficiency_read_guard.py",
    "tests/test_schedule_summary_observability.py",
    "tests/test_excel_utils_compare_digest_guard.py",
    "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py",
    "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py",
    "tests/regression_calendar_pages_readside_normalization.py"
  ],
  "milestones": [
    {
      "id": "round1-bootstrap-reverify",
      "title": "Round 1 bootstrap and cross-layer entrypoints re-verified",
      "summary": "Re-verified the bootstrap/request chain across `app.py:42-48`, `app_new_ui.py:42-49`, `web/bootstrap/factory.py:184-368`, `web/error_handlers.py:24-63`, and `web/ui_mode.py:117-323`.\n\nConfirmed the main call chain is still:\n`create_app()` -> `web.bootstrap.factory.create_app_core()` -> `@app.before_request _open_db()` -> `SystemMaintenanceService.run_if_due(...)`.\n\nThe previous maintenance-loop finding is **not reproduced as originally stated** on the current codebase:\n- `core/services/system/system_maintenance_service.py:58-60` now defines `CHECK_THROTTLE_SECONDS = 10`.\n- `core/services/system/system_maintenance_service.py:70-83` now short-circuits through `MaintenanceThrottle.allow_run(...)`.\n- `core/services/system/maintenance/throttle.py:11-18` implements the in-process throttle gate.\n- `tests/regression_system_maintenance_throttle_short_circuit.py:77-100` explicitly asserts that the second `run_if_due(...)` call is throttled.\n- `tests/regression_system_maintenance_jobstate_commit.py:53-156` also shows current maintenance telemetry persistence/failure-isolation behavior.\n\nConclusion for the stale prior finding: the old \"every request repeats failure with no cooldown\" claim should be closed, not carried forward unchanged.\n\nA separate UI-mode degradation issue remains live: when `get_ui_mode()` resolves to `\"v2\"`, `web/ui_mode.py:305-307` still executes `env = _get_v2_env(app) or app.jinja_env`. `init_ui_mode()` does log startup warnings on overlay creation failure at `web/ui_mode.py:152-158`, but render-time fallback itself is not separately surfaced and the same behavior also affects error-page rendering because `web/error_handlers.py:9` imports `render_ui_template` directly.",
      "status": "completed",
      "conclusion": "Round 1 completed. Old F001 is stale on current code and should be retired; the remaining bootstrap-layer issue is the V2-to-V1 render fallback path in `web/ui_mode.py`.",
      "evidenceFiles": [
        "app.py",
        "app_new_ui.py",
        "web/bootstrap/factory.py",
        "web/error_handlers.py",
        "web/ui_mode.py",
        "core/services/system/system_maintenance_service.py",
        "core/services/system/maintenance/throttle.py",
        "tests/regression_system_maintenance_throttle_short_circuit.py",
        "tests/regression_system_maintenance_jobstate_commit.py"
      ],
      "reviewedModules": [
        "app.py",
        "app_new_ui.py",
        "web/bootstrap/factory.py",
        "web/error_handlers.py",
        "web/ui_mode.py",
        "core/services/system/system_maintenance_service.py",
        "core/services/system/maintenance/throttle.py",
        "tests/regression_system_maintenance_throttle_short_circuit.py",
        "tests/regression_system_maintenance_jobstate_commit.py"
      ],
      "recommendedNextAction": "Continue route-by-route re-verification and convert the already collected route evidence into formal findings, especially silent summary fallbacks, bulk-operation catch-alls, and `holiday_default_efficiency` coercion paths.",
      "recordedAt": "2026-04-02T07:10:01.788Z",
      "findingIds": [
        "F002"
      ]
    },
    {
      "id": "routes-silent-fallback-cluster",
      "title": "Route-level silent fallback cluster re-verified",
      "summary": "Deep re-read and cross-checked the current route behavior in:\n- `web/routes/dashboard.py`\n- `web/routes/scheduler_batches.py`\n- `web/routes/system_history.py`\n- `web/routes/equipment_pages.py`\n- `web/routes/personnel_pages.py`\n- `web/routes/process_parts.py`\n- `web/routes/process_suppliers.py`\n- `web/routes/excel_utils.py`\n- `web/routes/scheduler_calendar_pages.py`\n- `web/routes/scheduler_excel_calendar.py`\n- `web/routes/personnel_calendar_pages.py`\n- `web/routes/personnel_excel_operator_calendar.py`\n- `web/routes/system_backup.py`\n- `web/routes/scheduler_resource_dispatch.py`\n- `web/routes/reports.py`\n- `web/routes/system_ui_mode.py`\n- `web/routes/system_health.py`\n- `web/routes/scheduler_batch_detail.py`\n\nCurrent route-level evidence falls into four live clusters:\n\n1. **Schedule summary / recent-history fallback remains too silent on read paths**\n- `web/routes/dashboard.py:27-38` converts `latest.result_summary` parse failures into `latest_summary = None` with no warning.\n- `web/routes/scheduler_batches.py:61-73` clears both `latest_history` and `latest_summary` on any exception in the whole recent-history block.\n- `web/routes/system_history.py:35-48` converts per-item `result_summary` parse failures to `None` with no warning.\n- `tests/regression_dashboard_overdue_count_tolerance.py:84-121` confirms that keeping the page alive on dirty summary data is intentional compatibility behavior, so the remaining issue is **observability**, not availability.\n\n2. **A real user-visible masking bug remains in equipment downtime status loading**\n- `web/routes/equipment_pages.py:61-67` returns `set()` on any exception from `MachineDowntimeQueryService.list_active_machine_ids_at(...)`.\n- This means the equipment list page will silently drop the planned-downtime overlay and fall back to plain `MachineStatus` rendering when the downtime read path breaks.\n\n3. **Bulk-management routes still swallow per-item failures without reason or logging**\nVerified current silent per-item catch-all sites:\n- `web/routes/equipment_pages.py:293-307`, `321-335`\n- `web/routes/personnel_pages.py:203-217`, `231-245`\n- `web/routes/scheduler_batches.py:199-213`\n- `web/routes/process_parts.py:157-171`\n- `web/routes/system_backup.py:147-183`\nThese routes still collapse both business-rule failures and unexpected exceptions into a failed-ID list with no per-item message and, for the verified sites above, no `current_app.logger.exception(...)` trace.\n\n4. **`holiday_default_efficiency` still silently collapses to `0.8` across both page and Excel import paths**\nVerified current scope:\n- `web/routes/scheduler_calendar_pages.py:17-24`\n- `web/routes/scheduler_excel_calendar.py:123-129`, `241-247`\n- `web/routes/personnel_calendar_pages.py:35-43`\n- `web/routes/personnel_excel_operator_calendar.py:93-99`, `221-226`\nMalformed/missing/non-positive config values are silently coerced to `0.8`, which directly affects page defaults and the preview/confirm baseline state used when blank holiday efficiency cells are imported.\n\nAdditional narrowing decisions from the current pass:\n- `web/routes/excel_utils.py:61-73` still contains the unnecessary `compare_digest(...)` -> `==` fallback.\n- The old broad `op_logger` claim should **not** be carried forward unchanged. The remaining omissions found in this pass are read-side helpers only: `web/routes/process_parts.py:98`, `web/routes/process_suppliers.py:29`, and `web/routes/process_suppliers.py:79`.\n- `web/routes/reports.py` and `web/routes/scheduler_resource_dispatch.py` mainly use explicit user-visible fallback/redirect behavior; no new high-confidence silent-failure bug from those files was promoted in this milestone.",
      "status": "completed",
      "conclusion": "Round-2 route evidence now points to a narrower but still real set of silent-fallback problems: summary/read-path observability gaps, equipment downtime masking, bulk-operation exception swallowing, and `holiday_default_efficiency` coercion.",
      "evidenceFiles": [
        "web/routes/dashboard.py",
        "web/routes/scheduler_batches.py",
        "web/routes/system_history.py",
        "web/routes/equipment_pages.py",
        "web/routes/personnel_pages.py",
        "web/routes/process_parts.py",
        "web/routes/process_suppliers.py",
        "web/routes/excel_utils.py",
        "web/routes/scheduler_calendar_pages.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/routes/system_backup.py",
        "web/routes/scheduler_resource_dispatch.py",
        "web/routes/reports.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_health.py",
        "web/routes/scheduler_batch_detail.py",
        "tests/regression_dashboard_overdue_count_tolerance.py"
      ],
      "reviewedModules": [
        "web/routes/dashboard.py",
        "web/routes/scheduler_batches.py",
        "web/routes/system_history.py",
        "web/routes/equipment_pages.py",
        "web/routes/personnel_pages.py",
        "web/routes/process_parts.py",
        "web/routes/process_suppliers.py",
        "web/routes/excel_utils.py",
        "web/routes/scheduler_calendar_pages.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/routes/system_backup.py",
        "web/routes/scheduler_resource_dispatch.py",
        "web/routes/reports.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_health.py",
        "web/routes/scheduler_batch_detail.py",
        "tests/regression_dashboard_overdue_count_tolerance.py"
      ],
      "recommendedNextAction": "Finish Round 3 consolidation: record the viewmodel/test corroboration, explicitly close the old broad F009/F010 claims, and summarize the `web_new_test/` compatibility result before recalculating the interim finding counts.",
      "recordedAt": "2026-04-02T07:11:05.610Z",
      "findingIds": [
        "F003",
        "F004",
        "F005",
        "F006",
        "F007"
      ]
    },
    {
      "id": "round3-viewmodels-webnewtest-corroboration",
      "title": "Round 3 viewmodels, web_new_test, and regression corroboration consolidated",
      "summary": "Deep re-read and corroborated:\n- `web/viewmodels/scheduler_analysis_vm.py`\n- `web/viewmodels/system_logs_vm.py`\n- `tests/regression_scheduler_analysis_observability.py`\n- `tests/test_ui_mode.py`\n- all `web_new_test/` files currently present in scope:\n  - `web_new_test/templates/base.html`\n  - `web_new_test/templates/dashboard.html`\n  - `web_new_test/templates/scheduler/batches_manage.html`\n  - `web_new_test/templates/scheduler/batches.html`\n  - `web_new_test/templates/scheduler/config_manual.html`\n  - `web_new_test/templates/scheduler/config.html`\n  - `web_new_test/templates/scheduler/gantt.html`\n  - `web_new_test/static/css/style.css`\n  - `web_new_test/static/docs/scheduler_manual.md`\n\nCurrent Round-3 conclusions:\n\n1. **Old F010 should not be carried forward as a current bug**\n- `web/viewmodels/scheduler_analysis_vm.py:7-23`, `95-105`, and `243-253` still use tolerant helpers such as `safe_float()`, `safe_int()`, and `_safe_load_json()`.\n- `tests/regression_scheduler_analysis_observability.py:145-209` explicitly verifies that old/new summary formats, truncated summaries, degraded observability flags, and missing attempt fields are rendered through those tolerant paths without breaking the analysis page.\n- On current evidence, this is an intentional display-layer compatibility contract, not a newly discovered defect.\n\n2. **No new high-confidence silent-fallback bug was reproduced inside `web_new_test/` itself**\n- `web_new_test/templates/base.html:42-45` always loads `static/css/ui_contract.css`, which defines the `--ui-*` variables consumed by `web_new_test/templates/scheduler/config.html:4-172`; there is no unresolved custom-property regression in that template stack.\n- `web_new_test/templates/scheduler/batches.html:40-74` and `web_new_test/templates/scheduler/config.html:194-261` use `safe_url_for(...)` plus explicit downgrade/debug copy when optional endpoints are unavailable, which is visible degradation rather than silent breakage.\n- `web_new_test/templates/scheduler/gantt.html:174-205` also keeps empty/error containers explicit instead of swallowing the state in the template layer.\n\n3. **The current Chrome 109+ compatibility assumption is not contradicted by the reviewed V2 CSS**\n- `web_new_test/static/css/style.css:160-165` uses `:has()` for legacy-card padding logic.\n- External compatibility reference (`https://caniuse.com/css-has`) shows Chrome support from version 105 onward, so this specific selector is compatible with the declared Chrome 109+ runtime assumption.\n- No stronger browser-compatibility regression was identified from the currently reviewed V2 CSS/templates.\n\n4. **`system_logs_vm` tolerance remains bounded and template-contract-oriented**\n- `web/viewmodels/system_logs_vm.py:7-33` degrades invalid JSON detail payloads to `detail_obj=None`, which matches the documented route/view fallback behavior and did not surface a new high-risk issue in this pass.\n\nNet result: Round 3 corroborates that the currently strongest remaining issues are still in the route/bootstrap layers, not in the already-reviewed `web_new_test/` template set or the analysis/system-log viewmodels.",
      "status": "completed",
      "conclusion": "Round 3 corroboration did not add a new high-confidence `web_new_test/` or viewmodel defect. Old F010 should be treated as accepted compatibility behavior, while the active review focus stays on the route/bootstrap findings already recorded.",
      "evidenceFiles": [
        "web/viewmodels/scheduler_analysis_vm.py",
        "web/viewmodels/system_logs_vm.py",
        "tests/regression_scheduler_analysis_observability.py",
        "tests/test_ui_mode.py",
        "web_new_test/templates/base.html",
        "web_new_test/templates/dashboard.html",
        "web_new_test/templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches.html",
        "web_new_test/templates/scheduler/config_manual.html",
        "web_new_test/templates/scheduler/config.html",
        "web_new_test/templates/scheduler/gantt.html",
        "web_new_test/static/css/style.css",
        "web_new_test/static/docs/scheduler_manual.md"
      ],
      "reviewedModules": [
        "web/viewmodels/scheduler_analysis_vm.py",
        "web/viewmodels/system_logs_vm.py",
        "tests/regression_scheduler_analysis_observability.py",
        "tests/test_ui_mode.py",
        "web_new_test/templates/base.html",
        "web_new_test/templates/dashboard.html",
        "web_new_test/templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches.html",
        "web_new_test/templates/scheduler/config_manual.html",
        "web_new_test/templates/scheduler/config.html",
        "web_new_test/templates/scheduler/gantt.html",
        "web_new_test/static/css/style.css",
        "web_new_test/static/docs/scheduler_manual.md"
      ],
      "recommendedNextAction": "Continue remaining route-file coverage and then recalculate the interim finding set and interim decision.",
      "recordedAt": "2026-04-02T07:11:29.640Z",
      "findingIds": []
    },
    {
      "id": "routes-excel-remaining-cluster",
      "title": "Remaining Excel route cluster and scheduler export/control routes re-verification",
      "summary": "Reviewed the remaining Excel-heavy route cluster and adjacent scheduler/control routes with focus on silent fallbacks, broad catch-alls, and preview/confirm drift guards.\n\nReviewed modules:\n- `web/routes/equipment_excel_machines.py`\n- `web/routes/equipment_excel_links.py`\n- `web/routes/personnel_excel_operators.py`\n- `web/routes/personnel_excel_links.py`\n- `web/routes/process_excel_suppliers.py`\n- `web/routes/process_excel_routes.py`\n- `web/routes/process_excel_part_operation_hours.py`\n- `web/routes/process_excel_op_types.py`\n- `web/routes/scheduler_config.py`\n- `web/routes/scheduler_excel_batches.py`\n- `web/routes/scheduler_gantt.py`\n- `web/routes/scheduler_run.py`\n- `web/routes/scheduler_week_plan.py`\n- `web/routes/system_logs.py`\n- `web/routes/equipment_downtimes.py`\n- `web/routes/excel_demo.py`\n- `web/routes/material.py`\n\nCorroborating tests re-read in this step:\n- `tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`\n- `tests/regression_part_service_external_default_days_fallback.py`\n- `tests/regression_supplier_service_invalid_default_days_not_silent.py`\n- `tests/test_supplier_excel_import_remark_normalization.py`\n- `tests/regression_process_excel_part_operation_hours_import.py`\n- `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`\n- `tests/regression_personnel_excel_links_header_aliases.py`\n- `tests/test_operator_machine_excel_route_error_handling.py`\n- `tests/regression_excel_preview_confirm_baseline_guard.py`\n- `tests/regression_excel_preview_confirm_extra_state_guard.py`\n- `tests/regression_system_logs_delete_no_clamp.py`\n- `tests/regression_system_health_route.py`\n\nConclusions from this cluster:\n- `web/routes/process_excel_suppliers.py` still normalizes blank `默认周期` to `1.0`, but this behavior is intentional and currently regression-backed rather than an untracked silent route bug. The current test suite explicitly accepts blank Excel `默认周期` importing as `default_days=1.0` in `tests/test_supplier_excel_import_remark_normalization.py`, while service-level fallback observability is separately covered by `tests/regression_supplier_service_invalid_default_days_not_silent.py`.\n- `web/routes/process_excel_routes.py` and `web/routes/scheduler_excel_batches.py` now expose strict-mode/baseline-guard behavior instead of silently continuing through hidden template drift. This is corroborated by `tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`, `tests/regression_excel_preview_confirm_baseline_guard.py`, and `tests/regression_excel_preview_confirm_extra_state_guard.py`.\n- `web/routes/process_excel_part_operation_hours.py` rejects external rows and non-finite numeric values during both preview and confirm; append semantics are explicit rather than silently overwriting non-empty rows. This is covered by `tests/regression_process_excel_part_operation_hours_import.py` and `tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py`.\n- `web/routes/personnel_excel_links.py`/`web/routes/equipment_excel_links.py` accept alias headers, but invalid downstream normalization/runtime failures are not silently swallowed at route level; `tests/test_operator_machine_excel_route_error_handling.py` confirms internal runtime errors still surface as HTTP 500 instead of being downgraded into false-success pages.\n- `web/routes/equipment_downtimes.py` batch creation routes use a broad final catch-all, but the underlying `core/services/equipment/machine_downtime_service.py:create_by_scope()` executes inside `self.tx_manager.transaction()` and reports overlap skips structurally, so this route was not promoted into the current bulk-swallow finding set.\n- `web/routes/system_logs.py` deletion behavior remains narrowed and guarded (`log_id <= 0` is rejected rather than clamped), matching `tests/regression_system_logs_delete_no_clamp.py`.\n- `web/routes/scheduler_config.py`, `web/routes/scheduler_gantt.py`, `web/routes/scheduler_run.py`, `web/routes/scheduler_week_plan.py`, `web/routes/excel_demo.py`, and `web/routes/material.py` contain availability-preserving generic error handling, but this pass did not find a new high-confidence silent fallback/catch-all bug strong enough to add beyond the existing active finding set.\n\nResult: no new active findings were added from this route cluster; active findings remain `F002`-`F007`, while the unresolved `F008` decision still needs explicit disposition against `web/routes/system_utils.py:_normalize_time_range()`.",
      "status": "completed",
      "conclusion": "Remaining Excel-centric route coverage narrowed several suspected fallback patterns but did not justify expanding the active finding set. The next high-value step is to resolve `F008` explicitly and then close out the remaining helper/blueprint route coverage.",
      "evidenceFiles": [
        "web/routes/equipment_excel_machines.py",
        "web/routes/equipment_excel_links.py",
        "web/routes/personnel_excel_operators.py",
        "web/routes/personnel_excel_links.py",
        "web/routes/process_excel_suppliers.py",
        "web/routes/process_excel_routes.py",
        "web/routes/process_excel_part_operation_hours.py",
        "web/routes/process_excel_op_types.py",
        "web/routes/scheduler_config.py",
        "web/routes/scheduler_excel_batches.py",
        "web/routes/scheduler_gantt.py",
        "web/routes/scheduler_run.py",
        "web/routes/scheduler_week_plan.py",
        "web/routes/system_logs.py",
        "web/routes/equipment_downtimes.py",
        "web/routes/excel_demo.py",
        "web/routes/material.py",
        "core/services/equipment/machine_downtime_service.py",
        "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py",
        "tests/regression_part_service_external_default_days_fallback.py",
        "tests/regression_supplier_service_invalid_default_days_not_silent.py",
        "tests/test_supplier_excel_import_remark_normalization.py",
        "tests/regression_process_excel_part_operation_hours_import.py",
        "tests/regression_process_excel_part_operation_hours_append_fill_empty_only.py",
        "tests/regression_personnel_excel_links_header_aliases.py",
        "tests/test_operator_machine_excel_route_error_handling.py",
        "tests/regression_excel_preview_confirm_baseline_guard.py",
        "tests/regression_excel_preview_confirm_extra_state_guard.py",
        "tests/regression_system_logs_delete_no_clamp.py",
        "tests/regression_system_health_route.py"
      ],
      "reviewedModules": [
        "web/routes/equipment_excel_machines.py",
        "web/routes/equipment_excel_links.py",
        "web/routes/personnel_excel_operators.py",
        "web/routes/personnel_excel_links.py",
        "web/routes/process_excel_suppliers.py",
        "web/routes/process_excel_routes.py",
        "web/routes/process_excel_part_operation_hours.py",
        "web/routes/process_excel_op_types.py",
        "web/routes/scheduler_config.py",
        "web/routes/scheduler_excel_batches.py",
        "web/routes/scheduler_gantt.py",
        "web/routes/scheduler_run.py",
        "web/routes/scheduler_week_plan.py",
        "web/routes/system_logs.py",
        "web/routes/equipment_downtimes.py",
        "web/routes/excel_demo.py",
        "web/routes/material.py"
      ],
      "recommendedNextAction": "Resolve the pending `F008` disposition for `web/routes/system_utils.py:_normalize_time_range()`, then finish the remaining helper/blueprint route sweep before recalculating the interim review decision.",
      "recordedAt": "2026-04-02T07:22:42.102Z",
      "findingIds": []
    },
    {
      "id": "routes-helper-blueprint-closeout",
      "title": "Route helper/blueprint sweep completed and old F008 disposition resolved",
      "summary": "Completed the remaining helper/blueprint route sweep and resolved the pending `F008` disposition.\n\nReviewed modules in this closeout step:\n- `web/routes/system_utils.py`\n- `web/routes/scheduler_utils.py`\n- `web/routes/process_bp.py`\n- `web/routes/personnel_bp.py`\n- `web/routes/equipment_bp.py`\n- `web/routes/process_excel_part_operations.py`\n- `web/routes/scheduler_pages.py`\n- `web/routes/equipment.py`\n- `web/routes/personnel.py`\n- `web/routes/process.py`\n- `web/routes/scheduler.py`\n- `web/routes/system.py`\n- `web/routes/system_bp.py`\n- `web/routes/scheduler_bp.py`\n- `web/routes/enum_display.py`\n- `web/routes/pagination.py`\n- `web/routes/normalizers.py`\n- `web/routes/personnel_teams.py`\n- `web/routes/process_op_types.py`\n- `web/routes/scheduler_ops.py`\n- `web/routes/system_plugins.py`\n- `web/routes/team_view_helpers.py`\n\nCorroborating tests/doc checks re-read in this step:\n- `tests/regression_excel_normalizers_mixed_case.py`\n- `tests/regression_page_manual_registry.py`\n- `tests/regression_safe_next_url_hardening.py`\n- `tests/regression_config_manual_markdown.py`\n\n`F008` disposition:\n- Old `F008` targeted `web/routes/system_utils.py:_normalize_time_range()` because lines `97-105` still contain `except Exception: _ = None` around the final `start_norm <= end_norm` comparison.\n- After re-verification, this is **not promoted as an active finding** in the current review run. The swallowed branch sits after both `start_norm` and `end_norm` have already been produced by `_parse_dt()` plus `strftime(\"%Y-%m-%d %H:%M:%S\")`, so user-controlled parse failures are already surfaced earlier as `ValidationError`, while the remaining swallowed branch is effectively dead defensive code around reparsing self-generated canonical timestamps.\n- In other words: the code is slightly messy and arguably unnecessary, but it is not a meaningful current silent user-facing fallback on the supported runtime. Old `F008` is therefore closed as a narrowed non-active note, not carried into the active finding set.\n\nAdditional helper-route conclusions:\n- `web/routes/normalizers.py` route-side defaults (`blank -> normal/yes/workday`) are intentional and regression-backed by `tests/regression_excel_normalizers_mixed_case.py`, and the calendar-day blank default is also documented in `tests/regression_page_manual_registry.py` (`\"leave blank -> workday\"`). These were not promoted as new findings.\n- `web/routes/system_utils.py:_safe_next_url()` and scheduler manual source filtering are explicitly hardened and covered by `tests/regression_safe_next_url_hardening.py`.\n- `web/routes/scheduler_config.py` manual-page/manual-download fallback behavior is availability-preserving and test-backed by `tests/regression_config_manual_markdown.py`; this pass did not find a new silent-failure bug there.\n- The remaining barrel/helper files (`equipment.py`, `personnel.py`, `process.py`, `scheduler.py`, `system.py`, `*_bp.py`, `team_view_helpers.py`) are registration/adapter shells only and did not introduce new catch-all or silent-fallback defects.\n- `web/routes/personnel_teams.py`, `web/routes/process_op_types.py`, `web/routes/scheduler_ops.py`, and `web/routes/system_plugins.py` did not add a new high-confidence active finding in this pass.\n\nResult: route/helper coverage is now effectively complete for the current `web/` re-verification scope. The active finding set remains exactly `F002`-`F007`; old `F001`, `F008`, `F009`, and `F010` are not active in the re-verified state.",
      "status": "completed",
      "conclusion": "The remaining helper sweep closed the last unresolved old-finding placeholder (`F008`) without expanding the active defect set. The re-verification now supports an interim overall decision based on six active low/medium findings and no reproduced high-severity web-layer regressions.",
      "evidenceFiles": [
        "web/routes/system_utils.py",
        "web/routes/scheduler_utils.py",
        "web/routes/process_bp.py",
        "web/routes/personnel_bp.py",
        "web/routes/equipment_bp.py",
        "web/routes/process_excel_part_operations.py",
        "web/routes/scheduler_pages.py",
        "web/routes/equipment.py",
        "web/routes/personnel.py",
        "web/routes/process.py",
        "web/routes/scheduler.py",
        "web/routes/system.py",
        "web/routes/system_bp.py",
        "web/routes/scheduler_bp.py",
        "web/routes/enum_display.py",
        "web/routes/pagination.py",
        "web/routes/normalizers.py",
        "web/routes/personnel_teams.py",
        "web/routes/process_op_types.py",
        "web/routes/scheduler_ops.py",
        "web/routes/system_plugins.py",
        "web/routes/team_view_helpers.py",
        "tests/regression_excel_normalizers_mixed_case.py",
        "tests/regression_page_manual_registry.py",
        "tests/regression_safe_next_url_hardening.py",
        "tests/regression_config_manual_markdown.py"
      ],
      "reviewedModules": [
        "web/routes/system_utils.py",
        "web/routes/scheduler_utils.py",
        "web/routes/process_bp.py",
        "web/routes/personnel_bp.py",
        "web/routes/equipment_bp.py",
        "web/routes/process_excel_part_operations.py",
        "web/routes/scheduler_pages.py",
        "web/routes/equipment.py",
        "web/routes/personnel.py",
        "web/routes/process.py",
        "web/routes/scheduler.py",
        "web/routes/system.py",
        "web/routes/system_bp.py",
        "web/routes/scheduler_bp.py",
        "web/routes/enum_display.py",
        "web/routes/pagination.py",
        "web/routes/normalizers.py",
        "web/routes/personnel_teams.py",
        "web/routes/process_op_types.py",
        "web/routes/scheduler_ops.py",
        "web/routes/system_plugins.py",
        "web/routes/team_view_helpers.py"
      ],
      "recommendedNextAction": "Recalculate the interim review outcome from the fully re-verified scope and close the review with the active set `F002`-`F007` only.",
      "recordedAt": "2026-04-02T07:25:42.290Z",
      "findingIds": []
    },
    {
      "id": "focused-remediation-reverify-closeout",
      "title": "Focused remediation re-verification for F002-F007 completed",
      "summary": "Focused re-verification was rerun against the implemented remediation set for the previously active findings `F002`-`F007`.\n\nVerified current code state:\n- `F005`: `web/routes/equipment_pages.py` now returns structured downtime-overlay state, logs read failures, and `templates/equipment/list.html` shows a persistent degraded banner instead of silently pretending there is no planned downtime overlay.\n- `F006`: bulk-management routes in `web/routes/equipment_pages.py`, `web/routes/personnel_pages.py`, `web/routes/scheduler_batches.py`, `web/routes/process_parts.py`, and `web/routes/system_backup.py` now preserve per-item business reasons, log unexpected exceptions with item identifiers, and keep partial-success redirect/flash behavior.\n- `F007`: `core/services/scheduler/config_service.py` now centralizes strict `holiday_default_efficiency` reading; GET pages in `web/routes/scheduler_calendar_pages.py` and `web/routes/personnel_calendar_pages.py` degrade visibly with warnings, while Excel preview/confirm flows in `web/routes/scheduler_excel_calendar.py` and `web/routes/personnel_excel_operator_calendar.py` now refuse to continue on invalid config instead of silently using `0.8`. Downstream alignment was also rechecked in `core/services/scheduler/calendar_admin.py` and `core/services/common/excel_validators.py`.\n- `F002`: `web/ui_mode.py` now emits a one-time runtime warning for V2 render fallback, exposes `ui_template_env` / `ui_template_env_degraded` in request/template context, and both `templates/base.html` and `web_new_test/templates/base.html` expose low-risk diagnostic meta tags.\n- `F003`: tolerant rendering remains intact in `web/routes/dashboard.py`, `web/routes/scheduler_batches.py`, and `web/routes/system_history.py`, but malformed `result_summary` payloads are now logged and `scheduler_batches.py` no longer erases the whole latest-history card when only summary parsing fails.\n- `F004`: `web/routes/excel_utils.py` now logs unexpected `compare_digest()` failures and returns `False` instead of downgrading to plain `==`.\n\nAutomated verification completed in this pass:\n- `python -m pytest tests/test_ui_mode.py tests/test_equipment_page_downtime_overlay_degraded.py tests/test_bulk_route_error_visibility.py tests/test_holiday_default_efficiency_read_guard.py tests/test_schedule_summary_observability.py tests/test_excel_utils_compare_digest_guard.py -q` -> `21 passed`\n- `python -m pytest tests/regression_dashboard_overdue_count_tolerance.py tests/regression_excel_preview_confirm_baseline_guard.py tests/regression_excel_preview_confirm_extra_state_guard.py tests/regression_scheduler_reject_nonfinite_and_invalid_status.py tests/regression_scheduler_apply_preset_reject_invalid_numeric.py tests/regression_calendar_pages_readside_normalization.py -q` -> `6 passed`\n- Optional regressions re-run successfully: `python tests/regression_system_health_route.py` and `python tests/regression_system_logs_delete_no_clamp.py` -> `OK`\n- Targeted lint recheck: `python -m ruff check ...` on the modified code/tests -> `All checks passed!`\n\nThis pass did not perform a human visual/manual page smoke session; however, the affected route/template behaviors were re-checked through targeted tests and focused source inspection.",
      "status": "completed",
      "conclusion": "Focused remediation re-verification is stable on the current workspace state. The previously active findings `F002`-`F007` are now remediated by code plus regression evidence, and no replacement high-confidence issue was found in the touched scope during this pass.",
      "evidenceFiles": [
        "core/services/scheduler/config_service.py",
        "core/services/scheduler/calendar_admin.py",
        "core/services/common/excel_validators.py",
        "web/routes/equipment_pages.py",
        "templates/equipment/list.html",
        "web/routes/personnel_pages.py",
        "web/routes/scheduler_batches.py",
        "web/routes/process_parts.py",
        "web/routes/system_backup.py",
        "web/routes/scheduler_calendar_pages.py",
        "templates/scheduler/calendar.html",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "templates/personnel/calendar.html",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/ui_mode.py",
        "templates/base.html",
        "web_new_test/templates/base.html",
        "web/routes/dashboard.py",
        "web/routes/system_history.py",
        "web/routes/excel_utils.py",
        "tests/test_ui_mode.py",
        "tests/test_equipment_page_downtime_overlay_degraded.py",
        "tests/test_bulk_route_error_visibility.py",
        "tests/test_holiday_default_efficiency_read_guard.py",
        "tests/test_schedule_summary_observability.py",
        "tests/test_excel_utils_compare_digest_guard.py",
        "tests/regression_dashboard_overdue_count_tolerance.py",
        "tests/regression_excel_preview_confirm_baseline_guard.py",
        "tests/regression_excel_preview_confirm_extra_state_guard.py",
        "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py",
        "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py",
        "tests/regression_calendar_pages_readside_normalization.py",
        "tests/regression_system_health_route.py",
        "tests/regression_system_logs_delete_no_clamp.py"
      ],
      "reviewedModules": [
        "core/services/scheduler/config_service.py",
        "core/services/scheduler/calendar_admin.py",
        "core/services/common/excel_validators.py",
        "web/routes/equipment_pages.py",
        "templates/equipment/list.html",
        "web/routes/personnel_pages.py",
        "web/routes/scheduler_batches.py",
        "web/routes/process_parts.py",
        "web/routes/system_backup.py",
        "web/routes/scheduler_calendar_pages.py",
        "templates/scheduler/calendar.html",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "templates/personnel/calendar.html",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/ui_mode.py",
        "templates/base.html",
        "web_new_test/templates/base.html",
        "web/routes/dashboard.py",
        "web/routes/system_history.py",
        "web/routes/excel_utils.py",
        "tests/test_ui_mode.py",
        "tests/test_equipment_page_downtime_overlay_degraded.py",
        "tests/test_bulk_route_error_visibility.py",
        "tests/test_holiday_default_efficiency_read_guard.py",
        "tests/test_schedule_summary_observability.py",
        "tests/test_excel_utils_compare_digest_guard.py",
        "tests/regression_dashboard_overdue_count_tolerance.py",
        "tests/regression_excel_preview_confirm_baseline_guard.py",
        "tests/regression_excel_preview_confirm_extra_state_guard.py",
        "tests/regression_scheduler_reject_nonfinite_and_invalid_status.py",
        "tests/regression_scheduler_apply_preset_reject_invalid_numeric.py",
        "tests/regression_calendar_pages_readside_normalization.py",
        "tests/regression_system_health_route.py",
        "tests/regression_system_logs_delete_no_clamp.py"
      ],
      "recommendedNextAction": "If this change set is going to be packaged or merged immediately, perform one final lightweight manual smoke on the affected pages and then split commits by finding cluster for cleaner history.",
      "recordedAt": "2026-04-02T08:23:00.000Z",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "F002",
      "severity": "medium",
      "category": "maintainability",
      "title": "`render_ui_template()` silently degrades V2 requests back to the V1 Jinja environment",
      "description": "`web/ui_mode.py:305-307` renders with `app.jinja_env` whenever `mode == \"v2\"` but `_get_v2_env(app)` is `None`. Startup initialization already emits a warning at `web/ui_mode.py:152-158`, but the render-time path itself adds no one-time warning/metric and still injects `ui_mode=\"v2\"` into the template context. Packaging or overlay regressions can therefore leave the request logically in V2 mode while the actual template resolution has already degraded to the V1 environment. Because `web/error_handlers.py:9` imports `render_ui_template`, the same silent degradation also affects HTML error pages.",
      "evidenceFiles": [
        "web/ui_mode.py",
        "web/error_handlers.py",
        "app.py",
        "app_new_ui.py",
        "web/bootstrap/factory.py",
        "core/services/system/system_maintenance_service.py",
        "core/services/system/maintenance/throttle.py",
        "tests/regression_system_maintenance_throttle_short_circuit.py",
        "tests/regression_system_maintenance_jobstate_commit.py"
      ],
      "relatedMilestoneIds": [
        "round1-bootstrap-reverify"
      ],
      "recommendation": "Keep the non-fatal fallback if required for availability, but emit a one-time runtime warning/metric whenever `mode == \"v2\"` and `_get_v2_env(app)` is missing, and consider exposing a visible diagnostics flag on the page or health endpoint."
    },
    {
      "id": "F003",
      "severity": "low",
      "category": "maintainability",
      "title": "Dashboard/history landing pages drop malformed schedule-summary state without telemetry",
      "description": "`web/routes/dashboard.py:27-38`, `web/routes/scheduler_batches.py:61-73`, and `web/routes/system_history.py:35-48` all preserve page availability by converting malformed `result_summary` payloads (or, in `scheduler_batches.py`, any exception inside the latest-history load block) into `None`/empty state without a warning log. `tests/regression_dashboard_overdue_count_tolerance.py:84-121` confirms that dirty summary tolerance is intentionally preserved for compatibility, so the defect is the missing observability: corrupted or partially unreadable history data becomes invisible to operators and reviewers.",
      "evidenceFiles": [
        "web/routes/dashboard.py",
        "web/routes/scheduler_batches.py",
        "web/routes/system_history.py",
        "tests/regression_dashboard_overdue_count_tolerance.py",
        "web/routes/equipment_pages.py",
        "web/routes/personnel_pages.py",
        "web/routes/process_parts.py",
        "web/routes/process_suppliers.py",
        "web/routes/excel_utils.py",
        "web/routes/scheduler_calendar_pages.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/routes/system_backup.py",
        "web/routes/scheduler_resource_dispatch.py",
        "web/routes/reports.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_health.py",
        "web/routes/scheduler_batch_detail.py"
      ],
      "relatedMilestoneIds": [
        "routes-silent-fallback-cluster"
      ],
      "recommendation": "Keep tolerant rendering if required, but log a warning with the affected version/id when `result_summary` parsing fails, and in `scheduler_batches.py` isolate summary parsing from `list_recent()` failures so a bad summary does not erase the whole latest-history card."
    },
    {
      "id": "F004",
      "severity": "low",
      "category": "other",
      "title": "`preview_baseline_matches()` downgrades token comparison to plain `==` on unexpected `compare_digest()` failure",
      "description": "`web/routes/excel_utils.py:61-73` normalizes both tokens to strings and then calls `hmac.compare_digest(...)`, but still catches any exception and falls back to `provided == expected`. On the supported Python 3.8 runtime, `compare_digest()` is available and the current call site already feeds it string inputs, so the fallback is unnecessary defensive code on a token-validation path and hides unexpected runtime problems.",
      "evidenceFiles": [
        "web/routes/excel_utils.py",
        "web/routes/dashboard.py",
        "web/routes/scheduler_batches.py",
        "web/routes/system_history.py",
        "web/routes/equipment_pages.py",
        "web/routes/personnel_pages.py",
        "web/routes/process_parts.py",
        "web/routes/process_suppliers.py",
        "web/routes/scheduler_calendar_pages.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/routes/system_backup.py",
        "web/routes/scheduler_resource_dispatch.py",
        "web/routes/reports.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_health.py",
        "web/routes/scheduler_batch_detail.py",
        "tests/regression_dashboard_overdue_count_tolerance.py"
      ],
      "relatedMilestoneIds": [
        "routes-silent-fallback-cluster"
      ],
      "recommendation": "Remove the `==` fallback, or at minimum log the exception and return `False` so runtime anomalies are visible instead of silently reclassifying the comparison path."
    },
    {
      "id": "F005",
      "severity": "medium",
      "category": "other",
      "title": "`_load_active_downtime_machine_ids()` silently hides downtime-query failures by returning an empty set",
      "description": "`web/routes/equipment_pages.py:61-67` catches every exception from `MachineDowntimeQueryService.list_active_machine_ids_at(...)` and returns `set()`. When that path fails, `web/routes/equipment_pages.py:134-144` and `84-114` build the equipment list without the active-downtime overlay, so machines that should render as `停机（计划）` silently fall back to plain `MachineStatus` labels. This is a real masking bug, not just a tolerance preference.",
      "evidenceFiles": [
        "web/routes/equipment_pages.py",
        "web/routes/dashboard.py",
        "web/routes/scheduler_batches.py",
        "web/routes/system_history.py",
        "web/routes/personnel_pages.py",
        "web/routes/process_parts.py",
        "web/routes/process_suppliers.py",
        "web/routes/excel_utils.py",
        "web/routes/scheduler_calendar_pages.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/routes/system_backup.py",
        "web/routes/scheduler_resource_dispatch.py",
        "web/routes/reports.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_health.py",
        "web/routes/scheduler_batch_detail.py",
        "tests/regression_dashboard_overdue_count_tolerance.py"
      ],
      "relatedMilestoneIds": [
        "routes-silent-fallback-cluster"
      ],
      "recommendation": "Log the exception and surface a degraded-state marker to the template, or fail the downtime overlay separately while preserving the base list so operators can distinguish query failure from `no active downtimes`."
    },
    {
      "id": "F006",
      "severity": "medium",
      "category": "maintainability",
      "title": "Multiple bulk-management routes still swallow per-item exceptions without logging or per-item reason",
      "description": "The currently verified routes `web/routes/equipment_pages.py:293-307`, `321-335`, `web/routes/personnel_pages.py:203-217`, `231-245`, `web/routes/scheduler_batches.py:199-213`, `web/routes/process_parts.py:157-171`, and `web/routes/system_backup.py:147-183` all convert per-item failures into an ID-only failed list. These handlers do not preserve `AppError.message` per item and, for the verified sites above, also skip `current_app.logger.exception(...)`, so reference-protection failures and true crashes are flattened into the same UI outcome.",
      "evidenceFiles": [
        "web/routes/equipment_pages.py",
        "web/routes/personnel_pages.py",
        "web/routes/scheduler_batches.py",
        "web/routes/process_parts.py",
        "web/routes/system_backup.py",
        "web/routes/dashboard.py",
        "web/routes/system_history.py",
        "web/routes/process_suppliers.py",
        "web/routes/excel_utils.py",
        "web/routes/scheduler_calendar_pages.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/routes/scheduler_resource_dispatch.py",
        "web/routes/reports.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_health.py",
        "web/routes/scheduler_batch_detail.py",
        "tests/regression_dashboard_overdue_count_tolerance.py"
      ],
      "relatedMilestoneIds": [
        "routes-silent-fallback-cluster"
      ],
      "recommendation": "Handle `AppError` separately so the user sees concrete per-item reasons, and log unexpected exceptions with the affected ID so partial bulk failures remain diagnosable."
    },
    {
      "id": "F007",
      "severity": "medium",
      "category": "other",
      "title": "Calendar pages and Excel imports silently coerce invalid `holiday_default_efficiency` to `0.8`",
      "description": "`web/routes/scheduler_calendar_pages.py:17-24`, `web/routes/scheduler_excel_calendar.py:123-129` and `241-247`, `web/routes/personnel_calendar_pages.py:35-43`, and `web/routes/personnel_excel_operator_calendar.py:93-99` and `221-226` all replace malformed/missing/non-positive `holiday_default_efficiency` config values with `0.8` without warning. Because the same fallback is reused in both page rendering and preview/confirm extra-state construction, a broken config can silently change the default efficiency applied to blank holiday rows and still look internally consistent during preview confirmation.",
      "evidenceFiles": [
        "web/routes/scheduler_calendar_pages.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/personnel_calendar_pages.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/routes/dashboard.py",
        "web/routes/scheduler_batches.py",
        "web/routes/system_history.py",
        "web/routes/equipment_pages.py",
        "web/routes/personnel_pages.py",
        "web/routes/process_parts.py",
        "web/routes/process_suppliers.py",
        "web/routes/excel_utils.py",
        "web/routes/system_backup.py",
        "web/routes/scheduler_resource_dispatch.py",
        "web/routes/reports.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_health.py",
        "web/routes/scheduler_batch_detail.py",
        "tests/regression_dashboard_overdue_count_tolerance.py"
      ],
      "relatedMilestoneIds": [
        "routes-silent-fallback-cluster"
      ],
      "recommendation": "Validate `holiday_default_efficiency` centrally in `ConfigService` (or at startup) and log/surface a degraded-state warning whenever the route layer has to fall back to `0.8`, especially on Excel import paths that can persist derived values."
    }
  ]
}
<!-- LIMCODE_REVIEW_METADATA_END -->
