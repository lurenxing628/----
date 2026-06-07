# KEEP_TRIM Spec — Batch B06_data_a

Phase P5.2 KEEP_TRIM. Branch `cleanup/p3-main-style-to-pytest`. Repo root = CWD.
This file is the source of truth the implementation agent follows. Trim only the
anchored brittle items below; everything else is KEEP. Line numbers are
indicative of CURRENT file content (re-verified against the files on this branch),
but anchors are the authoritative locators — apply by matching the verbatim anchor
string, not by line number.

## Cross-cutting finding that constrains this whole batch (READ FIRST)

The four `preview_confirm_*_guard` files and the strict-mode guard all assert the
baseline-drift REJECT via the user-facing phrase **`请重新上传 Excel 并检查`**
(or the longer `导入被拒绝：数据已变化，请重新上传 Excel 并检查后再确认写入。`).

I traced the producer: the reject path is delivered ONLY as a Flask `flash(...,
"error")` message and the route returns **HTTP 200** (see
`web/routes/excel_utils.py:172-175`, `web/routes/domains/scheduler/scheduler_excel_batches.py:273`,
`web/routes/personnel_excel_links.py:193`, etc.). There is **no ErrorCode, no enum,
no distinct status code** on the reject path. The phrase substring is therefore the
ONLY observable signal distinguishing "guard fired / write rejected" from "import
silently succeeded". Per the KEEP_TRIM rule ("if the exact string IS the contract —
an error-code-less user-facing guarantee with no other anchor — KEEP it"), every
`请重新上传 Excel 并检查` assertion in this batch is a **load-bearing reject oracle
and MUST be KEPT**. This is especially true in `extra_state_guard` where there is
NO DB-count check — the phrase is the sole proof of rejection.

Consequence: the four guard files (`strict_mode_extra_state_guard`,
`preview_confirm_baseline_guard`, `preview_confirm_extra_state_guard`, and the
`hidden_payload` reject half) have very little trimmable surface. Their TSV `value`
of `high` reflects high contract value, not "high trim yield". Under-trim bias
applies hard here. Net trim for this batch is small and concentrated in
`detail_linkage`, `conversion_output_contracts`, and `hidden_payload`'s
presentational-markup tail.

---

## 1. tests/regression_batch_detail_linkage.py
- Current line count: **102**
- TSV reason (re-mapped): "mostly brittle: asserts HTML attrs/IDs + greps JS for fn
  names and exact tooltip text; only operatorMachines=None->JSON null contract is real."
- Registry refs: none (grep of tools/ + tests/ for `test_batch_detail_linkage` and
  the file basename returned nothing).
- Single test function: `test_batch_detail_linkage`.

### KEEP (real contract — do not touch)
- Template-injection structural contract, current lines 68–77. These assert the
  presence of named DOM hooks the JS depends on; `data-linkage-row`, the two lazy
  templates, the JSON-injection node, the `window.__APS_BATCH_DETAIL_LINKAGE__`
  config, the bidirectional `machineOperators`/`operatorMachines` maps, and
  `lazySelectEnabled`. These are structural invariants (keys/hooks present), not
  cosmetic copy. KEEP all of lines 68–77.
- The `（已删除）` fallback-placeholder assert (line 71): this is a behavioral
  fallback contract (deleted-resource → placeholder), KEEP.
- **The JSON-null contract (line 80)** — the one item the TSV singles out as real:
  ```
  assert re.search(r'"operatorMachines"\s*:\s*null\b', html_null), "operatorMachines=None 时应以 JSON null 注入"
  ```
  This encodes the documented behavior "operatorMachines=None injected as JSON null,
  reconstructed client-side from machineOperators". KEEP.

