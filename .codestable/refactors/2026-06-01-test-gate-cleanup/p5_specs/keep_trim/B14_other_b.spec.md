# KEEP_TRIM Spec — Batch B14_other_b

Phase P5.2 KEEP_TRIM. Each file below has real contract value mixed with brittle source-text / template-grep / exact-Chinese-snapshot tails. This spec is content-anchored: an implementation agent should locate the verbatim anchor strings (not raw line numbers — files may have shifted) and apply the stated deletions, keeping everything else.

Registry coupling note (applies to whole batch): the only two batch files referenced by registry machinery are `tests/regression_web_silent_fallback_contract.py` (tools/test_registry_data.py:94, tools/test_registry_groups_scheduler.py:284) and `tests/test_holiday_default_efficiency_read_guard.py` (tools/test_registry_data.py:214, tools/test_registry_groups_scheduler.py:102). Both references are **FILE-PATH list entries**, NOT function-nodeid lists — so trimming interior functions is safe **as long as each file keeps existing with at least one test**. Neither file is fully deleted here. No function-level nodeid is referenced anywhere in tools/ or tests/ for any candidate in this batch.

---

## 1. tests/regression_v2_strategy_zh_contract.py

- Current line count: **46**
- Single test function: `test_v2_strategy_zh_contract` (lines 15-46).
- TSV reason: "strict_strategy_display_label mapping real (line 28) but rest greps templates for literal label tokens + absence of strategy_zh (line 37-50) brittle".
- Grep result for `test_v2_strategy_zh_contract` in tools/ & tests/ (excluding self): **no hits** → not referenced by any registry/contract machinery.

### Classification & decision

This is a single function with three blocks. The reason flags the two template-grep blocks as brittle. Re-mapped to current content:

**KEEP — real behavioral contract (the helper mapping):** lines 17-25, the `expected` dict + the loop calling `strict_strategy_display_label(key)` and raising on mismatch. This asserts the presenter helper actually maps the 4 strategy codes to the 4 Chinese labels. This is real algorithm/branch behavior (catches a genuine mapping bug). KEEP.

**BRITTLE item A — gantt.html literal-token grep (the "still inlined" assertion).** This reads `web_new_test/templates/scheduler/gantt.html` as text and asserts the verbatim Python-dict-literal token `'priority_first': '优先级优先'` (etc.) is present in the template. It fails on any cosmetic reformatting of the template (quote style, spacing, key order) without any behavior regression. The "contract" it encodes — that gantt.html still owns its own inline mapping — is a structural-debt marker, not a user-facing guarantee.

- Anchor (delete this whole block):
  ```python
      gantt_files = [
          os.path.join(repo_root, "web_new_test", "templates", "scheduler", "gantt.html"),
      ]
      for path in gantt_files:
          text = _read(path)
          for key, label in expected.items():
              token = f"'{key}': '{label}'"
              if token not in text:
                  raise RuntimeError(f"模板缺少 strategy_zh 映射：{os.path.relpath(path, repo_root)} -> {token}")
  ```
- Keep-context: keep the `expected` dict + helper-mapping loop above it; delete this block.

**BRITTLE item B — presenter-owned-templates absence grep.** Reads three templates and asserts the substrings `strategy_zh`/`status_zh`/`mode_zh`/`*.get` are ABSENT. Pure source-text grep on rendered templates; fails on any incidental token reuse, comment, or rename. Structural-drift only.

- Anchor (delete this whole block):
  ```python
      presenter_owned_templates = [
          os.path.join(repo_root, "templates", "scheduler", "batches.html"),
          os.path.join(repo_root, "web_new_test", "templates", "scheduler", "batches.html"),
          os.path.join(repo_root, "templates", "system", "history.html"),
      ]
      for path in presenter_owned_templates:
          text = _read(path)
          for token in ("strategy_zh", "status_zh", "mode_zh", "status_zh.get", "strategy_zh.get", "mode_zh.get"):
              if token in text:
                  raise RuntimeError(f"已收口页面不应继续在模板里维护本地状态映射：{os.path.relpath(path, repo_root)} -> {token}")
  ```
