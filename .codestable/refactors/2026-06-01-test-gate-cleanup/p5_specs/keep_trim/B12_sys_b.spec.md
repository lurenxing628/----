# KEEP_TRIM spec — batch B12_sys_b

Source TSV: `.codestable/refactors/2026-06-01-test-gate-cleanup/p5_specs/keep_trim_files.tsv`
Repo root = CWD. All anchors are verbatim from CURRENT file content (TSV line numbers were stale and have been re-mapped by content).
Implementation agent: apply only the DELETE blocks below; everything else is KEEP. Never empty a file or break imports/fixtures/shared helpers.

## Registry coupling summary (read first)

File-PATH membership lists in `tools/` reference three of these files. They pin the file path only — NOT function names, NOT assert counts. They survive any in-function trim and any whole-function deletion **as long as the file keeps existing and still has ≥1 collectable+passing test**. Therefore: never delete a whole file, never trim a file down to zero test functions.

- `tests/regression_route_version_normalizers_contract.py`
  - `tools/test_registry_data.py:64: "tests/regression_route_version_normalizers_contract.py",` (QUALITY_GATE_GUARD_TESTS tuple)
  - `tools/test_registry_groups_scheduler.py:161: "tests/regression_route_version_normalizers_contract.py",` (group target_paths)
- `tests/regression_system_history_route_contract.py`
  - `tools/test_registry_data.py:61: "tests/regression_system_history_route_contract.py",` (QUALITY_GATE_GUARD_TESTS tuple)
  - `tools/test_registry_groups_misc.py:189: "tests/regression_system_history_route_contract.py",` (group ui_layout_presenters_system target_paths)
- `tests/test_win7_launcher_runtime_paths.py`
  - `tools/test_registry_data.py:11: "tests/test_win7_launcher_runtime_paths.py",` (QUALITY_GATE_STARTUP_REGRESSION_ARGS tuple)

No function-name nodeid references were found for ANY proposed-deleted function across `tools/` and `tests/` (greps run per function, all empty). Shared helpers `_command_line_matches_exact_profile` / `_command_line_matches_installer_profile` / `_split_command_line_args` are used ONLY inside `test_win7_launcher_runtime_paths.py` — see win7 section for which trims keep them alive.

---

## 1. tests/regression_route_version_normalizers_contract.py — 130 lines

TSV reason (re-mapped): real `resolve_version_or_latest` + `parse_optional_version_int` algorithm (default/latest/explicit/no_history) is high value; the only brittle item is one verbatim full-Chinese-sentence equality. The cited "line35" is stale; the verbatim sentence is now at line 37.

Trim type: exact_chinese_snapshot — but a STABLE CODE ANCHOR exists (`VERSION_ERROR_MESSAGE` constant, imported at line 8 and already asserted by-identity at lines 124/129). So the verbatim string literal in `test_core_version_resolution_rejects_invalid_explicit_values` is a redundant snapshot that can be reduced to the constant + the structural `field` contract.

### KEEP (all real contract):
- Both parametrized algorithm tests `test_core_version_resolution_contract`, `test_parse_optional_version_int_contract` — branch outcomes (default/latest/explicit, 0/-1 passthrough).
- `test_parse_optional_version_int_rejects_non_integer_text` — keeps fragment `"期望整数" in ...message` (fragment, not full sentence → already non-brittle; KEEP as-is).
- `test_resolve_version_or_latest_no_history_does_not_synthesize_v1`, `test_resolve_version_or_latest_missing_explicit_version_is_not_selected`, `test_version_resolution_defaults_to_latest`, `test_version_resolution_accepts_latest_keyword`, `test_version_resolution_reports_missing_explicit_history` — status/has_history/requested_version invariants.
- `test_version_resolution_rejects_invalid_explicit_value` — asserts by `VERSION_ERROR_MESSAGE` identity + `field`; this is the canonical non-brittle form, KEEP untouched.

### TRIM (1 assert-line edit inside a KEPT function):
In `test_core_version_resolution_rejects_invalid_explicit_values`, replace the verbatim-sentence equality with the stable constant identity. The constant is already imported (`VERSION_ERROR_MESSAGE` at line 8). The function keeps its `field == "version"` assertion, so it retains meaningful behavioral coverage.