### TRIM (brittle — delete)
- **Brittle item 1.1 — JS source-text grep block (JS-source-grep).** The entire
  `js_path` read + the `for needle in (...)` loop that asserts function-name and
  literal-source substrings exist inside `static/js/batch_detail_linkage.js`. This
  is the textbook JS-source-grep brittleness: it fails on any rename/refactor of the
  JS with zero behavior change, and it duplicates coverage that JS unit/e2e would
  own. Delete the JS read and the needle loop.
  - Unique anchor (delete from this line):
    ```
    # JS 契约：核心函数与关键分支存在（仅验证语义钩子）
    js_path = os.path.join(str(repo_root), "static", "js", "batch_detail_linkage.js")
    ```
  - Through the end of the needle loop:
    ```
        for needle in (
            "ensureSelectOptionsLoaded",
            ...
            "cfg.operatorMachines || buildOperatorMachinesFromMachineOperators",
        ):
            assert needle in js, f"缺少关键联动逻辑片段: {needle}"
    ```
- **Brittle item 1.2 — exact JS tooltip-copy greps (exact Chinese snapshot in JS
  source).** Current lines 100–102:
  ```
      # 关键提示文案约束（防回退）
      assert re.search(r"当前设备/人员组合不匹配", js), "缺少不匹配提示"
      assert re.search(r"已删除：请改选或清空", js), "缺少孤儿资源提示"
  ```
  These grep exact Chinese UI copy out of the JS source file. Brittle (copy edits
  break it; no behavior regression). Delete.
- After deletion, `js` / `js_path` are unused → the `os` and the `repo_root`
  fixture become unused. Implementation agent should ALSO drop the now-unused
  `repo_root` fixture param from the signature (`def test_batch_detail_linkage(app_client, repo_root)`
  → `def test_batch_detail_linkage(app_client)`) and remove `import os` (line 5) if
  no other use remains (it does not — `os` is only used for `js_path`). `re` is
  still used by the line-80 null contract, KEEP `import re`.
- Function is NOT deleted (keeps 9 meaningful structural asserts + the null
  contract). assert/line trims only.
- Risk: **low**. Brittle items are unambiguous JS-source greps + copy greps with a
  cleanly separable, well-anchored block.

---

## 2. tests/regression_batch_excel_preview_confirm_strict_mode_extra_state_guard.py
- Current line count: **142**
- TSV reason (re-mapped): "real route preview->confirm strict_mode drift guard + DB
  atomicity (now lines ~119–142); inlines duplicate helpers (lines 8–39) of
  excel_preview_confirm_helpers.py and exact text check (now line 133)."
- Registry refs: none.
- Single test function: `test_batch_excel_preview_confirm_strict_mode_extra_state_guard`.

### KEEP (real contract)
- The whole route flow: GET page → assert `strict_mode` control rendered + default
  hidden value `"no"` (lines 71–77) — these are structural hidden-field contracts,
  KEEP. preview POST with `strict_mode=yes` (79–106). Preserved-hidden-field asserts
  (109–112: strict_mode round-trips as `yes`, auto_generate_ops as `1`) — KEEP, these
  encode the drift-detection precondition. preview_baseline extraction (114–117) KEEP.
- **The DB-atomicity check (lines 136–142)**: after a rejected confirm, `Batches`
  count for `B_STRICT_GUARD` must be 0. This is the real transactional guarantee —
  KEEP.
- **The reject marker (line 133)** `"请重新上传 Excel 并检查"`: per the cross-cutting
  finding above, this is the sole observable reject oracle on a 200+flash route.
  **KEEP** — do NOT trim despite the TSV calling line 133 "exact text check". The DB
  count alone proves "not written" but NOT "rejected for the right reason"; the phrase
  proves the strict_mode-drift guard fired rather than some unrelated 200. Together
  they are the contract.

### TRIM
- The TSV flags "inlines duplicate helpers (lines 8–39) of
  excel_preview_confirm_helpers.py". I checked: trimming these helpers is OUT OF
  SCOPE for KEEP_TRIM (that is a de-dup/MERGE concern, P5.1, not a brittle-assert
  trim) and they are live dependencies of the kept flow (`_make_xlsx_bytes`,
  `_extract_raw_rows_json`, `_extract_hidden_input`, `_assert_status` are all called
  by the kept test). Deleting them would break the test. **Do NOT trim helpers here.**
- No brittle assert lines to trim in this file. Everything that could be called
  "brittle" (the one phrase) is the reject oracle and must be kept.
