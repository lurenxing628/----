# KEEP_TRIM Spec — Batch B05_frontend_c

Branch: `cleanup/p3-main-style-to-pytest`
Authored from current file content (line numbers re-mapped from the TSV reason, not trusted verbatim).
Source TSV: `.codestable/refactors/2026-06-01-test-gate-cleanup/p5_specs/keep_trim_files.tsv`

## Batch-wide findings (read first)

- **NO `test_` function is deleted anywhere in this batch.** All trims are (a) assert-line removals inside kept functions, or (b) deletion of the non-test `main()` / `find_repo_root()` helpers in the two `run_*` evidence scripts.
- **Registry/debt coupling: NONE.** All 85 `test_` function names across the batch were grepped against `tools/` — zero hits. The two `run_*` files are referenced by `tests/regression_gantt_critical_outline_sync.py` but only for their reusable helpers (see below), never by `tools/test_registry_data.py` / `tools/test_debt_registry.py`.
- **CRITICAL cross-file dependency (run_complex_case_and_export_gantt.py):** `tests/regression_gantt_critical_outline_sync.py` loads this module by path via `importlib.util.spec_from_file_location(...)` + `exec_module` and calls BOTH `build_preview_client_bootstrap(...)` (line 712, 1160, 1338, 1517, 1847) AND `module._write_html(...)` (lines 1667, 1973). **Both helpers MUST be kept verbatim.** `exec_module` runs the module top-level but NOT `main()` (module name is `run_complex_case_and_export_gantt`, not `__main__`), so deleting `main()` is safe. Keep ALL top-level imports to avoid breaking the kept helpers.

---

## 1. tests/regression_scheduler_candidate_week_plan_contract.py  (278 lines)

TSV reason (mid): keep `_plan_context_from_data` resolution + Excel cells/DB-log filter checks; brittle = exact Chinese copy + `&amp;` URL fragments in HTML snapshot tail.

### KEEP (real contract)
- `test_week_plan_fallback_context_uses_common_plan_resolution_fields` (L162-173) — pure resolution-dict contract, no HTML. KEEP whole.
- `test_week_plan_context_keeps_existing_plan_resolution_dict` (L176-196) — dict passthrough invariant. KEEP whole.
- `test_week_plan_export_uses_same_plan_role_and_logs_requested_effective_roles` (L235-278) — Excel sheetnames + cell values that encode candidate-row data selection, plus OperationLogs `filters` contract (version / requested_plan_role / effective_plan_role / plan_role_status / candidate_key) and Content-Disposition role name. These are real behavioral selectors, NOT layout snapshots. KEEP whole, including `sheet["A2"]/["E2"]/["F2"]` (they assert candidate-row data flowed through, not cell geometry).

### TRIM (brittle, assert-line removals inside kept functions)

**Item 1.1** — in `test_week_plan_page_uses_candidate_rows_and_export_url_preserves_plan_role` (currently L199-218). KEEP the function and KEEP the structural/behavioral asserts (status 200, `name="plan_role"`, `候选设备`/`候选人员` presence proving candidate rows rendered, `plan_role=baseline_best` present, and the `... not in html` negative guard). TRIM the two exact full-sentence Chinese copy snapshots:

  - Delete line (anchor, verbatim):
    ```
        assert "当前查看的是“原算法代表方案”" in html
    ```
  - Delete line (anchor, verbatim):
    ```
        assert "这是一套对比参考方案" in html
    ```
  Why brittle: these are exact full-sentence UI copy with no stable key/code; the plan_role contract is already anchored by `plan_role=baseline_best` and the `&amp;plan_role=` URL asserts which remain. Keep-context: leave `assert "当前周计划正在预览" not in html` (negative behavioral guard — it asserts the scenario-preview banner is absent for a comparison plan; keep).
  Conservative note: the `&amp;` URL-fragment asserts (L211-215) read as brittle to the TSV author, but they encode a real contract (plan_role is preserved through every nav link AND the HTML-escaping of `&` is the actual route behavior). KEEP all five `&amp;` URL asserts.

**Item 1.2** — in `test_week_plan_missing_valid_plan_role_page_only_shows_fallback_notice` (currently L221-232). This function's entire body is exact-copy snapshots; but it carries a real fallback-vs-comparison behavioral distinction. KEEP the function. Trim ONE pure-decorative exact sentence, KEEP the differential pair:
  - Delete line (anchor, verbatim):
    ```
        assert "你原本选择的是“重点工序优先代表方案”" in html
    ```
  KEEP `assert "已显示正式采用方案" in html` (the load-bearing fallback signal) and KEEP both negative guards `assert "这套结果只用来对照查看" not in html` / `assert "这是一套对比参考方案" not in html` (they assert fallback notice is shown but comparison notice is NOT — a real branch outcome). Keep status-200 assert.
  Why brittle (only the deleted line): the requested-role echo sentence is exact copy; the fallback behavior is already proven by the kept positive + two negatives.

Risk: low. est net lines removed: **3**.

---

## 2. tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py  (415 lines)

TSV reason (high): real route invalid-query redirect/sanitization + fail-closed 404 + HTTP error mapping 400/500 + `_resolve_version` logic; brittle = L27-32 greps template/js bundle as snippet tail.