- Keep-context: this is the tail of the function; delete it, leaving the helper-mapping loop as the last block. The kept function still has a meaningful assertion (the mapping check), so it is not left empty.

**Note on `_read` helper:** after deleting both grep blocks, the module-level `_read` helper (lines 10-12) becomes unused. Leave it in place to avoid risk (an unused private helper is harmless and removing it is a separate cosmetic call); OR delete lines 10-12 if the implementation agent confirms no other use — low value. RECOMMEND: leave `_read` to stay conservative. `os` import also becomes unused except `REPO_ROOT`; `REPO_ROOT`/`os.path` still used at line 16 (`repo_root = REPO_ROOT`) so keep `import os`.

- est lines removed: ~18 (two blocks, ~8 + ~10 lines).
- Risk: **low**. The kept mapping assertion is the genuine contract; both deleted blocks are source-text greps.

---

## 2. tests/regression_web_silent_fallback_contract.py

- Current line count: **472**
- TSV reason: "core asserts real no-silent-fallback: safe_float/parse_failed flags + NaN/Infinity not leaked + ValidationError raises (line 38-419) but 3 fns grep week_plan/overview templates (line 424-456) brittle".
- Registry coupling: file path appears at tools/test_registry_data.py:94 and tools/test_registry_groups_scheduler.py:284 (file-level, not nodeid). File retains 8 real test functions → safe.
- Grep results for the 3 candidate functions (`test_week_plan_template_does_not_fallback_to_raw_result_status`, `test_week_plan_selected_strategy_uses_public_display_label`, `test_scheduler_analysis_selected_overview_keeps_zero_time_budget`): **no hits** in tools/ or tests/ → no nodeid coupling.

### KEEP — real behavioral contracts (untouched, lines 37-422 and 461-472)

These exercise live code paths and assert real behavior; all KEEP:
- `test_scheduler_trend_numeric_helpers_only_swallow_parse_errors` (37) — safe_float/safe_int default vs RuntimeError propagation. Real.
- `test_scheduler_trend_summary_reports_bad_version_rows` (63) — bad-version filtering + parse_failed_count. Real.
- `test_scheduler_analysis_candidate_metrics_do_not_leak_raw_bad_values` (81) — parse_failed flags + NaN/Infinity/bad_metric_value not leaked into display. Real security/leak contract. (The `"记录异常"`/`"无法安全对比"` substring asserts here are the no-leak guardrail oracle — KEEP, they are the contract, not cosmetic copy.)
- `test_scheduler_analysis_attempt_and_diagnostic_bool_numbers_are_visible_errors` (176) — bool-as-number rejected, raw `True`/`布尔值` not leaked. Real.
- `test_report_numeric_helpers_keep_empty_values_but_reject_bad_service_numbers` (225) — many ValidationError/ReportPresentationValueError raises + field-name-not-leaked. Real.
- `test_system_time_range_and_job_detail_parse_errors_stay_visible` (287) — time-range validation + bad-json detail handling. Real.
- `test_report_context_parse_failure_blocks_row_feedback_links` (315) — can_dispatch/can_write_feedback forced False on parse failure + disabled link. Real security/guardrail.
- `test_report_plan_status_keeps_parse_failure_and_historical_reasons` (353) / `..._exposes_non_executable_official_result` (381) — status-text branch outcomes + raw reason-code not leaked. Real (these assert branch logic + leak prevention; the Chinese substrings are the differential between branches, not a fixed-copy snapshot — KEEP).
- `test_resource_dispatch_parse_failure_overrides_stale_write_flags` (398) — stale write-flag override + leak prevention. Real.
- `test_scheduler_analysis_time_budget_labels_reject_bad_values` (461) — `_time_budget_seconds_label/_display` branch outcomes (0/"30"/None/"  "/False/"1.5"). Real algorithm behavior. KEEP.

### BRITTLE — three template source-text grep functions (DELETE WHOLE)