- whole_functions_deleted: none. assert_only_trim_count: 0.
- Risk: **mid** (file is high-value; recommendation is effectively NO-TRIM to avoid
  weakening the strict-mode drift guard). est lines removed: 0.

---

## 3. tests/regression_calendar_pages_readside_normalization.py
- Current line count: **68**
- TSV reason (re-mapped): "read-side page render normalization to 假期/是/否 is real
  but verified via brittle `<td>..</td>` adjacency regex (helper `_assert_calendar_row`,
  lines 14–33; calls at 63 & 68); same contract as export twin."
- Registry refs: none.
- Single test function: `test_calendar_pages_readside_normalization`.

### Analysis
The REAL contract: legacy stored values (`day_type=Weekend`, `allow_normal=Yes/是/NO`)
must render normalized to Chinese (`假期`/`是`/`否`) on both `/scheduler/calendar`
and `/personnel/<id>/calendar`. That is a genuine read-side normalization behavior —
a real bug would slip English/mixed-case through to the user. This MUST be kept.

The brittleness is purely in the VERIFICATION MECHANISM: `_assert_calendar_row`
builds a strict `<td>X</td>\s*<td>Y</td>.*?<td>...</td>` adjacency regex that pins
exact column ORDER and `<td>` markup. A cosmetic template change (add a column,
wrap a `<span>`, reorder) breaks it with no behavior regression.

### Decision: KEEP (cannot cleanly trim under read-only edit rules)
- KEEP_TRIM only deletes lines; it does not rewrite the verification into a looser
  form. If we delete the two `_assert_calendar_row` calls (lines 63, 68) we are left
  with a test that inserts legacy rows and only asserts HTTP 200 — i.e. it would no
  longer verify normalization at all (the entire point), violating "never leave a
  kept test with zero meaningful assertions" and silently deleting the real
  coverage. So we KEEP the calls and the helper.
- Under-trim bias resolves this to **KEEP whole file unchanged**.
- RECOMMENDATION for a later (out-of-scope) rewrite pass, recorded for the
  implementer NOT to do now: replace the adjacency regex with per-value presence
  assertions scoped to the row (e.g. assert the normalized `假期`/`是`/`否` tokens
  co-occur in the row block for that date, without pinning `<td>` adjacency/order).
  That preserves the contract while shedding the markup-shape brittleness. Do this
  only in a rewrite phase, not in KEEP_TRIM.
- whole_functions_deleted: none. assert_only_trim_count: 0. est lines removed: 0.
- Risk: **mid** — the brittleness is real but inseparable from the contract under
  pure-deletion semantics; trimming would delete coverage. NO-TRIM.

---

## 4. tests/regression_excel_conversion_output_contracts.py
- Current line count: **147**
- TSV reason (re-mapped): "converter-output-vs-definition equality is real (the
  `assert _nonempty_rows(...) == expected_rows` at current line 126, and header
  equality 124/141, and supplier enum 145) but bulk is xlsx layout snapshot
  freeze_panes/bold/align/exact col-width/enum-range (helper
  `_assert_layout_matches_definition`, lines 71–99)."
- Registry refs (FILE-LEVEL, contract membership — both preserved by this trim plan):
  - `tools/test_registry_data.py:217: "tests/regression_excel_conversion_output_contracts.py",`
  - `tools/test_registry_groups_misc.py:135: "tests/regression_excel_conversion_output_contracts.py",`
  These pin the FILE (the file must keep ≥1 test). This plan deletes NO test
  function (only the layout helper + its 2 call-sites + now-dead helpers), so the
  file and both its test functions survive → registry membership intact. No FLAG.
- Two test functions:
  `test_op_type_conversion_output_matches_current_converter_result_and_layout`,
  `test_supplier_conversion_output_matches_current_template_layout`.

