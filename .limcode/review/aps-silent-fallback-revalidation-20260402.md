# APS Silent Fallback 三轮复核审查
- Date: 2026-04-02
- Overview: 将此前结论全部视为待验证，基于当前未提交改动重新进行三轮深度审查。
- Status: completed
- Overall decision: needs_follow_up

## Review Scope
# APS Silent Fallback 三轮复核审查

> 说明：本轮复核将此前所有结论一律视为“待验证”，不直接继承旧结论；仅把既有结论当作待复核假设。

### 复核范围
- 当前工作区未提交改动
- silent fallback / strict_mode 相关关键链路
- 相关回归测试与架构门禁

### 复核原则
- 只基于当前代码与当前测试结果下结论
- 对旧结论逐项复核，不默认成立
- 不修改业务代码，仅产出审查结论与证据

### 当前状态
- 第1轮：进行中
- 第2轮：待开始
- 第3轮：待开始

## Review Summary
<!-- LIMCODE_REVIEW_SUMMARY_START -->
- Current status: completed
- Reviewed modules: web/routes, templates, core/algorithms/greedy, tooling, core/services/process, core/services/scheduler, tests, core/services/common
- Current progress: 3 milestones recorded; latest: m3-regression-and-gates
- Total milestones: 3
- Completed milestones: 3
- Total findings: 4
- Findings by severity: high 0 / medium 2 / low 2
- Latest conclusion: Three-round revalidation of the current uncommitted workspace confirms that the reviewed built-in `strict_mode` paths now surface the targeted silent-fallback cases instead of silently downgrading them. The end-to-end UI -> route -> service -> scheduler propagation is present, and the focused regression pack passed for the core reviewed behaviors: unknown op types, missing supplier mappings, invalid supplier `default_days`, invalid `ext_days_*`, and invalid `dispatch_mode` / `dispatch_rule` / `auto_assign_enabled` are all rejected under `strict_mode=True` in the examined built-in flows. That said, the workspace is not yet fully releasable / gate-clean. A reproduced compatibility regression remains around `ConfigService.get_snapshot(strict_mode=...)` for old monkeypatch/stub signatures, the architecture fitness suite is still red (including the `common <-> scheduler` cycle and threshold/allowlist debt affecting changed files), and the full suite still contains non-core persistent / flaky failures. The correct final judgment for this rerun is therefore: the silent-fallback fix is materially effective on the core reviewed paths, but the branch still requires follow-up work before it can be treated as fully verified end-to-end.
- Recommended next action: Resolve or consciously encapsulate the `ConfigService.get_snapshot(strict_mode=...)` compatibility boundary, break the `common <-> scheduler` dependency cycle (or explicitly accept/document it), and rerun `tests/regression_auto_assign_persist_truthy_variants.py`, `tests/test_architecture_fitness.py`, and the broader suite before claiming branch health.
- Overall decision: needs_follow_up
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
- [low] other: strict_mode remains partial for numeric scheduler config fields
  - ID: finding-strict-config-numeric-gap
  - Description: `build_schedule_config_snapshot(..., strict_mode=True)` raises for reviewed choice / yes-no fields such as `dispatch_mode`, `dispatch_rule`, and `auto_assign_enabled`, but numeric readers `_get_float()` and `_get_int()` still coerce invalid values back to defaults. As a result, strict mode is not yet uniform for numeric scheduler config keys such as weights, time budgets, and other numeric snapshot fields.
  - Evidence Files:
    - `core/services/scheduler/config_snapshot.py`
    - `core/services/scheduler/config_service.py`
    - `core/services/process/route_parser.py`
    - `core/services/process/part_service.py`
    - `core/services/process/external_group_service.py`
    - `core/services/scheduler/batch_service.py`
    - `core/services/scheduler/batch_template_ops.py`
    - `core/services/scheduler/config_presets.py`
    - `core/services/scheduler/schedule_service.py`
    - `core/services/scheduler/schedule_optimizer_steps.py`
    - `core/algorithms/greedy/scheduler.py`
    - `core/algorithms/greedy/schedule_params.py`
    - `web/routes/process_parts.py`
    - `web/routes/process_excel_routes.py`
    - `web/routes/scheduler_batches.py`
    - `web/routes/scheduler_excel_batches.py`
    - `web/routes/scheduler_run.py`
    - `web/routes/scheduler_week_plan.py`
  - Related Milestones: m2-strict-chain-revalidation
  - Recommendation: Either document the narrower strict-mode contract explicitly, or extend strict validation to numeric snapshot fields so that invalid numeric config values also surface as hard failures under strict mode.