These three functions do `(REPO_ROOT / ... .html or .py).read_text()` and assert verbatim Jinja-expression substrings present/absent. They fail on any template re-edit (rename of a display var, whitespace, quote style) with zero behavior regression. The actual behavior they gesture at (public display labels instead of raw fallback) is already covered by the VM-level tests kept above (`_time_budget_seconds_label`, candidate display, report_plan_status). These are pure source-grep snapshots → delete whole functions.

**BRITTLE B1 — DELETE whole function `test_week_plan_template_does_not_fallback_to_raw_result_status`** (currently lines 425-433).
- Anchor (delete entire function, def line through last assert):
  ```python
  def test_week_plan_template_does_not_fallback_to_raw_result_status() -> None:
      source = (REPO_ROOT / "templates" / "scheduler" / "week_plan.html").read_text(encoding="utf-8")

      assert "v.result_status or '-'" not in source
      ...
      assert "selected_summary_display.result_status_label or status_zh.get(selected_history.result_status, '结果状态未知')" in source
  ```
- grep result: no external reference. Safe to delete.

**BRITTLE B2 — DELETE whole function `test_week_plan_selected_strategy_uses_public_display_label`** (currently lines 436-447).
- Anchor (delete entire function):
  ```python
  def test_week_plan_selected_strategy_uses_public_display_label() -> None:
      template_source = (REPO_ROOT / "templates" / "scheduler" / "week_plan.html").read_text(encoding="utf-8")
      ...
      assert "format_public_datetime(selected_history.get(\"schedule_time\"))" in route_source
  ```
- grep result: no external reference. Safe to delete.

**BRITTLE B3 — DELETE whole function `test_scheduler_analysis_selected_overview_keeps_zero_time_budget`** (currently lines 450-458).
- Anchor (delete entire function):
  ```python
  def test_scheduler_analysis_selected_overview_keeps_zero_time_budget() -> None:
      source = (REPO_ROOT / "templates" / "scheduler" / "analysis_parts" / "_selected_overview.html").read_text(
          encoding="utf-8"
      )

      assert "algo.time_budget_seconds or '-'" not in source
      ...
      assert "algo_config_snapshot_time_budget_seconds_display" in source
  ```
- grep result: no external reference. Safe to delete.

**Import note:** after deleting B1-B3, `REPO_ROOT` (line 13) is still used by no remaining test? Check: the kept tests import their targets internally and use `pytest`, `Flask`, `g`, `SimpleNamespace`, `ValidationError`, `Path`. `REPO_ROOT = Path(...).parents[1]` is only consumed by the three deleted template-readers. After deletion `REPO_ROOT` becomes unused but is a harmless module constant — LEAVE it (removing it risks nothing but is cosmetic; conservative = keep). `Path` import is still referenced by the `REPO_ROOT` definition, so keep both. Do NOT remove `from pathlib import Path` or `REPO_ROOT`.

- est lines removed: ~32 (three functions, ~9 + ~12 + ~9 incl. trailing blank lines between them).
- Risk: **low**. Three pure source-grep functions deleted; all genuine no-silent-fallback behavior remains covered by the 10 kept VM/route tests.

---

## 3. tests/test_enum_display_consistency.py  ⚠ B-COMPAT B-4 RED LINE

- Current line count: **63**
- Single test function: `test_enum_display_wrappers_expected_outputs` (lines 6-63), one big assert block.
- TSV reason + B-4 safeguard: real enum_display_zh wrapper behavior (trim / unknown-passthrough / None-fallback) is VALUABLE; exact label pairs (active=可用 etc.) are a translation-table snapshot. **R41 needs the bad-value / None / passthrough rows as a differential oracle before its loud-error refactor.** Stale cited lines :18/:19-20/:23/:59-61 → re-map to SEMANTIC rows, not raw numbers.
- Grep result for `test_enum_display_wrappers_expected_outputs`: **no hits** externally.
- **b4_redline = TRUE.** This is row-level surgery inside the single kept function — NOT a whole-function delete.

### Re-mapped semantic rows — MUST KEEP (the R41 differential oracle)