### KEEP (real contract)
- `test_op_type_...`: header equality (line 124
  `assert [ws.cell(1, col_idx).value ...] == headers`) and the converter-output
  equality (line 126 `assert _nonempty_rows(ws, len(headers)) == expected_rows`).
  The latter is the real "delivered xlsx content == current UnitExcelConverter
  output" contract — a genuine regression if the shipped converted file drifts from
  the converter. KEEP both, plus the `expected_rows`/`UnitExcelConverter().convert`
  setup that feeds line 126 (lines 116–119), plus the workbook load (121–123).
- `test_supplier_...`: header equality (line 141) KEEP; the non-empty-rows + the
  `row[4] in ("启用","停用")` enum-value contract (lines 143–145) KEEP — that is a
  real value-domain invariant (启用/停用 only), not layout.
- Shared helpers KEEP because they feed the kept asserts: `_nonempty_rows`,
  `_read_workbook_rows` (supplier path), and `get_template_definition` import.

### TRIM (brittle — openpyxl layout snapshot)
- **Brittle item 4.1 — `_assert_layout_matches_definition` (the layout snapshot
  helper), current lines 71–99.** It asserts `freeze_panes == "A2"`, header
  `font.bold is True`, `alignment.horizontal/vertical == "center"`, per-column
  `number_format == "@"`, exact computed `column_dimensions[...].width` to ±0.01,
  and the exact data-validation enum range string (`A2:A<format_max_row>`). This is
  pure openpyxl cell-formatting/geometry snapshotting (`openpyxl_layout`): bold,
  alignment, pixel-equivalent column width, freeze panes, validation-range literal —
  all break on cosmetic spreadsheet-styling changes with no data/behavior regression.
  Delete the whole helper.
  - Unique anchor (the def line — delete the entire function body through line 99):
    ```
    def _assert_layout_matches_definition(ws: Any, definition: Mapping[str, Any], filename: str) -> None:
    ```
    ...ends at:
    ```
            assert _data_validation_contracts(ws, one_based_col_idx) == [{"values": values, "range": expected_range}]
    ```
- **Brittle item 4.2 — the two call-sites of the helper.** Delete:
  - In `test_op_type_...`, line 125: `        _assert_layout_matches_definition(ws, definition, filename)`
  - In `test_supplier_...`, line 142: `        _assert_layout_matches_definition(ws, definition, filename)`
- **Dead-helper cascade (delete only because they become unused after 4.1):**
  - `_definition_enum_values_by_header` (lines 20–27) — only used by the layout helper.
  - `_inline_validation_values` (lines 30–34) — only used by `_data_validation_contracts`.
  - `_data_validation_contracts` (lines 37–51) — only used by the layout helper.
  - `_expected_column_width` (lines 63–68) — only used by the layout helper.
  - Implementation agent MUST verify each is unreferenced after removing 4.1/4.2
    before deleting (grep within file). `get_column_letter` import becomes unused
    once these go — drop it too; `load_workbook`, `Sequence`, `Mapping`, `Any`,
    `Dict`, `List` usage: re-check (`Mapping` was only the layout-helper signature;
    `_definition_enum_values_by_header` used `Mapping`/`Dict`/`List` too). Keep
    whatever the surviving `_nonempty_rows`/`_read_workbook_rows`/tests still use.
- Both test functions SURVIVE with meaningful asserts (header + content equality /
  enum domain). NOT a whole-function delete. So registry membership is safe.
- assert_only_trim_count: counts the 2 call-site deletions (2). The helper/dead-helper
  removals are structural (function bodies), tallied in est_lines_removed.
- est lines removed: ~55 (layout helper ~29 + 4 dead helpers ~28 + 2 call lines −
  minor import lines; net counting blank lines ~55).
- Risk: **mid** — large block; the cascade requires the agent to confirm no other
  use of the dead helpers (they are local, single-purpose, so safe), and to NOT
  touch the two surviving content-equality asserts which are the real contract.

---

## 5. tests/regression_excel_hidden_payload_contract.py
- Current line count: **164**
- TSV reason (re-mapped): "real anti-tamper baseline guard: b64-encoded preview,
  tampered raw_rows_json rejected + not written to DB (now lines ~121–148); brittle
  `<details>/<summary>` markup + internal/external not-in-html tails (now lines
  104–110)."