Anchor (delete this exact line):
```
    assert exc_info.value.message == "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。"
```
Replace with:
```
    assert exc_info.value.message == VERSION_ERROR_MESSAGE
```
Keep-context: the preceding `assert exc_info.value.field == "version"` line stays. Why-brittle: full UI sentence snapshot that fails on any copy reword, while the same guarantee is already pinned structurally by the `VERSION_ERROR_MESSAGE` constant elsewhere in this file. (If the implementer prefers zero behavior change, this single line may simply be DELETED outright — the `field=="version"` assert + the no-raise/raise structure still proves the validation contract. Net −1 either way.)

est lines removed: 0 net (line replaced) — counted as 0; if deleted instead, −1. Risk: low. No whole-function deletion.

---

## 2. tests/regression_system_config_dirty_fields_contract.py — 64 lines

TSV reason (re-mapped): real `SystemConfigService.get_snapshot` sanitization (yes/no + clamp min1/max365/default60 + dirty_reasons) is high value; brittle tail = the template-HTML-source grep at the end. Cited "line80-84" is stale; the template grep is now lines 60-63, inside the single test function `test_system_config_dirty_fields_contract`.

Trim type: js_source_grep / template-source snapshot (reads `templates/system/*.html` as text and asserts presence/absence of a Jinja expression).

### KEEP (all real contract, lines 8-58):
- snapshot normalization: `auto_backup_enabled == "yes"`, `interval == 1`, `keep_days == 365`, `log_cleanup == 60` (clamp/default branch outcomes).
- `expected_dirty.issubset(dirty_fields)` — structural invariant.
- the four `dirty_reasons` substring asserts (52-57): these are user-facing reason FRAGMENTS, but there is **no stable code/key anchor** for the reason text and they encode the sanitization-rule mapping (which clamp produced which reason). KEEP — under-trim is safe; these are differential, not cosmetic.
- `_dirty_field_label("new_internal_config_key") == "系统配置项"` (line 58) — passthrough/fallback behavioral contract. KEEP.

### TRIM (delete the template-source grep loop, lines 60-63):
This is the only brittle item. It reads two HTML templates as text and asserts a Jinja expression was removed/added — pure source-text snapshot that breaks on any template refactor without a behavior regression. After removing it the function still has 10+ meaningful behavioral asserts, so it never goes empty. Also remove the now-unused `from pathlib import Path` import (line 5) and the `repo_root` fixture param if it becomes unused (it is used ONLY by this loop).

Anchor (delete this exact block):
```
    for rel_path in ("templates/system/backup.html", "templates/system/logs.html"):
        text = Path(repo_root, rel_path).read_text(encoding="utf-8")
        assert "settings.dirty_field_labels or settings.dirty_fields" not in text, rel_path
        assert "dirty_labels | join" in text, rel_path
```
Follow-up edits (required to avoid unused-import / unused-arg lint):
- Delete line 5 `from pathlib import Path` (used only by the deleted block).
- Change signature `def test_system_config_dirty_fields_contract(db_path, repo_root) -> None:` → `def test_system_config_dirty_fields_contract(db_path) -> None:` (drop now-unused `repo_root` fixture). Verify no other reference to `repo_root` remains in the function (there is none).

Keep-context: keep everything from `assert snapshot.auto_backup_enabled == "yes"` through `_dirty_field_label(...) == "系统配置项"`.

est lines removed: ~6 (4-line loop + import line + arg edit). Risk: low.

---

## 3. tests/regression_system_history_route_contract.py — 340 lines

TSV reason (re-mapped): real history-route JSON logic + secret-redaction guard is high value; brittle = verbatim Chinese HTML-body phrase asserts (full rendered-page substrings via `_build_real_app`) + the template-source grep function. Cited "line241-325 / line327-338" — re-mapped below.

Trim type: mixed (full_page_text rendered-HTML substrings + template doc_snapshot).