For EACH wrapper, keep: every **trim/whitespace** row (`"  active  "` → normalized), every **unknown/passthrough** row (`"weird"` → either echoed back or mapped to a default), every **empty-string** row (`""` → placeholder/default), every **None** row (`None` → placeholder/default). These encode behavior (normalization + fallback policy) and are R41's oracle.

Concretely KEEP these current lines:
- machine: `machine_status_zh("  active  ") == "可用"` (19, trim), `machine_status_zh("weird") == "weird"` (20, passthrough), `machine_status_zh("") == "-"` (21, empty), `machine_status_zh(None) == "-"` (22, None).
- operator: `operator_status_zh("  inactive ") == "停用/休假"` (26), `operator_status_zh("weird") == "weird"` (27), `operator_status_zh("") == "-"` (28), `operator_status_zh(None) == "-"` (29).
- day_type: `day_type_zh("  weekend  ") == "假期"` (34), `day_type_zh("WorkdayX") == "WorkdayX"` (35), `day_type_zh("") == "-"` (36), `day_type_zh(None) == "-"` (37).
- batch: `batch_status_zh("  pending  ") == "待排"` (44), `batch_status_zh("weird") == "weird"` (45), `batch_status_zh("") == "-"` (46), `batch_status_zh(None) == "-"` (47).
- priority: `priority_zh("  urgent  ") == "急件"` (52), `priority_zh("weird") == "未知"` (53), `priority_zh("") == "普通"` (54), `priority_zh(None) == "普通"` (55).
- ready: `ready_zh("  yes  ") == "齐套"` (60), `ready_zh("weird") == "未齐套"` (61), `ready_zh("") == "未齐套"` (62), `ready_zh(None) == "未齐套"` (63).

### BRITTLE — pure happy-path label-mapping rows to DELETE (translation-table snapshot)

These map a canonical lowercase code straight to its Chinese label with no normalization/fallback semantics — they are the translation table itself, the thing R41 will rewrite. Delete ONLY these exact lines:

- `assert machine_status_zh("active") == "可用"` (16)
- `assert machine_status_zh("maintain") == "维修"` (17)
- `assert machine_status_zh("inactive") == "停用"` (18)
- `assert operator_status_zh("active") == "在岗"` (24)
- `assert operator_status_zh("inactive") == "停用/休假"` (25)
- `assert day_type_zh("workday") == "工作日"` (31)
- `assert day_type_zh("holiday") == "假期"` (32)
- `assert day_type_zh("weekend") == "假期"` (33)
- `assert batch_status_zh("pending") == "待排"` (39)
- `assert batch_status_zh("scheduled") == "已排"` (40)
- `assert batch_status_zh("processing") == "加工中"` (41)
- `assert batch_status_zh("completed") == "已完成"` (42)
- `assert batch_status_zh("cancelled") == "已取消"` (43)
- `assert priority_zh("critical") == "特急"` (49)
- `assert priority_zh("urgent") == "急件"` (50)
- `assert priority_zh("normal") == "普通"` (51)
- `assert ready_zh("yes") == "齐套"` (57)
- `assert ready_zh("partial") == "部分齐套"` (58)
- `assert ready_zh("no") == "未齐套"` (59)

Each anchor is the verbatim single assert line (unique within the file). Keep-context: within each wrapper's group, delete the canonical-code rows above but KEEP the trim/passthrough/empty/None rows listed in the prior section. Every wrapper retains at least 4 meaningful asserts → no group left empty, function not left empty.

