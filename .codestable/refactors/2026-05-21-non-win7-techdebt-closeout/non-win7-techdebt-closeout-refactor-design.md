---
doc_type: implementation-plan
refactor: 2026-05-21-non-win7-techdebt-closeout
status: draft
scope: Non-Win7 prioritized technical-debt closeout from `audit/2026-05/20260520_非静默回退技术债务留档.md`.
summary: Deep sequencing plan for PR7E review-state closeout, PR8 clean-worktree proof, PR7 L3/L2 scheduler debts, route-import refactor, and operator-machine import/readside refactor.
excluded_scope: Win7 / launcher accepted risks; silent fallback debt entries themselves.
---

# Non-Win7 Technical Debt Closeout — Detailed Implementation Plan

This plan is intentionally **implementation-ready but not implementation itself**. It excludes item `3. Win7 / launcher accepted risks` entirely, except for this non-scope statement.

Line anchors below reflect the workspace snapshot at plan creation time. If any anchor drifts, locate by the named function, variable, or test before editing.

## 1. Scope, non-scope, and hard guardrails

### 1.1 In scope

1. **PR7E review-state closeout**
   - Current code appears to contain the previously requested PR7E fields and downstream-weight chain.
   - The debt is therefore likely stale review/status state, not first-pass business-code implementation.
   - Source of mismatch: `.limcode/review/pr7e-uncommitted-changes-review.md:21-30` still reports two open medium findings, and `.limcode/review/pr7e-uncommitted-changes-review.md:34-79` still lists both findings as open.
   - Fix style: verify code/tests, then update review/status artifacts only if evidence passes.

2. **PR8 clean-worktree QualityGate proof**
   - `.codestable/features/2026-05-20-scheduler-graph-resource-matching-report/scheduler-graph-resource-matching-report-acceptance.md:89-93` explicitly says the final clean-worktree quality gate proof is still missing.
   - Fix style: do not claim proof until a real clean-worktree run succeeds.

3. **PR7 L3 week-plan export redirect context preservation**
   - `web/routes/domains/scheduler/scheduler_week_plan.py:263-266` currently redirects with `plan_role` only.
   - `week_plan_export()` reads `week_start`, `plan_role`, `offset`, and `version` at `web/routes/domains/scheduler/scheduler_week_plan.py:345-360`, but the generic failure branch at `web/routes/domains/scheduler/scheduler_week_plan.py:383-386` loses `week_start / offset / version`.
   - Fix style: small user-visible bug fix with a targeted regression test; do not add new fallback behavior.

4. **PR7 L2 version allocation gap contract proof**
   - `data/repositories/schedule_history_repo.py:43-50` documents the intended version sequence contract: version gaps are allowed, version reuse is not.
   - `core/services/scheduler/run/schedule_orchestrator.py:351-365` validates schedule rows before version allocation, then allocates a version in a short transaction.
   - Fix style: add/strengthen contract tests and documentation first; do not prematurely move the transaction boundary.

5. **`web/routes/process_excel_routes.py::excel_routes_confirm` cohesion refactor**
   - `web/routes/process_excel_routes.py:215-380` currently owns request parsing, stale-baseline rejection, preview rebuild, transaction application, error aggregation, warning aggregation, audit logging, flash messages, and redirect.
   - Fix style: behavior-equivalent extraction into cohesive helpers.

6. **`core/services/personnel/operator_machine_service.py::apply_import_links` and readside `_normalize_row` refactor**
   - `core/services/personnel/operator_machine_service.py:408-504` mixes preview-row classification, identity extraction, row-level validation aggregation, writes, counters, and sample construction.
   - `core/services/personnel/operator_machine_query_service.py:25-67` mixes dirty-marker bookkeeping with skill and primary normalization.
   - Fix style: extract small pure helpers; preserve explicit row-level validation accumulation; propagate unexpected exceptions.

### 1.2 Explicit non-scope

- No work on **Win7 / launcher accepted risks**.
- No expansion or implementation of the silent-fallback debt entries themselves.
- No broad product behavior changes outside the listed debts.
- No commit, release note, or final “resolved” claim unless the relevant command or evidence has actually succeeded.
- No full complexity rescan claim while `radon` remains unavailable; if the gate reports `QualityGateError: 缺少 radon，无法执行复杂度扫描`, stop and treat it as an explicit tooling blocker, not as a skipped check.

### 1.3 Hard implementation guardrails

- Do **not** add new `except Exception` blocks.
- Do **not** swallow errors. Logger failures, DB errors, contract errors, and unexpected normalizer errors must remain visible.
- Do **not** add defensive “if missing then silently default” logic unless it is already an explicit product contract.
- Do **not** convert unexpected runtime errors into row-level Excel warnings.
- Preserve existing intentional row-level validation semantics:
  - `AppError` / `ValidationError` tied to a specific Excel row may be accumulated as a visible row error where the current route/service already does this.
  - `RuntimeError`, `TypeError`, repository contract errors, and unexpected normalizer failures must propagate to the app error boundary or test failure.