- Registry refs (FILE-LEVEL — both preserved; this plan deletes no test function):
  - `tools/test_registry_data.py:218: "tests/regression_excel_hidden_payload_contract.py",`
  - `tools/test_registry_groups_misc.py:136: "tests/regression_excel_hidden_payload_contract.py",`
- Test function: `test_excel_hidden_payload_contract` (delegates to `main(monkeypatch)`).

### KEEP (real anti-tamper contract)
- `_decode_preview_payload` requiring the `aps-preview-json-b64:` prefix (lines
  72-76) — real: proves preview rows are b64-encoded not plaintext. KEEP.
- The decoded-rows assertions (lines 115–119): list len, `工种编号 == "OT_PAYLOAD"`,
  `"工种ID" not in decoded_rows[0]` (key-normalization contract), name, and
  **`归属 == "internal"`** (the value normalized from "自制" → internal). These are
  real semantic/normalization contracts. KEEP.
- **`assert "internal" not in html` / `assert "external" not in html` (lines
  109–110)** — KEEP. The TSV labels these "not-in-html tails" as brittle, but they
  are the CORE anti-tamper/info-hiding contract this whole file exists for (the page
  must not leak internal归属 tokens in plaintext source; the value lives only inside
  the b64 payload). A regression here is a real information-disclosure bug, not
  cosmetics. KEEP both.
- The tamper→reject flow (lines 121–148): re-encode tampered rows, POST confirm,
  assert the long reject phrase `导入被拒绝：数据已变化，请重新上传 Excel 并检查后再确认写入。`
  (line 139) and the DB count of `OT_TAMPERED == 0` (lines 143–146). KEEP ALL — the
  reject phrase is the sole reject oracle (see cross-cutting finding) and the DB
  count is the real "not written" guarantee.
- KEEP the negative `assert "检查数据解析失败，请重新上传 Excel 并检查。" not in html`
  (line 99): asserts the preview did NOT error out — a real success-path guard, KEEP.
- KEEP the structural field-presence asserts at lines 100–103 (`raw_rows_json`,
  `preview_baseline`, `action=".../confirm"`, and the `value` regex on
  preview_baseline) — these are structural form contracts the confirm step depends
  on. KEEP.

### TRIM (brittle — presentational markup snapshot)
- **Brittle item 5.1 — collapsible-UI markup snapshot.** Current lines 104–107:
  ```
      assert '<details class="aps-row-detail">' in html
      assert "<summary>查看数据</summary>" in html
      assert "本行数据" in html
      assert "raw_rows_json" in html
      assert "preview_baseline" in html
  ```
  WAIT — re-map carefully. Lines 104–106 are the brittle markup snapshot
  (`<details class="aps-row-detail">`, `<summary>查看数据</summary>`, `本行数据`).
  I confirmed via grep these are purely presentational chrome in
  `templates/components/excel_import.html:126-129` and the batches twin — collapsible
  "查看数据 / 本行数据" UI with no behavioral meaning. These are full-page-HTML /
  CSS-class markup snapshots → brittle. **Delete exactly lines 104, 105, 106:**
  - Anchor (delete these three consecutive lines):
    ```
        assert '<details class="aps-row-detail">' in html
        assert "<summary>查看数据</summary>" in html
        assert "本行数据" in html
    ```
  - KEEP lines 107–108 (`assert "raw_rows_json" in html` and
    `assert "preview_baseline" in html`) — these are duplicated-but-cheap structural
    field-presence checks; they overlap lines 100–101 so are low-value, but they are
    NOT markup-brittle. Under-trim bias → KEEP them (harmless, and deleting adds risk
    for ~2 lines of yield).
- whole_functions_deleted: none (function + `main()` survive intact). The 3 deleted
  lines are inside `main()`.
- assert_only_trim_count: 3.
- est lines removed: ~3.
- Risk: **low** — the 3 deleted asserts are unambiguous presentational markup with no
  behavioral coverage; everything load-bearing (b64, internal/external hiding, tamper
  reject, DB) is explicitly kept.

---

