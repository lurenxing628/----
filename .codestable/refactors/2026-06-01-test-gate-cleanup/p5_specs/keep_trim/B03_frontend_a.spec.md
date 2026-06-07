# P5.2 KEEP_TRIM — Batch B03_frontend_a — TRIM SPEC

Source of truth for the implementation agent. Do NOT trust line numbers in the TSV `reason` column —
they were authored against an older snapshot. Every anchor below was re-mapped to CURRENT file content
(verified by reading each file in full on 2026-06-07). Apply by matching the verbatim ANCHOR string, not the line number.

Global rules honored:
- BIAS-TO-KEEP. Under-trim is safe; over-trim deletes real coverage.
- Registry coupling: `tools/test_registry_data.py`, `tools/test_registry_groups_*.py`, `tools/quality_gate_shared.py`
  reference these tests at **FILE-PATH** granularity (a list of `"tests/xxx.py"` strings), NOT per-function nodeids.
  Therefore deleting individual brittle FUNCTIONS inside a file is safe **as long as the file keeps >=1 test**.
  Verified: no whole-function-deletion candidate in this batch is referenced by name/nodeid anywhere in `tools/` or `tests/`
  (grep run per function, all empty — see each file's section).
- `main()` orchestrators: 4 files run their tests via a module-level `main()` + `_assert_*` chain. When a whole test
  function is deleted, its call line inside `main()` MUST be removed in the same edit, or `main()` will `NameError`.

---

## 1. tests/regression_dashboard_overdue_count_tolerance.py — 101 lines — risk: low — TRIM: NONE (keep entire)

TSV reason: "real dirty-data tolerance ... brittle Chinese hint assert line 104 + HTML-coupled regex".
Line 104 is STALE (file is only 101 lines). Re-mapped: the cited "Chinese hint" is at **current line 71-72**
(`"排产摘要里的超期批次数不是整数" not in html`) and the "HTML-coupled regex" is the helper `_extract_overdue_count_text` (14-18).

DECISION: **KEEP ENTIRELY. No trim.**
- The whole test is a single real dirty-data tolerance contract: count="2.9" must render "数据不足" + a problem notice and
  must NOT leak "2.9" or fake a 0. The Chinese notice `"排产摘要里的超期批次数不是整数"` is a user-facing guarantee with
  NO ErrorCode anchor — per the brief, when the exact string IS the contract with no stable key, KEEP it.
- The regex in `_extract_overdue_count_text` is load-bearing: it pins the value to the specific stat card (so a leak into
  another card is caught). Trimming it would gut the differential.
est_lines_removed: 0.

---

## 2. tests/regression_excel_template_contracts.py — 840 lines — risk: mid — TRIM: NONE (META-GATE, keep entire)

TSV reason: keep `_apply_sheet_layout` refresh/split + ensure_excel_templates protect; "trim heavy manual/page Chinese-phrase snapshot (line 720-820)".
Re-mapped region 720-820 = helpers `_assert_process_excel_dropdown_values_match_page_and_full_manuals` (722-773),
`_assert_page_manual_help_columns_match_template_headers` (776-789), `_assert_relation_reverse_header_copy_matches_templates` (792-822),
all called from the single test `test_excel_template_contracts` (825).

DECISION: **KEEP ENTIRELY. No trim. (META-GATE)**
Rationale (extra-conservative per META-GATE caution):
- This file is a doc⊆template consistency RATCHET. The "phrase snapshot" helpers are not accidental brittleness — they
  enforce that the Excel template dropdown ENUM VALUES stay byte-identical between (a) the registered template definition,
  (b) the actual generated `.xlsx` file, and (c) the user-facing page manuals / `scheduler_manual.md`. The
  `forbidden_page_phrases`/`forbidden_manual_phrases` lists catch a real regression: old English enum aliases
  (`内部`/`外部`, `在用`/`正常`/`禁用`) leaking back into user docs.
- Mixed within the "snapshot" helpers are REAL structural invariants that must not be lost:
  `_definition_enum_values_by_header(...) == actual` dropdown parity (722-745), and
  `actual_columns == expected_headers` help-card column-ordering (786, 815).
- Trimming any of these REDUCES enforcement of the doc/template consistency gate. Net coverage loss > cosmetic-fragility gain.
- The only arguably-pure cosmetic items are the two exact markdown-table-row literals at 801/804
  (`"| 人员管理侧 | 工号、设备编号、技能等级、主操设备 |"` etc.) — but they are part of the same ratchet and removing them
  would leave a half-enforced gate. Given bias-to-keep + meta-gate, leave them.
est_lines_removed: 0.
NOTE: If a later, more aggressive pass wants this file trimmed, the safe scope is ONLY the two markdown-row literals at
807-/missing... no — leave for a dedicated meta-gate review, not this KEEP_TRIM batch.

---

## 3. tests/regression_form_run_option_checkbox_layout_contract.py — 387 lines — risk: mid — TRIM: 3 whole functions (source/CSS snapshots)

TSV reason: keep render contract (checkbox-before-hidden ordering via app render); "trim grep-source symbol/class snapshots (line 173-270, 354-372)".
Re-mapped: the source-grep snapshots are functions at 175-201, 204-272; the CSS class snapshot is 356-374.

KEEP (real render contracts, do NOT touch):
- `_render_excel_import_component` (27-58), `_build_app` (61-87), helpers `_html`/`_assert_toggle_field_order`/
  `_assert_disabled_display_checkbox_without_name`/`_make_xlsx_bytes`/`_seed_strict_mode_render_data`/`_with_db` — shared, keep.
- `test_excel_import_component_renders_strict_mode_toggle_fields` (274-282) — renders Jinja component, asserts checkbox-before-hidden ORDER. KEEP.
- `test_process_pages_render_strict_mode_toggle_fields` (285-295), `test_scheduler_batch_pages_render_strict_mode_toggle_fields` (298-307),
  `test_process_excel_page_renders_strict_mode_toggle_fields` (310-315),
  `test_batch_excel_confirm_page_uses_hidden_strict_mode_and_readonly_display` (318-353) — real app render + DOM ordering. KEEP.

### TRIM 3a — DELETE whole function `test_form_run_options_use_compact_toggle_fields_in_process_pages`
Anchor (function header, unique):
```
def test_form_run_options_use_compact_toggle_fields_in_process_pages() -> None:
```
Delete from that `def` line through the blank line before `def test_scheduler_batch_related_strict_options_are_no_longer_raw_checkbox_labels`.
WHY BRITTLE: pure template/route SOURCE-GREP — reads `.html`/`.py` files as text and asserts CSS class names / Jinja symbols
present or absent (`"aps-form-toggle-field" in create_block`, `"aps-form-run-options" not in create_block`, etc.). Only failure
mode is cosmetic class-rename / markup refactor; no behavior bug is caught (the actual rendered ordering is covered by the KEEP tests).
grep `tools/ tests/` (excl. self): EMPTY — no registry/nodeid coupling.

### TRIM 3b — DELETE whole function `test_scheduler_batch_related_strict_options_are_no_longer_raw_checkbox_labels`
Anchor:
```
def test_scheduler_batch_related_strict_options_are_no_longer_raw_checkbox_labels() -> None:
```
Delete through the blank line before `def test_excel_import_component_renders_strict_mode_toggle_fields`.
WHY BRITTLE: same source-grep snapshot pattern over many template/route files (asserts symbol presence/absence and
`.count(...) == N` of `form_toggle_bool` occurrences in source text). The `.count==N` asserts look structural but are grep
counts on source, not behavioral — they break on any benign refactor. Behavioral submit-handling is not exercised here.
grep `tools/ tests/` (excl. self): EMPTY.

### TRIM 3c — DELETE whole function `test_run_option_css_is_scoped_to_the_right_surfaces`
Anchor:
```
def test_run_option_css_is_scoped_to_the_right_surfaces() -> None:
```
Delete through the blank line before `def main`.
WHY BRITTLE: pure CSS selector-literal snapshot — `assert ".aps-run-option-card .aps-toggle-title" in css` x18. Only failure
mode is CSS selector rename; catches no behavior.
grep `tools/ tests/` (excl. self): EMPTY.

### REQUIRED companion edit — update `main()` (377-381)
Remove the 3 calls to the deleted functions. Resulting `main()` must read:
```
def main() -> None:
    test_excel_import_component_renders_strict_mode_toggle_fields()
    print("OK")
```
(Delete the lines `test_form_run_options_use_compact_toggle_fields_in_process_pages()`,
`test_scheduler_batch_related_strict_options_are_no_longer_raw_checkbox_labels()`, and
`test_run_option_css_is_scoped_to_the_right_surfaces()`.)
File keeps 5 real test functions → registry file-path ref stays valid.
est_lines_removed: ~120 (3a ~27 + 3b ~69 + 3c ~19 + 3 main lines, minus blank-line bookkeeping).

---

## 4. tests/regression_frappe_gantt_short_task_contract.py — 286 lines — risk: low — TRIM: 1 whole function (vendor min.js substring snapshot)

TSV reason: keep JS geometry exec tests; "trim vendor min.js substring snapshot test (line 259-271)". Re-mapped to function at 261-273.

KEEP (real JS-exec geometry, do NOT touch): `_load_gantt_dom_helpers` (12-19),
`test_frappe_gantt_keeps_short_tasks_visible_and_draggable` (22-139),
`test_frappe_gantt_supports_hour_and_minute_zoom_geometry` (142-188),
`test_short_task_width_matrix_covers_all_readonly_zoom_levels_and_midnight_edges` (191-258).

### TRIM 4a — DELETE whole function `test_short_task_fix_stays_inside_vendor_time_geometry`
Anchor:
```
def test_short_task_fix_stays_inside_vendor_time_geometry() -> None:
    vendor_js = (REPO_ROOT / "static" / "js" / "frappe-gantt.min.js").read_text(encoding="utf-8")
```
Delete from `def test_short_task_fix_stays_inside_vendor_time_geometry` through the blank line before `def main`.
WHY BRITTLE: asserts EXACT minified-JS source substrings inside vendored `frappe-gantt.min.js`
(`"this.duration=(this.task._end-this.task._start)/(this.gantt.options.step_ms||36e5*this.gantt.options.step)" in vendor_js`,
`"compute_start_end_date(){const t=this.$bar" in vendor_js`, ...). A re-minify or vendor bump breaks it with zero behavior
change; the actual geometry it is "guarding" is fully exercised by the three KEEP JS-exec tests above
(width math, hitWidth>=12, zero drift across all zoom levels).
grep `tools/ tests/` (excl. self): EMPTY.

### REQUIRED companion edit — update `main()` (276-281)
Remove `test_short_task_fix_stays_inside_vendor_time_geometry()`. Resulting:
```
def main() -> None:
    test_frappe_gantt_keeps_short_tasks_visible_and_draggable()
    test_frappe_gantt_supports_hour_and_minute_zoom_geometry()
    test_short_task_width_matrix_covers_all_readonly_zoom_levels_and_midnight_edges()
    print("OK")
```
est_lines_removed: ~15.

---

## 5. tests/regression_frontend_offline_static_assets.py — 302 lines — risk: mid — TRIM: 1 whole function + 1 in-function data trim

TSV reason: keep offline-deploy guardrail + regex self-test + strict-utf8; "trim forbidden-Chinese-phrase mockup/doc blacklist tests (line 273-298)".
Re-mapped: the blacklist functions are `test_workbench_mockup_uses_plain_language_for_users` (276-287) and
`test_user_visible_docs_do_not_use_internal_or_draft_terms` (290-301).

KEEP (real guardrails, do NOT touch):
- All module constants for the EXTERNAL/CDN scan + the scan helpers (`_frontend_files`, `_collect_external_resource_violations*`, etc.).
- `test_frontend_static_assets_are_offline_local` (242-244) — real offline-deploy guardrail.
- `test_external_resource_patterns_cover_remote_images_srcset_and_css_url` (247-262) — self-test of the detection regexes (real).
- `test_frontend_static_asset_scan_reads_utf8_strictly` (265-273) — strict-utf8 behavior (real).

### TRIM 5a — DELETE whole function `test_workbench_mockup_uses_plain_language_for_users`
Anchor:
```
def test_workbench_mockup_uses_plain_language_for_users() -> None:
    text = WORKBENCH_MOCKUP.read_text(encoding="utf-8")
```
Delete from that `def` through the blank line before `def test_user_visible_docs_do_not_use_internal_or_draft_terms`.
WHY BRITTLE: pure DOC/MOCKUP TEXT BLACKLIST snapshot — iterates `WORKBENCH_MOCKUP_FORBIDDEN_TEXT` (a ~40-phrase Chinese
copy list, e.g. "异常解释", "第一卡点", "看影响清单") asserting none appear in a static prototype HTML. Failure mode is purely
editorial wording drift in a mockup; catches no product behavior.
ALSO delete the now-orphaned constant `WORKBENCH_MOCKUP_FORBIDDEN_TEXT` (43-85) and
`WORKBENCH_MOCKUP_FORBIDDEN_PATTERNS` (118-121) — they are used ONLY by this function (verify: grep the two names in-file;
both appear only in the deleted body). Keep `WORKBENCH_MOCKUP` constant (24) — it is unused elsewhere after deletion, so
also remove `WORKBENCH_MOCKUP` (24) and its use in `_frontend_files` lines 178-179
(`if WORKBENCH_MOCKUP.exists() and WORKBENCH_MOCKUP not in seen: yield WORKBENCH_MOCKUP`).
  - CAUTION: `_frontend_files` is shared by the KEEP offline-scan. Removing the mockup from the scan set means the workbench
    mockup HTML would no longer be scanned for external/CDN resources. To AVOID weakening the offline guard, **DO NOT remove
    lines 178-179 / the `WORKBENCH_MOCKUP` constant** — keep them so the mockup still gets the offline scan. Only delete the
    text-blacklist function + the two FORBIDDEN constants it solely uses. (Net: offline scan unchanged; only the editorial
    blacklist is dropped.)
grep `tools/ tests/` (excl. self): EMPTY.

### TRIM 5b — IN-FUNCTION data trim inside `test_user_visible_docs_do_not_use_internal_or_draft_terms` (KEEP the function)
This function is MIXED: it forbids `USER_VISIBLE_LEGACY_DRAFT_TEXT` (draft-phrasing blacklist = brittle) AND
`USER_VISIBLE_INTERNAL_TERMS` (internal field-name leak guard = REAL: `plan_role`, `scenario_id`, `ReasonCode`,
`ExecutionEvent`, ... must never appear in user-facing docs). KEEP the function; trim only the brittle half.
Anchor to edit (line 292):
```
    forbidden_terms = tuple(USER_VISIBLE_LEGACY_DRAFT_TEXT + USER_VISIBLE_INTERNAL_TERMS)
```
Replace with:
```
    forbidden_terms = tuple(USER_VISIBLE_INTERNAL_TERMS)
```
Then DELETE the now-orphaned constant `USER_VISIBLE_LEGACY_DRAFT_TEXT` (87-97). (grep in-file: used only at line 292.)
WHY BRITTLE: `USER_VISIBLE_LEGACY_DRAFT_TEXT` = ["第一版","后续版本再补","当前阶段",...] is a draft-wording blacklist that
breaks on benign doc edits; the internal-term leak guard is the real security/clarity contract and stays.
META-GATE NOTE: this test is partly a leak GATE. We retain the leak half — enforcement of "no internal schema terms in user docs"
is fully preserved. Only the editorial draft-phrasing ratchet is dropped.
est_lines_removed for file: ~55 (5a function ~12 + FORBIDDEN_TEXT const ~43 + FORBIDDEN_PATTERNS ~4 + 5b draft-const ~11, minus the kept-line replacement).

---

## 6. tests/regression_frontend_ui_language_polish.py — 846 lines — risk: mid — TRIM: selective (1 whole func + protect the rest)

TSV reason: keep normalizer round-trip (462-481→now 399-483) + ensure_excel_templates overwrite-protect (484-619→now 486-621);
"trim heavy Chinese-hint/forbidden-term/source-grep snapshots (line 30-258, 668-844)".

This file is the densest meta-gate in the batch: its STATED PURPOSE is a user-facing-language quality ratchet. Most of its
functions are source-greps / exact-Chinese-copy snapshots — but many double as genuine GATES (mojibake-repair guard,
internal-schema-leak guard, vague-vocabulary-for-operators policy). Per META-GATE caution + bias-to-keep, we trim ONLY the
clearest pure-redundant brittle snapshot, and explicitly KEEP the rest with a recorded enforcement rationale.

KEEP — real behavioral / genuine-gate (do NOT touch):
- `test_excel_templates_default_to_chinese_enum_values_accepted_by_backend` (399-483) — normalizer round-trip on real enums. (TSV KEEP)
- `test_ensure_excel_templates_refreshes_known_stale_generated_template` (486-511),
  `..._refreshes_known_legacy_id_headers` (514-556),
  `test_template_download_preserves_existing_disk_file_when_headers_match` (559-592),
  `test_ensure_excel_templates_preserves_user_custom_template_with_extra_rows` (595-621) — real overwrite-protect/preserve. (TSV KEEP)
- `test_known_garbled_error_messages_are_repaired` (817-845, parametrized) — MOJIBAKE-REPAIR GATE: asserts corrupted byte
  sequences (璁惧/鈥/宸ョ/鍋滄満) are absent AND correct Chinese present. This catches a real encoding-corruption regression. KEEP.
- `test_manuals_keep_backend_supported_english_aliases_but_mark_them_as_compatible` (263-364) — MIXED: KEEP. It carries a unique
  REAL normalizer block (332-355: `normalize_yes_no_optional("on"/"off"/"true"/"false")`, `normalize_..._value("weekend")→HOLIDAY`,
  etc.) not covered by 399-483. Do NOT delete the function. (Optional micro-trim: the doc-phrase asserts 317-330 & 357-363 are
  brittle copy snapshots, but they are the alias-compat ratchet; leave them under meta-gate caution.)
- `test_scheduler_run_copy_avoids_vague_vocabulary_for_operators` (70-99) — operator-clarity policy GATE (forbid vague words). Meta-gate, KEEP.
- `test_excel_exports_use_chinese_labels_for_enum_columns` (651-667) — structural contract: exports route through *_label helpers,
  not raw enums. Borderline but a real "no raw enum leakage in exports" guard. KEEP.

KEEP-but-acknowledged-brittle (source-grep / Chinese-copy snapshots that ARE language-quality gates; left intact under
META-GATE caution — trimming them would remove the only enforcement of these copy/leak policies):
- `test_scheduler_config_and_batch_hints_are_user_facing_chinese` (32-68) — long exact-Chinese hint contracts, no ErrorCode anchor → KEEP per brief.
- `test_scheduler_config_repair_notices_use_public_field_labels` (101-120),
  `test_scheduler_analysis_gantt_and_logs_do_not_surface_internal_terms` (122-151),
  `test_debug_details_do_not_expose_flask_endpoint_names_to_users` (153-167),
  `test_process_excel_current_tables_render_chinese_display_fields` (170-260),
  `test_supplier_manual_matches_required_default_days_and_template_columns` (366-383),
  `test_material_status_and_delete_messages_match_user_page_labels` (385-397),
  `test_import_errors_present_chinese_first_and_english_as_compatible_aliases` (624-648),
  `test_frontend_scripts_keep_internal_details_out_of_user_messages` (670-741),
  `test_process_and_scheduler_errors_use_chinese_terms` (743-762),
  `test_scheduler_analysis_hides_internal_schema_and_attempt_tags` (764-782),
  `test_reports_and_v2_batch_templates_match_public_manual_contracts` (793-815)
  — all source-grep/copy snapshots, but each enforces a distinct "no internal term / correct Chinese" leak or clarity policy.
  Recorded as candidates for a FUTURE dedicated language-gate consolidation; NOT trimmed in this KEEP_TRIM pass.

### TRIM 6a — DELETE whole function `test_gantt_contract_frontend_preserves_reason_code_and_deduplicates_unavailable_tooltip` (784-790)
Anchor:
```
def test_gantt_contract_frontend_preserves_reason_code_and_deduplicates_unavailable_tooltip() -> None:
    gantt_contract = _read("static/js/gantt_contract.js")
    assert "reason_code" in gantt_contract
```
Delete from that `def` through the blank line before `def test_reports_and_v2_batch_templates_match_public_manual_contracts`.
WHY BRITTLE + SAFE: it is a JS SOURCE-GREP (`"dedupeCriticalReason" in gantt_contract`, `"reason_code" in gantt_contract`).
Its underlying behavior is FULLY and BEHAVIORALLY exercised by JS-exec in
`regression_gantt_critical_outline_sync.py::test_gantt_contract_critical_unavailable_message_maps_reason_code` (current 1765-1796:
asserts `state["critical"]["reason_code"]=="repo_exception"`, tooltip dedupes to count==1, and `"repo_exception" not in public_text`).
So deleting the grep loses zero real coverage.
grep `tools/ tests/` (excl. self): EMPTY.
NO `main()` in this file — pure pytest, no companion edit.
est_lines_removed: ~8.

RISK NOTE: This file remains a large language-quality gate. We intentionally trimmed only the one redundant JS-grep. A heavier
trim would risk silently removing the only enforcement of several copy/leak policies (meta-gate). Keep file-path registry ref valid (file keeps many tests).

---

## 7. tests/regression_gantt_critical_outline_sync.py — 1989 lines — risk: mid — TRIM: 1 whole function + its sole helper (SHARED HELPER FILE — handle with care)

CRITICAL: this file is the SHARED DOM-shim + node-runner module imported via `importlib` by
`regression_frappe_gantt_short_task_contract.py` and `regression_gantt_readonly_mode_contract.py`
(both call `_load_gantt_dom_helpers()` → load this module and use `DOM_SHIM_JS`, `_run_node_json`, `_vendor_js`, `_gantt_*_js`,
`createHost`, `findWrapperById`, etc.). DO NOT touch any of: `DOM_SHIM_JS` (49-704), `_preview_bootstrap` (705),
`_run_node_json` (715), `_outline_js`/`_vendor_js`/`_gantt_*_js`/`_load_preview_module` (732-797). They are the public surface.

TSV reason: keep shared helpers + JS-exec outline/escaping/reason_code tests; "trim template-script-order/git-tracked snapshot (line 800-845)".
Re-mapped: function `test_gantt_contract_asset_is_tracked_and_loaded_before_render_in_all_templates` (803-848) + its sole helper
`_template_static_scripts` (798-800).

KEEP (real, do NOT touch): the contract-clearing test (16-46), the outline adapter JS-exec test (851-947), live-render sync
(950-1133), preview bootstrap sync (1135-1245), missing-dependency error-hiding (1247-1275), formal/preview tooltip+help
semantics (1277-1487), critical-unavailable parity (1489-1681), help-list contract (1683-1689), task-name XSS sanitization
(1691-1718), calendar-fallback (1721-1742), no-raw-event leak (1744-1762), reason_code mapping w/o leak (1765-1796),
public-history no-leak (1799-1828), degradation/overdue parity (1831-1989). All are real algorithm/behavior/security contracts.

### TRIM 7a — DELETE whole function `test_gantt_contract_asset_is_tracked_and_loaded_before_render_in_all_templates` (803-848)
Anchor (function header):
```
def test_gantt_contract_asset_is_tracked_and_loaded_before_render_in_all_templates() -> None:
    expected_order = [
        "js/frappe-gantt.min.js",
```
Delete from that `def` through the blank line before `def test_outline_helper_contract_and_adapter_binding`.
WHY BRITTLE: (1) `assert scripts == expected_order` — a hardcoded ORDERED LIST of 16 static JS filenames snapshotted against
template `<script>` tags; breaks on any benign script reorder/add/rename. The real load-order CONTRACT (scripts actually
producing a working render in dependency order) is exercised by the live-render JS-exec tests in this same file
(950-1133, 1831-1989 load each script and run `ns.render()`/`loadAndRender()`). (2) the git-`ls-files --error-unmatch`
tracked-asset check (830-848) is a low-value structural snapshot. The TSV explicitly groups both as the trim target.
RISK NOTE (mid): the git-tracked half has mild guardrail value (asset committed so deploy doesn't 404). If the implementer
prefers to retain that single guarantee, it is acceptable to KEEP only the 830-848 `for asset_rel ...` loop and delete only the
`expected_order`/`scripts == expected_order` block (804-828). Default recommendation: delete the whole function (TSV intent).

### TRIM 7a-companion — DELETE the now-orphaned helper `_template_static_scripts` (798-800)
Anchor:
```
def _template_static_scripts(template_path: Path) -> List[str]:
    text = template_path.read_text(encoding="utf-8")
    return re.findall(r"url_for\('static',\s*filename='([^']+)'\)", text)
```
Verified sole user: only `test_gantt_contract_asset_is_tracked_and_loaded_before_render_in_all_templates` (grep `_template_static_scripts`
in tests/ tools/ → only this file, only lines 798 def + 825 call). Safe to remove WITH 7a.
(If the implementer keeps the git-tracked loop variant of 7a, then `_template_static_scripts` is still orphaned and should still be deleted.)

grep `tools/ tests/` (excl. self) for the deleted test funcname: EMPTY.
NO `main()` in this file. File keeps ~20 tests → all importers + registry file-path ref unaffected (public helper surface untouched).
est_lines_removed: ~50 (function 803-848 ~46 + helper 798-800 ~3).

---

## 8. tests/regression_gantt_default_version_span.py — 226 lines — risk: low — TRIM: 2 whole functions (gantt_boot.js source-order snapshots)

TSV reason: keep app+DB range-resolution; "trim gantt_boot.js source-order snapshot (line 191-209)".
Re-mapped: functions `test_gantt_boot_sends_one_range_mode_to_data_endpoint` (193-204) and
`test_gantt_boot_keeps_version_span_as_data_default` (207-211).

KEEP (real app+DB range-resolution, do NOT touch): `_build_app` (14-66) and all 6 endpoint tests:
69-82, 84-99, 102-121, 124-152, 155-176, 179-190, 214-225.
NOTE on KEEP region: lines 80 (`"2026年5月11日 ～ 2026年5月16日" in html`) and 121
(`empty_message == "当前范围无任务，请切换到 2026-05-11 ～ 2026-05-16。"`) are Chinese strings but are COMPUTED OUTPUTS of the
range-resolution logic (the derived span / empty message), not cosmetic UI labels → they ARE the behavioral contract. KEEP.

### TRIM 8a — DELETE whole function `test_gantt_boot_sends_one_range_mode_to_data_endpoint` (193-204)
Anchor:
```
def test_gantt_boot_sends_one_range_mode_to_data_endpoint() -> None:
    js = (REPO_ROOT / "static/js/gantt_boot.js").read_text(encoding="utf-8")

    start_idx = js.index('if (hasEffectiveRange) {')
```
Delete through the blank line before `def test_gantt_boot_keeps_version_span_as_data_default`.
WHY BRITTLE: JS SOURCE-ORDER snapshot — `js.index(...)` chain asserting the byte-order of `start_date`/`end_date`/`week_start`/
`offset` setter calls inside `gantt_boot.js`. Breaks on any source reformat; the actual "no double-offset / one range mode"
BEHAVIOR is covered by the KEEP endpoint tests (124-152 ignore-offset-when-explicit, 179-190 start-only-ignores-offset).

### TRIM 8b — DELETE whole function `test_gantt_boot_keeps_version_span_as_data_default` (207-211)
Anchor:
```
def test_gantt_boot_keeps_version_span_as_data_default() -> None:
    js = (REPO_ROOT / "static/js/gantt_boot.js").read_text(encoding="utf-8")

    assert 'const usesVersionSpanRange = cfg.rangeSource === "version_span";' in js
```
Delete through the blank line before `def test_gantt_without_version_span_keeps_request_range_source`.
WHY BRITTLE: exact JS source-substring snapshot of two lines from `gantt_boot.js`. Behavior covered by version_span endpoint
tests (84-99 page+data use version_span, 214-225 no-span falls back to request).
grep `tools/ tests/` (excl. self) for both names: EMPTY.
NO `main()`. File keeps 7 tests → registry file-path ref valid.
est_lines_removed: ~22.

---

## 9. tests/regression_gantt_offset_range_consistency.py — 100 lines — risk: low — TRIM: 1 in-function block (gantt_boot.js source-order snapshot inside a kept test)

TSV reason: keep offset/range consistency via app+DB; "trim gantt_boot.js source-order snapshot (line 111-132)".
Re-mapped: there is only ONE test (`test_gantt_offset_range_consistency`, 30-99). The brittle source-order snapshot is the
TAIL BLOCK at current lines 78-99 (reads `gantt_boot.js` and asserts `src.index(...)` ordering). It lives INSIDE the kept test,
so this is an IN-FUNCTION trim, NOT a function deletion.

KEEP (real, do NOT touch): the entire HTTP/range behavior 30-76 (data-attr extraction, `_call_data` parity asserts:
old-style start/end+offset must not double-offset 64-69; new-style without offset same range 72-76; no-history hint 60-61).

### TRIM 9a — DELETE the gantt_boot.js source-order tail block (78-99) inside `test_gantt_offset_range_consistency`
Anchor (start of block to delete; verbatim, unique):
```
    boot_js_path = os.path.join(str(repo_root), "static", "js", "gantt_boot.js")
    with open(boot_js_path, "r", encoding="utf-8") as f:
        src = f.read()
```
Delete from that `boot_js_path = ...` line through the END of the function (the final `)` closing the last `_assert_true(...)`
at line 99). The function then ENDS at the `new_style_data` assertions (line 76).
WHY BRITTLE: JS source-order snapshot — `src.index('const usesVersionSpanRange...')`, then a chain of `src.index(...)` calls and
`explicit_idx < start_idx < ... < offset_idx` ordering assert. Pure structural snapshot of `gantt_boot.js` text; the request-time
behavior it shadows is already asserted via the live HTTP calls in 64-76.
KEEP-CONTEXT: after deletion the function still has meaningful asserts (status 200, success True, week_start/week_end parity
across old-style and new-style queries) → not left assertion-empty. The `import os` (line 6) becomes unused after this trim;
also remove `import os` if no other use (grep `os.` in-file: only used in the deleted block → safe to drop the import). `re`,
`json`, `urllib.parse` remain used.
grep coupling: function is the only test; file keeps 1 test → registry file-path ref valid. No whole-func deletion, no main().
est_lines_removed: ~23 (block ~22 + `import os` ~1).

---

## 10. tests/regression_gantt_readonly_mode_contract.py — 225 lines — risk: low — TRIM: 1 whole function (template Chinese-copy/attr snapshot)

TSV reason: keep vendor-gantt JS-exec readonly blocks-drag tests; "trim template Chinese-copy/attr snapshot (line 204-211)".
Re-mapped: function `test_templates_show_readonly_mode_and_zoom_contract` (206-213).

KEEP (real JS-exec, do NOT touch): `_load_gantt_dom_helpers` (12-19),
`test_readonly_gantt_blocks_drag_resize_and_progress_events_but_keeps_click` (22-97),
`test_formal_render_passes_readonly_options_and_blocks_drag` (100-203).

### TRIM 10a — DELETE whole function `test_templates_show_readonly_mode_and_zoom_contract` (206-213)
Anchor:
```
def test_templates_show_readonly_mode_and_zoom_contract() -> None:
    for rel in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        html = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "当前为查看模式" in html
```
Delete through the blank line before `def main`.
WHY BRITTLE: template TEXT/ATTR snapshot — exact Chinese copy `"当前为查看模式"` + HTML attribute/id literals
(`'id="ganttZoomLevel"'`, `'data-gantt-mode="view"'`, `'data-zoom-level="{{ gantt_zoom or'`). The actual readonly BEHAVIOR
(options passed through, drag/resize/progress blocked, click+popup kept) is fully exercised by the two JS-exec KEEP tests.
grep `tools/ tests/` (excl. self): EMPTY.

### REQUIRED companion edit — update `main()` (216-220)
Remove `test_templates_show_readonly_mode_and_zoom_contract()`. Resulting:
```
def main() -> None:
    test_readonly_gantt_blocks_drag_resize_and_progress_events_but_keeps_click()
    test_formal_render_passes_readonly_options_and_blocks_drag()
    print("OK")
```
File keeps 2 tests → registry file-path ref valid.
est_lines_removed: ~10.

---

## 11. tests/regression_gantt_status_mode_semantics.py — 181 lines — risk: low — TRIM: 1 in-function block (depsMode JS source-grep inside kept main())

TSV reason: keep node-exec statusKeyForTask priority test; "trim depsMode source-grep (line 157-160)".
Re-mapped: the depsMode source-grep is at current lines 156-162 inside `main()` (which is the orchestrator the pytest entry
`test_regression_gantt_status_mode_semantics` (175-176) calls). This is an IN-FUNCTION assert-block trim, NOT a func deletion.

KEEP (real, do NOT touch): `find_repo_root` (10-15), `_run_node_status_check` (18-144, the node DOM-shim + statusKeyForTask exec),
the status-semantics exec + assertion block in `main()` (164-172), the pytest entry (175-176), `__main__` guard (179-180).

### TRIM 11a — DELETE the gantt.js depsMode source-grep block (156-162) inside `main()`
Anchor (verbatim block to delete):
```
    with open(core_js_path, "r", encoding="utf-8") as f:
        src = f.read()
    # 依赖模式应统一为 depsMode，不再保留旧双复选框语义
    if "depsMode" not in src:
        raise RuntimeError("gantt.js 缺少 depsMode 语义字段")
    if "showProcessDeps" in src or "onlyCCDeps" in src:
        raise RuntimeError("gantt.js 仍包含旧依赖开关字段（showProcessDeps/onlyCCDeps）")
```
WHY BRITTLE: JS SOURCE-GREP — asserts `gantt.js` text contains `depsMode` and not `showProcessDeps`/`onlyCCDeps`. Pure rename-fragile
snapshot; no behavior verified (unlike the statusKeyForTask node-exec which stays).
KEEP-CONTEXT: keep the lines around it that are still needed — `core_js_path` is computed at 149 and is ALSO referenced only by
this block (151 `os.path.exists(core_js_path)` check + 156 read). After deleting the read/grep (156-162), the `core_js_path`
existence guard at 151-152 becomes dead weight but is harmless; SAFE to also delete `core_js_path = ...` (149) and its existence
check (151-152) since after trim nothing else uses `core_js_path` (grep in-file: only 149/151/156). Leave `color_js_path`
(150) and its check (153-154) — they feed `_run_node_status_check` (164), KEEP.
After trim, `main()` flows: find_repo_root → color_js_path + its exists-check → `_run_node_status_check(color_js_path)` → assert
rows → print("OK"). Still meaningful (real statusKeyForTask oracle).
grep coupling: no whole-func deletion; pytest entry name unchanged; file keeps its test → registry file-path ref valid.
est_lines_removed: ~10 (block 7 + core_js_path setup/guard ~4 - bookkeeping).

---

## 12. tests/regression_gantt_task_detail_panel_contract.py — 301 lines — risk: low — TRIM: 1 whole function (template/CSS layout snapshot)

TSV reason: keep viewmodel+integration (no op_id leak / public labels / execution facts / context+guard / no scenario_id leak);
"trim template/CSS layout snapshot (line 281-299)". Re-mapped: function `test_gantt_templates_and_css_define_stable_detail_layout` (283-301).

KEEP (real viewmodel/integration, do NOT touch): helpers `_read`/`_gantt_data`/`_first_task`/`_links_by_label`/`_assert_url_contains_all`
(22-50) and the 6 contract tests:
`test_gantt_task_public_title_does_not_use_internal_op_id_fallback` (52-93),
`test_critical_chain_edges_keep_internal_ids_but_expose_public_labels` (94-139),
`test_gantt_task_meta_uses_execution_facts_and_keeps_no_record_state` (140-172),
`test_gantt_task_detail_links_preserve_context_and_guard_execution_review` (173-203),
`test_gantt_task_detail_preview_links_do_not_leak_scenario_id` (204-246),
`test_gantt_task_detail_links_explain_summary_parse_failure` (247-281).

### TRIM 12a — DELETE whole function `test_gantt_templates_and_css_define_stable_detail_layout` (283-301)
Anchor:
```
def test_gantt_templates_and_css_define_stable_detail_layout() -> None:
    for rel_path in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        html = _read(rel_path)
        assert 'class="aps-gantt-workbench"' in html
```
Delete from that `def` through end of file (it is the last function; line 301).
WHY BRITTLE: CSS PIXEL/GEOMETRY + template-attr snapshot — asserts literal CSS selectors and pixel literals
(`"grid-template-columns: minmax(0, 1fr) minmax(300px, 360px);"`, `"@media (min-width: 1180px)"`, `"@media (max-width: 1179px)"`)
plus HTML class/id literals and one weak `html.index('id="gantt"') < html.index('id="ganttTaskDetail"')` ordering. Pure layout
snapshot; breaks on any CSS tweak; catches no product behavior (the detail-panel DATA contracts are fully covered by the 6 KEEP tests).
grep `tools/ tests/` (excl. self): EMPTY.
NO `main()`. File keeps 6 tests → registry file-path ref valid.
est_lines_removed: ~19.

---

## Batch totals
- Whole functions deleted: 9 (files 3×3, 4×1, 5×1, 6×1, 7×1, 8×2, 10×1, 12×1) + sole-helper `_template_static_scripts` (file 7).
- In-function trims (function kept): file 5b, file 9a, file 11a.
- KEEP-ENTIRELY / NONE: file 1 (real), file 2 (META-GATE).
- Registry coupling: all references are FILE-PATH level (tools/test_registry_data.py, test_registry_groups_*.py,
  quality_gate_shared.py); every file retains >=1 test after trim, so no dangling references. No per-function nodeid coupling found.
- main() companion edits required: files 3, 4, 10 (delete call lines). Files 9, 11 trim inside an existing function/main body.
- Estimated net lines removed: ~327 (file3 ~120, file4 ~15, file5 ~55, file6 ~8, file7 ~50, file8 ~22, file9 ~23, file10 ~10,
  file11 ~10, file12 ~19; files 1 & 2 = 0).