- Prefer concise helper extraction and data flow over nested conditional branches.
- If fresh verification contradicts this plan, stop and revise the plan instead of patching opportunistically.

## 2. Dependency graph and sequencing

```text
Step 1 PR7E review-state closeout
  ├─ independent of business-code refactors
  ├─ must finish before calling PR7E debt resolved
  └─ produces review/status evidence only if tests pass

Step 2 PR7 L3 week-plan redirect context
  ├─ small bug fix
  ├─ safe before larger refactors
  └─ adds targeted route regression

Step 3 PR7 L2 version allocation gap contract
  ├─ contract-proof work, mostly tests/docs
  ├─ should not depend on Step 2
  └─ must not alter persistence transaction semantics unless tests expose an actual contradiction

Step 4 excel_routes_confirm cohesion refactor
  ├─ larger refactor with user-facing import semantics
  ├─ should start only after smaller scheduler fixes are green
  └─ must preserve strict mode, stale baseline rejection, replace guard, audit log, warning flash

Step 5 operator-machine import/readside refactor
  ├─ larger service/readside cleanup
  ├─ can run after Step 4 or in a separate branch
  └─ must preserve row-level error accumulation and dirty-field visibility

Step 6 PR8 clean-worktree QualityGate proof
  ├─ last step only
  ├─ requires all intended code/docs/tests settled and worktree clean
  └─ may require a user-approved commit or clean checkout before running `--require-clean-worktree`
```

Recommended order: **1 → 2 → 3 → 4 → 5 → 6**. Do not combine steps in one implementation pass; each step has its own validation and rollback.

## 3. Step-by-step implementation design

## Step 1 — PR7E review-state closeout

### 3.1.1 Current evidence chain

The stale status is in review artifacts:

- `.limcode/review/pr7e-uncommitted-changes-review.md:21-30`
  - `问题总数: 2` and latest conclusion still say both PR7E findings need follow-up.
- `.limcode/review/pr7e-uncommitted-changes-review.md:34-79`
  - `pr7e-downstream-weight-unused` and `pr7e-candidate-summary-fields-missing` are still open in the findings section.
- `.limcode/plans/pr7e-candidate-closeout-fix-plan.md:5-13`
  - all PR7E fix-plan TODOs are already completed.
- `.limcode/plans/pr7e-candidate-closeout-fix-plan.md:30-35`
  - original implementation guardrails match this plan: concise, no silent fallback, no swallowed errors, no over-defensive programming.

The current code chain appears already closed:

1. Candidate spec generation
   - `core/services/scheduler/run/schedule_candidate_specs.py:21-31`
     - `CandidateRunSpec.graph_downstream_weight` exists.
   - `core/services/scheduler/run/schedule_candidate_specs.py:49-88`
     - `generate_candidate_specs()` generates baseline `graph_downstream_weight=0` and critical-chain downstream weights via `max(1, int(round(1 * float(multiplier))))`.

2. Candidate runner propagation
   - `core/services/scheduler/run/schedule_candidate_runner.py:66-78`
     - `CandidateComparisonOutcome` includes `skipped_candidate_labels` and `baseline_missing_or_failed`.
   - `core/services/scheduler/run/schedule_candidate_runner.py:119-123`
     - `run_candidate_comparison()` builds specs from current `cfg.graph_critical_weight` and `cfg.graph_impact_weight`.
   - `core/services/scheduler/run/schedule_candidate_runner.py:227-248`
     - `_comparison_outcome()` populates counts and the two requested status fields.
   - `core/services/scheduler/run/schedule_candidate_runner.py:255-267`
     - `_skipped_candidate_labels()` and `_baseline_missing_or_failed()` encode the summary contract.
   - `core/services/scheduler/run/schedule_candidate_runner.py:387-396`
     - `_candidate_cfg()` passes `graph_downstream_weight=int(spec.graph_downstream_weight)` into the candidate config.

3. Graph score usage
   - `core/services/scheduler/run/schedule_graph_dispatch_context.py:41-49`
     - `graph_score_weights()` reads `graph_downstream_weight` from config.
   - `core/services/scheduler/run/schedule_graph_dispatch_context.py:52-57`
     - `graph_score_requested()` treats downstream weight as an enabling score weight.
   - `core/services/scheduler/run/schedule_graph_dispatch_context.py:60-67`
     - `score_weight_summary()` exposes `downstream_minutes_weight`.
   - `core/services/scheduler/graph/scoring.py:68-87`
     - `graph_score_bonus()` uses `downstream_minutes_weight` directly in the score formula.