### KEEP (high-value behavioral contract — DO NOT TOUCH):
- `test_system_history_route_uses_request_services` (116-153): JSON projection logic, request-service wiring, `version_limits==[30]/recent_limits==[20]` call-shape invariants, `code` field — KEEP entirely. (Its warning-text strings are echoed back from the stub input as data round-trip, not a UI snapshot — they ARE the projection contract here.)
- `test_system_history_route_exposes_warning_pipeline_display` (155-190): asserts a structured dict mapping (source/summary_merge_failed/counts). The two Chinese values (`"排产提示没有完整整理。"` / `"部分排产提示没有完整写入历史摘要。"`) are inside a STRUCTURED-DICT equality that also pins keys + booleans + counts. This is a presenter-mapping contract, not a free-floating UI snapshot. KEEP whole (do NOT split the dict — partial edit would break the `==` and lose the key/bool coverage).
- `test_system_history_route_zero_and_negative_versions_keep_exact_query_semantics` (192-210): 0/-1 passthrough query semantics + `selected is None` — KEEP.
- `test_system_history_route_surfaces_missing_version_message` (213-226): `selected_missing_version==999`, message present, query call shape — KEEP. (The `"v999 无对应排产历史"` here is a JSON-payload field value pinned alongside `selected_missing_version==999`, not a rendered-page snapshot → KEEP.)
- `test_system_history_route_rejects_non_integer_version` (229-240): **HTTP 400 + error code "1001"** — top-tier behavioral contract. KEEP. (Fragment `"version 不合法（期望整数）"` is a fragment + paired with code 1001 → KEEP.)

### SECRET-REDACTION asserts — KEEP (security contract, never trim):
Inside `test_system_history_page_renders_warning_pipeline_guard_html` and `test_system_history_page_hides_zero_warning_preview_button`, these are NOT brittle:
- `assert "summary_warnings_assignment_failed" not in html`
- `assert "INTERNAL_RESULT_SUMMARY_SECRET" not in html`
- `assert "sqlite" not in html`
- `assert "调试详情：原始摘要" not in html`
These are negative leak guards = security behavior. KEEP every one.

### TRIM (positive verbatim rendered-HTML phrase asserts inside KEPT real-app functions):
The brittle items are the POSITIVE substring asserts on full rendered HTML (these break on any template copy/markup reword). Trim only these, keeping each function's structural + redaction asserts so none goes empty.

`test_system_history_page_renders_warning_pipeline_guard_html` (243-274) — KEEP `status_code==200`, the `html.count("排产提醒：2 条") == 1` (count invariant — KEEP, it encodes de-dup rule), and ALL four negative leak guards. DELETE these positive-copy snapshot lines:
```
    assert "排产提醒整理状态：未完整整理" in html
    assert "排产提醒：2 条" in html
    assert "结果提醒：0 条" in html
    assert "部分排产提示没有完整写入历史摘要。" in html
```
and
```
    assert "告警 1 条" in html
    assert "摘要已加载；页面仅展示公开摘要、告警和处理提示。" in html
```
Keep-context: `assert response.status_code == 200` stays at top; `assert html.count("排产提醒：2 条") == 1` stays (NOTE: this count line references the same phrase as a deleted `in` line — keep the `.count(...)==1` line, delete only the bare `... in html` line). The four `not in html` redaction asserts stay. Function retains status + count-invariant + 4 redaction asserts → non-empty.

`test_system_history_page_hides_zero_warning_preview_button` (277-295) — KEEP `status_code==200`, the negative button-hiding asserts (`"提醒：1 条" not in`, `"查看前 0 条提醒" not in`, `"另有 1 条提醒" not in`, `"当前详情没有可安全展开的提醒明细" not in`, `"sqlite" not in`) — these encode the zero-preview branch rule + secret redaction, KEEP. DELETE only the two positive verbatim-copy asserts:
```
    assert "维护诊断：1 条" in html
```
and
```
    assert "这次没有需要调度员处理的业务提醒" in html
```
Why-brittle: positive Chinese UI copy with no stable key; the behavioral rule (button hidden, no leak) is fully covered by the surrounding `not in` asserts. (Conservative note: if the implementer judges `"维护诊断：1 条"` to encode the "diagnostics counted separately from business warnings" branch rule rather than mere copy, KEEP it — under-trim is safe. The clearer-brittle of the two is the long sentence `"这次没有需要调度员处理的业务提醒"`.)

`test_system_history_page_renders_missing_version_notice` (298-307) — KEEP. `"v999 无对应排产历史"` is the missing-version notice value also pinned in the JSON-route test; paired with `"摘要已加载" not in html`. This is a small load-bearing branch (missing version → notice, no summary). KEEP whole; do not trim (would leave only one assert and lose the branch). 

`test_system_history_version_dropdown_uses_completion_status_label` (310-326) — `html.count("模拟排产 / 部分成功") >= 2` and `"v3 · 部分成功"` and `"结果状态未知" not in html` encode the completion-status-label mapping rule (count >=2 = appears in dropdown AND row). This is presenter-mapping behavior, borderline. BIAS=KEEP whole — the count invariant + negative "未知" guard are real; trimming risks emptying the rule.