### KEEP (real contract — the bulk of this file)
- `test_resource_dispatch_invalid_queries_redirect_to_clean_url` (L121-182) — 302 + query-key cleanup table. KEEP whole.
- `test_resource_dispatch_missing_history_version_fails_closed_without_query_cleanup` (L185-205) — 404 fail-closed + no cleanup keys. KEEP whole (the one Chinese string `排产版本不存在，请先选择已有版本。` is a user-facing guarantee with no error code on the page; it is the only anchor for the fail-closed page body and recurs on 3 endpoints — KEEP per the "exact string IS the contract" rule).
- `test_resource_dispatch_data_returns_machine_field_and_invalid_query_keys` (L235-281) — ordered key/label lists encode a sanitization RULE (ordering is the contract), KEEP whole.
- `test_resource_dispatch_data_uses_app_error_http_mapping` (L284-300) / `..._unexpected_error_uses_unified_unknown_error_contract` (L303-319) — ErrorCode + HTTP status mapping. KEEP whole.
- `test_resource_dispatch_export_redirects_to_sanitized_page_url` (L322-335). KEEP whole.
- `test_resource_dispatch_service_validation_errors_use_machine_field_keys` (L338-347), `..._version_latest_contract...` (L350-369), `..._no_history_latest_returns_empty_zero_version` (L372-405), `..._range_validation_errors...` (L408-415) — pure algorithm/branch logic. KEEP whole.
- `test_resource_dispatch_mixed_invalid_filters_settle_without_500` (L219-233) — KEEP. The `资源排班` + `id="rdPage"` asserts prove the page settled (no 500) and the `查询日期填写不正确，请检查后重试。` is the user-facing message contract with the negative guard `query_date格式不正确 not in html` (proves internal jargon is not leaked). KEEP all (behavioral: fail-soft + no-leak).

### TRIM (brittle)

**Item 2.1** — DELETE the entire body asserts of `test_resource_dispatch_page_renders_generic_degradation_channel` (currently L28-34) — js-source / template-source grep snapshot. BUT this is the whole function being brittle. Per granularity rule (a) we cannot leave a kept function with zero asserts. Decision: **KEEP the function, TRIM only the two js_source greps, KEEP the one template-source id assert** so a meaningful structural anchor remains.
  - KEEP: `template_source = _read("templates/scheduler/resource_dispatch.html")` and `assert 'id="rdDegradationSummary"' in template_source` (a stable element-id contract — the degradation channel exists).
  - Delete line (anchor, verbatim):
    ```
        assert "summary.degradation_events" in js_source
    ```
  - Delete line (anchor, verbatim):
    ```
        assert "rdDegradationSummary" in js_source
    ```
  - Delete line (anchor, verbatim) — the now-unused js bundle read:
    ```
        js_source = read_resource_dispatch_script_bundle()
    ```
  Why brittle: `assert "<jsfn>(" in js_source` / reading the JS bundle as text breaks on any cosmetic JS refactor (rename, minify) without a behavior bug; the channel's existence is anchored by the kept `id="rdDegradationSummary"` template assert.
  Import-safety note: after removing the `js_source` read, the import `from tests.resource_dispatch_frontend_support import read_resource_dispatch_script_bundle` (L19) becomes unused **in this file**. The implementation agent SHOULD delete that import line too (anchor: `from tests.resource_dispatch_frontend_support import read_resource_dispatch_script_bundle`). The support module itself stays (it may be used elsewhere — do NOT delete the module).

Risk: low. est net lines removed: **4** (3 asserts/reads in-function + 1 now-dead import).

---

## 3. tests/regression_scheduler_week_plan_summary_observability.py  (515 lines)

TSV reason (high): core `build_summary_display_state` status-precedence / simulated / warning-pipeline logic is high value; trim HTML-copy render tests (snapshot tail).

### KEEP (real contract — the entire viewmodel/route logic core)
- `test_week_plan_prefers_week_start_and_drops_stale_start_end` (L125-147) — call-arg capture + export_url query rule. KEEP whole.
- `test_week_plan_route_exposes_selected_summary_display` (L212-247) — exact dict-shape contract of `selected_summary_display` (completion_status, result_state dict, primary_degradation details, counts). KEEP whole (these are structural payload invariants, not page copy).
- `test_week_plan_route_marks_selected_summary_parse_failure` (L272-282) — parse_failed flag. KEEP.
- All `test_build_summary_display_state_*` (L285-436) — pure algorithm: simulated raw-status preservation, completion-status precedence, warning-pipeline display dicts. KEEP every one whole; these are the load-bearing R-line oracle for the summary-display refactor.
- `test_week_plan_route_surfaces_missing_history_but_keeps_preview_rows` (L439-468) — missing-history branch + preview-row retention. KEEP whole.

### TRIM (brittle — rendered-HTML copy snapshots)

**Item 3.1** — in `test_week_plan_page_hides_zero_warning_preview_button` (currently L250-269). This function mixes a real behavioral guard (sqlite path / internal diagnostic must NOT leak to page) with exact-copy snapshots. KEEP the function. KEEP status-200, KEEP the security/no-leak negatives `assert "sqlite" not in html` and `assert "/system/history?version=3" not in html` and `assert "去排产历史查看" not in html`. TRIM the exact-copy count-string snapshots that are pure cosmetic phrasing:
  - Delete line (anchor): `    assert "提醒：1 条" not in html`
  - Delete line (anchor): `    assert "维护诊断：1 条" in html`
  - Delete line (anchor): `    assert "查看前 0 条提醒" not in html`
  - Delete line (anchor): `    assert "另有 1 条提醒" not in html`
  - Delete line (anchor): `    assert "当前页没有可安全展开的提醒明细" not in html`
  Why brittle: these are exact Chinese count-phrasing strings; the underlying behavior (zero-warning button hidden; internal diagnostics not leaked) is preserved by the kept `sqlite`/`/system/history` negative guards.
  Conservative call: KEEP `维护诊断：1 条`? It is the one POSITIVE assert proving the maintenance-diagnostic channel still renders. To avoid leaving only negatives, KEEP `assert "维护诊断：1 条" in html` and remove it from the delete list. **Final delete set for 3.1: the 4 `not in html` copy lines only** (`提醒：1 条`, `查看前 0 条提醒`, `另有 1 条提醒`, `当前页没有可安全展开的提醒明细`). Keep `维护诊断：1 条`, keep `sqlite`/`/system/history`/`去排产历史查看` negatives.