- **WHEN IN DOUBT, KEEP** (per B-4). I deliberately KEEP all `"weird"` passthrough rows including `priority_zh("weird") == "未知"` and `ready_zh("weird") == "未齐套"` (these are fallback-policy rows, not pure label mapping — they show what an UNKNOWN value resolves to, which is exactly R41's differential oracle).
- assert-only trim count: **19** (within-function line removals; function kept).
- est lines removed: **19**.
- Risk: **mid** (B-4 red line; semantic re-mapping required — do not delete by raw line number, match the verbatim assert text).

---

## 4. tests/test_holiday_default_efficiency_read_guard.py

- Current line count: **612**
- TSV reason: "core real: invalid cfg degraded-not-repaired row-count invariants + reject-no-write upsert/preview (line 353-410) but verbatim full Chinese error equality (line 184-239) + calendar_picker.js grep (line 444) brittle".
- Registry coupling: file path at tools/test_registry_data.py:214 and tools/test_registry_groups_scheduler.py:102 (file-level, not nodeid). File retains all behavioral tests → safe.
- Grep result for `test_calendar_picker_js_does_not_rebuild_local_0_8_default`: **no hits** externally → no nodeid coupling.

### KEEP — real behavioral contracts (untouched)

- `test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid` (246) — status 200 + degraded warning shown + internal key `holiday_default_efficiency` NOT leaked + JSON `holidayDefaultEfficiency: null` (not silently 0.8) + logger warning emitted. Real degrade-not-repair + leak contract. KEEP all asserts (the `"假期工作效率"` / `"页面已临时按"` / `"继续依赖该默认值进行操作"` substrings here are guardrail-presence checks against a degraded path, not fixed-copy snapshots — KEEP).
- `test_scheduler_config_page_shows_degraded_warning...` (285) — status + form field + `value="0.8"` fallback + warning card. Real.
- `test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2` (305) — multi-field degrade summary + `>= 3` inline warnings count (count encodes a rule). Real.
- `test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config` (342, parametrized) — **the core invariant**: read routes do NOT repair a deleted config key (row-count before==after, missing key stays missing). Real transaction/no-side-effect contract. KEEP entirely.
- `test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2` (369) — v1/v2 both render the toggle copy + "已关闭" state. Real branch behavior. KEEP.
- `test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain` (387) / `test_operator_calendar_upsert_rejects...` (415) — POST rejected, no row written (`WorkCalendar`/`OperatorCalendar` count == 0), success copy absent. Real reject-no-write security contract. KEEP.
- `test_scheduler_excel_calendar_preview_and_confirm_reject_invalid...` (449) / `test_operator_calendar_excel_preview_and_confirm_reject...` (495) — preview+confirm reject + no `raw_rows_json` re-emitted. Real. KEEP.
- `test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read` (551) / `test_operator_calendar_excel_preview_bootstraps...` (576) — first-access bootstrap writes config (`ScheduleConfig > 0`). Real. KEEP.

### BRITTLE item A — verbatim full-Chinese error-string equality (row-level trim, KEEP the functions)

`test_calendar_excel_row_errors_use_plain_column_copy` (172) and `test_operator_calendar_excel_row_errors_use_plain_column_copy` (204) assert `error == "<entire two-sentence Chinese paragraph>"`. The full-paragraph equality is a copy snapshot: it fails on any wording polish ("尽量" → "会", punctuation) with no behavior regression. BUT there IS a real contract here: the error must (1) be non-None for a bad value, and (2) reference the **plain column name** (`"类型"` / `"允许普通件"` / `"允许急件"`) rather than an internal key — that is the "plain column copy" guarantee in the function name. So this is row-level surgery: replace exact-equality with a key-fragment containment + non-None check. KEEP the functions; trim the brittle exact-string tails.

There is NO ErrorCode/enum anchor for these calendar-row validators (they return a plain user-facing string, no code) — so per the brittle rule we KEEP a stable key fragment (the quoted column name + the recommendation tokens), NOT the whole paragraph.

**A1 — `test_calendar_excel_row_errors_use_plain_column_copy` (~172-201).** For each of the three `assert X_error == ("…长文案…")` blocks, replace with a containment check on the stable column-name fragment and the recommendation core. Recommended rewrite per block:
- type_error: replace `assert type_error == (...)` with
  ```python
      assert type_error is not None and "“类型”" in type_error and "工作日 / 假期" in type_error
  ```
- normal_error: replace with
  ```python
      assert normal_error is not None and "“允许普通件”" in normal_error and "是 / 否" in normal_error
  ```
- urgent_error: replace with
  ```python
      assert urgent_error is not None and "“允许急件”" in urgent_error and "是 / 否" in urgent_error
  ```
- Anchor for each deletion = the verbatim `assert <name>_error == (` line plus its parenthesized multi-line string literal through the closing `)`. Keep the `validate_calendar_import_row(...)` call lines above each.

**A2 — `test_operator_calendar_excel_row_errors_use_plain_column_copy` (~204-243).** Same pattern for its three `assert <name>_error == (...)` blocks; rewrite to the same containment form (column-name fragment + `工作日 / 假期` for type, `是 / 否` for normal/urgent). Keep the `_build_app` / `_seed_operator` / `get_operator_calendar_row_validate_and_normalize` scaffolding and the `validate({...})` calls.

> NOTE: A1/A2 are the lower-confidence trims in this batch. If the implementation agent prefers maximum safety, it MAY keep these exact-string asserts (the column-name guarantee is genuine and the copy is fairly stable). Marking them brittle is defensible because the failure mode on copy polish is cosmetic and the plain-column-name contract survives the containment rewrite. Counted as assert-level trims (functions kept).

### BRITTLE item B — calendar_picker.js source-text grep (DELETE WHOLE FUNCTION)

`test_calendar_picker_js_does_not_rebuild_local_0_8_default` (444-446) reads `static/js/calendar_picker.js` as text and asserts `": 0.8;" not in source`. Pure JS-source grep; fails on any JS reformat (spacing `: 0.8 ;`, minify, rename) and the "don't rebuild local default" intent is a structural-debt marker with no runtime oracle here. The real degrade-not-repair behavior is fully covered by the kept route/preview tests above (which assert the page does NOT silently substitute 0.8). Delete whole function.

- Anchor (delete entire function):
  ```python
  def test_calendar_picker_js_does_not_rebuild_local_0_8_default() -> None:
      source = (REPO_ROOT / "static" / "js" / "calendar_picker.js").read_text(encoding="utf-8")
      assert ": 0.8;" not in source, "calendar_picker.js 不应在前端重建 0.8 本地默认值"
  ```
- grep result: no external reference. Safe to delete.
- Import note: `REPO_ROOT`, `Path`, `openpyxl`, `json`, `io`, `importlib` all remain used by other kept tests → no import cleanup needed.

- whole functions deleted: `test_calendar_picker_js_does_not_rebuild_local_0_8_default` (1).
- assert-only trim count: **6** (3 exact-string asserts in A1 + 3 in A2, each rewritten to containment; functions kept).
- est lines removed: ~30 (JS function ~4 lines net incl. blanks; A1+A2 collapse ~6 multi-line string-literal blocks of ~5-6 lines each down to one-line asserts → ~26 net).
- Risk: **mid** — the JS-grep deletion is low risk; the A1/A2 exact-string→containment rewrite is the judgment call (genuine plain-column-name contract preserved, only the cosmetic full-paragraph equality dropped). No registry nodeid coupling.

---

## 5. tests/test_source_merge_mode_constants.py

- Current line count: **108**
- TSV reason: "real compute_utilization/compute_downtime_impact only-internal-source filter (line 42-84) but test_target_files_have_no...quoted_literals greps 5 src files for 'internal' token (line 92-106) brittle".
- Grep result for `test_target_files_have_no_source_merge_mode_quoted_literals`: **no hits** externally → no nodeid coupling.

### KEEP — real behavioral contracts (untouched)

- `test_compute_utilization_only_counts_internal_source` (12-45) — feeds INTERNAL + EXTERNAL rows, asserts only the INTERNAL machine/operator survive (`["MC1"]` / `["OP1"]`). Real algorithm/filter behavior. KEEP.
- `test_compute_downtime_impact_only_counts_internal_source` (48-86) — only INTERNAL schedule rows count toward downtime overlap (`len(items) == 1`, overlap > 0). Real. KEEP.

### BRITTLE — source-file quoted-literal grep (DELETE WHOLE FUNCTION)

`test_target_files_have_no_source_merge_mode_quoted_literals` (89-108) opens 5 source files (`schedule_optimizer.py`, `freeze_window.py`, `calculations.py`, `process_parts.py`, `process_excel_op_types.py`) and asserts the quoted tokens `'internal'` / `"internal"` (etc.) do NOT appear. This is a hardcoded-path-list source-text grep / anti-drift snapshot: it fails whenever a source file is moved/renamed or legitimately mentions the token in a new context, and the "no bare literal" guarantee is a structural-debt marker, not a behavioral oracle. The genuine semantic-drift protection (that only INTERNAL counts) is already enforced by the two kept compute_* tests which use the imported `INTERNAL`/`EXTERNAL`/`MERGED`/`SEPARATE` constants directly. Delete whole function.

- Anchor (delete entire function, including its docstring):
  ```python
  def test_target_files_have_no_source_merge_mode_quoted_literals() -> None:
      """
      防漂移：这些文件里不应再出现 source/merge_mode 控制值的裸字符串字面量。
      （允许在错误提示文案中出现 internal/external 子串，因此只匹配带引号 token：'internal' / "internal"）
      """
      repo_root = Path(__file__).resolve().parents[1]
      targets = [
          repo_root / "core/services/scheduler/run/schedule_optimizer.py",
          ...
          repo_root / "web/routes/process_excel_op_types.py",
      ]

      tokens = (INTERNAL, EXTERNAL, MERGED, SEPARATE)
      for p in targets:
          text = p.read_text(encoding="utf-8")
          for t in tokens:
              assert f"'{t}'" not in text, f"{p.as_posix()} 存在裸字符串 {t!r}"
              assert f'"{t}"' not in text, f"{p.as_posix()} 存在裸字符串 {t!r}"
  ```
- grep result: no external reference. Safe to delete.
- **Import note:** after deleting this function, `EXTERNAL` is still used by the two kept compute_* tests (rows with `"source": EXTERNAL`), and `INTERNAL` too. But `MERGED` and `SEPARATE` are ONLY referenced inside the deleted function's `tokens` tuple. `from pathlib import Path` is also ONLY used by the deleted function (the kept tests use `datetime` and dict literals). After deletion:
  - KEEP `from core.algorithms.value_domains import EXTERNAL, INTERNAL, MERGED, SEPARATE` AS-IS to avoid touching the import line / risk of breaking — `MERGED`/`SEPARATE` becoming unused is a harmless lint-only condition, NOT an import error. CONSERVATIVE recommendation: leave the import unchanged.
  - `from pathlib import Path` becomes unused after deletion. It is safe to leave (harmless unused import) OR remove. RECOMMEND leaving it to stay minimal-touch; if the repo runs an unused-import gate (flake8 F401) the implementation agent should then narrow `value_domains` import to `EXTERNAL, INTERNAL` and drop `from pathlib import Path`. Flag: verify whether F401 is enforced before trimming imports.

- whole functions deleted: `test_target_files_have_no_source_merge_mode_quoted_literals` (1).
- assert-only trim count: 0.
- est lines removed: ~20.
- Risk: **low** — pure source-grep function; semantic-drift contract still covered by the kept value-domain-constant-based compute_* tests. (Mild caveat: if a strict unused-import gate exists, an import-line follow-up is needed — noted above.)

---

## Batch totals

- Files: 5
- Whole functions deleted: 5 total — `test_week_plan_template_does_not_fallback_to_raw_result_status`, `test_week_plan_selected_strategy_uses_public_display_label`, `test_scheduler_analysis_selected_overview_keeps_zero_time_budget` (file 2); `test_calendar_picker_js_does_not_rebuild_local_0_8_default` (file 4); `test_target_files_have_no_source_merge_mode_quoted_literals` (file 5).
- Assert-only trims (functions kept): file 1 (2 grep blocks inside the kept function), file 3 (19 label-mapping rows, B-4), file 4 (6 exact-string→containment rewrites).
- Registry/contract nodeid coupling: NONE (only file-path-level registry entries for files 2 & 4; both files keep ≥1 test).
- B-4 red line: file 3 (`test_enum_display_consistency.py`).
- Est net lines removed across batch: ~119.