### TRIM (whole-function deletion) — `test_system_history_template_uses_presenter_status_fields` (329-340):
This entire function is a template-SOURCE grep (`history.html` read as text, asserting Jinja var names / route-name strings / a CSS class `aps-table--multiline` present/absent). Pure source snapshot — breaks on any template rename/refactor with no behavior regression. The presenter→template wiring it guards is already exercised behaviorally by the `_build_real_app` rendered-page tests above (which render through the real template and assert the projected values appear). 

grep result (function-name nodeid refs): NONE.
```
grep -rn "test_system_history_template_uses_presenter_status_fields" tools/ tests/  → (no hits outside this file)
```
File-path registry refs exist (test_registry_data.py:61, test_registry_groups_misc.py:189) but pin the FILE only; file keeps 8 other test functions after this deletion, so the path membership stays satisfied. Safe to delete the whole function.

Anchor (delete the entire function, lines 329-340):
```
def test_system_history_template_uses_presenter_status_fields() -> None:
    template = (REPO_ROOT / "templates" / "system" / "history.html").read_text(encoding="utf-8")

    assert "status_zh" not in template
    assert "status_zh.get" not in template
    assert "{{ v.version_option_label }}" in template
    assert "selected_summary_display.result_status_label" in template
    assert "r.result_summary_display.result_status_label" in template
    assert "scheduler.gantt_page', view='machine', version=version" in template
    assert "scheduler.week_plan_page', version=version" in template
    assert "scheduler.resource_dispatch_page', version=version" in template
    assert "aps-table--multiline" in template
```
Keep-context: this is the last function in the file; deleting it leaves 8 functions intact. Do not remove `REPO_ROOT` (still used by `_build_real_app`).

est lines removed: ~22 (whole template-grep function ~12 + 6 positive-copy lines in guard_html + 2 in hides_zero + blank lines). Risk: mid (file is a QUALITY_GATE_GUARD_TEST; we keep all JSON-route + redaction + 400/code contracts and the structured presenter-dict, so enforcement of real behavior is fully retained — only rendered-copy + template-source snapshots drop).

---

## 4. tests/regression_system_maintenance_invalid_last_run_visible.py — 45 lines

TSV reason (re-mapped): behavior = bad jobstate JSON/timestamp degrades gracefully (page does not crash, returns 200) BUT asserts verbatim Chinese HTML body phrases. Cited "line73-80" stale; the verbatim phrases are now at lines 38/39/45.

Trim type: full_page_text (rendered-HTML substring snapshot) — BUT this is the **mid-risk disguised-snapshot case**. The "real behavior" is "does not crash". The graceful-degradation NOTICE text is the only thing distinguishing "rendered a proper fallback notice" from "rendered a blank/garbage 200". There is NO stable code/key anchor for these notices.

### KEEP (do NOT trim the notice asserts):
- `_assert_status(...)` for both `/system/logs` and `/system/backup` → **HTTP 200 + no-crash** behavioral contract. KEEP.
- The three notice substring asserts (38/39/45): KEEP. Per the spec BIAS rule and the "if exact string IS the contract with no other anchor, KEEP it" rule — the fallback-notice text is the differential oracle that proves the bad-JSON/bad-timestamp path produced the *intended* graceful message rather than an empty 200. Removing them would reduce this test to a bare status check that a blank page would also pass, silently deleting the real coverage.

### TRIM: NONE.
This file is the case where the apparent "snapshot" is actually the behavioral oracle. No safe trim exists without a stable key (none present). Mark as a file we INSPECTED and deliberately keep whole. (The TSV mid verdict reflects exactly this tension; conservative outcome = no edit.)

est lines removed: 0. Risk: mid (documented no-op: trimming the notices would gut the graceful-degradation contract). whole-function deletions: none.

---

## 5. tests/test_migration_logging_fallback.py — 233 lines

TSV reason (re-mapped): real broken-logger resilience for migrations v1-v6 + ensure_schema sanitizes data + bumps version is high value; brittle tail = verbatim Chinese migration messages in stderr asserts. Cited "line117-229" — re-mapped to the `expected_stderr` parametrize column (119-123) + the per-test stderr substring asserts (139, 203, 231).