- [medium] test: `ConfigService.get_snapshot(strict_mode=...)` breaks old monkeypatch / stub signatures
  - ID: finding-get-snapshot-monkeypatch-compat
  - Description: `ScheduleService` now calls `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`. The reproduced failure in `tests/regression_auto_assign_persist_truthy_variants.py` shows that any monkeypatch or stub still defined as `get_snapshot(self)` now fails with `TypeError: unexpected keyword argument 'strict_mode'`. This does not invalidate the built-in strict-mode flow, but it is a real compatibility risk for tests, stubs, and external extension points that replace `ConfigService.get_snapshot` without accepting the new kwarg.
  - Evidence Files:
    - `tests/regression_auto_assign_persist_truthy_variants.py`
    - `core/services/scheduler/schedule_service.py`
    - `core/services/scheduler/config_service.py`
    - `tests/test_architecture_fitness.py`
    - `core/services/common/excel_validators.py`
    - `core/services/process/part_service.py`
    - `core/services/process/route_parser.py`
    - `core/services/scheduler/batch_service.py`
    - `core/services/scheduler/resource_pool_builder.py`
    - `core/services/scheduler/schedule_optimizer.py`
    - `core/services/scheduler/schedule_summary.py`
    - `static/js/config_manual.js`
    - `tests/test_team_pages_excel_smoke.py`
  - Related Milestones: m3-regression-and-gates
  - Recommendation: Preserve backward compatibility at this boundary by either making monkeypatches/stubs accept `strict_mode`/`**kwargs`, or by applying an optional-kwarg compatibility guard similar to `schedule_optimizer_steps._schedule_with_optional_strict_mode()` if external replacement of `get_snapshot` is an intended extension point.

- [medium] maintainability: Service package cycle `common <-> scheduler` is still present
  - ID: finding-common-scheduler-cycle
  - Description: `tests/test_architecture_fitness.py::test_no_circular_service_dependencies` still fails with `common <-> scheduler`. The most concrete reviewed dependency edge is `core/services/common/excel_validators.py` importing `core.services.scheduler.number_utils.parse_finite_int`, while scheduler modules continue to import `core.services.common.*`. This keeps the reviewed branch architecturally non-green and increases cross-package coupling around the strict-mode-adjacent scheduler/common utility layer.
  - Evidence Files:
    - `tests/test_architecture_fitness.py`
    - `core/services/common/excel_validators.py`
    - `core/services/scheduler/config_service.py`
    - `core/services/scheduler/batch_service.py`
    - `core/services/scheduler/resource_pool_builder.py`
    - `tests/regression_auto_assign_persist_truthy_variants.py`
    - `core/services/scheduler/schedule_service.py`
    - `core/services/process/part_service.py`
    - `core/services/process/route_parser.py`
    - `core/services/scheduler/schedule_optimizer.py`
    - `core/services/scheduler/schedule_summary.py`
    - `static/js/config_manual.js`
    - `tests/test_team_pages_excel_smoke.py`
  - Related Milestones: m3-regression-and-gates
  - Recommendation: Break the cycle by moving shared numeric/normalization helpers into a dependency-neutral common utility module (or otherwise inverting the dependency) so that `common` no longer imports from `scheduler`.

- [low] test: Architecture fitness and full-suite health are still not green on the reviewed workspace
  - ID: finding-architecture-gates-still-red
  - Description: Beyond the package cycle, the reviewed workspace still fails `test_no_silent_exception_swallow`, `test_file_size_limit`, and `test_cyclomatic_complexity_threshold`, including some changed strict-mode-related files (`part_service.py`, `route_parser.py`, `batch_service.py`, `schedule_optimizer.py`, `schedule_service.py`, `schedule_summary.py`). The broader suite also ended at `261 passed, 11 failed`, with both persistent non-core failures and order-dependent/flaky behavior outside the strict-mode core path. This means the branch cannot yet be described as fully regression- / gate-clean even though the targeted strict-mode behavior materially improved.
  - Evidence Files:
    - `tests/test_architecture_fitness.py`
    - `core/services/process/part_service.py`
    - `core/services/process/route_parser.py`
    - `core/services/scheduler/batch_service.py`
    - `core/services/scheduler/schedule_optimizer.py`
    - `core/services/scheduler/schedule_service.py`
    - `core/services/scheduler/schedule_summary.py`
    - `static/js/config_manual.js`
    - `tests/test_team_pages_excel_smoke.py`
    - `tests/regression_auto_assign_persist_truthy_variants.py`
    - `core/services/scheduler/config_service.py`
    - `core/services/common/excel_validators.py`
    - `core/services/scheduler/resource_pool_builder.py`
  - Related Milestones: m3-regression-and-gates
  - Recommendation: Before claiming branch health, either refactor the changed files / fix the remaining failures, or explicitly update the gate allowlists with rationale so the architecture fitness suite reflects the intended debt posture.
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
### m1-scope-and-surface · Round 1 - change scope, surface wiring, and residual changed-file pass
- Status: completed
- Recorded At: 2026-04-02T07:22:13.160Z
- Reviewed Modules: web/routes, templates, core/algorithms/greedy, tooling
- Summary:
Re-collected the current uncommitted workspace from scratch and treated all prior conclusions as unverified. The active review scope remains a 49-file diff (2985 insertions / 2599 deletions). Re-ran the reference tracer (`evidence/DeepReview/reference_trace.md`), which reported 289 analyzed functions, 544 call relations, and 2 heuristic cross-layer boundary risks that were kept as investigation leads rather than promoted findings.