**Item 3.2** — in `test_week_plan_page_renders_warning_pipeline_guard_html` (currently L471-497). This RE-renders, via full page, the same warning-pipeline dict already contract-tested at the viewmodel level by `test_build_summary_display_state_exposes_warning_pipeline_display` (L387-415). The page-copy asserts are a snapshot tail. KEEP the function shell but reduce to the load-bearing security guard + one presence anchor:
  - KEEP: status-200, and KEEP `assert "summary_warnings_assignment_failed" not in html` (real no-leak guard: internal error key must not reach the page).
  - KEEP one presence anchor: `assert "排产提醒整理状态：未完整整理" in html` (proves the guard banner renders at all).
  - Delete line (anchor): `    assert "排产提醒：2 条" in html`
  - Delete line (anchor): `    assert "结果提醒：0 条" in html`
  - Delete line (anchor): `    assert "部分排产提示没有完整写入历史摘要。" in html`
  Why brittle: the count phrasing and the note sentence are exact copy already asserted as a dict in 3's viewmodel test; rendering-layer re-snapshot adds cosmetic fragility. Keep the no-leak negative (security) + one banner-presence positive.

**Item 3.3** — in `test_week_plan_page_renders_simulated_completion_status_label` (currently L500-515). The label `模拟排产 / 部分成功` is already contract-tested as `result_status_label` in `test_build_summary_display_state_prefers_persisted_completion_status_for_simulated` (L311-331). The page test is a render snapshot. KEEP the function with status-200 + ONE label anchor; trim the redundant second snapshot:
  - KEEP: status-200, KEEP `assert "模拟排产 / 部分成功" in html` (one label presence anchor proving the viewmodel label reaches the page).
  - Delete line (anchor): `    assert "v3 · 部分成功" in html`
  Why brittle: `v3 · 部分成功` is an exact composed display string (version + label join) that drifts on any formatting tweak; the label semantics are anchored by the kept line + the viewmodel test.

Risk: mid (this is a high-value file; trims are confined to render-layer copy that is double-covered at the viewmodel layer — explicitly cross-referenced above). Never leave a function assertion-empty: each touched function retains status-200 + at least one positive presence anchor + security negatives. est net lines removed: **9** (4 + 3 + 1, plus 1 conservatively kept back).

---

## 4. tests/regression_ui_contract_component_tokens.py  (270 lines)

TSV reason (mid): L135-178 actually render Jinja macros asserting a11y role/aria-live + hidden-value + summary presenter (real); trim CSS-token / source-grep snapshots.

### KEEP (real, rendered behavior)
- `test_notice_macro_defaults_to_static_message_and_allows_explicit_live_role` (L139-158) — RENDERS the macro and asserts a11y `role`/`aria-live` injection behavior. KEEP whole.
- `test_toggle_object_keeps_disabled_checked_hidden_value_safe` (L161-166) — rendered hidden-value safety. KEEP whole.
- `test_business_templates_do_not_call_low_level_toggle_row_macro_directly` (L168-176) — architectural boundary guard (no business template calls internal macro). KEEP whole.
- `test_summary_item_legacy_macro_still_shows_dash_for_old_pages` (L179-182) / `test_summary_grid_uses_presenter_items_without_legacy_fallback` (L185-193) — rendered presenter behavior. KEEP whole.

### TRIM / conservative-KEEP (source-text greps & token snapshots)

**Item 4.1** — `test_ui_contract_declares_semantic_tokens_and_components` (L63-97): asserts a long literal list of `--ui-*` CSS variable names and `.aps-*` selectors exist as substrings in `static/css/ui_contract.css`. This is a **CSS-token / member-LIST snapshot** (brittle per spec). HOWEVER it is the ONLY guard that these design tokens/selectors exist at all — deleting it removes the entire contract. Per "if the list IS the contract, KEEP" and meta-gate caution: **KEEP whole, mark conservative.** Do NOT pixel/geometry literals appear here (no `320px` etc.) — it's name-presence, which is closer to a structural-invariant than a cosmetic pixel snapshot. KEEP.

**Item 4.2** — `test_ui_macros_expose_shared_contract_components` (L100-136): reads `ui_macros.html` as text and asserts `macro X(` definitions exist + inspects macro-internal Jinja source (`role=''`, `{% if role %}...`, checkbox-before-hidden index, `submitted_value`). This is **source-text grep** (brittle). But it encodes the same a11y/ordering contract that the RENDERED test 4-KEEP (`test_notice_macro_defaults...`, `test_toggle_object...`) already verifies behaviorally. The macro-presence list (`notice`/`details_notice`/`empty_state`/`summary_grid`/`toggle`/`_toggle_row_internal`) is a member-list snapshot.
  - Decision: **conservative partial trim.** KEEP the macro-existence loop (L103-111) — it is the structural "these macros exist" contract and is cheap/stable. TRIM the source-internals greps that re-assert behavior already covered by the rendered tests:
    - Delete block (anchor, the notice-internals inspection, verbatim contiguous lines):
      ```
          notice_start = source.index("{% macro notice(")
          notice_block = source[notice_start : source.index("{% endmacro %}", notice_start)]
          assert "role=''" in notice_block
          assert "aria_live=''" in notice_block
          assert "{% if role %} role=\"{{ role }}\"{% endif %}" in notice_block
          assert "{% if aria_live %} aria-live=\"{{ aria_live }}\"{% endif %}" in notice_block
          assert "role='status'" not in notice_block
          assert "aria_live='polite'" not in notice_block
      ```
      Why brittle: inspects raw Jinja source text; identical behavior is asserted by the rendered `test_notice_macro_defaults_to_static_message_and_allows_explicit_live_role` (KEEP). Removing the source-grep does not reduce real coverage.
  - **KEEP** the toggle-internals block (L122-131) and summary_grid block (L133-136): the checkbox-before-hidden ORDERING and `_summary_item_presenter(item)` vs `summary_item(` are partly structural and the rendered tests do NOT fully assert source ordering. Conservative KEEP to avoid over-trim.
  Net: delete the 8-line notice-internals block only.