Trim type: exact_chinese_snapshot (stderr message strings). HOWEVER these are NOT pure UI copy — each `expected_stderr` is the differential oracle proving *which migration ran and that its fallback-to-stderr path fired when the logger raised*. The behavioral contract being tested is "broken logger → migration still completes AND emits its progress line to stderr". The message string IS what proves the stderr-fallback fired for the correct migration.

### KEEP (the structural resilience contract — never trim):
- `_BrokenLogger` / `_CollectingLogger` classes, all `_prep_vN` helpers, `_mem_conn` — shared fixtures, KEEP.
- `test_each_migration_falls_back_to_stderr_when_logger_is_broken` (126-141): the `assert logger.calls` (broken logger was invoked) + `assert expected_stderr in stderr` together = the fallback contract. KEEP both. The `expected_stderr` values are oracles, not cosmetic — KEEP.
- `test_v5_run_does_not_log_changed_rows_for_canonical_values` (144-163): `after - before == 0` (no-op on canonical values) + `not [... if "已修正" in msg]` — branch outcome (canonical → no change, no "已修正" log). KEEP. The `"已修正"` here is a NEGATIVE substring guard (assert it is ABSENT) tied to total_changes==0 → real differential, KEEP.
- `test_ensure_schema_migration_entry_path_survives_broken_logger` (166-203): sanitized data (`skill_level=="expert"`, `is_primary=="yes"`) + version bump (`>= CURRENT_SCHEMA_VERSION`) = top behavioral contract. KEEP. The closing `assert "数据库已备份" in stderr or "数据库迁移完成" in stderr` (203) is the stderr-fallback-fired oracle (already an OR over two phrases = somewhat resilient). KEEP.
- `test_v6_run_falls_back_to_stderr_when_logger_is_broken` (206-233): `assert logger.calls` + v6 column-add stderr oracle. KEEP.

### TRIM: NONE (conservative).
Every Chinese string in this file is bound to a behavioral oracle (broken-logger fallback fired for the right migration, or canonical no-op). There is no stable error-code/enum anchor for migration progress messages, so per the KEEP-when-no-stable-anchor rule, do not trim. This file's "brittle tail" is illusory: the strings carry the test's entire signal. Mark inspected, no edit.

est lines removed: 0. Risk: low (no-op; documented). whole-function deletions: none.

---

## 6. tests/test_plugin_enabled_source_contract.py — 100 lines

TSV reason (re-mapped): real plugin logic (optional plugins disabled by default + openpyxl default backend + `_apply_enabled_sources` config mapping + secret redaction) is high value; brittle tail = template/presenter source grep. Cited "line90-98" stale; the source-grep function is now lines 93-100.

Trim type: js_source_grep / template+presenter source snapshot.

### KEEP (all real contract, lines 23-91):
- `_status_by_id` helper — KEEP (used by kept tests).
- `test_real_optional_plugins_stay_disabled_without_config_and_openpyxl_remains_default` (23-39): enabled/loaded/enabled_source=="default" branch outcomes, capability-absence invariants, default backend class == OpenpyxlBackend. KEEP entirely.
- `test_apply_enabled_sources_keeps_explicit_config_source_and_public_error_message` (42-72): config-source mapping + **secret redaction** (`"SECRET_INTERNAL_TRACE" not in str(plugin_status)`) + public error message. KEEP. (The Chinese error message `"插件加载失败，请联系维护人员检查系统运行记录。"` at line 69 is paired with the redaction guard at 72 and IS the public-facing redaction contract — there is no error code anchor for it; KEEP per no-stable-anchor rule.)
- `test_apply_enabled_sources_summarizes_default_due_to_config_read_failed` (75-90): config_source summary enum == "default_due_to_config_read_failed". KEEP.

### TRIM (whole-function deletion) — `test_system_backup_template_mentions_plugin_conflicts_and_telemetry_state` (93-100):
Entire function reads `backup.html` template + `system_backup_page.py` presenter as TEXT and asserts Chinese-label / Python-identifier presence/absence. Pure source snapshot — breaks on any rename/markup change with no behavior regression. The presenter fields it greps (`telemetry_persisted`, `conflicted_capabilities`) are produced by `_apply_enabled_sources` whose output contract is already exercised behaviorally by the three kept tests.

grep result (function-name nodeid refs): NONE.
```
grep -rn "test_system_backup_template_mentions_plugin_conflicts_and_telemetry_state" tools/ tests/  → (no hits outside this file)
```
No file-path registry ref for this test file in tools/ either. Safe to delete the whole function.