4. Summary and analysis visibility
   - `core/services/scheduler/run/schedule_candidate_summary.py:128-151`
     - public summary includes `skipped_candidate_labels` and `baseline_missing_or_failed`.
   - `core/services/scheduler/run/schedule_candidate_summary.py:154-200`
     - minimal/log summaries preserve those fields.
   - `web/viewmodels/scheduler_analysis_candidates.py:210-222`
     - analysis viewmodel renders visible warning messages for failed baseline and skipped labels.

5. Existing regression anchors
   - `tests/regression_scheduler_candidate_runner_contract.py:199-226`
     - downstream weights remain active even when visible critical/impact weights are zero.
   - `tests/regression_scheduler_candidate_runner_contract.py:430-456`
     - skipped labels are recorded when the candidate budget is reached.
   - `tests/regression_scheduler_candidate_runner_contract.py:591-648`
     - missing/failed baseline is detected.

### 3.1.2 Implementation action

This step should be a **verification + artifact closeout**, not a code patch, unless verification fails.

1. Run targeted PR7E tests:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
     tests/regression_scheduler_candidate_runner_contract.py \
     tests/regression_scheduler_candidate_persistence_contract.py \
     tests/regression_scheduler_candidate_analysis_contract.py
   ```

2. Optionally run the narrower code-level checks first when iterating:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
     tests/regression_scheduler_candidate_runner_contract.py::test_candidate_runner_keeps_internal_downstream_weights_when_visible_weights_are_zero \
     tests/regression_scheduler_candidate_runner_contract.py::test_comparison_outcome_marks_missing_or_failed_baseline
   ```

3. If tests pass and the code chain above still exists:
   - Reopen/finalize the review artifact with a new milestone stating that the two findings have been verified fixed in current code.
   - Update tracking status for:
     - `pr7e-downstream-weight-unused`
     - `pr7e-candidate-summary-fields-missing`
   - Preserve the original historical review text; append closeout evidence instead of rewriting history.

4. If any test or code-chain assertion fails:
   - Stop.
   - Do not silently update review status.
   - Create a revised implementation patch plan for the failing chain only.

### 3.1.3 Touch / do-not-touch

Touch only after tests pass:

- `.limcode/review/pr7e-uncommitted-changes-review.md`
- optionally `.limcode/plans/pr7e-candidate-closeout-fix-plan.md` only for progress/status synchronization if required by the plan tooling.

Do not touch in the happy path:

- `core/services/scheduler/run/schedule_candidate_runner.py`
- `core/services/scheduler/run/schedule_graph_dispatch_context.py`
- `core/services/scheduler/run/schedule_candidate_summary.py`
- `web/viewmodels/scheduler_analysis_candidates.py`

### 3.1.4 Exit signal

- Targeted PR7E tests pass.
- Review artifact no longer reports the two PR7E findings as open without supporting evidence.
- No business code changed for this step unless verification uncovered a real drift.

### 3.1.5 Rollback

- Revert only the review/status artifact update.
- Do not revert PR7E code unless a separately approved code patch was made.

## Step 2 — PR7 L3 week-plan export redirect context preservation

### 3.2.1 Current evidence chain

- `web/routes/domains/scheduler/scheduler_week_plan.py:263-266`
  - `_week_plan_page_redirect(plan_role)` preserves only `plan_role`.
- `web/routes/domains/scheduler/scheduler_week_plan.py:269-273`
  - `_handle_week_plan_export_app_error(error, plan_role)` redirects through the same helper for non-404 app errors.
- `web/routes/domains/scheduler/scheduler_week_plan.py:276-342`
  - `week_plan_page()` consumes `week_start`, `offset`, `version`, and `plan_role` and builds `export_url`.
- `web/routes/domains/scheduler/scheduler_week_plan.py:345-360`
  - `week_plan_export()` reads the same request context before calling `get_week_plan_rows()`.
- `web/routes/domains/scheduler/scheduler_week_plan.py:381-386`
  - generic export failure flashes `导出周计划失败，请稍后重试。` and redirects with `plan_role` only.

Current tests cover related but not identical behavior:

- `tests/regression_week_plan_filename_uses_normalized_version.py:80-96`
  - export version normalization / invalid version redirect behavior.
- `tests/regression_week_plan_filename_uses_normalized_version.py:115-157`
  - export prefers `week_start` over stale `start_date/end_date`.
- `tests/regression_scheduler_candidate_week_plan_contract.py:159-215`
  - plan-role page/export contract.

### 3.2.2 Implementation action

Make redirect context explicit and small.

1. Replace `_week_plan_page_redirect(plan_role)` with a context-aware helper, for example:

   ```python
   def _week_plan_page_redirect(
       *,
       week_start: Optional[str],
       offset: int,
       version: Optional[str],
       plan_role: Optional[str],
   ):
       args = {
           "week_start": week_start,
           "offset": str(int(offset)),
           "version": version,
           "plan_role": plan_role,
       }
       return redirect(url_for("scheduler.week_plan_page", **{k: v for k, v in args.items() if str(v or "").strip()}))
   ```

   Notes:
   - This is a query builder, not a fallback.
   - It adds no new exception handling.
   - It uses a single dictionary comprehension rather than nested `if` blocks.
   - If preserving `offset=0` is mandatory for exact request echoing, remove the filter for `offset` and always pass it. Otherwise, the page default is already `0`.