## 6. tests/regression_excel_import_result_semantics.py
- Current line count: **372**
- TSV reason (re-mapped): "real export->preview->confirm skip-semantics across 7
  flows + DB write verify (now lines ~163–373); brittle COUNT_RE + alert-class +
  exact-phrase rendering checks; dup confirm scaffold (helpers lines 56–160)."
- Registry refs: none (grep clean).
- Single test function: `test_excel_import_result_semantics` (+ module-level helpers
  `COUNT_RE`, `_extract_*`, `_make_xlsx_bytes`, `_assert_status`,
  `_post_export_preview_confirm`, `_post_file_preview_confirm`, `_assert_skip_semantics`).

### Analysis
The contract here is genuinely behavioral: for 7 export→re-import round-trips,
UNCHANGED rows must be counted as skips (new=update=error=0, skip>0), the success
alert must render, and the auto-ops suffix must appear for the batch flows; plus a
real DB write-verify on the calendar write-path; plus the warning/error-sample path
when error_count>0. The "COUNT_RE + alert-class + exact-phrase" the TSV calls brittle
are actually the MEASUREMENT of those counts/branches — they encode a rule
(new=update=error=0 ∧ skip>0), not cosmetic copy.

### Decision: KEEP (effectively NO-TRIM)
- `COUNT_RE` (line 8) parses `新增 X，更新 X，跳过 X，错误 X` into integers that the
  `_assert_skip_semantics` rule (lines 152–156) checks. This is a structural
  count-invariant, NOT a copy snapshot. KEEP.
- `"alert alert-success"` (line 157) / `"alert alert-warning"` (line 371) — these
  assert the RESULT CLASS (success vs warning branch), which is the behavioral
  outcome of error_count==0 vs >0. That is a real branch contract (a bug that renders
  warning-as-success would be caught). KEEP.
- `"导入部分完成"` + `"错误示例"` + `"模拟部分失败"` (lines 367–370): these verify the
  partial-completion warning branch surfaces the injected error sample. The mocked
  `apply_preview_rows` returns error_count=1 (lines 343–353); the assertions prove the
  view routes the error sample through. Real branch+propagation contract. KEEP. (The
  exact phrase `导入部分完成` is, like the reject phrase, the only signal distinguishing
  the warning branch from success — no enum/code — so KEEP per the cross-cutting rule.)
- `"已按模板自动生成批次工序"` (line 159, gated by `expect_auto_suffix`): verifies the
  auto_generate_ops suffix on batch flows — a real feature-presence contract tied to
  the `auto_generate_ops=1` param. KEEP.
- The calendar real-write-path DB verify (lines 297–314): shift_hours==10,
  efficiency==1.2, allow_* normalized to "yes", remark written — real DB write
  contract. KEEP.
- The `_post_export_preview_confirm` / `_post_file_preview_confirm` scaffold helpers
  the TSV calls "dup" are LIVE dependencies of every kept case; de-dup is a P5.1/MERGE
  concern, out of scope for KEEP_TRIM. Do NOT delete.
- whole_functions_deleted: none. assert_only_trim_count: 0. est lines removed: 0.
- Risk: **mid** — high-value behavioral file; the "brittle-looking" asserts are
  count-invariants / branch oracles, not cosmetic. NO-TRIM is the conservative,
  correct call.

---

## 7. tests/regression_excel_preview_confirm_baseline_guard.py
- Current line count: **402**
- TSV reason (re-mapped): "preview_baseline concurrent-write guard across 5 import
  flows: preview->concurrent write->confirm rejected + DB count stays 1 (the whole
  body, lines ~51–402); exact-phrase marker brittle; dup helpers lines 8–48."
- Registry refs: none.
- Single test function: `test_excel_preview_confirm_baseline_guard`.

### Analysis
This is one of the highest-value files in the batch: 5 concurrency scenarios
(batch / operator-calendar / global-calendar / machine / operator-machine-link),
each doing preview → out-of-band concurrent write of the same PK → confirm-must-reject,
each verified by a DB COUNT == 1 (no double write). That is a real
transaction/concurrency-safety contract — exactly the "MUST keep" category.