Anchor (delete the entire function + its now-unused import):
```
def test_system_backup_template_mentions_plugin_conflicts_and_telemetry_state() -> None:
    template_text = (REPO_ROOT / "templates" / "system" / "backup.html").read_text(encoding="utf-8")
    presenter_text = (REPO_ROOT / "web" / "viewmodels" / "system_backup_page.py").read_text(encoding="utf-8")
    assert "冲突能力" in template_text
    assert "留痕状态" in presenter_text
    assert "telemetry_persisted" in presenter_text
    assert "conflicted_capabilities" in presenter_text
    assert "conflicted_capabilities" not in template_text
```
Follow-up: after deletion, `REPO_ROOT` (line 12) and `from pathlib import Path` (line 6) are STILL used by `test_real_optional_plugins_stay_disabled...` (passes `str(REPO_ROOT)` to `PluginManager.load_from_base_dir`) — DO NOT remove the import or REPO_ROOT. Keep-context: this is the last function; 3 functions remain.

est lines removed: ~9 (whole function + surrounding blank). Risk: low.

---

## 7. tests/test_win7_launcher_runtime_paths.py — 1921 lines

TSV reason (re-mapped): real launcher logic (path resolve, lock fail-closed, stop-runtime state classify, contract-override-endpoint, force-kill confirmed-pid-only, arg-parser adjacent-profile guard) spanning ~line 88-1582 is HIGH value; brittle = hardcoded facade hasattr LIST (cited 1584-1622, now `test_launcher_facade_exports_runtime_contract_surface` at 1587-1624) + grep of .bat/.iss/.ps1/.py SOURCE text (cited 1624-1919, now the block of functions 1627-1921).

Trim type: mixed — hardcoded member-list snapshot (facade) + js_source_grep (every `*_bat_*`, `*_installer_*`, `*_package_script_*`, `*_build_scripts_*`, `*_python_runtime_stop_*` function reads a `.bat`/`.iss`/`.ps1`/`.py` file as TEXT and asserts substring presence/absence).

### KEEP (the entire real-behavior block, lines 1-1585) — DO NOT TOUCH:
Functions 16-1551 exercise launcher behavior via imports + monkeypatched deps + tmp_path (real path resolution, runtime-lock fail-closed semantics, stop-runtime state classification, contract-vs-endpoint override, force-kill confirmed-pid-only, wait-for-stop recheck, CLI flag wiring at 1551). These are genuine algorithm/branch/security contracts. KEEP every one.
Also KEEP shared helpers used by behavior tests: `_split_command_line_args` (1189), `_command_line_matches_exact_profile` (1215), `_command_line_matches_installer_profile` (1224) — but NOTE their callers below.

### Shared-helper liveness check (decisive for trim boundary):
`_command_line_matches_exact_profile` is called inside `test_chrome_pid_query_script_matches_exact_user_data_dir_argument` (1239, KEEP — pure logic on the helper) AND inside the brittle `test_launcher_bat_chrome_alive_probe...` (1642) and `test_package_script_exposes_explicit_best_effort_cleanup_wrapper` (1766). `_command_line_matches_installer_profile` is called inside `test_installer_profile_patterns_reject_adjacent_profile_names` (KEEP) — verify before deleting any installer test. Because the helpers retain KEEP-test callers (1239, 1292), deleting the brittle source-grep functions does NOT orphan the helpers. Confirmed: helpers stay alive.

### TRIM (whole-function deletions) — the facade-list + source-grep block:
All of the following functions are pure snapshot tests (hardcoded member list, or read an asset/installer/build script as TEXT and grep substrings). They break on cosmetic .bat/.iss/.ps1 edits with no behavior regression, and the real launcher *behavior* is covered by the 1-1551 block. grep for EACH function name across `tools/ tests/` returned NO hits (function-name nodeid refs: NONE for all 19). File-path registry ref `tools/test_registry_data.py:11` pins the FILE only and is satisfied by the ~70 KEEP behavior tests that remain.

Delete these entire functions (anchor = the `def ...():` signature line, unique per function; delete from the `def` line through the line before the next top-level `def`):