2. Build a local context once in `week_plan_export()` after parsing request values:

   ```python
   redirect_context = {
       "week_start": week_start,
       "offset": offset,
       "version": request.args.get("version"),
       "plan_role": plan_role,
   }
   ```

3. Change `_handle_week_plan_export_app_error()` to accept the same context:

   ```python
   def _handle_week_plan_export_app_error(error: AppError, *, redirect_context: Dict[str, Any]):
       if error.code == ErrorCode.NOT_FOUND:
           return user_visible_app_error_message(error), 404
       flash(user_visible_app_error_message(error), "error")
       return _week_plan_page_redirect(**redirect_context)
   ```

4. In the generic exception branch, keep the current logging and flash message, but redirect with the full context:

   ```python
   return _week_plan_page_redirect(**redirect_context)
   ```

Do not change `_get_int_arg()` behavior, export workbook generation, plan-role resolution, or user-facing error text.

### 3.2.3 Regression test

Add a targeted test to `tests/regression_week_plan_filename_uses_normalized_version.py` or `tests/regression_scheduler_candidate_week_plan_contract.py`:

1. Monkeypatch `GanttService.get_week_plan_rows()` to raise `RuntimeError("forced export failure")`.
2. Request:

   ```text
   /scheduler/week-plan/export?week_start=2026-05-11&offset=2&version=7&plan_role=baseline_best
   ```

3. Assert:
   - response is `302` when `follow_redirects=False`;
   - `Location` contains:
     - `week_start=2026-05-11`
     - `offset=2`
     - `version=7`
     - `plan_role=baseline_best`
   - body/log does not expose `forced export failure` to the user.

### 3.2.4 Validation commands

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/regression_week_plan_filename_uses_normalized_version.py \
  tests/regression_scheduler_candidate_week_plan_contract.py \
  tests/regression_scheduler_week_plan_summary_observability.py
```

### 3.2.5 Exit signal

- The new regression fails before the helper change and passes after it.
- Existing week-plan export filename, plan-role, and stale-range tests still pass.
- No new broad catch or defaulting behavior is introduced.

### 3.2.6 Rollback

- Revert the helper signature and the single test.
- Since this step should touch only one route file plus one test file, rollback is low-risk.

## Step 3 — PR7 L2 version allocation gap contract proof

### 3.3.1 Current evidence chain

- `data/repositories/schedule_history_repo.py:43-50`
  - `allocate_next_version()` explicitly states gaps are allowed and reuse is not.
- `data/repositories/schedule_history_repo.py:77-87`
  - a sequence row is inserted and validated as a positive version.
- `data/repositories/schedule_history_repo.py:88-94`
  - allocation failure is wrapped as `AppError`; do not copy or expand the nested logger-swallowing pattern.
- `core/services/scheduler/run/schedule_orchestrator.py:351-356`
  - schedule payload is validated before version allocation.
- `core/services/scheduler/run/schedule_orchestrator.py:363-365`
  - version allocation occurs in a short transaction before summary building and later persistence.
- `core/services/scheduler/run/schedule_orchestrator.py:408-441`
  - orchestration returns `ScheduleOrchestrationOutcome` containing the allocated version and candidate comparison.
- `core/services/scheduler/run/schedule_candidate_persistence.py:230-270`
  - candidate comparison persistence uses the allocated `version` for candidate rows/selections.
- `tests/regression_schedule_orchestrator_contract.py:114-162`
  - empty results must fail before allocation.
- `tests/regression_schedule_orchestrator_contract.py:316-379`
  - invalid rows must fail before allocation.

### 3.3.2 Implementation action

This is a **contract-proof step**, not a transaction rewrite.

1. Add a focused repository-level regression test, preferably in a new file such as `tests/regression_schedule_history_version_gap_contract.py` or in the existing orchestrator contract test if that file is already the version-contract home.

2. Test contract:
   - Load schema into a test DB.
   - Allocate `v1` and commit the sequence allocation without creating `ScheduleHistory`.
   - Allocate `v2` and create `ScheduleHistory` for `v2`.
   - Assert:
     - `v2 == v1 + 1`;
     - no `ScheduleHistory` exists for `v1`;
     - `ScheduleHistoryRepository.get_latest_version()` returns `v2`;
     - a third allocation returns `v3`, not `v1`.

3. Add a small documentation note near the test or in the technical-debt closeout note explaining:
   - version gaps are intentional after an allocation has committed;
   - the invariant is **monotonic non-reuse**, not contiguous version numbers;
   - invalid or empty scheduler results still fail before allocation, already covered by `tests/regression_schedule_orchestrator_contract.py:114-162` and `tests/regression_schedule_orchestrator_contract.py:316-379`.

4. Do not change `orchestrate_schedule_run()` transaction boundaries unless the new test reveals that current behavior contradicts the documented invariant.

### 3.3.3 Validation commands

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/regression_schedule_orchestrator_contract.py \
  tests/regression_schedule_history_version_gap_contract.py
```