**Item 4.3** — `test_presenterized_pages_do_not_bypass_summary_item_values` (L196-221) and `test_business_toggle_routes_use_order_independent_form_parsers` (L223-270): these grep Python route source and template source for hardcoded marker strings / call-site lists. They are **source-grep + hardcoded member-list snapshots** (brittle category). BUT they are the only enforcement that presenter migration was done across each named page/route (an architectural ratchet). Deleting them silently re-permits the regressions they were written to catch.
  - Decision: **KEEP both, mark conservative (mid risk if trimmed).** Per meta-gate caution — these are migration ratchets; trimming reduces enforcement. Do NOT trim.

Risk: mid (file is partly a quality/architecture gate). Only the notice-source-internals block is trimmed (double-covered by a rendered test). est net lines removed: **8**.

---

## 5. tests/regression_week_plan_filename_uses_normalized_version.py  (197 lines)

TSV reason (high): version normalize default/latest->v7 + invalid->400, export filename, week_start-only call-args, export-fail redirect preserves ctx without leaking error; trim HTML class/copy asserts.

### KEEP (real contract)
- `test_week_plan_no_history_page_empty_and_export_404` (L102-115) — empty-state + 404 + `暂无排产历史` (user-facing guarantee, the only anchor). KEEP whole.
- `test_week_plan_export_uses_week_start_only_when_stale_range_present` (L118-165) — call-arg capture (`calls == [{...}]`) + filename + Excel `A2`/`B2` data cells (prove week_start-only data flowed). KEEP whole.
- `test_week_plan_export_failure_redirect_preserves_request_context` (L168-197) — 302 + preserved query context + error-message NOT leaked into Location. KEEP whole (security/no-leak + behavior).

### TRIM (brittle — HTML class/label copy snapshots)

**Item 5.1** — in `test_week_plan_filename_uses_normalized_version` (currently L57-99). This function does TWO things: (a) version normalization → filename contract (REAL), (b) page-summary HTML class/label snapshots (brittle). KEEP the function; KEEP all status codes, the invalid-version 400 message (user-facing guarantee, only anchor — KEEP), and ALL filename asserts (`v7_2026-03-02至2026-03-08.xlsx`). TRIM the page-render class/label snapshots that re-prove `v7` via fragile HTML-class substrings:
  - Delete line (anchor): `    assert "所选版本摘要" in default_html`
  - Delete line (anchor): `    assert 'aps-summary-label">版本' in default_html`
  - Delete line (anchor): `    assert 'aps-summary-value">v7' in default_html`
  - Delete line (anchor): `    assert "所选版本摘要" in latest_html`
  - Delete line (anchor): `    assert 'aps-summary-label">版本' in latest_html`
  - Delete line (anchor): `    assert 'aps-summary-value">v7' in latest_html`
  Keep-context: KEEP `assert page_default.status_code == 200` / `assert page_latest.status_code == 200` (and the lines that read `default_html`/`latest_html` may become unused — see below). The normalization-to-v7 contract is fully preserved by the kept export-filename asserts `v7_...xlsx` (default + latest both normalize to v7 in the filename).
  Why brittle: `aps-summary-value">v7` is an HTML-class + value substring snapshot (cosmetic markup); the v7 normalization is the real contract and is anchored by the filename asserts.
  Import/var-safety: after removing the 6 lines, `default_html = page_default.get_data(as_text=True)` and `latest_html = page_latest.get_data(...)` become unused. The implementation agent SHOULD also delete those two now-dead assignment lines (anchors: `    default_html = page_default.get_data(as_text=True)` and `    latest_html = page_latest.get_data(as_text=True)`). KEEP the two `status_code == 200` asserts.

Risk: low (normalization contract fully retained via filename). est net lines removed: **8** (6 asserts + 2 dead assignments).

---

## 6. tests/regression_workbench_nav_entry_contract.py  (256 lines)

TSV reason (high): renders `workbench_nav_menu` macro + HTMLParser asserts read-only security boundaries (no form/script/data-*/internal-token leak) + link disabling; trim exact-label snapshots.