1. `def test_launcher_facade_exports_runtime_contract_surface():` (1587-1624) — hardcoded_path_list snapshot of facade attribute names; behavior of each symbol is exercised by the import-based tests above. grep: no hits.
2. `def test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process():` (1627-1655) — .bat source grep. (helper calls inside it are redundant; helper stays alive via 1239/1292.)
3. `def test_launcher_bat_has_no_unescaped_rc_parentheses_in_if_blocks():` (1657-1664) — .bat source grep.
4. `def test_launcher_bat_digit_validation_does_not_echo_trailing_space_before_pipe():` (1666-1678) — .bat source grep.
5. `def test_launcher_bat_contains_json_health_probe_and_owner_fallback():` (1680-1706) — .bat source grep.
6. `def test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup():` (1708-1726) — .py source grep (greps launcher_processes/stop/chrome .py for identifiers/PowerShell snippets).
7. `def test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths():` (1728-1740) — .ps1 source grep.
8. `def test_package_script_exposes_explicit_best_effort_cleanup_wrapper():` (1742-1779) — .ps1 source grep.
9. `def test_installer_uninstall_stop_checks_multiple_runtime_roots():` (1781-1786) — .iss source grep.
10. `def test_installers_include_diagnostic_cmd_k_shortcut():` (1788-1795) — .iss source grep.
11. `def test_main_installer_contains_precleanup_and_skip_legacy_migration():` (1797-1807) — .iss source grep.
12. `def test_legacy_installer_uses_runtime_root_stop_contract():` (1809-1819) — .iss source grep.
13. `def test_installers_fail_closed_on_silent_uninstall_and_retry_delete():` (1821-1838) — .iss source grep.
14. `def test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only():` (1840-1845) — .iss source grep.
15. `def test_chrome_installer_stop_helper_matches_user_data_dir_argument_exactly():` (1847-1863) — .iss source grep.
16. `def test_chrome_installer_stop_helper_uses_current_user_profile_path_marker():` (1865-1872) — .iss source grep.
17. `def test_chrome_installer_stop_helper_uses_final_remaining_process_check():` (1874-1880) — .iss source grep.
18. `def test_build_scripts_guard_vendor_and_launcher_path():` (1882-1916) — .bat/.ps1 source grep (NOTE: this one imports `_ROUTE_MODULES` and loops asserting `--hidden-import` strings present in build scripts — still a source-text snapshot; the route-module registration behavior is covered elsewhere by scheduler route-registration contract tests. Delete.)
19. `def test_chrome_installer_remains_non_target_for_precleanup():` (1918-1921, file end) — .iss source grep.

Keep-context: after deleting functions 1-19 (lines 1587 through EOF), the file ends cleanly at line 1585 (the blank line after `test_runtime_stop_cli_passes_stop_aps_chrome_flag`'s final assert at 1584). All ~70 behavior tests + the 3 shared helpers + their KEEP callers (1239, 1255, 1292) remain. No import becomes unused: `Path` is used throughout the KEEP block (tmp_path round-trips, `_repo_root`), `List` used by `_split_command_line_args`. Verify `_command_line_matches_exact_profile`/`_command_line_matches_installer_profile` still have callers at 1239/1292 (they do) before finalizing.

CAUTION (not a hard block, but note in PR): deleting #6 `test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup` removes the only guard that the launcher .py files use PowerShell-not-wmic and fail-closed wording. This is a source-grep, not behavior — its loss is acceptable per KEEP_TRIM scope, but flag it so reviewer can confirm a behavior-level test covers the PowerShell path (the stop-runtime behavior tests at 884/934/1363/1396 cover the fail-closed cleanup behavior; the wmic→powershell choice itself is only source-grepped). If reviewer wants belt-and-suspenders, KEEP #6 only. Everything else is clean to delete.

est lines removed: ~335 (lines 1587-1921 = 335 lines, the full facade-list + source-grep tail). Risk: mid (large deletion, but all source-text snapshots; behavior fully covered by the 1-1585 block; file-path registry membership preserved by remaining tests).

---

## Batch totals
- whole-function deletions: 21 (1 in #3, 1 in #6, 19 in #7). All grep-clean (no function-name nodeid refs anywhere).
- assert-line-only trims: #1 (1 line), #3 (6 positive-copy lines across 2 kept functions).
- no-op (inspected, deliberately KEEP whole): #4, #5.
- est net lines removed across batch: ~370.
- File-path registry coupling on #1 (route_version_normalizers), #3 (system_history_route), #7 (win7) — all satisfied because each file keeps ≥1 (in fact many) passing test functions; do NOT delete or empty any file.