If the new test is placed in the existing file, adjust the second path accordingly.

### 3.3.4 Exit signal

- Contract test proves gaps are allowed and versions are not reused.
- No persistence transaction boundary changed.
- No new catch-all or logger-swallowing branch added.

### 3.3.5 Rollback

- Revert the new test/documentation note only.
- No production rollback should be needed if this step remains contract-proof only.

## Step 4 — Refactor `web/routes/process_excel_routes.py::excel_routes_confirm`

### 3.4.1 Current responsibility slices

`excel_routes_confirm()` at `web/routes/process_excel_routes.py:215-380` currently includes these slices:

1. Request and payload loading
   - `start`, `mode`, `strict_mode`, `filename`, `payload`, `rows`: `web/routes/process_excel_routes.py:217-224`.

2. Current-state and stale-baseline validation
   - `part_svc`, `existing`, `preview_baseline_is_stale(...)`: `web/routes/process_excel_routes.py:226-245`.
   - Must preserve rejection message exactly:
     - `导入被拒绝：数据已变化，请重新上传 Excel 并检查后再确认写入。`

3. Preview rebuild and error-row return
   - inline `validate_row`: `web/routes/process_excel_routes.py:247`.
   - `ExcelService.preview_import(...)`: `web/routes/process_excel_routes.py:249-256`.
   - `collect_error_rows()` and render-return: `web/routes/process_excel_routes.py:258-269`.

4. Transactional apply loop
   - transaction and counters: `web/routes/process_excel_routes.py:271-277`.
   - replace-mode batch guard: `web/routes/process_excel_routes.py:278-284`.
   - status handling and skip logic: `web/routes/process_excel_routes.py:286-313`.
   - `part_svc.upsert_and_parse_no_tx(...)`: `web/routes/process_excel_routes.py:314-321`.
   - route warning aggregation: `web/routes/process_excel_routes.py:322-330`.
   - `AppError` row-level accumulation: `web/routes/process_excel_routes.py:335-346`.

5. Result, audit, flash, redirect
   - result dict and `log_excel_import(...)`: `web/routes/process_excel_routes.py:348-365`.
   - `extract_import_stats()` and `flash_import_result(...)`: `web/routes/process_excel_routes.py:366-374`.
   - route warning flash text: `web/routes/process_excel_routes.py:375-379`.
   - final redirect: `web/routes/process_excel_routes.py:380`.

Existing guard coverage:

- `tests/regression_process_excel_routes_extra_state_guard.py:64-103`
  - helper flow for preview/confirm.
- `tests/regression_process_excel_routes_extra_state_guard.py:194-227`
  - strict-mode / op-type / supplier drift re-preview guards.
- `tests/regression_excel_preview_confirm_baseline_guard.py:150-163`
  - stale baseline rejection message style for another Excel route.

### 3.4.2 Implementation strategy

Refactor by extraction only. Do not change route semantics.

#### Extraction A — shared row sample helpers

Add small helpers near route-import helpers:

- `_preview_row_location(pr: ImportPreviewRow) -> Dict[str, Any]`
  - returns `row`, `source_row_num`, `source_sheet_name`.
- `_append_error_sample(errors_sample: List[Dict[str, Any]], pr: ImportPreviewRow, message: str, *, limit: int = 10) -> None`
  - one length guard, no exception handling.
- `_append_route_warning_sample(route_warnings_sample: List[Dict[str, Any]], pr: ImportPreviewRow, warning: Any, *, limit: int = 5) -> bool`
  - returns whether a visible sample was added if needed; alternatively keep total counting in caller.

Keep helpers dumb and deterministic. They must not catch or normalize unexpected failures.

#### Extraction B — preview rebuild helper

Add:

```python
def _preview_excel_route_rows(
    *,
    part_svc: PartService,
    rows: List[Dict[str, Any]],
    existing: Dict[str, Dict[str, Any]],
    mode: ImportMode,
    strict_mode: bool,
) -> List[Any]:
    def validate_row(row: Dict[str, Any]) -> Optional[str]:
        return _validate_route_row(part_svc, row, strict_mode=strict_mode)
    excel_svc = ExcelService(backend=get_excel_backend(), logger=None, op_logger=getattr(g, "op_logger", None))
    return excel_svc.preview_import(...)
```

Use it from both `excel_routes_preview()` and `excel_routes_confirm()` if the change remains concise. If sharing with preview route causes awkward `g` coupling, keep the helper local to confirm in the first patch and extract preview later.

#### Extraction C — stale baseline render helper

Add one explicit render helper for the stale-baseline rejection path, for example:

```python
def _render_routes_confirm_rejected(...):
    flash("导入被拒绝：数据已变化，请重新上传 Excel 并检查后再确认写入。", "error")
    return _render_excel_routes_page(...)
```

Do not introduce a generic “safe render fallback”. This helper is only for the existing stale-baseline contract.

#### Extraction D — transactional apply helper

Move the transaction and loop into a single helper such as:

```python
@dataclass
class RouteImportApplyResult:
    total_rows: int
    new_count: int
    update_count: int
    skip_count: int
    error_count: int
    errors_sample: List[Dict[str, Any]]
    route_warnings_sample: List[Dict[str, Any]]
    route_warning_total: int


def _apply_excel_route_preview_rows(
    *,
    part_svc: PartService,
    preview_rows: List[Any],
    mode: ImportMode,
    strict_mode: bool,
    existing: Dict[str, Dict[str, Any]],
) -> RouteImportApplyResult:
    ...
```

Keep the existing semantics exactly:

- `ImportMode.REPLACE` still checks `BatchQueryService(g.db).has_any()` before `part_svc.delete_all_no_tx()`.
- `RowStatus.ERROR` increments `error_count` and samples the visible message.
- `RowStatus.SKIP` increments `skip_count`.
- `RowStatus.UNCHANGED` increments `skip_count` unless replace mode currently treats it differently.
- `ImportMode.APPEND and pn in existing` still skips.
- `part_svc.upsert_and_parse_no_tx(...)` receives the same `part_no`, `part_name`, `route_raw`, `strict_mode`.
- Only `AppError` remains a row-level visible error in the apply loop.
- Unexpected exceptions still propagate out of the transaction.

#### Extraction E — final flash helper

Add a small finalizer:

```python
def _flash_route_import_outcome(result: RouteImportApplyResult) -> None:
    flash_import_result(...)
    if result.route_warnings_sample:
        ... existing warning text exactly ...
```

Preserve this warning text exactly unless a separate UX issue approves changing it:

`导入完成，但有些工艺路线先按临时规则处理：{warning_text}。请补齐资料后重新导入，或让系统重新检查工艺路线。`

### 3.4.3 Target final shape

After refactor, `excel_routes_confirm()` should read approximately as orchestration:

```python
def excel_routes_confirm():
    start = time.time()
    mode = _parse_mode(...)
    strict_mode = form_toggle_bool(...)
    filename = ...
    payload = load_confirm_payload(...)
    rows = payload.rows
    _ensure_unique_ids(rows, id_column="图号")

    part_svc = PartService(...)
    existing = part_svc.build_existing_for_excel_routes()
    if preview_baseline_is_stale(...):
        return _render_routes_confirm_rejected(...)

    preview_rows = _preview_excel_route_rows(...)
    error_rows = collect_error_rows(preview_rows)
    if error_rows:
        return _render_routes_confirm_errors(...)

    result = _apply_excel_route_preview_rows(...)
    _log_route_import_result(...)
    _flash_route_import_outcome(result)
    return redirect(url_for("process.excel_routes_page"))
```

The only `if` statements left in the route should be the real domain branches already present: stale baseline and preview error rows.

### 3.4.4 Validation commands

Run after each extraction chunk:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/regression_process_excel_routes_extra_state_guard.py \
  tests/regression_excel_preview_confirm_baseline_guard.py \
  tests/regression_excel_failure_semantics_contracts.py \
  tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py
```

Then run a syntax/static pass on touched files:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check web/routes/process_excel_routes.py tests/regression_process_excel_routes_extra_state_guard.py
```

### 3.4.5 Exit signal

- Route behavior tests pass.
- `excel_routes_confirm()` is short orchestration rather than a transaction-heavy route body.
- Strict-mode, stale-baseline, replace-mode guard, row-level `AppError`, audit logging, and warning flash behavior remain unchanged.

### 3.4.6 Rollback

- Revert `web/routes/process_excel_routes.py` and any test-only change from this step.
- Because helper extraction is behavior-equivalent, rollback should not require DB migration or data cleanup.

## Step 5 — Refactor operator-machine import and readside normalization

### 3.5.1 Current evidence chain

Write/import chain:

- `core/services/personnel/operator_machine_service.py:137-159`
  - preview parsing converts only `ValidationError` into row-level preview errors.
- `core/services/personnel/operator_machine_service.py:255-277`
  - `_resolve_write_values()` converts only `ValidationError` into a row-level write error string; unexpected errors propagate.
- `core/services/personnel/operator_machine_service.py:370-406`
  - `preview_import_links()` builds preview rows and enforces primary uniqueness.
- `core/services/personnel/operator_machine_service.py:408-504`
  - `apply_import_links()` performs counters, error samples, identity checks, write-value resolution, add/update/skip, and result dict assembly.

Readside normalization chain:

- `core/services/personnel/operator_machine_query_service.py:25-67`
  - `_normalize_row()` normalizes `skill_level` and `is_primary` and records `dirty_fields` / `dirty_reasons`.

Existing tests prove non-swallowing behavior:

- `tests/test_operator_machine_exception_paths.py:39-65`
  - skill-level normalizer unexpected errors propagate.
- `tests/test_operator_machine_exception_paths.py:68-79`
  - readside normalization unexpected errors propagate through `list_by_operator()`.
- `tests/test_operator_machine_exception_paths.py:82-111`
  - preview optional parsing converts validation errors but propagates unexpected errors.
- `tests/test_operator_machine_exception_paths.py:116-144`
  - write-value resolution converts validation errors but propagates unexpected errors.
- `tests/test_operator_machine_exception_paths.py:148-158`
  - query service only handles `ValueError` as legacy dirty data and propagates unexpected errors.
- `tests/test_query_services.py:177-185`, `tests/test_query_services.py:198-218`, and `tests/test_query_services.py:247-255`
  - normalized values and dirty markers are visible.
- `tests/regression_excel_failure_semantics_contracts.py:214-227`
  - `OperatorMachineService.apply_import_links()` counts invalid row write values as row-level errors and does not write them.
- `tests/test_operator_machine_excel_route_error_handling.py:43-100`
  - internal runtime errors are hidden from user HTML by the app error boundary, not swallowed by the service.

### 3.5.2 `apply_import_links()` implementation strategy

Refactor in two small chunks.

#### Chunk A — error-sample extraction

Add:

```python
def _append_import_error_sample(
    errors_sample: List[Dict[str, Any]],
    pr: ImportPreviewRow,
    message: str,
    *,
    limit: int = 10,
) -> None:
    if len(errors_sample) >= limit:
        return
    errors_sample.append({...})
```

This introduces one existing limit guard but removes repeated dict construction. It must not catch exceptions.

Use it for:

- `RowStatus.ERROR` branch at `core/services/personnel/operator_machine_service.py:423-435`.
- missing `工号/设备编号` branch at `core/services/personnel/operator_machine_service.py:445-458`.
- `_resolve_write_values()` error branch at `core/services/personnel/operator_machine_service.py:463-477`.

#### Chunk B — write-row extraction

Add a helper that assumes a preview row has already passed status and identity validation:

```python
def _apply_import_link_write(
    self,
    *,
    op_id: str,
    mc_id: str,
    new_skill: str,
    new_primary: str,
    mode: ImportMode,
    existing_map: Dict[str, Dict[str, str]],
) -> str:
    key = f"{op_id}|{mc_id}"
    if self.repo.exists(op_id, mc_id):
        if mode == ImportMode.APPEND:
            return "skip"
        if new_primary == YesNo.YES.value:
            self.repo.clear_primary_for_operator(op_id)
        self.repo.update_fields(op_id, mc_id, skill_level=new_skill, is_primary=new_primary)
        existing_map[key] = {"skill_level": new_skill, "is_primary": new_primary}
        return "update"
    if new_primary == YesNo.YES.value:
        self.repo.clear_primary_for_operator(op_id)
    self.repo.add(op_id, mc_id, skill_level=new_skill, is_primary=new_primary)
    existing_map[key] = {"skill_level": new_skill, "is_primary": new_primary}
    return "new"
```

Then `apply_import_links()` only maps the returned action into counters.

Important: do not catch repository exceptions here. If `repo.add()` or `repo.update_fields()` fails, the transaction must fail visibly.

### 3.5.3 `_normalize_row()` implementation strategy

Extract field-specific pure helpers while preserving `ValueError`-only legacy dirty handling.

Recommended structure:

```python
def _mark_dirty(dirty_fields: List[str], dirty_reasons: Dict[str, str], field: str, reason: str) -> None:
    ... existing logic ...


def _normalize_skill_field(out: Dict[str, Any], dirty_fields: List[str], dirty_reasons: Dict[str, str]) -> None:
    raw_skill = out.get("skill_level")
    raw_skill_text = "" if raw_skill is None else str(raw_skill).strip()
    try:
        out["skill_level"] = normalize_skill_level(...)
    except ValueError:
        ... existing dirty message ...
    else:
        ... existing old-writing dirty message ...


def _normalize_primary_field(out: Dict[str, Any], dirty_fields: List[str], dirty_reasons: Dict[str, str]) -> None:
    ... existing behavior ...
```

Then `_normalize_row()` becomes:

```python
out = dict(r or {})
dirty_fields = []
dirty_reasons = {}
if "skill_level" in out:
    _normalize_skill_field(out, dirty_fields, dirty_reasons)
if "is_primary" in out:
    _normalize_primary_field(out, dirty_fields, dirty_reasons)
if dirty_fields:
    out["dirty_fields"] = list(dirty_fields)
    out["dirty_reasons"] = dict(dirty_reasons)
return out
```

This keeps the two real field-presence branches and removes nested bookkeeping noise. It does not add fallback behavior.