Manually re-checked the strict-mode surface wiring across route and template entry points. `web/routes/process_parts.py`, `web/routes/process_excel_routes.py`, `web/routes/scheduler_batches.py`, `web/routes/scheduler_excel_batches.py`, `web/routes/scheduler_run.py`, and `web/routes/scheduler_week_plan.py` all expose a local `_strict_mode_enabled()` parser and forward the resulting flag into service calls. The UI carry-through is also present in `templates/components/excel_import.html`, `templates/scheduler/excel_import_batches.html`, `templates/process/list.html`, `templates/process/detail.html`, `templates/scheduler/batches.html`, `templates/scheduler/batches_manage.html`, and `templates/scheduler/batch_detail.html` via `name="strict_mode"` controls / hidden fields.

To close the remaining lower-confidence gaps in the changed set, I also spot-reviewed `core/algorithms/greedy/dispatch/sgs.py`, `core/algorithms/greedy/seed.py`, `check_manual_layout.py`, and `verify_manual_styles.py`. `dispatch/sgs.py` now degrades scoring failures into explicit worst-rank candidates plus counters instead of silently dropping candidates during ranking; `seed.py` normalizes malformed / duplicate seed results with warnings and counters; the two manual-layout scripts are tooling-only and do not alter business strict-mode semantics.

