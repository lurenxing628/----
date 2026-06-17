# KEEP_TRIM spec — batch B11_sys_a

Branch: cleanup/p3-main-style-to-pytest
Authored by: recon analyst (P5.2). Implementation agent must apply ONLY what is marked TRIM; everything else is KEEP.

Files in batch (3):
1. tests/regression_analysis_page_version_default_latest.py (160 lines)
2. tests/regression_config_field_spec_contract.py (322 lines, last line 323 has no trailing newline)
3. tests/regression_config_manual_markdown.py (740 lines, last line 741)

## Registry / contract coupling (applies to all 3 files)

All three files are registered at FILE level (target_paths / gate file lists), NOT at function/nodeid level. Grep results (verbatim, recorded per-file below):
- tools/test_registry_data.py:42  "tests/regression_config_field_spec_contract.py",
- tools/test_registry_data.py:57  "tests/regression_analysis_page_version_default_latest.py",
- tools/test_registry_groups_scheduler.py:94  "tests/regression_config_field_spec_contract.py",
- tools/test_registry_groups_scheduler.py:251  "tests/regression_analysis_page_version_default_latest.py",
- tools/quality_gate_shared.py:144 / :812 / :822  "tests/regression_config_manual_markdown.py"

Implication: as long as each FILE keeps existing and keeps at least one meaningful passing test, none of these references dangle. Per-function grep (`grep -rn "<funcname>" tools/ tests/` excluding the file itself) returned ZERO hits for every test function in all three files — no function name / nodeid is hardcoded anywhere. So whole-function deletion would NOT dangle a registry reference; the only constraint is "don't empty the file / don't gut the registered gate's contract value". We respect that by trimming conservatively and never deleting whole functions here.

---

## File 1: tests/regression_analysis_page_version_default_latest.py — VERDICT: NO-TRIM (keep as-is)

Line count: 160.
TSV reason (B11_sys_a, mid): "real version-resolution+400/200 status logic but trailing HTML snapshot asserts (aps-summary-value v7 at line62; exact zh error text line81)".

Re-mapping the cited anchors to current content:
- "aps-summary-value v7 at line62" maps to current lines 64, 71, 78: `assert 'aps-summary-value">v7' in html` (repeated for default / `?version=` empty / `?version=latest`).
- "exact zh error text line81" maps to current line 83: `assert "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。" in invalid_html`.

### Decision: KEEP everything. Rationale per cited "brittle" item:

1. `aps-summary-value">v7` (lines 64, 71, 78) — looks like an HTML/class snapshot, but it is the load-bearing assertion of the version-RESOLUTION contract: missing / empty / `latest` must all resolve to the newest version (v7). Trimming the class prefix down to a bare `"v7" in html` would make the assertion match incidental noise (v7 can appear in dropdown lists, trend captions, etc.) and weaken a real branch-outcome oracle. The class literal `aps-summary-value">` anchors it to the summary value cell specifically. Net: this is a real contract, not a cosmetic snapshot. KEEP.
   - Note: line 97 `assert 'aps-summary-value">v999' not in html` and line 96 `assert "v999 无对应排产历史" in html` together encode the "do not fake a selected version" rule — definitely KEEP.