### Decision: KEEP (NO-TRIM)
- Every `请重新上传 Excel 并检查` assertion (lines 128, 203, 278, 326, 390) is the
  reject oracle (cross-cutting finding). KEEP all 5.
- Every `COUNT(1) ... != 1` DB check (lines 133–135, 208–213, 331–333, 395–400; note
  scenario 3/global-calendar has no count check because upsert is idempotent by
  design — that's fine) is the real no-double-write guarantee. KEEP.
- Helpers `_make_xlsx_bytes`, `_extract_raw_rows_json`, `_extract_hidden_input`,
  `_assert_status` (lines 8–48) are live dependencies; "dup helpers" is a MERGE/P5.1
  concern, NOT a KEEP_TRIM brittle trim. Do NOT delete.
- whole_functions_deleted: none. assert_only_trim_count: 0. est lines removed: 0.
- Risk: **mid** — pure concurrency-contract file; the only "brittle" item (the
  phrase) is the sole reject oracle. NO-TRIM.

---

## 8. tests/regression_excel_preview_confirm_extra_state_guard.py
- Current line count: **303**
- TSV reason (re-mapped): "extra-state baseline guard: 7 drift scenarios
  (cfg/operator/template-snapshot/source/team/op_type/machine) between preview-confirm
  rejected (now lines ~120–303); verifies only via text marker no DB check; dup
  scaffold lines 8–84."
- Registry refs: none.
- Single test function: `test_excel_preview_confirm_extra_state_guard`.

### Analysis
7 scenarios where unrelated master-data drifts between preview and confirm
(holiday efficiency cfg / operator deleted / part-ops template snapshot / op source /
team rename / op_type rename / machine deleted), each must be rejected. The TSV
explicitly notes "verifies ONLY via text marker, no DB check" — which means the
`请重新上传 Excel 并检查` phrase is LITERALLY THE ONLY assertion of correctness in
each scenario. Trimming the phrase would leave the test asserting nothing but HTTP
200 (i.e., deleting 100% of the coverage). This is the strongest KEEP case in the
batch.

### Decision: KEEP (NO-TRIM)
- `_assert_need_repreview` (lines 82–84) and its 7 call-sites (lines 142, 179, 206,
  231, 255, 279, 303) are the entire behavioral oracle. KEEP all.
- Scaffold helpers `_make_xlsx_bytes`, `_extract_*`, `_assert_status`,
  `_preview_excel`, `_confirm_excel` (lines 8–79) are live dependencies; "dup
  scaffold" is a MERGE concern, out of KEEP_TRIM scope. Do NOT delete.
- whole_functions_deleted: none. assert_only_trim_count: 0. est lines removed: 0.
- Risk: **mid/high** — the phrase IS the only coverage; under-trim bias mandates
  NO-TRIM. Do not weaken this guard.

---

## B-4 RED LINES
Neither B-4 file (`tests/test_enum_display_consistency.py`,
`tests/regression_schedule_result_view_context.py`) is in batch B06_data_a.
b4_redline = false for all 8 files. No B-4 handling required here.

## META-GATE
No file in B06_data_a is a consistency/quality GATE (none in B01_meta). The two
files with registry membership (#4 conversion_output_contracts, #5 hidden_payload)
are guarded at FILE level only and keep all their test functions, so enforcement is
unchanged.

## BATCH SUMMARY
- Net trimmable surface is small and intentional, because the dominant pattern in
  this batch — the `请重新上传 Excel 并检查` / `导入部分完成` rendered-phrase
  assertions — turned out to be the ONLY available reject/branch oracle (no
  ErrorCode/status anchor), so they are contract, not brittleness, and are KEPT.
- Real trims: file #1 (JS-source-grep + JS copy greps), file #4 (openpyxl layout
  snapshot helper + dead-helper cascade), file #5 (3 presentational-markup asserts).
- Files #2, #3, #6, #7, #8 → NO-TRIM (their "brittle" items are inseparable from, or
  identical to, real contracts; deleting would remove genuine coverage).
- Estimated net lines removed across batch: ~70 (≈12 in #1, ≈55 in #4, ≈3 in #5).