Round-1 conclusion: the current review target is correctly re-established as the present 49-file workspace, and the strict-mode flag is consistently surfaced from UI/forms into the route layer without a newly observed bypass in the residual changed files reviewed here.
- Conclusion: Round 1 completed: the current workspace scope and UI/route strict_mode surface were revalidated from scratch, and the remaining changed tooling/algorithm helper files reviewed in this pass did not introduce a new strict-mode bypass.
- Evidence Files:
  - `evidence/DeepReview/reference_trace.md`
  - `web/routes/process_parts.py`
  - `web/routes/process_excel_routes.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_run.py`
  - `web/routes/scheduler_week_plan.py`
  - `templates/components/excel_import.html`
  - `templates/scheduler/excel_import_batches.html`
  - `templates/process/list.html`
  - `templates/process/detail.html`
  - `templates/scheduler/batches.html`
  - `templates/scheduler/batches_manage.html`
  - `templates/scheduler/batch_detail.html`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/seed.py`
  - `check_manual_layout.py`
  - `verify_manual_styles.py`
- Recommended Next Action: Proceed to the deep chain-level review of process/template/scheduler propagation and strict/fallback semantics.

### m2-strict-chain-revalidation · Round 2 - end-to-end strict_mode propagation and fallback semantics
- Status: completed
- Recorded At: 2026-04-02T07:22:30.833Z
- Reviewed Modules: core/services/process, core/services/scheduler, core/algorithms/greedy
- Summary:
Deep-read the core process / template / scheduler chain and revalidated strict-mode propagation end to end. On the process side, `web/routes/process_parts.py` forwards strict mode into `PartService.create(...)`, `PartService.reparse_and_save(...)`, and `ExternalGroupService.set_merge_mode(...)`; `web/routes/process_excel_routes.py` uses strict parsing during preview validation and confirm flow. On the scheduler/template side, `web/routes/scheduler_batches.py`, `web/routes/scheduler_excel_batches.py`, `web/routes/scheduler_run.py`, and `web/routes/scheduler_week_plan.py` forward the same flag into `BatchService` / `ScheduleService`.

The service chain now preserves that flag through the reviewed built-in code paths: `BatchService._default_template_resolver()` forwards strict mode into `PartService`, `BatchService._invoke_template_resolver()` only omits the kwarg when a custom resolver signature does not support it, `ScheduleService` passes strict mode into both `ConfigService.get_snapshot(...)` and `optimize_schedule(...)`, `schedule_optimizer_steps._schedule_with_optional_strict_mode()` only drops the kwarg when a scheduler implementation does not accept it, and `GreedyScheduler.schedule(..., strict_mode=False)` forwards the flag into `resolve_schedule_params(...)`.

Within those paths, the formerly silent fallbacks reviewed in this audit now surface as explicit errors under strict mode. `RouteParser.parse(..., strict_mode=True)` rejects unknown op types, missing supplier mappings, and supplier default-day values that would otherwise be normalized to 1.0. `PartService.create(..., strict_mode=True)` pre-parses before persistence and therefore preserves atomic rejection. `ExternalGroupService._apply_separate_mode(..., strict_mode=True)` raises on invalid `ext_days_*` instead of writing 1.0. `resolve_schedule_params(..., strict_mode=True)` raises on invalid `dispatch_mode`, `dispatch_rule`, and `auto_assign_enabled` instead of silently downgrading them.

Residual nuance from this round: `build_schedule_config_snapshot(..., strict_mode=True)` is only strict for choice / yes-no fields. Invalid numeric values still flow through `_get_float()` / `_get_int()` and are coerced back to defaults rather than rejected, so strict mode is not yet semantically uniform across the entire scheduler config surface.
- Conclusion: Round 2 completed: the reviewed built-in process/template/scheduler chains now propagate strict_mode end to end and convert the targeted silent fallbacks into explicit failures, but strict numeric validation in the config snapshot remains only partial.
- Evidence Files:
  - `core/services/process/route_parser.py`
  - `core/services/process/part_service.py`
  - `core/services/process/external_group_service.py`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `core/services/scheduler/config_service.py`
  - `core/services/scheduler/config_presets.py`
  - `core/services/scheduler/config_snapshot.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/schedule_params.py`
  - `web/routes/process_parts.py`
  - `web/routes/process_excel_routes.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_run.py`
  - `web/routes/scheduler_week_plan.py`
- Recommended Next Action: Execute and analyze the regression / architecture gate reruns to determine whether the revalidated strict-mode behavior is still blocked by compatibility or architecture issues.
- Findings:
  - [low] other: strict_mode remains partial for numeric scheduler config fields

### m3-regression-and-gates · Round 3 - targeted regressions, full-suite rerun, and architecture gates
- Status: completed
- Recorded At: 2026-04-02T07:23:02.165Z
- Reviewed Modules: tests, core/services/scheduler, core/services/common, core/services/process
- Summary:
Executed the focused strict/silent-fallback regression pack and then rechecked broader gates. The targeted pack passed in full (`13 passed`): `regression_schedule_summary_v11_contract`, `regression_scheduler_route_enforce_ready_tristate`, `regression_scheduler_strict_mode_dispatch_flags`, `regression_dict_cfg_contract`, `regression_batch_detail_linkage`, `regression_supplier_service_invalid_default_days_not_silent`, `regression_route_parser_supplier_default_days_zero_trace`, `regression_route_parser_strict_mode_rejects_supplier_fallback`, `regression_route_parser_missing_supplier_warning`, `regression_batch_service_strict_mode_template_autoparse`, `regression_batch_excel_import_strict_mode_hardfail_atomic`, `regression_part_service_create_strict_mode_atomic`, and `regression_external_group_service_strict_mode_blank_days`. This confirms that the reviewed built-in strict-mode paths behave as intended on the current branch.

The branch is not fully clean, however. `tests/regression_auto_assign_persist_truthy_variants.py` fails because `ScheduleService` now calls `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`, while the test monkeypatch replaces `ConfigService.get_snapshot` with `_patched_get_snapshot(self)` that does not accept the new kwarg. Although this was reproduced through a test monkeypatch, it represents a real compatibility risk for any external stub/monkeypatch that still assumes the old signature.

Architecture fitness is also still red. `tests/test_architecture_fitness.py` reports `common <-> scheduler` in `test_no_circular_service_dependencies`, and the most concrete reviewed edge is `core/services/common/excel_validators.py` importing `core.services.scheduler.number_utils.parse_finite_int` while many scheduler modules import `core.services.common.*`. The same test file also still fails `test_no_silent_exception_swallow`, `test_file_size_limit`, and `test_cyclomatic_complexity_threshold`, including changed strict-mode-related files such as `core/services/process/part_service.py`, `core/services/process/route_parser.py`, `core/services/scheduler/batch_service.py`, `core/services/scheduler/schedule_optimizer.py`, `core/services/scheduler/schedule_service.py`, and `core/services/scheduler/schedule_summary.py`. Some failures are clearly pre-existing/unrelated, but the branch cannot be called architecture-gate-clean in its current state.

The broader suite rerun finished at `261 passed, 11 failed`. Two persistent non-core failures remained on direct rerun (`regression_config_manual_markdown` exact-string contract drift in `static/js/config_manual.js`, and `test_team_pages_excel_smoke` with a Windows `PermissionError` on an Excel template file). Several other full-suite-only failures passed when rerun directly, so there is also an order-dependent / flaky component outside the strict-mode core path.
- Conclusion: Round 3 completed: the critical reviewed strict-mode regressions pass, but the current workspace still has a reproduced compatibility break around `ConfigService.get_snapshot(strict_mode=...)` and remains non-green on architecture gates / full-suite health.
- Evidence Files:
  - `tests/regression_auto_assign_persist_truthy_variants.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/config_service.py`
  - `tests/test_architecture_fitness.py`
  - `core/services/common/excel_validators.py`
  - `core/services/process/part_service.py`
  - `core/services/process/route_parser.py`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_summary.py`
  - `static/js/config_manual.js`
  - `tests/test_team_pages_excel_smoke.py`