2. Exact Chinese error sentence (line 83) — this is the ONE borderline-brittle item. It is a full-sentence UI copy snapshot. HOWEVER:
   - There is NO ErrorCode / stable key available for this 400 message (the route returns plain user-facing prose; the test docstring's contract is literally "口语化提示不泄露技术细节").
   - The real no-leak contract is carried by the NEGATIVE asserts at lines 84-85: `assert "version 不合法" not in invalid_html` and `assert "期望整数" not in invalid_html`, plus the status assert at line 82 `assert resp_invalid.status_code == 400`. Those MUST be kept.
   - Per project rule "trim exact Chinese copy ONLY if a stable key/code exists" — none exists here. Per the KEEP-when-uncertain bias and the fact that this file is a registry gate (scheduler_analysis_gantt group), the safe call is to KEEP line 83 as-is. If a future change adds an ErrorCode for this path, this single line can be revisited; for now under-trim is correct.

3. All status-code asserts (60, 67, 74, 82, 95, 114, 156), the no-fake-selected asserts (97-98), the trend-visibility assert (99), the completion-status-label asserts (115-116), and the freeze-window degradation asserts (157-160) are pure behavioral contracts — KEEP.

est_lines_removed: 0. risk: low (no edit performed). This file is reported here so the implementation agent does NOT trim it.

registry_refs_found: tools/test_registry_data.py:57, tools/test_registry_groups_scheduler.py:251 (file-level only; no function pin).

---

## File 2: tests/regression_config_field_spec_contract.py — VERDICT: LIGHT TRIM (hint/label exact-copy snapshots inside the kept big function)

Line count: 322.
TSV reason (B11_sys_a, mid): "real field-spec defaults/choices/strict-validation contract but heavy label+hint text snapshots (line91 最少超期, lines167-190 'X not in hint' negative text asserts)".

This file has six other tests besides the big `test_config_field_spec_registry_contract`. The real contracts to KEEP across the file:
- field-key presence set (lines 53-67) — structural invariant.
- defaults & choices tuples (lines 70-96, 154-180 value asserts, 219-243, 274-275) — real algorithm/registry outcomes.
- `not hasattr(objective_spec, "policy")` (68) — real schema invariant.
- metadata key ordering + set equality (120-153) — encodes a rule (order of page fields). KEEP.
- strict-mode ValidationError on missing sort_strategy (278-289), TypeError on removed kwargs (244-245, 318-322) — security/error-propagation contracts. KEEP all.
- snapshot hidden-field default `auto_assign_persist == "yes"` (231, 274-275) and single-arg `.get()` TypeError (244-245) — KEEP.

### TRIM items (delete specific assert lines INSIDE `test_config_field_spec_registry_contract`, which is KEPT and still has dozens of meaningful asserts). All are exact Chinese-label / hint-prose snapshots whose only failure mode is UI copy editing, AND each has a sibling structural assert (the `choices[i]["value"]` / key-presence asserts) that survives and still proves the field is wired. We trim the LABEL/HINT prose, never the value/structure.

Re-mapping the TSV's "line91 最少超期" and "lines167-190": the file has shifted; the actual current anchors are below.

TRIM-2a — exact Chinese label values that duplicate a value-level assert already present:
- Anchor (delete this exact line): `    assert choice_label_map_for("objective")["min_overdue"] == "最少超期"`
  why-brittle: exact_chinese_snapshot of a UI label; the same key's VALUE wiring is proven by line 154/155 `metadata["objective"].choices[0]["value"] == "min_overdue"` and the structural equality at 157-159 `metadata["objective"].choices == tuple(... objective_choice_labels() ...)`. The label string itself is cosmetic copy.
  keep-context: KEEP the immediately following line `    assert choice_label_map_for("objective")["min_weighted_tardiness"] == "最少加权拖期小时"`? -> SEE TRIM-2b; both are the same class. KEEP line 92 `assert choice_label_map_for("objective") == objective_choice_labels()` — that one is a structural identity (map equals the canonical source) and is NOT brittle. KEEP it.
- Anchor (delete this exact line): `    assert choice_label_map_for("objective")["min_weighted_tardiness"] == "最少加权拖期小时"`
  why-brittle: same class (exact_chinese_snapshot); structure proven by line 156 `metadata["objective"].choices[2]["value"] == "min_weighted_tardiness"`.

TRIM-2b — exact Chinese label snapshots in the metadata block whose VALUE/key is asserted on an adjacent line:
- Anchor: `    assert metadata["objective"].choices[0]["label"] == "最少超期"`
  why-brittle: exact_chinese_snapshot; the adjacent `choices[0]["value"] == "min_overdue"` (line 154) proves wiring.
  CAUTION: line 157-159 asserts `metadata["objective"].choices == tuple({"value": key, "label": label} for key, label in objective_choice_labels().items())` — this ALREADY pins every label to the canonical source structurally. So the individual `.label == "最少超期"` is fully redundant AND brittle. Safe to trim.
- Anchor: `    assert metadata["graph_analysis_mode"].choices[1]["label"] == "只看分析报告"`
  why-brittle: exact_chinese_snapshot; value proven by line 165 `choices[1]["value"] == "report"`.
- Anchor: `    assert metadata["graph_analysis_mode"].choices[2]["label"] == "参与排产"`
  why-brittle: exact_chinese_snapshot; value proven by line 166 `choices[2]["value"] == "on"`.
- Anchor: `    assert metadata["graph_candidate_weight_count"].choices[1]["label"] == "5 档（默认）"`
  why-brittle: exact_chinese_snapshot of a dropdown option label; the count default is already proven by line 77 `default_for("graph_candidate_weight_count") == 5` and choices tuple line 78.

TRIM-2c — the negative hint-prose asserts (TSV "X not in hint"). These assert that specific Chinese phrases are ABSENT from a hint/description. They were added to enforce a one-time copy-cleanup (removing "阶段 2", "ready 队列", "图评分", "debug/export" wording etc.). Their only failure mode now is someone re-introducing or paraphrasing that exact phrase — pure copy churn, not behavior. Trim the negative-prose asserts; KEEP the positive structural/keyword asserts that prove the hint EXISTS and carries the user-facing keyword.
- KEEP (do NOT trim): line 162 `assert metadata["freeze_window_enabled"].hint` (existence), line 163 `.unit == "天"` (unit contract), line 170 `assert "参与排产" in ...hint`, line 171 `assert "先排普通方案" in ...hint` — these prove the hint is present and on-message; borderline but KEEP per under-trim bias.
- TRIM these negative-absence prose asserts (delete each exact line):
  - `    assert "阶段 2" not in metadata["graph_analysis_mode"].hint`
  - `    assert "可用 DAG 会用 ready 队列参与 SGS 候选" not in metadata["graph_analysis_mode"].hint`
  - `    assert "ready 队列" not in metadata["graph_analysis_mode"].hint`
  - `    assert "图评分" not in metadata["graph_analysis_mode"].hint`
  - `    assert "预留" not in get_field_spec("graph_critical_weight").description`
  - `    assert "当前不改变排产结果" not in metadata["graph_critical_weight"].hint`
  - `    assert "ready 候选" not in metadata["graph_critical_weight"].hint`
  - `    assert "ready 候选" not in metadata["graph_impact_weight"].hint`
  - `    assert "on 且" not in metadata["graph_critical_weight"].hint`
  - `    assert "on 且" not in metadata["graph_impact_weight"].hint`
  - `    assert "阶段 2" not in metadata["graph_debug_export"].hint`
  - `    assert "debug/export" not in metadata["graph_debug_export"].hint`
  - `    assert "logs/schedule_graph" not in metadata["graph_debug_export"].hint`
  why-brittle: full_page_text / doc_snapshot style negative copy asserts. They guard against a specific historical phrasing reappearing; paraphrase or re-wording the hint (legitimate UX copy work, no behavior change) trips them. The positive description asserts at lines 182-183 (`"影响完工时间的工序会更靠前" in ...description`, `"会影响更多后续工序的当前工序会更靠前" in ...description`) DO carry a small semantic contract about meaning — these are borderline; per under-trim bias KEEP lines 182-183.

  CONSERVATIVE BOUNDARY: TRIM-2c removes 13 negative-absence prose asserts. If the implementation agent is uncertain about any single one, KEEP it — they are independent lines and partial application is safe.

Net for File 2: ~5 exact-label lines (TRIM-2a/2b) + 13 negative-prose lines (TRIM-2c) = ~18 assert lines deleted from a function that retains ~70+ meaningful asserts. No function emptied, no import touched, no helper removed.

whole-functions deleted: NONE.
est_lines_removed: 18.
risk: low. trim_type: mixed (exact_chinese_snapshot + doc/full-page negative-text asserts).
registry_refs_found: tools/test_registry_data.py:42, tools/test_registry_groups_scheduler.py:94 (file-level only).

---

## File 3: tests/regression_config_manual_markdown.py — VERDICT: TARGETED TRIM (JS source-grep block + exact-manual-phrase mega-list), KEEP runtime + HTTP-mode contracts

Line count: 740 (last line 741 `    print("OK")`).
TSV reason (B11_sys_a, low): "mostly brittle: greps config_manual.js for function names (line646-665) + asserts hundreds of exact manual phrases ('最后更新：2026年5月' line518) + V1==V2 byte equality; only node hash-runtime(line685) + HTTP mode=full/page contract(line711) worth keeping".

This is a SINGLE test function `test_config_manual_markdown_contract` plus many module-level helpers. Helpers must be evaluated: only delete a helper if it becomes unused after trimming.

### KEEP (load-bearing, do NOT trim):
- Section 7 "行为契约：真实请求验证双模式" (current lines 685-738): real HTTP behavior — status 200, JSON `mode == "full"/"page"`, `currentManual is None` in full mode, `relatedManuals == []`, page-mode `currentManual.title == "物料主数据"`, `preview_sections <= 2`, `#content` count == 1, noscript fallback. These are genuine route/contract behaviors. KEEP ALL of section 7.
- The node hash-runtime checks (lines 666-671) calling `_run_hash_runtime_check(... "full")` / `("page")` and asserting `.get("ok")`: this is a REAL runtime regression (digit-prefix hash must not crash init, scrollspy must activate). KEEP. Therefore the entire `_run_hash_runtime_check` helper (lines 131-347) and its embedded node_code MUST be KEPT.
- The security-protocol asserts (Section 3, lines 648-654): `isSafeHref` whitelist, `javascript:` NOT opened, `noopener noreferrer`. These are SECURITY contracts, not cosmetic. KEEP all of Section 3.
- The compatibility-degradation asserts (Section 4, lines 656-659): IntersectionObserver fallback + scrollIntoView degrade path — behavioral fallback contract. KEEP.
- The hash-init structural asserts (Section 5, lines 661-665): `getElementById(hashId)` preferred + `querySelector(hash)` degrade — behavioral. Borderline (they grep JS text) but they encode the digit-prefix-safe branch that the runtime check exercises; per under-trim bias KEEP.

### TRIM items:

TRIM-3a — Section 2 "Markdown 解析核心能力" JS function-name source greps (current lines 627-647). This is a textbook `js_source_grep`: asserting `"function readConfig(" in js` etc. Their only failure mode is renaming/reformatting a JS function (e.g. arrow-fn refactor) with zero behavior change. The node RUNTIME check (KEEP, lines 666-671) already proves the JS actually parses+renders+scrollspies, which is the real contract these greps weakly proxy.
  - Delete the whole block from the comment line through the last grep assert. Unique start anchor (delete from here):
    ```
    # 2) Markdown 解析核心能力
    for needle in (
        "function readConfig(",
    ```
    through end anchor (inclusive, delete up to and including):
    ```
    assert 'const markdownSource = manualMode === "page" ? buildPageMarkdown(currentManual) : rawMarkdown;' in js, "JS 缺少双模式渲染分支"
    ```
    i.e. current lines 626-646 (the `# 2)` comment + the `for needle in (... initManual( ...)` loop at 627-640, plus the 6 follow-up single asserts 641-646).
  why-brittle: js_source_grep — matches function declaration text and exact const-statement source lines. KEEP-context: the line immediately above is Section 1's `assert "相关模块说明" in tpl ...` (line 624) — KEEP that. The line immediately below is the `# 3) 安全约束` comment (line 648) — KEEP Section 3 entirely.
  CAUTION / boundary: do NOT over-extend into Section 3. The deletion ends at the `markdownSource` assert (line 646); the next kept line is blank (647) then `# 3) 安全约束`.
  NOTE on `js = _read(js_path)` (line 598): `js` is still used by Sections 3/4/5, so it stays. Do NOT delete the `_read` of the JS file.

TRIM-3b — the giant exact-manual-phrase lists inside helpers `_assert_scheduler_manual_required_content` (lines 498-587) and its callees. This is the "asserts hundreds of exact manual phrases" the reason flags. These are doc-text snapshots: each asserts a verbatim Chinese sentence is present/absent in scheduler_manual.md. They break on ANY copy edit to the manual. HOWEVER several carry genuine semantic CONTRACTS (the docstring's "必备口径与边界说明在场"):
  - KEEP (real boundary/semantic contracts, NOT mere copy): the export/restore non-promise asserts in `_assert_history_section_does_not_claim_export_or_restore` (lines 407-421) — these enforce that the manual does NOT over-promise export/restore (a correctness-of-documentation guard tied to a real product limitation). KEEP this whole helper and its call (line 587).
  - KEEP: `_assert_manual_uses_batch_maintenance_entry_names` (lines 119-128) + the legacy-Excel-term absence check — enforces the "入口统一叫批量维护" rename contract; this is a structural/naming invariant, not free-form copy. KEEP (call at line 679).
  - KEEP: internal-anchor integrity (lines 680-683): `missing_hashes` must be empty — every `[..](#x)` link resolves to a heading id. This is a real link-integrity invariant. KEEP.
  - KEEP: the `_assert_ordered_phrases` full-flow ordering check (lines 574-586) — ordering encodes the real "先建基础资料 → ... → 最后复盘和下发" process rule. KEEP.
  - KEEP: the closeout/resource-dispatch semantic asserts in `_assert_scheduler_manual_closeout_contracts` (452-496) and `_assert_resource_dispatch_site_record_section` (424-449) carry product-fact contracts (5-column device template, "严格限制不是普通备注", "当前是直接导入不走预览"). These are documentation-correctness contracts — KEEP both helpers and their calls (566-567).

  TRIM within `_assert_scheduler_manual_required_content`: the TWO loose `for needle in (...)` mega-lists are the brittle part:
  - TRIM the FIRST small list (current lines 499-500): `for needle in ("TRUE/FALSE", "NaN", "Inf", "Infinity", "5e0", "1E2", "最后更新：2026年5月"): assert needle in markdown_text`. The `"最后更新：2026年5月"` token (TSV "line518") is a pure date-stamp snapshot that breaks every month the doc is touched — classic brittle. The numeric-literal tokens (TRUE/FALSE/NaN/Inf/...) are documentation-presence snapshots of example values. Delete this 2-line block (the `for needle in (...)` header + the `assert` body) entirely.
    Unique anchor (delete both lines):
    ```
    for needle in ("TRUE/FALSE", "NaN", "Inf", "Infinity", "5e0", "1E2", "最后更新：2026年5月"):
        assert needle in markdown_text, f"{label} 缺少说明书必备内容：{needle}"
    ```
    keep-context: this is the first statement of `_assert_scheduler_manual_required_content`; the function continues with the big second list which we trim SEPARATELY below. The function is NOT emptied because the semantic-contract helper calls (566-567), the ordered-phrases call (575-586), the export/restore call (587), and the batch-warning paragraph asserts (569-572) all remain.
  - TRIM the SECOND mega `for needle in (...): assert needle in markdown_text` list (current lines 502-549): ~46 verbatim Chinese sentence fragments. These are doc_snapshot brittle copy. BUT a subset are genuine boundary口径 (the docstring's named contracts). To stay conservative AND meaningful: KEEP the named-boundary semantic sentences and TRIM the rest is HARD to apply deterministically line-by-line. SAFER DECISION: KEEP the entire second list AS-IS. Rationale: this list is a single statement, deleting individual interior tuple elements is error-prone for an implementation agent (no unique per-line anchor for many near-duplicate fragments), and several elements (e.g. "版本留空或版本为空字符串，都表示看最新排产历史", "输入 `abc` 这类不是数字的版本号", "查询结果表包含 10 列", "任务明细表有 14 列", the column-count table rows) ARE real structural/口径 contracts. Per the under-trim bias, KEEP lines 502-549 and the negative-forbidden list at 550-565. Only the date-stamp mini-list (499-500) is trimmed from this helper.
  - KEEP the negative-forbidden list (553-565) and the standalone forbidden asserts (550-552): they enforce the manual does NOT re-introduce removed features ("贪心", "OR-Tools 尝试时间", "备份与恢复" etc.) — documentation-correctness contracts. KEEP.

TRIM-3c — V1==V2 byte-equality of the manual mirror. TSV flags "V1==V2 byte equality". Current line 676: `assert manual_text == manual_v2_text, "主说明书与 v2 镜像副本必须完全同步"`. Re-mapping: this is NOT cosmetic — it enforces the real invariant that the v2 mirror copy stays byte-identical to the source-of-truth manual (the docstring's "主副本逐字一致"). A drift here is a genuine bug (stale mirror shipped to users). DECISION: KEEP. (Listed here only to record that the TSV-flagged item was evaluated and deliberately kept — it is a structural sync invariant, not brittle copy.)
  - Similarly KEEP line 674 `manual_text.startswith("# 系统使用说明")` (title source-of-truth) and 675 (mirror exists). Both structural. KEEP.

TRIM-3d — Section 1 template-contract greps (lines 604-624). These grep the Jinja templates for exact attribute/expression fragments (`'"mode": manual_mode'`, `"fallback_text if manual_mode == 'page' else manual_text"`, etc.). Borderline js/template source-grep. HOWEVER they pin the template→JS data-wiring contract (the `aps-config-manual-data` JSON block structure) that the runtime check consumes, and the runtime check uses a STUB, not the real template — so these greps are the only thing tying the real template to the data contract. DECISION: KEEP Section 1 (under-trim bias; these are the data-contract bridge, not pure cosmetics).

### Helper-liveness check after TRIM-3a + TRIM-3b(date-list only):
- `_run_hash_runtime_check` — still called (666,669). KEEP.
- `_read`, `_find_repo_root`, `_build_url`, `_extract_json_config`, `_mode_headers` — still used by Section 7. KEEP.
- `_extract_section`, `_extract_paragraph_containing`, `_assert_ordered_phrases`, `_assert_history_*`, `_assert_resource_dispatch_*`, `_assert_scheduler_manual_closeout_contracts`, `_assert_manual_uses_batch_maintenance_entry_names`, `_extract_heading_ids`, `_extract_internal_hashes`, `_slugify_heading`, `_find_legacy_excel_entry_terms`, `_is_historical_legacy_entry_note`, `_find_heading_entry_line` — all still called by KEPT asserts. KEEP all helpers.
- Constants `LEGACY_EXCEL_ENTRY_TERMS`, `MANUAL_BATCH_MAINTENANCE_SECTIONS` — still used by kept helpers. KEEP.
- No helper becomes unused. No import becomes unused (`re`, `json`, `os`, `subprocess`, `url_for`, typing — all still used).

Net for File 3: TRIM-3a (JS function-name grep block, ~21 lines incl. comment+blank) + TRIM-3b date-stamp mini-list (2 lines). The bulk of the brittle phrase-lists are KEPT under the conservative bias because (a) many carry real口径 contracts and (b) interior tuple-element deletion lacks unique anchors. The function `test_config_manual_markdown_contract` retains all HTTP-mode, runtime, security, anchor-integrity, ordering, and boundary-口径 contracts.

whole-functions deleted: NONE.
est_lines_removed: 23.
risk: mid (this file is a quality-gate-listed py38-scope gate at quality_gate_shared.py:812/822; trimming the JS-name greps slightly reduces JS-symbol-presence enforcement, but the node runtime check (kept) provides stronger behavioral coverage of the same JS, so net enforcement loss is minimal). trim_type: mixed (js_source_grep + doc_snapshot date stamp).
registry_refs_found: tools/quality_gate_shared.py:144, tools/quality_gate_shared.py:812, tools/quality_gate_shared.py:822 (file-level gate listing only; no function/nodeid pin).

---

## Batch totals
- est_lines_removed: 0 (File1) + 18 (File2) + 23 (File3) = 41.
- whole functions deleted: 0 across the batch.
- B-4 red lines: none of the three files are on the B-4 red-line list (test_enum_display_consistency.py / regression_schedule_result_view_context.py). b4_redline=false for all.
- Meta-gate caution: File3 is a quality-gate-listed file; handled conservatively above (kept the runtime + HTTP + security contracts; trimmed only redundant JS-name greps + one date stamp).