### KEEP (real, high-value — security boundary)
- `test_base_header_mounts_plan_workbench_menu` (L96-100) — mount + "base.html carries no copy" boundary. KEEP whole.
- `test_workbench_menu_renders_six_core_destinations` (L103-121) — anchor href list + count==7 + label-in-text. KEEP whole (href list + count encode the read-only entry-set RULE; the labels here are paired with hrefs and are the menu's structural contract — not a trimmable cosmetic tail).
- `test_workbench_menu_preserves_report_workbench_context` (L124-158) — context passthrough into link query (real). KEEP whole.
- `test_workbench_menu_disables_team_context_links_that_would_400` (L160-181) — link-disabling branch + scope rewriting. KEEP whole.
- `test_workbench_menu_disables_execution_review_for_non_formal_context` (L183-193) — `aria-disabled` + href-absence behavior. KEEP whole.
- `test_workbench_menu_is_readonly_and_hides_internal_fields` (L196-243) — **SECURITY contract**: no internal tokens (plan_role/scenario_id/candidate_id/...), no form/script/input tags, no `data-*`/`on*`/`javascript:`. KEEP entirely; do NOT touch.

### TRIM — none recommended (conservative)

The TSV reason ("trim exact-label snapshots L105-119") points at `test_workbench_menu_renders_six_core_destinations`. Re-mapping to current content: the label/href pairs there are NOT a cosmetic tail — they are the **read-only entry-set invariant** (exactly 7 entries, exact hrefs, label paired to href). The `len(parser.links) == 7` count and `anchor_hrefs == [...]` ordered list encode a security/UX rule (no extra entries can sneak in). Deleting the labels would weaken the "no rogue menu item" guard.
  - Decision: **KEEP all (no trim).** The only arguably-cosmetic asserts are the per-pair `assert label in text` (L120-121), but they bind label→href and are cheap; removing them risks letting a mislabeled entry pass. Under-trim is safe; over-trim here would erode a security-adjacent boundary.
  - `test_workbench_menu_uses_local_css_and_no_javascript_dependency` (L245-257) greps macro+css source for structural markers and a no-external-CDN guard — this is a **security guard** (no external `https://`/`cdn`/`unpkg`). KEEP whole.

Risk: high IF trimmed (security boundary). Recommendation: **do not trim this file.** est net lines removed: **0**.

---

## 7. tests/run_complex_case_and_export_gantt.py  (782 lines)

TSV reason (mid): `build_preview_client_bootstrap`/`_write_html` helpers imported by real `regression_gantt_critical_outline_sync` test (KEEP); `main()` is a demo/evidence generator writing `evidence/FullE2E` artifacts (excise demo).

This is a `main`-style script (no `test_` functions). It is loaded by `regression_gantt_critical_outline_sync.py` via `exec_module` to reuse two helpers.

### KEEP (cross-file load-bearing — verbatim)
- `build_preview_client_bootstrap(...)` (L19-407) — called by the sync test at 5 sites. KEEP verbatim.
- `_write_html(...)` (L410-502) — called by the sync test at 2 sites (`preview_module._write_html(...)`). KEEP verbatim.
- All top-level imports (L3-8: `json, os, sys, tempfile, textwrap, typing`). KEEP all — even ones that become top-level-unused after `main()` removal — to avoid any risk to the kept helpers and to the `exec_module` load. (`build_preview_client_bootstrap` uses `textwrap`; `_write_html` uses `json`, `os`.)

### DELETE (whole non-test function — demo/evidence generator)
- **`find_repo_root()` (L11-16)** — only called inside `main()`; safe to delete.
  - grep result: `grep -rn "find_repo_root" tools tests` → only self-references in this file; **NOT** used by `regression_gantt_critical_outline_sync.py` (that test computes `REPO_ROOT` itself). registry_refs_found: none.
- **`main()` (L505-779)** — builds a complex DB case, runs `run_schedule`, writes `evidence/FullE2E/*.json` and `*.html`. Pure demo/evidence; not a test, not imported.
  - grep result: `grep -rn "run_complex_case_and_export_gantt" tools tests` (exclude self) → only the two `spec_from_file_location(...)` loads in `regression_gantt_critical_outline_sync.py` (lines 706-707, 789-790), which load the MODULE for its helpers and do NOT call `main()`. `exec_module` does not trigger the `if __name__ == "__main__"` guard. registry_refs_found: none in `tools/`.
- **`if __name__ == "__main__": main()` (L781-782)** — delete along with `main()`.

Keep-context anchors:
- Delete from (anchor, verbatim start): `def find_repo_root() -> str:` through the end of `main()` and the `__main__` guard. Specifically remove the contiguous range: the `find_repo_root` def (L11-16) AND the block from `def main() -> None:` (anchor: `def main() -> None:`) through the final two lines:
  ```
  if __name__ == "__main__":
      main()
  ```
- Leave `build_preview_client_bootstrap` and `_write_html` fully intact (they sit between/after the docstring+imports and before `main()`; `find_repo_root` is BEFORE `build_preview_client_bootstrap` — deleting it does not disturb the kept helpers).
- The module docstring (L1) describes the demo; it may be left as-is (harmless) or trimmed — leave it to avoid churn.

Why brittle/excisable: `main()` writes timestamped evidence HTML/JSON to `evidence/FullE2E` — pure artifact generation with no assertions of record (only `raise RuntimeError` on empty tasks); it is run manually, never collected by pytest, never imported. Its value (the reusable bootstrap/html helpers) is retained.

Risk: mid (cross-file `exec_module` dependency — but verified `main()` is not executed on import and not referenced). est net lines removed: **~283** (find_repo_root 6 lines + main 275 lines + guard 2 lines).

---

## 8. tests/run_one_job_and_export_gantt.py  (350 lines)

TSV reason (mid): `main()`-driven full E2E (Excel preview/confirm → run_schedule → gantt data → report assertions) is real integration; trim HTML-copy report asserts + evidence-HTML writing.

This is a `main`-style script with NO `test_` functions and NO cross-file importers (grep: `run_one_job_and_export_gantt` referenced nowhere in `tools/` or `tests/`). Pytest does not collect it (no `test_` functions). It only runs when executed directly.

### Important caveat on granularity
Unlike file 7, here the TSV verdict is to KEEP the integration flow but trim the report-copy tail + evidence-HTML writing. Since this file is `main`-driven and never imported, the helpers (`_make_xlsx_bytes`, `_extract_raw_rows_json`, `_extract_preview_baseline`, `_assert_status`, `find_repo_root`) are all used only by `main()`. **Do NOT delete `main()` here** (the TSV explicitly marks the integration flow as real and worth keeping as a runnable smoke). Trim only the two brittle tails INSIDE `main()`:

### TRIM (brittle — inside `main()`)

**Item 8.1 — report-copy text snapshots (currently L264-291).** These assert exact Chinese report copy. KEEP the structural/behavioral checks (status 200 via `_assert_status`, the `name="start_date" value="{week_start}"` / `name="end_date" value="{week_end}"` date-passthrough checks, and the resource-row presence `MC001/OP001`). TRIM the exact-copy phrase guards:
  - Delete block (anchor, verbatim contiguous):
    ```
        if "当前无超期批次" not in overdue_html:
            raise RuntimeError("超期清单文案异常（期望“当前无超期批次”）")
    ```
    Keep the preceding `r = client.get(f"/reports/overdue?version={version}")` + `_assert_status("reports overdue", r, 200)` (proves the endpoint serves 200). The `overdue_html = r.data.decode(...)` assignment becomes unused → also delete its line (anchor: `    overdue_html = r.data.decode("utf-8", errors="ignore")`).
  - Delete block (anchor, verbatim):
    ```
        if "已按所选版本的排程范围自动带入日期" not in util_html:
            raise RuntimeError("utilization 缺少“按版本排程范围”提示文案")
    ```
  - Delete block (anchor, verbatim):
    ```
        if "已按所选版本的排程范围自动带入日期" not in dt_html:
            raise RuntimeError("downtime 缺少“按版本排程范围”提示文案")
    ```
  Why brittle: these are exact Chinese hint-phrase snapshots; the real contract (default dates auto-filled from the version's scheduling range) is anchored by the KEPT `name="start_date" value=...` / `name="end_date" value=...` checks immediately above each. KEEP those date-value checks and the `MC001/OP001` resource-row check (real data presence).

**Item 8.2 — evidence-HTML writing (currently L293-345).** Writes `evidence/FullE2E/gantt_tasks.json` + `gantt_preview.html`. This is pure artifact emission after the assertions already ran. Excise the artifact-writing tail:
  - Delete the block from (anchor, verbatim start): `    out_dir = os.path.join(repo_root, "evidence", "FullE2E")` through the end of the HTML write and the two trailing `print(...)` lines:
    ```
        print("OK")
        print(f"html={html_path}")
        print(f"tasks_json={tasks_path}")
    ```
  - Keep-context: the last RETAINED behavioral statement is the gantt-tasks non-empty check (currently L261-262: `if not isinstance(tasks, list) or not tasks: raise RuntimeError("甘特 tasks 为空")`) and the trimmed report checks above. After removing the evidence block, `main()` ends after the report assertions; this is fine for a runnable smoke.
  - Note: `import re`, `import time`, `from datetime import date` — `re` is used by `_extract_*` (KEEP import), `date` is used at L248 (KEEP import). `time` appears unused already; leave it to avoid churn. The HTML-string f-string and `json.dump` of evidence are removed with the block.

Why brittle/excisable: the evidence HTML/JSON is manual-inspection output, not asserted; removing it does not reduce coverage.

Risk: mid. est net lines removed: **~60** (≈8 report-copy/dead-var lines + ≈52 evidence-writing lines).

---

## 9. tests/test_scheduler_batches_page_viewmodel.py  (696 lines)

TSV reason (high): viewmodel data assembly + strict validation high value (filter-state contract / batch-row labels + internal-field hiding / latest-history panel raising on unknown-or-incomplete values / route truly goes through viewmodel); ~half are full-page HTML substring snapshots (element id / option-selected / Chinese copy / hidden-field order) → should be trimmed/sunk.

### KEEP (real contract — pure viewmodel + raising oracles)
- `test_batches_filter_state_preserves_default_and_empty_status_contract` (L211-220). KEEP.
- `test_batches_filter_state_preserves_non_pending_status_for_service` (L223-228). KEEP.
- `test_batch_rows_filter_ready_and_add_public_labels` (L231-272) — filter + label + internal-field-hiding (`priority_zh`/`ready_status_zh`/`status_zh` absent). KEEP whole.
- ALL `test_latest_history_panel_*` raising tests (L502-610) — `pytest.raises(ScheduleHistoryDisplayValueError, match=...)`. The `match=` strings are ERROR-MESSAGE contracts of a loud-error refactor (differential oracle). KEEP every one whole; do NOT trim the match strings.
- `test_scheduler_batches_route_uses_page_view_model` (L652-697) — proves the route calls `build_scheduler_batches_page_view_model` and renders its output (sentinel substitution). KEEP whole (kwargs-shape asserts + sentinel-in-body are behavioral, not cosmetic).

### KEEP with caution / selective TRIM (full-page HTML snapshots)

The page-render tests (`test_batches_page_*`) mix REAL behavioral guards (which batch rows appear given a filter; internal raw values NOT leaked) with cosmetic snapshots (element ids, `<option ... selected>` markup, exact Chinese copy, hidden-field order). Conservative policy: in each, KEEP status-200, KEEP row-visibility behavioral asserts (`"B-X" in/not in body` — these encode the filter RULE), KEEP all no-leak negatives (`"abc" not in body`, `"future_strategy" not in body`, `"{invalid json" not in body`, `"auto_assign_persist" not in body`). TRIM only the pure-cosmetic element-id / option-markup / exact-copy snapshots that are NOT the load-bearing behavior and are double-covered by the viewmodel tests above.

Because these are densely interleaved and high-value, apply a NARROW trim — only the clearest cosmetic snapshots:

**Item 9.1** — `test_batches_page_renders_run_option_toggle_fields` (L292-309): this entire function is element-id + hidden-value + ordering markup snapshots (`id="jsRunScheduleForm"`, `type="hidden" name=... value="no"`, checkbox-before-hidden). The toggle-ordering contract is already covered structurally by `regression_ui_contract_component_tokens.py::test_toggle_object_keeps_disabled_checked_hidden_value_safe` and the `_assert_checkbox_before_hidden` helper here re-asserts pure markup order.
  - Decision: **conservative KEEP.** Although markup-heavy, the "run controls render with order-independent hidden defaults" is a real route-rendering contract specific to THIS page (the cross-file token test only covers the macro in isolation, not the batches page wiring). Trimming risks losing the page-level wiring guard. KEEP whole; mark as a sink-candidate for a future dedicated lower-tier test (out of scope here).

**Item 9.2** — `test_batches_page_latest_algo_config_snapshot_renders_public_snapshot_state` (L613-650): asserts exact public-label copy (`最近一次排产快照`, `优先级优先`, `自动补设备人员`, `aps-summary-value">已关闭`, `保存补齐资源`, `查看说明`, `aps-summary-value">已启用`). The label-mapping (improve/priority_first/auto_assign flags → public labels) is exactly what the viewmodel `build_latest_schedule_history_panel_state` produces and is contract-tested by the raising tests + presenter. This page test is a render-copy snapshot.
  - TRIM the exact-copy / class-value snapshots, KEEP status-200 + version anchor + the load-bearing on/off mapping that is behavioral:
    - KEEP: `assert response.status_code == 200`, `assert 'aps-latest-schedule-value">v8' in body` (version anchor proving the panel rendered for this history).
    - Delete line (anchor): `    assert "最近一次排产快照" in body`
    - Delete line (anchor): `    assert 'aps-latest-schedule-label">版本' in body`
    - Delete line (anchor): `    assert "排产方式" in body`
    - Delete line (anchor): `    assert "优先级优先" in body`
    - Delete line (anchor): `    assert "查看说明" in body`
  - KEEP (behavioral on/off mapping — proves config_snapshot yes/no → 已关闭/已启用, which is a real value mapping, not pure copy): `assert "自动补设备人员" in body`, `assert 'aps-summary-value">已关闭' in body`, `assert "保存补齐资源" in body`, `assert 'aps-summary-value">已启用' in body`. (Keep these as the differential that `auto_assign_enabled="no"`→已关闭 and `auto_assign_persist="yes"`→已启用.)
  Why brittle (deleted lines): section heading + class-label + static method-label copy; they drift on cosmetic rephrasing and are double-covered by the viewmodel layer.

**Item 9.3** — the remaining `test_batches_page_*` (defaults/empty/non-pending/only-ready/empty-filtered/config-degraded/no-history/parse-failed/degrades-unknown): these are dominated by REAL filter-behavior (`B-X in/not in body`) and no-leak negatives. The few cosmetic bits (`<option value=... selected>` markup, `aps-empty-state`, exact empty-state copy) are tightly bound to the behavior being asserted (e.g. the empty-state message IS the user-facing contract with no other anchor).
  - Decision: **conservative KEEP all.** The Chinese strings here (`当前筛选条件下暂无批次数据...`, `还没有排过产`, `当前版本的排产摘要读取失败...`, `最近一次排产历史摘要不完整...`) are user-facing guarantees that are the ONLY anchor for that branch's output, and each sits beside a real behavioral assert. Under-trim per BIAS.

Risk: high (this is a high-value strict-validation file; the raising-oracle tests must not be touched). Trim is confined to 9.2's 5 cosmetic copy/class lines. est net lines removed: **5**.

---

## 10. tests/test_ui_browser_geometry_env.py  (152 lines)

TSV reason (mid): validates browser/Chrome/Node probe env skip/fail + error-message assembly logic (env vars / capability detection / graceful exit) — real probe branches; the LAST test asserts on the probe-script SOURCE TEXT → brittle, trim.

### KEEP (real branch/logic)
- `test_find_chrome_explicit_bad_path_does_not_fallback` (L14-26) — fail-not-fallback branch + error-code marker `browser_env_bad_chrome_path`. KEEP.
- `test_find_chrome_missing_local_can_skip` (L29-38) / `test_find_chrome_required_missing_fails` (L41-51) — skip-vs-fail branch on env. KEEP.
- `test_find_chrome_version_failure_reports_stdout_stderr` (L54-70) — error-message assembly includes stdout/stderr. KEEP.
- `test_find_node_missing_local_can_skip` (L73-81) / `test_find_node_required_missing_fails` (L84-91) / `test_find_node_capability_failure_reports_version` (L94-113) — node probe branches + capability message. KEEP (these assert error-marker codes and assembled context, which are behavioral).
- `test_run_chrome_probe_spawn_error_reports_kind` (L116-144) — spawn-failure assertion includes `chrome_spawn_failed` / `runtime_context` / version / node realpath. KEEP (real error-propagation contract).

### TRIM (brittle — probe-script SOURCE text grep)

**Item 10.1** — `test_chrome_geometry_probe_requests_graceful_chrome_exit_before_sigkill` (L147-153): reads `runtime.UI_GEOMETRY_PROBE_SOURCE` as text and asserts JS source substrings (`chrome.kill("SIGTERM")`, `if (!chromeExitWait.exited)`, and a negative on an exact multi-line source arrangement). This is a **JS/probe source-text grep** (brittle category). The graceful-exit BEHAVIOR is not executed here — only the source string is matched, so it breaks on any cosmetic refactor of the probe script without a behavior bug.
  - Decision: **DELETE the whole function** `test_chrome_geometry_probe_requests_graceful_chrome_exit_before_sigkill`.
    - grep result: `grep -rn "test_chrome_geometry_probe_requests_graceful_chrome_exit_before_sigkill" tools tests` → no hits outside this file. registry_refs_found: none. Not referenced by any registry/debt tooling.
  - Anchor (delete from this line to end of file):
    ```
    def test_chrome_geometry_probe_requests_graceful_chrome_exit_before_sigkill() -> None:
        source = runtime.UI_GEOMETRY_PROBE_SOURCE.read_text(encoding="utf-8")

        assert 'chrome.kill("SIGTERM")' in source
        assert "if (!chromeExitWait.exited)" in source
        assert 'try { chrome.kill("SIGKILL"); } catch {}\n              const chromeExitWait' not in source
    ```
  - Import-safety: `subprocess`, `Path`, `pytest`, `browser`, `runtime` all remain used by the kept tests. No import becomes dead. (This is the only function whose sole purpose is the source-text snapshot.)

Risk: low (the one deleted function is pure JS-source grep; all probe-behavior branches retained). est net lines removed: **~8** (function + its blank-line separator).

---

## 11. tests/test_ui_geometry_html_contract.py  (146 lines)

TSV reason (mid): two tests validate the error-page-keyword detector helper (distinguishing app-shell vs error page) — valuable; two others render per-page and assert meta/id/stable-text substrings → brittle HTML contract snapshot; suggested: keep 500/error-page guard, trim per-page text snapshots.

### KEEP (real helper logic + guards)
- `test_error_keyword_detector_does_not_flag_normal_app_shell_log_text` (L89-98) — helper logic: shell present + benign log text → not flagged. KEEP whole.
- `test_error_keyword_detector_flags_error_page_title` (L101-105) — helper logic: error title → flagged. KEEP whole.
- The `_matched_error_keyword` helper (L64-86) and `_HtmlSignalParser` (L14-58) — shared by kept tests AND the smoke loop. KEEP.

### Conservative-KEEP (per-page snapshot loop)
- `test_ui_geometry_contract_includes_first_version_workbench_pages` (L108-121) — asserts `workbench_paths ⊆ SMOKE_PATHS`. This is a **coverage ratchet** (every workbench page must be smoked). It is a hardcoded path-list, but deleting it lets pages silently drop out of the smoke set → reduces enforcement. KEEP whole (meta-gate caution).
- `test_ui_smoke_pages_render_expected_html_contract` (L124-146) — the per-page render loop. The TSV suggests trimming "per-page text snapshots", BUT the per-page `stable_texts`/`forbidden_texts` are sourced from the EXTERNAL module `tests/ui_geometry_contract_data.py` (`EXPECTED_PAGE_SIGNALS`), NOT from this file. Trimming them would require editing an out-of-batch file. Within THIS file, the loop's asserts are all load-bearing: HTTP 200 per page, app-shell presence (meta `aps-ui-template-env` + `apsThemeToggle` id + nav/header), and the **error-page guard** `matched_error == ""` (the 500/error-page detector the reason says to keep). The `stable_texts`/`forbidden_texts` loop is data-driven and is the no-leak + presence contract.
  - Decision: **KEEP whole, no trim in this file.** The brittle per-page text literals live in `ui_geometry_contract_data.py` (out of scope for B05_frontend_c). Trimming here would either (a) break the data-driven loop or (b) remove the real shell/200/error-page guards. Per BIAS, KEEP.

Risk: mid (file is a UI smoke gate; trimming would reduce enforcement and the literal snapshots are externalized). est net lines removed: **0**. NOTE for planners: if the per-page Chinese `stable_texts` snapshots are to be de-brittled, the edit belongs in `tests/ui_geometry_contract_data.py`, not here.

---

## Batch roll-up

| # | File | Lines | Trim type | Whole-fn deleted | Est. lines removed | Risk |
|---|------|------:|-----------|------------------|------:|------|
| 1 | regression_scheduler_candidate_week_plan_contract.py | 278 | exact_chinese_snapshot | — | 3 | low |
| 2 | regression_scheduler_resource_dispatch_invalid_query_cleanup.py | 415 | js_source_grep | — | 4 | low |
| 3 | regression_scheduler_week_plan_summary_observability.py | 515 | full_page_text | — | 9 | mid |
| 4 | regression_ui_contract_component_tokens.py | 270 | js_source_grep/css | — | 8 | mid |
| 5 | regression_week_plan_filename_uses_normalized_version.py | 197 | full_page_text | — | 8 | low |
| 6 | regression_workbench_nav_entry_contract.py | 256 | none (KEEP all) | — | 0 | high-if-trimmed |
| 7 | run_complex_case_and_export_gantt.py | 782 | demo excise | find_repo_root, main | 283 | mid |
| 8 | run_one_job_and_export_gantt.py | 350 | full_page_text + demo excise (inside main) | — | 60 | mid |
| 9 | test_scheduler_batches_page_viewmodel.py | 696 | full_page_text | — | 5 | high |
| 10 | test_ui_browser_geometry_env.py | 152 | js_source_grep | test_chrome_geometry_probe_requests_graceful_chrome_exit_before_sigkill | 8 | low |
| 11 | test_ui_geometry_html_contract.py | 146 | doc/full_page_text (externalized) | — | 0 | mid |

**B-4 red lines:** none of the two B-COMPAT B-4 files (`test_enum_display_consistency.py`, `regression_schedule_result_view_context.py`) are in this batch — no b4_redline rows here.

**Registry coupling:** zero across the batch (all 85 test-fn names + both run_* module names grepped against `tools/` → no hits). The only cross-file dependency is `regression_gantt_critical_outline_sync.py` reusing `build_preview_client_bootstrap` + `_write_html` from file 7 — both KEPT verbatim; deleted `main()`/`find_repo_root` are not executed on `exec_module` import.