- Recommended Next Action: Finalize the review with a needs-follow-up decision: the critical strict-mode silent-fallback paths were revalidated, but release confidence remains blocked by the compatibility regression and non-green architecture gates.
- Findings:
  - [medium] test: `ConfigService.get_snapshot(strict_mode=...)` breaks old monkeypatch / stub signatures
  - [medium] maintainability: Service package cycle `common <-> scheduler` is still present
  - [low] test: Architecture fitness and full-suite health are still not green on the reviewed workspace
<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mnh4ma4o-x4nla6",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "finalizedAt": "2026-04-02T07:23:26.590Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "latestConclusion": "Three-round revalidation of the current uncommitted workspace confirms that the reviewed built-in `strict_mode` paths now surface the targeted silent-fallback cases instead of silently downgrading them. The end-to-end UI -> route -> service -> scheduler propagation is present, and the focused regression pack passed for the core reviewed behaviors: unknown op types, missing supplier mappings, invalid supplier `default_days`, invalid `ext_days_*`, and invalid `dispatch_mode` / `dispatch_rule` / `auto_assign_enabled` are all rejected under `strict_mode=True` in the examined built-in flows. That said, the workspace is not yet fully releasable / gate-clean. A reproduced compatibility regression remains around `ConfigService.get_snapshot(strict_mode=...)` for old monkeypatch/stub signatures, the architecture fitness suite is still red (including the `common <-> scheduler` cycle and threshold/allowlist debt affecting changed files), and the full suite still contains non-core persistent / flaky failures. The correct final judgment for this rerun is therefore: the silent-fallback fix is materially effective on the core reviewed paths, but the branch still requires follow-up work before it can be treated as fully verified end-to-end.",
  "recommendedNextAction": "Resolve or consciously encapsulate the `ConfigService.get_snapshot(strict_mode=...)` compatibility boundary, break the `common <-> scheduler` dependency cycle (or explicitly accept/document it), and rerun `tests/regression_auto_assign_persist_truthy_variants.py`, `tests/test_architecture_fitness.py`, and the broader suite before claiming branch health.",
  "reviewedModules": [
    "web/routes",
    "templates",
    "core/algorithms/greedy",
    "tooling",
    "core/services/process",
    "core/services/scheduler",
    "tests",
    "core/services/common"
  ],
  "milestones": [
    {
      "id": "m1-scope-and-surface",
      "title": "Round 1 - change scope, surface wiring, and residual changed-file pass",
      "summary": "Re-collected the current uncommitted workspace from scratch and treated all prior conclusions as unverified. The active review scope remains a 49-file diff (2985 insertions / 2599 deletions). Re-ran the reference tracer (`evidence/DeepReview/reference_trace.md`), which reported 289 analyzed functions, 544 call relations, and 2 heuristic cross-layer boundary risks that were kept as investigation leads rather than promoted findings.\n\nManually re-checked the strict-mode surface wiring across route and template entry points. `web/routes/process_parts.py`, `web/routes/process_excel_routes.py`, `web/routes/scheduler_batches.py`, `web/routes/scheduler_excel_batches.py`, `web/routes/scheduler_run.py`, and `web/routes/scheduler_week_plan.py` all expose a local `_strict_mode_enabled()` parser and forward the resulting flag into service calls. The UI carry-through is also present in `templates/components/excel_import.html`, `templates/scheduler/excel_import_batches.html`, `templates/process/list.html`, `templates/process/detail.html`, `templates/scheduler/batches.html`, `templates/scheduler/batches_manage.html`, and `templates/scheduler/batch_detail.html` via `name=\"strict_mode\"` controls / hidden fields.\n\nTo close the remaining lower-confidence gaps in the changed set, I also spot-reviewed `core/algorithms/greedy/dispatch/sgs.py`, `core/algorithms/greedy/seed.py`, `check_manual_layout.py`, and `verify_manual_styles.py`. `dispatch/sgs.py` now degrades scoring failures into explicit worst-rank candidates plus counters instead of silently dropping candidates during ranking; `seed.py` normalizes malformed / duplicate seed results with warnings and counters; the two manual-layout scripts are tooling-only and do not alter business strict-mode semantics.\n\nRound-1 conclusion: the current review target is correctly re-established as the present 49-file workspace, and the strict-mode flag is consistently surfaced from UI/forms into the route layer without a newly observed bypass in the residual changed files reviewed here.",
      "status": "completed",
      "conclusion": "Round 1 completed: the current workspace scope and UI/route strict_mode surface were revalidated from scratch, and the remaining changed tooling/algorithm helper files reviewed in this pass did not introduce a new strict-mode bypass.",
      "evidenceFiles": [
        "evidence/DeepReview/reference_trace.md",
        "web/routes/process_parts.py",
        "web/routes/process_excel_routes.py",
        "web/routes/scheduler_batches.py",
        "web/routes/scheduler_excel_batches.py",
        "web/routes/scheduler_run.py",
        "web/routes/scheduler_week_plan.py",
        "templates/components/excel_import.html",
        "templates/scheduler/excel_import_batches.html",
        "templates/process/list.html",
        "templates/process/detail.html",
        "templates/scheduler/batches.html",
        "templates/scheduler/batches_manage.html",
        "templates/scheduler/batch_detail.html",
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/seed.py",
        "check_manual_layout.py",
        "verify_manual_styles.py"
      ],
      "reviewedModules": [
        "web/routes",
        "templates",
        "core/algorithms/greedy",
        "tooling"
      ],
      "recommendedNextAction": "Proceed to the deep chain-level review of process/template/scheduler propagation and strict/fallback semantics.",
      "recordedAt": "2026-04-02T07:22:13.160Z",
      "findingIds": []
    },
    {
      "id": "m2-strict-chain-revalidation",
      "title": "Round 2 - end-to-end strict_mode propagation and fallback semantics",
      "summary": "Deep-read the core process / template / scheduler chain and revalidated strict-mode propagation end to end. On the process side, `web/routes/process_parts.py` forwards strict mode into `PartService.create(...)`, `PartService.reparse_and_save(...)`, and `ExternalGroupService.set_merge_mode(...)`; `web/routes/process_excel_routes.py` uses strict parsing during preview validation and confirm flow. On the scheduler/template side, `web/routes/scheduler_batches.py`, `web/routes/scheduler_excel_batches.py`, `web/routes/scheduler_run.py`, and `web/routes/scheduler_week_plan.py` forward the same flag into `BatchService` / `ScheduleService`.\n\nThe service chain now preserves that flag through the reviewed built-in code paths: `BatchService._default_template_resolver()` forwards strict mode into `PartService`, `BatchService._invoke_template_resolver()` only omits the kwarg when a custom resolver signature does not support it, `ScheduleService` passes strict mode into both `ConfigService.get_snapshot(...)` and `optimize_schedule(...)`, `schedule_optimizer_steps._schedule_with_optional_strict_mode()` only drops the kwarg when a scheduler implementation does not accept it, and `GreedyScheduler.schedule(..., strict_mode=False)` forwards the flag into `resolve_schedule_params(...)`.\n\nWithin those paths, the formerly silent fallbacks reviewed in this audit now surface as explicit errors under strict mode. `RouteParser.parse(..., strict_mode=True)` rejects unknown op types, missing supplier mappings, and supplier default-day values that would otherwise be normalized to 1.0. `PartService.create(..., strict_mode=True)` pre-parses before persistence and therefore preserves atomic rejection. `ExternalGroupService._apply_separate_mode(..., strict_mode=True)` raises on invalid `ext_days_*` instead of writing 1.0. `resolve_schedule_params(..., strict_mode=True)` raises on invalid `dispatch_mode`, `dispatch_rule`, and `auto_assign_enabled` instead of silently downgrading them.\n\nResidual nuance from this round: `build_schedule_config_snapshot(..., strict_mode=True)` is only strict for choice / yes-no fields. Invalid numeric values still flow through `_get_float()` / `_get_int()` and are coerced back to defaults rather than rejected, so strict mode is not yet semantically uniform across the entire scheduler config surface.",
      "status": "completed",
      "conclusion": "Round 2 completed: the reviewed built-in process/template/scheduler chains now propagate strict_mode end to end and convert the targeted silent fallbacks into explicit failures, but strict numeric validation in the config snapshot remains only partial.",
      "evidenceFiles": [
        "core/services/process/route_parser.py",
        "core/services/process/part_service.py",
        "core/services/process/external_group_service.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/batch_template_ops.py",
        "core/services/scheduler/config_service.py",
        "core/services/scheduler/config_presets.py",
        "core/services/scheduler/config_snapshot.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/schedule_params.py",
        "web/routes/process_parts.py",
        "web/routes/process_excel_routes.py",
        "web/routes/scheduler_batches.py",
        "web/routes/scheduler_excel_batches.py",
        "web/routes/scheduler_run.py",
        "web/routes/scheduler_week_plan.py"
      ],
      "reviewedModules": [
        "core/services/process",
        "core/services/scheduler",
        "core/algorithms/greedy"
      ],
      "recommendedNextAction": "Execute and analyze the regression / architecture gate reruns to determine whether the revalidated strict-mode behavior is still blocked by compatibility or architecture issues.",
      "recordedAt": "2026-04-02T07:22:30.833Z",
      "findingIds": [
        "finding-strict-config-numeric-gap"
      ]
    },
    {
      "id": "m3-regression-and-gates",
      "title": "Round 3 - targeted regressions, full-suite rerun, and architecture gates",
      "summary": "Executed the focused strict/silent-fallback regression pack and then rechecked broader gates. The targeted pack passed in full (`13 passed`): `regression_schedule_summary_v11_contract`, `regression_scheduler_route_enforce_ready_tristate`, `regression_scheduler_strict_mode_dispatch_flags`, `regression_dict_cfg_contract`, `regression_batch_detail_linkage`, `regression_supplier_service_invalid_default_days_not_silent`, `regression_route_parser_supplier_default_days_zero_trace`, `regression_route_parser_strict_mode_rejects_supplier_fallback`, `regression_route_parser_missing_supplier_warning`, `regression_batch_service_strict_mode_template_autoparse`, `regression_batch_excel_import_strict_mode_hardfail_atomic`, `regression_part_service_create_strict_mode_atomic`, and `regression_external_group_service_strict_mode_blank_days`. This confirms that the reviewed built-in strict-mode paths behave as intended on the current branch.\n\nThe branch is not fully clean, however. `tests/regression_auto_assign_persist_truthy_variants.py` fails because `ScheduleService` now calls `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`, while the test monkeypatch replaces `ConfigService.get_snapshot` with `_patched_get_snapshot(self)` that does not accept the new kwarg. Although this was reproduced through a test monkeypatch, it represents a real compatibility risk for any external stub/monkeypatch that still assumes the old signature.\n\nArchitecture fitness is also still red. `tests/test_architecture_fitness.py` reports `common <-> scheduler` in `test_no_circular_service_dependencies`, and the most concrete reviewed edge is `core/services/common/excel_validators.py` importing `core.services.scheduler.number_utils.parse_finite_int` while many scheduler modules import `core.services.common.*`. The same test file also still fails `test_no_silent_exception_swallow`, `test_file_size_limit`, and `test_cyclomatic_complexity_threshold`, including changed strict-mode-related files such as `core/services/process/part_service.py`, `core/services/process/route_parser.py`, `core/services/scheduler/batch_service.py`, `core/services/scheduler/schedule_optimizer.py`, `core/services/scheduler/schedule_service.py`, and `core/services/scheduler/schedule_summary.py`. Some failures are clearly pre-existing/unrelated, but the branch cannot be called architecture-gate-clean in its current state.\n\nThe broader suite rerun finished at `261 passed, 11 failed`. Two persistent non-core failures remained on direct rerun (`regression_config_manual_markdown` exact-string contract drift in `static/js/config_manual.js`, and `test_team_pages_excel_smoke` with a Windows `PermissionError` on an Excel template file). Several other full-suite-only failures passed when rerun directly, so there is also an order-dependent / flaky component outside the strict-mode core path.",
      "status": "completed",
      "conclusion": "Round 3 completed: the critical reviewed strict-mode regressions pass, but the current workspace still has a reproduced compatibility break around `ConfigService.get_snapshot(strict_mode=...)` and remains non-green on architecture gates / full-suite health.",
      "evidenceFiles": [
        "tests/regression_auto_assign_persist_truthy_variants.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/config_service.py",
        "tests/test_architecture_fitness.py",
        "core/services/common/excel_validators.py",
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/resource_pool_builder.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_summary.py",
        "static/js/config_manual.js",
        "tests/test_team_pages_excel_smoke.py"
      ],
      "reviewedModules": [
        "tests",
        "core/services/scheduler",
        "core/services/common",
        "core/services/process"
      ],
      "recommendedNextAction": "Finalize the review with a needs-follow-up decision: the critical strict-mode silent-fallback paths were revalidated, but release confidence remains blocked by the compatibility regression and non-green architecture gates.",
      "recordedAt": "2026-04-02T07:23:02.165Z",
      "findingIds": [
        "finding-get-snapshot-monkeypatch-compat",
        "finding-common-scheduler-cycle",
        "finding-architecture-gates-still-red"
      ]
    }
  ],
  "findings": [
    {
      "id": "finding-strict-config-numeric-gap",
      "severity": "low",
      "category": "other",
      "title": "strict_mode remains partial for numeric scheduler config fields",
      "description": "`build_schedule_config_snapshot(..., strict_mode=True)` raises for reviewed choice / yes-no fields such as `dispatch_mode`, `dispatch_rule`, and `auto_assign_enabled`, but numeric readers `_get_float()` and `_get_int()` still coerce invalid values back to defaults. As a result, strict mode is not yet uniform for numeric scheduler config keys such as weights, time budgets, and other numeric snapshot fields.",
      "evidenceFiles": [
        "core/services/scheduler/config_snapshot.py",
        "core/services/scheduler/config_service.py",
        "core/services/process/route_parser.py",
        "core/services/process/part_service.py",
        "core/services/process/external_group_service.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/batch_template_ops.py",
        "core/services/scheduler/config_presets.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/schedule_params.py",
        "web/routes/process_parts.py",
        "web/routes/process_excel_routes.py",
        "web/routes/scheduler_batches.py",
        "web/routes/scheduler_excel_batches.py",
        "web/routes/scheduler_run.py",
        "web/routes/scheduler_week_plan.py"
      ],
      "relatedMilestoneIds": [
        "m2-strict-chain-revalidation"
      ],
      "recommendation": "Either document the narrower strict-mode contract explicitly, or extend strict validation to numeric snapshot fields so that invalid numeric config values also surface as hard failures under strict mode."
    },
    {
      "id": "finding-get-snapshot-monkeypatch-compat",
      "severity": "medium",
      "category": "test",
      "title": "`ConfigService.get_snapshot(strict_mode=...)` breaks old monkeypatch / stub signatures",
      "description": "`ScheduleService` now calls `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`. The reproduced failure in `tests/regression_auto_assign_persist_truthy_variants.py` shows that any monkeypatch or stub still defined as `get_snapshot(self)` now fails with `TypeError: unexpected keyword argument 'strict_mode'`. This does not invalidate the built-in strict-mode flow, but it is a real compatibility risk for tests, stubs, and external extension points that replace `ConfigService.get_snapshot` without accepting the new kwarg.",
      "evidenceFiles": [
        "tests/regression_auto_assign_persist_truthy_variants.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/config_service.py",
        "tests/test_architecture_fitness.py",
        "core/services/common/excel_validators.py",
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/resource_pool_builder.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_summary.py",
        "static/js/config_manual.js",
        "tests/test_team_pages_excel_smoke.py"
      ],
      "relatedMilestoneIds": [
        "m3-regression-and-gates"
      ],
      "recommendation": "Preserve backward compatibility at this boundary by either making monkeypatches/stubs accept `strict_mode`/`**kwargs`, or by applying an optional-kwarg compatibility guard similar to `schedule_optimizer_steps._schedule_with_optional_strict_mode()` if external replacement of `get_snapshot` is an intended extension point."
    },
    {
      "id": "finding-common-scheduler-cycle",
      "severity": "medium",
      "category": "maintainability",
      "title": "Service package cycle `common <-> scheduler` is still present",
      "description": "`tests/test_architecture_fitness.py::test_no_circular_service_dependencies` still fails with `common <-> scheduler`. The most concrete reviewed dependency edge is `core/services/common/excel_validators.py` importing `core.services.scheduler.number_utils.parse_finite_int`, while scheduler modules continue to import `core.services.common.*`. This keeps the reviewed branch architecturally non-green and increases cross-package coupling around the strict-mode-adjacent scheduler/common utility layer.",
      "evidenceFiles": [
        "tests/test_architecture_fitness.py",
        "core/services/common/excel_validators.py",
        "core/services/scheduler/config_service.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/resource_pool_builder.py",
        "tests/regression_auto_assign_persist_truthy_variants.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_summary.py",
        "static/js/config_manual.js",
        "tests/test_team_pages_excel_smoke.py"
      ],
      "relatedMilestoneIds": [
        "m3-regression-and-gates"
      ],
      "recommendation": "Break the cycle by moving shared numeric/normalization helpers into a dependency-neutral common utility module (or otherwise inverting the dependency) so that `common` no longer imports from `scheduler`."
    },
    {
      "id": "finding-architecture-gates-still-red",
      "severity": "low",
      "category": "test",
      "title": "Architecture fitness and full-suite health are still not green on the reviewed workspace",
      "description": "Beyond the package cycle, the reviewed workspace still fails `test_no_silent_exception_swallow`, `test_file_size_limit`, and `test_cyclomatic_complexity_threshold`, including some changed strict-mode-related files (`part_service.py`, `route_parser.py`, `batch_service.py`, `schedule_optimizer.py`, `schedule_service.py`, `schedule_summary.py`). The broader suite also ended at `261 passed, 11 failed`, with both persistent non-core failures and order-dependent/flaky behavior outside the strict-mode core path. This means the branch cannot yet be described as fully regression- / gate-clean even though the targeted strict-mode behavior materially improved.",
      "evidenceFiles": [
        "tests/test_architecture_fitness.py",
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_summary.py",
        "static/js/config_manual.js",
        "tests/test_team_pages_excel_smoke.py",
        "tests/regression_auto_assign_persist_truthy_variants.py",
        "core/services/scheduler/config_service.py",
        "core/services/common/excel_validators.py",
        "core/services/scheduler/resource_pool_builder.py"
      ],
      "relatedMilestoneIds": [
        "m3-regression-and-gates"
      ],
      "recommendation": "Before claiming branch health, either refactor the changed files / fix the remaining failures, or explicitly update the gate allowlists with rationale so the architecture fitness suite reflects the intended debt posture."
    }
  ]
}
<!-- LIMCODE_REVIEW_METADATA_END -->