### 3.5.4 Validation commands

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_operator_machine_exception_paths.py \
  tests/test_operator_machine_excel_route_error_handling.py \
  tests/test_query_services.py \
  tests/regression_excel_failure_semantics_contracts.py \
  tests/regression_operator_machine_dirty_flags_visible.py \
  tests/regression_operator_machine_missing_columns.py \
  tests/regression_operator_machine_detail_readside_normalization.py
```

Then:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check \
  core/services/personnel/operator_machine_service.py \
  core/services/personnel/operator_machine_query_service.py \
  tests/test_operator_machine_exception_paths.py
```

### 3.5.5 Exit signal

- Existing exception-path tests still prove unexpected errors propagate.
- Existing dirty-field tests still prove legacy DB normalization remains visible.
- `apply_import_links()` remains explicit about row-level validation but no longer owns repetitive dict construction and write branching.

### 3.5.6 Rollback

- Revert `core/services/personnel/operator_machine_service.py` and `core/services/personnel/operator_machine_query_service.py`.
- No schema or data migration is involved.

## Step 6 — PR8 clean-worktree QualityGate proof

### 3.6.1 Current evidence chain

- `.codestable/features/2026-05-20-scheduler-graph-resource-matching-report/scheduler-graph-resource-matching-report-acceptance.md:89-93`
  - current acceptance explicitly says final clean-worktree quality gate proof is still pending.

### 3.6.2 Preconditions

Run this only after:

1. Steps 1-5 are complete or explicitly deferred.
2. All intended code and documentation changes are committed or the run is performed in a clean checkout.
3. `git status --short` is empty.
4. The environment has all gate dependencies, including `radon`; if not, stop with an explicit blocker.

### 3.6.3 Command

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

### 3.6.4 Evidence update

Only after the command succeeds:

- Update the relevant acceptance / audit closeout note with:
  - command;
  - timestamp;
  - exit status;
  - output summary;
  - clean `git status --short` evidence.

Do not update `.codestable/features/2026-05-20-scheduler-graph-resource-matching-report/scheduler-graph-resource-matching-report-acceptance.md:89-93` to “resolved” until the run has actually succeeded on a clean worktree.

### 3.6.5 Rollback

- If the gate fails, keep the failure evidence and record the blocker.
- Do not mark PR8 resolved.

## 4. Cross-step verification matrix

| Step | Primary files | Targeted tests | No-silent-fallback proof |
|---|---|---|---|
| 1 PR7E closeout | `.limcode/review/pr7e-uncommitted-changes-review.md` | `tests/regression_scheduler_candidate_runner_contract.py`, `tests/regression_scheduler_candidate_persistence_contract.py`, `tests/regression_scheduler_candidate_analysis_contract.py` | Review status changes only after code/tests prove fields exist and errors propagate. |
| 2 Week-plan redirect | `web/routes/domains/scheduler/scheduler_week_plan.py` | `tests/regression_week_plan_filename_uses_normalized_version.py`, `tests/regression_scheduler_candidate_week_plan_contract.py`, `tests/regression_scheduler_week_plan_summary_observability.py` | Existing generic error branch remains visible; only redirect query context is preserved. |
| 3 Version gap contract | `data/repositories/schedule_history_repo.py`, `core/services/scheduler/run/schedule_orchestrator.py` tests/docs only | `tests/regression_schedule_orchestrator_contract.py`, new version-gap contract test | Test proves explicit monotonic non-reuse; no transaction-boundary fallback added. |
| 4 Route import refactor | `web/routes/process_excel_routes.py` | route extra-state, preview-baseline, failure semantics, strict route-parser tests | Only `AppError` remains row-level; unexpected errors propagate. |
| 5 Operator-machine refactor | `core/services/personnel/operator_machine_service.py`, `core/services/personnel/operator_machine_query_service.py` | exception paths, query services, Excel failure semantics, dirty flags | Existing tests prove unexpected normalizer/runtime errors are not swallowed. |
| 6 PR8 proof | acceptance/audit docs only after command succeeds | `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` | Gate itself enforces clean worktree; no proof is claimed on failure. |

## 5. Final implementation checklist

- [ ] Step 1 PR7E tests pass and review findings are closed only with evidence.
- [ ] Step 2 week-plan export failure redirect preserves `week_start / offset / version / plan_role`.
- [ ] Step 3 version-gap contract test proves allowed gaps and non-reuse.
- [ ] Step 4 `excel_routes_confirm()` is orchestration-only and route import regressions pass.
- [ ] Step 5 operator-machine import/readside helpers are extracted and exception-path tests pass.
- [ ] Step 6 clean-worktree quality gate succeeds before PR8 proof is claimed.
- [ ] No new `except Exception` blocks were added.
- [ ] No new silent defaulting or swallowed error path was added.
- [ ] No Win7 / launcher accepted-risk item was included in implementation.
