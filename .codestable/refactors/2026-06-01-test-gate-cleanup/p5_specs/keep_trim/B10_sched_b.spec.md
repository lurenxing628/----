# KEEP_TRIM Spec — Batch B10_sched_b

Branch: cleanup/p3-main-style-to-pytest
Author: recon analyst (P5.2 KEEP_TRIM)
Scope: 8 scheduler-domain test files. Trim ONLY cosmetic/structural brittle tails; KEEP every behavioral contract.

## Registry coupling — global finding (read first)

Two registry data files reference these test files **by file-path only** (no `::function` nodeids anywhere — `grep -c '::'` on both files == 0). They are flat path lists used to gate "required regression present":
- `tools/test_registry_data.py` — 7 of the 8 batch files listed (lines 37, 41, 93, 102, 160, 165, 223).
- `tools/test_registry_groups_scheduler.py` — same 7 files (lines 93, 153, 190, 194, 195, 283, 304).
- `tests/test_greedy_refactor_contracts.py` — NOT referenced by any tools/ registry.

Implication: **deleting whole test functions is safe** as long as the file (a) keeps existing and (b) keeps at least one collectable test. We never empty a file in this batch. No registry references any individual function, so no dangling nodeid risk. `registry_refs_found` is therefore empty for every per-function deletion below (the file-path hits are not per-function and do not dangle on a partial trim).

Per-function grep `grep -rn "<funcname>" tools/ tests/` (excluding own file) returned **zero hits** for every whole-function deletion candidate in this batch.

---

## File 1: tests/regression_scheduler_bp_result_summary_guard.py — 104 lines — risk LOW

L3 reason (TSV line 99, "mid"): "parse_history_summary_state structure logic is real but tail asserts exact warning copy '结构不合法/解析失败' (line 56-101) brittle".

Re-mapping: the cited lines 56-101 cover three of the four test functions. On re-read these are NOT pure copy snapshots — they are the **differential oracle for the warning-emission contract** (which reason → warn vs stay quiet, and how many warnings). The exact Chinese fragments `"result_summary 结构不合法"`, `"result_summary 解析失败"` are short stable KEY fragments (substring `in`, not `==`), each paired with a behavioral assertion (count, `type=...` discriminator, `JSONDecodeError` presence). These are the contract, not cosmetic.

**Verdict: KEEP ENTIRE FILE. No trim.** Trimming the copy fragments would gut the only oracle distinguishing "structure invalid" from "decode failed" from "missing-and-quiet". The `type=list/int/NoneType/str/bool` asserts (lines 59-63) encode the discriminator branch and the `len(warnings) == N` lines (57, 84, 102) encode the "stay quiet on missing" contract. Under-trim is mandated here.

est_lines_removed: 0.

---

## File 2: tests/regression_scheduler_config_route_contract.py — 1155 lines — risk MID

L3 reason (TSV line 100, "high"): "real route+ConfigService provenance/degradation logic but test at line 326 reads template+constants asserting exact Chinese copy presence/absence is brittle snapshot".

Re-mapping: line 326 has drifted. The template+constants snapshot test is now `test_scheduler_config_template_graph_copy_matches_cycle_gate_stage` at **lines 328-349**.

### Brittle item 2a — DELETE WHOLE FUNCTION: `test_scheduler_config_template_graph_copy_matches_cycle_gate_stage` (lines 328-349)

This function reads `templates/scheduler/config.html` and `core/services/scheduler/config/config_constants.py` as raw text and asserts exact Chinese-copy presence/absence (`"阶段 2 只保存" not in template`, `"只看分析报告" in template`, `"参与候选排序" not in config_constants`, etc.). Pure doc/template-text snapshot — fails on any wording rephrase with no behavior change. The behavioral equivalent (that the GET route surfaces the right notice items) is already covered by `test_scheduler_config_route_uses_request_services` (see 2b — which we KEEP).

Grep `grep -rn "test_scheduler_config_template_graph_copy_matches_cycle_gate_stage" tools/ tests/` → no hits. Safe to delete whole function.

Anchor (delete from this line through the function's last assert, inclusive):
```
def test_scheduler_config_template_graph_copy_matches_cycle_gate_stage() -> None:
    template = (REPO_ROOT / "templates/scheduler/config.html").read_text(encoding="utf-8")
    config_constants = (REPO_ROOT / "core/services/scheduler/config/config_constants.py").read_text(encoding="utf-8")
```
…delete down to and including:
```
    assert "参与候选排序" not in config_constants
```
Keep context: the function ABOVE it (`test_scheduler_config_route_uses_request_services`, ends at line 325 `assert config_service.restore_default_called is True`) and the function BELOW it (`test_scheduler_config_post_uses_atomic_save_entrypoint`, starts line 352) are both KEPT. Remove the now-orphaned blank lines between them, leaving one blank-line separation.

### Brittle item 2b — TRIM ASSERT LINES inside KEPT function `test_scheduler_config_route_uses_request_services` (lines 290-302)

This GET-route test is REAL (it exercises the request-level ConfigService → renders payload). But its middle block asserts presence/absence of exact Chinese notice copy in `current_config_notice_items`:
```
    assert "阶段 2" not in notice_text
    assert "尚未接入" not in notice_text
    assert "只看分析报告" in notice_text
    assert "参与排产" in notice_text
    assert "先排普通方案" in notice_text
    assert "report 会生成只读报告" not in notice_text
    assert "on 当前先按 report-only" not in notice_text
    assert "不会让图分析参与 ready 队列" not in notice_text
    assert "on 会先做图安全检查" not in notice_text
    assert "可用 DAG 会用 ready 队列参与 SGS 候选" not in notice_text
    assert "参与候选排序" not in notice_text
    assert "图评分" not in notice_text
    assert "仍不启用图评分" not in notice_text
```
These 13 lines (290-302) are exact-copy presence/absence snapshots of notice text — the same brittle class as 2a. **Trim these 13 lines AND the two lines that build `notice_text` (line 289 `notice_text = json.dumps(...)` and there is no separate trailing use).** Wait — `notice_text` is defined at line 289 and used only by these asserts. After removing the asserts, also remove line 289.

Anchor for removal (delete this contiguous block, lines 289-302):
```
    notice_text = json.dumps(payload["current_config_notice_items"], ensure_ascii=False)
    assert "阶段 2" not in notice_text
    assert "尚未接入" not in notice_text
    assert "只看分析报告" in notice_text
    assert "参与排产" in notice_text
    assert "先排普通方案" in notice_text
    assert "report 会生成只读报告" not in notice_text
    assert "on 当前先按 report-only" not in notice_text
    assert "不会让图分析参与 ready 队列" not in notice_text
    assert "on 会先做图安全检查" not in notice_text
    assert "可用 DAG 会用 ready 队列参与 SGS 候选" not in notice_text
    assert "参与候选排序" not in notice_text
    assert "图评分" not in notice_text
    assert "仍不启用图评分" not in notice_text
```
Keep context AROUND it: the asserts ABOVE (lines 280-288: status_code 200, `builtin_presets`, `current_config_state` fields, `auto_assign_persist_state`) are STRUCTURAL invariants — KEEP. The asserts BELOW (lines 303-320: `toggles` set equality, toggle id/name/checked_attr/submitted_value) are STRUCTURAL — KEEP. The function keeps ~22 meaningful behavioral asserts after this trim; it does NOT become assertion-empty.

CAUTION on partial-trim within 2b: line 318 `assert "不保证每次一定更好" in toggles["ortools_enabled"]["desc"]` is a copy fragment too, but it is the only assertion that the ortools toggle carries a *description payload at all* and is a short stable fragment — borderline. **KEEP it** (bias-to-keep; deleting it removes the only check that `desc` is populated for that toggle). Do NOT extend the trim past line 302.

### Items explicitly KEPT (not brittle)
- `test_scheduler_config_legacy_wrapper_loads_only_scheduler_config_leaf` (779-804): runs a subprocess and asserts module-load topology (`loaded_pages is False`, `loaded_registrar is False`). This is a STRUCTURAL import-isolation contract (catches a real lazy-import regression), not a copy snapshot. KEEP.
- `test_scheduler_config_legacy_wrapper_uses_domain_registrar_source_of_truth` (1150-1155): reads `web/routes/scheduler_config.py` source and asserts `"load_scheduler_route_module" in source` and `".domains.scheduler.scheduler_analysis" not in source`. This is a thin source-grep, BUT it guards the legacy-wrapper-delegates-to-registrar invariant (a real architectural contract that a refactor could silently break by inlining). It is 3 asserts on stable symbol names (not Chinese copy). Borderline brittle. **KEEP (bias-to-keep)** — symbol-name greps for an architectural single-source-of-truth are lower brittleness than copy snapshots, and this is the only guard for that wrapper contract.
- All POST save-outcome / flash-text-label tests (352-1148): these assert field-LABEL-ization and "no raw field name leaked" — behavioral security/UX contracts. KEEP all.

est_lines_removed: ~22 (function 2a ≈ 9 incl. blanks; block 2b ≈ 14). Net ~22 after collapsing blank lines. risk MID — this file is partly a config-route quality gate; the two deletions are pure template/notice copy snapshots and the load-bearing route+save-outcome behavior is fully retained.

---

## File 3: tests/regression_scheduler_dispatch_plan_identity_guardrails.py — 498 lines (file has 499 incl. trailing) — risk MID

L3 reason (TSV line 101, "high"): "real ResourceDispatchService plan-identity write guardrails+readonly DB checks but tails read templates asserting copy presence (line 297-302) brittle".

Re-mapping: the cited block 297-302 is inside `test_current_official_dispatch_surfaces_write_guardrail_in_page_data_and_excel`. On re-read, lines 299-304 are the brittle template-grep tail; lines 296-297 are openpyxl summary-cell *copy snapshots*. Let me classify precisely.

### Brittle item 3a — TRIM ASSERT LINES inside KEPT function `test_current_official_dispatch_surfaces_write_guardrail_in_page_data_and_excel` (lines 299-304)

The template-source grep block:
```
        template_source = (REPO_ROOT / "templates/scheduler/resource_dispatch.html").read_text(encoding="utf-8")
        assert "plan_identity.guardrail_text" in template_source
        assert "ui.summary_item('查看方案'" in template_source
        assert "ui.summary_item('计划身份'" not in template_source
        assert "ui.summary_item('现场记录'" not in template_source
        assert "ui.summary_item('派工反馈'" not in template_source
```
These read the Jinja template as text and assert presence/absence of `ui.summary_item('…')` macro-call literals and `plan_identity.guardrail_text` token. Pure template-text snapshot — fails on a template refactor (e.g. renaming the summary helper, restructuring the macro) with no behavior change. The behavioral guarantee (page context carries `guardrail_text`, excel summary shows the right labels) is already asserted in the SAME function via `page["plan_identity"]["guardrail_text"]` (284-285), `data["plan_identity"]` (289-293), and `summary["计划身份"]`/`summary["现场记录说明"]` (296-297).

**Trim lines 299-304** (the `template_source` read + its 5 asserts). Keep everything above (the page-context, payload, and excel-summary behavioral asserts at 282-297). The function retains ~16 behavioral asserts.

Anchor (delete this contiguous block):
```
        template_source = (REPO_ROOT / "templates/scheduler/resource_dispatch.html").read_text(encoding="utf-8")
        assert "plan_identity.guardrail_text" in template_source
        assert "ui.summary_item('查看方案'" in template_source
        assert "ui.summary_item('计划身份'" not in template_source
        assert "ui.summary_item('现场记录'" not in template_source
        assert "ui.summary_item('派工反馈'" not in template_source
```
Keep context: the line ABOVE (297, `assert summary["现场记录说明"] == "这套是当前可执行的正式采用方案…"`) is KEPT — see note 3-KEEP below. The `finally: conn.close()` block at 305-306 stays. Watch indentation — these are inside a `try:` so removal leaves the `try` body ending at line 297.

### Items explicitly KEPT (not brittle) — note 3-KEEP
- Lines 296-297 (`summary["计划身份"] == "正式采用方案；可以填写现场实际"` and `summary["现场记录说明"] == "…按规则填写现场实际。"`): these are openpyxl summary-cell value `==` exact-string snapshots, which the brittle taxonomy normally flags. **KEEP them.** Rationale: this user-facing guardrail copy is the *contract surface* a shop-floor operator reads to know whether they may write actual production data; there is no ErrorCode/enum behind it, and the same strings are asserted as a *write-permission consequence* (paired with `can_write_feedback`). Trimming the exact string would leave no oracle that the official-plan path emits the affirmative-write copy rather than the read-only copy. Bias-to-keep applies. (These are `==` not layout-coordinate snapshots; the cell *coordinate* is not asserted — `_summary_values` keys by row label, so this is value-by-key, not B7-layout brittleness.)
- `test_history_comparison_and_scenario_plans_are_read_only_with_plain_reasons` (309-374): all `can_dispatch/can_write_feedback is False` + `kind_label` + guardrail-fragment asserts are the READ-ONLY ENFORCEMENT contract. KEEP entirely.
- `test_public_payload_and_export_never_show_internal_plan_identity_fields` (377-415): forbidden-key/leak checks — SECURITY contract. KEEP entirely.
- `test_plan_identity_write_flags_cannot_be_overridden_by_outer_fields` (418-439): write-flag override-resistance — SECURITY/integrity contract. KEEP.
- `test_resource_dispatch_get_data_and_export_do_not_write_schedule_or_execution_events` (442-498): row-count-before/after + no-confirm-route checks are transaction/safety contracts. The two tail asserts (495-496, `routes_source.read_text` then `"/resource-dispatch/confirm" not in routes_source` and `"resource_dispatch_confirm" not in routes_source`) ARE a source-grep — borderline brittle. **KEEP (bias-to-keep)**: they guard the "no write-confirm route exists" invariant for which the table-name check (489-490) is the runtime half; deleting the source-grep weakens the "GET stays read-only" guarantee and the grep is on stable route-symbol names, not copy. Under-trim here.

est_lines_removed: ~6 (block 3a). risk MID — this file is a write-guardrail/security regression; the only trim is a Jinja template-text snapshot whose behavioral equivalent is already asserted in the same function.

---

## File 4: tests/regression_scheduler_historical_plan_label_contract.py — 210 lines (211 incl. trailing) — risk MID

L3 reason (TSV line 102, "mid"): "viewmodel public_plan_role_options/build_report_context logic real (line 165-208) but route tests assert exact HTML span markup+literal labels via regex (line 54-162) brittle snapshot".

Re-mapping: lines 165-208 → the three pure-viewmodel tests (`public_plan_role_options` ×2 + `build_report_context`) are now at **167-210**; the route-rendered HTML-regex tests are at **81-164** plus the regex helpers at **56-78**.

### Analysis of the route tests (81-164)
These spin up a Flask client, seed a superseded version, hit real routes (`/scheduler/gantt`, `/scheduler/week-plan`, `/reports/`, `/scheduler/resource-dispatch`, `/reports/overdue`, week-plan export) and assert via regex against rendered HTML span markup. This is a mix:
- The `_assert_context_plan_label` / `_assert_selected_plan_option_label` helpers (56-78) bake in exact HTML structure: `<span class="aps-context-label">方案</span><span class="aps-context-value">…</span>` and `<option value="adopted" … selected …>`. The CSS-class + tag structure is brittle (a template markup refactor breaks it). BUT the *label string* being matched (`历史正式方案（已被新版本替代）` vs the wrong `正式采用方案`) is the real behavioral contract: "a superseded adopted version must be relabeled as historical everywhere, and must NOT show the live-official label."

Re-classifying with bias-to-keep: the route tests verify a genuine cross-page invariant (the same relabel happens in gantt, week-plan, week-plan-export, reports-index, resource-dispatch, overdue-filter, plus the export filename + xlsx summary). That breadth IS the contract — it catches a real bug where one surface forgets to relabel. The brittleness is concentrated in the **HTML-span/CSS-class structure inside the regexes**, not in the assertions' intent.

**Verdict for File 4: KEEP all route tests; do a NARROW helper-level trim of the structural CSS-class coupling only IF it can be done without losing the label oracle — but it cannot be done cheaply (the regex needs *some* anchor to locate the label). Therefore KEEP the helpers as-is and KEEP all route tests.** The only item I would trim is the redundant wrong-label negative inside `_assert_context_plan_label` (`wrong_pattern` for `正式采用方案`, lines 62-66) — but that negative IS the "must not still show live-official label" half of the contract and catches the most likely regression (relabel applied to display but old value leaks elsewhere). Bias-to-keep: **KEEP it too.**

The export test (104-118) asserts `resp.status_code == 200`, Content-Disposition contains `历史正式方案`, and xlsx summary `方案 == "历史正式方案（已被新版本替代）"` + `!= "正式采用方案"`. These are value-by-key (not B-cell-layout) + status code — KEEP.

The unknown-plan-role redirect test (121-128): `status_code == 302` + `"future_role" not in location` — SECURITY (no raw-role leak) contract. KEEP.

The reports-index test (131-143): `"这是历史正式方案，只能查看" in html`, `"复盘正式方案" not in html`, `"查看计划和现场实际" in html` — these are full-page substring copy snapshots, the most brittle items in the file. BUT they are the differential oracle (read-only-historical copy present, live-official copy absent) with no ErrorCode behind them and a real bug class (showing the editable-official affordance on a historical plan). **KEEP (bias-to-keep).**

### Verdict: KEEP ENTIRE FILE. No trim.
The viewmodel tests (167-210) are obviously real. The route tests, on close reading, each carry the cross-surface relabel contract with no cheaper anchor; the brittleness is structural-regex coupling that cannot be removed without deleting the only label oracle. Per the explicit bias ("when the exact string IS the contract with no other anchor, KEEP it"), this file is KEEP-all. Mark risk MID and note in the registry that this file's value is the breadth of surfaces — do not narrow it later without a replacement oracle.

est_lines_removed: 0.

(If the implementation team later insists on a trim here, the ONLY defensible micro-trim is collapsing the duplicated `_seed_newer_executable_version(13)` calls — but that is dedup, not de-brittling, and out of scope for KEEP_TRIM. Leave it.)

---

## File 5: tests/regression_scheduler_plan_identity_summary_guardrail.py — 411 lines (412 incl. trailing) — risk MID

L3 reason (TSV line 103, "mid"): "resolve_plan summary parse_failed/superseded/writable logic real (line 116-223) but dashboard/dispatch/review tests assert exact visible Chinese copy+href absence on rendered pages (line 36-113 226-410) brittle snapshot".

Re-mapping: the resolve_plan-logic tests (`test_bad_newer_summary_does_not_promote…`, `test_blocked_or_missing_summary…`, `test_empty_schedule_detail…`) are at 118-225 (the cited 116-223 shifted by ~2). The dashboard/dispatch/review rendered-page tests are 38-115 (helpers + `test_bad_current_result_summary…`) and 228-412.

### Analysis
The "brittle" tail per the reason is the visible-Chinese-copy + href-absence assertions on rendered pages. On re-read these are NOT cosmetic snapshots — they encode a **specific anti-fabrication / fail-soft contract**: when `result_summary` is bad/missing or the version is superseded/invalid, the page must show a visible *data-gap* notice ("当前排产摘要读取失败", "数据不足", "当前请求不可用", "请求的排产版本 v999 不存在") AND must NOT (a) fabricate zeros ("超期批次 0" not in text, "设备利用率 0%" not in text), (b) 500, or (c) expose the write/feedback affordances (`href="/reports/execution-review"` absent, `data-actual-record-url-template=` absent). Each Chinese phrase is paired with a behavioral negative (no-fake-zero / no-feedback-link / no-500). This is the core regression the whole file exists to lock.

Critically, several asserts are href/link STRUCTURAL checks, not copy:
- `_assert_no_path_links(dashboard, {"/reports/execution-review"})` (50)
- `'href="/reports/execution-review' not in dispatch_html`, `data-actual-*-url` absent (63-66)
- analysis-link version checks (254-267): `version=12` present, `version=999` absent — these encode the "redirect to latest, never echo the bad version" rule.

The Chinese phrases here are **short stable gap-notice keys** (`"数据不足"`, `"当前请求不可用"`) used as `in` substrings, each as the visible half of a behavior the negative asserts. There is no ErrorCode surface for these user-facing fail-soft notices — the phrase IS the contract anchor. Per the bias rule, KEEP.

### Verdict: KEEP ENTIRE FILE. No trim.
The pure-logic tests (118-225) are real `plan_identity` resolution contracts. The rendered-page tests are fail-soft / anti-fabrication / no-feedback-leak contracts where the Chinese gap-notice phrase is the only anchor and is always paired with a behavioral negative (no fake zero, no 500, no write link). Trimming the phrases would delete the visible-gap oracle and leave only "page rendered 200" which does not catch the fabrication bug. Under-trim mandated.

est_lines_removed: 0. risk MID (it reads like a copy snapshot but is a fail-soft behavioral gate — explicitly preserved).

---

## File 6: tests/regression_scheduler_route_enforce_ready_tristate.py — 487 lines (488 incl. trailing) — risk LOW

L3 reason (TSV line 104, "high"): "tri-state enforce_ready/strict_mode form parsing across run/simulate/plugin/backup/part/batch routes+form_yes_no_value contract (line 279-459) real logic but tail reads templates+vm source asserting copy presence (line 461-475)".

Re-mapping: the cited tail 461-475 is the template + viewmodel-source grep block at the end of `main()`. Current lines: **463-477**.

### Brittle item 6a — TRIM ASSERT/STATEMENT LINES inside KEPT `main()` (lines 463-477)

The tail of `main()` opens two templates + one viewmodel source and asserts token/copy presence:
```
    tpl_path = os.path.join(repo_root, "templates", "scheduler", "batches.html")
    run_panel_path = os.path.join(repo_root, "templates", "scheduler", "_run_panel.html")
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    with open(run_panel_path, "r", encoding="utf-8") as f:
        tpl += "\n" + f.read()
    assert "ui.toggle(option.toggle" in tpl, "batches.html 应通过 viewmodel toggle 对象渲染运行选项"
    assert "run_options" in tpl, "batches.html 缺少 run_options 入口"
    assert "发现参数问题就停止排产" in tpl, "batches.html 缺少 strict_mode 文案"

    vm_path = os.path.join(repo_root, "web", "viewmodels", "scheduler_run_options.py")
    with open(vm_path, "r", encoding="utf-8") as f:
        vm_source = f.read()
    assert '"enforce_ready"' in vm_source, "scheduler_batches_page.py 缺少 enforce_ready toggle"
    assert '"strict_mode"' in vm_source, "scheduler_batches_page.py 缺少 strict_mode toggle"
```
This is a template-text + viewmodel-source grep: `"ui.toggle(option.toggle" in tpl`, `"发现参数问题就停止排产" in tpl` (exact Chinese copy), `'"enforce_ready"' in vm_source`. Pure source/template snapshot — breaks on any template/vm rename or copy edit with no behavior change. The actual tri-state form-parsing behavior (the contract the file exists for) is fully exercised by the route-invocation helpers and `_assert_form_parser_contract` ABOVE this block, which call the real routes and assert `enforce_ready is None/True/False`, `strict_mode`, and ValidationError-on-bad-value.

**Trim lines 463-477** (the two template reads + 3 template asserts + the vm read + 2 vm asserts). The KEPT body of `main()` ends at the last route-behavioral assert (line 461, `batch_excel_preview.get("strict_mode") is True …`) followed by `print("OK")`.

Anchor (delete this contiguous block, between the last `batch_excel_preview` assert and `print("OK")`):
```
    tpl_path = os.path.join(repo_root, "templates", "scheduler", "batches.html")
    run_panel_path = os.path.join(repo_root, "templates", "scheduler", "_run_panel.html")
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    with open(run_panel_path, "r", encoding="utf-8") as f:
        tpl += "\n" + f.read()
    assert "ui.toggle(option.toggle" in tpl, "batches.html 应通过 viewmodel toggle 对象渲染运行选项"
    assert "run_options" in tpl, "batches.html 缺少 run_options 入口"
    assert "发现参数问题就停止排产" in tpl, "batches.html 缺少 strict_mode 文案"

    vm_path = os.path.join(repo_root, "web", "viewmodels", "scheduler_run_options.py")
    with open(vm_path, "r", encoding="utf-8") as f:
        vm_source = f.read()
    assert '"enforce_ready"' in vm_source, "scheduler_batches_page.py 缺少 enforce_ready toggle"
    assert '"strict_mode"' in vm_source, "scheduler_batches_page.py 缺少 strict_mode toggle"
```
Keep context: line ABOVE = `    assert batch_excel_preview.get("strict_mode") is True, f"批次 Excel strict_mode 反序提交应识别 yes：{batch_excel_preview!r}"` (461). Line BELOW = `    print("OK")` (479). After removal, `main()` flows straight from the last route assert into `print("OK")`. Collapse the surrounding blank lines to one.

Note on `find_repo_root()` / `repo_root`: `repo_root` is still used earlier in `main()` (for `sys.path` insert and inside the helper invocations indirectly), so do NOT remove the `find_repo_root()` call or the `repo_root` variable. Only the `tpl_path`/`run_panel_path`/`vm_path` locals (defined inside the deleted block) go away. No import becomes unused (`os` still used by `find_repo_root`).

est_lines_removed: ~15 (block 6a). risk LOW — the deleted block is a pure template/vm source grep; the entire tri-state form-parsing behavior is retained in the route-invocation harness above it.

---

## File 7: tests/test_greedy_refactor_contracts.py — 1118 lines — risk LOW

L3 reason (TSV line 105, "high"): "deep algorithm tests legacy callback/seed normalize/auto-assign root-cause/strict reject (line 124-1117) but trim source-grep import contracts+line-count<500+function-span<80+radon complexity<15 gate snapshots (line 56-101)".

Re-mapping: confirmed accurate. The real algorithm tests are 126-1117 (callback/seed/auto-assign/sgs/strict). The structural-gate snapshots are at 58-103, plus their helper machinery at 5/13-55. NOT referenced by any tools/ registry (greedy file absent from registry).

### Brittle item 7a — DELETE WHOLE FUNCTION: `test_refactored_files_and_entry_functions_stay_under_quality_gate` (lines 86-100)
Asserts every refactored file is `< 500` lines and named entry functions are `<= 80` lines. Pure line-count/function-span structural gate — fails on any benign line growth (adding a comment or a guard) with zero behavior change. Classic structural snapshot.
Grep → no hits. Delete whole function.

### Brittle item 7b — DELETE WHOLE FUNCTION: `test_refactored_algorithm_files_stay_under_complexity_threshold` (lines 102-103)
Asserts radon cyclomatic complexity `<= 15` across the files. Pure complexity-gate snapshot. Grep → no hits. Delete whole function.

### Brittle item 7c — DELETE WHOLE FUNCTION: `test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers` (lines 58-63)
Reads `schedule_optimizer.py` source and asserts exact import-line presence/absence (`"from core.algorithms.ordering import …" in text`). Source-grep import contract — brittle (breaks on import reformatting/aliasing). Grep → no hits. Delete whole function.

### Brittle item 7d — DELETE WHOLE FUNCTION: `test_dispatch_modules_do_not_call_scheduler_private_callbacks` (lines 75-83)
Reads `batch_order.py` + `sgs.py` source and asserts `"._schedule_internal" not in text` etc. Source-grep decoupling contract — brittle. Grep → no hits. Delete whole function.
NOTE: the *behavioral* version of this decoupling (dispatch modules actually use the legacy callback wrapper, not private internals) is covered by `test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper` (669) and `test_run_context_enforces_strict_internal_input_before_legacy_callback` (719), which we KEEP — so deleting the source-grep does not lose the real coverage.

### KEEP: `test_scheduler_keeps_legacy_ordering_helper_export` (66-72)
This imports the real function and asserts its behavior (`resolve_batch_sort_batch_id("", batch) == "B-FIELD"`). Behavioral, not source-grep. KEEP.

### Orphaned-helper cleanup after 7a-7d
After deleting 7a/7b/7c/7d, these module-level helpers become unused and should ALSO be removed (they exist only for the gate tests):
- `REFACTORED_ALGORITHM_FILES` tuple (lines 14-27) — used only by 7a (88) and 7b (103). DELETE.
- `_module_text` (30-31) — used by 7c (59), 7d (76-77), `_function_span` (35), `_line_count` (44), `_complexity_violations` (52). After deleting 7a-7d AND `_function_span`/`_line_count`/`_complexity_violations`, `_module_text` has no remaining callers → DELETE.
- `_function_span` (34-40) — used only by 7a (99). DELETE.
- `_line_count` (43-44) — used only by 7a (88). DELETE.
- `_complexity_violations` (47-54) — used only by 7b (103). DELETE.
- `import ast` (line 5) — used only by `_function_span`. DELETE.
- `from typing import List, Tuple` (line 9): VERIFIED `grep -nE "List\[|Tuple\["` shows `List[`/`Tuple[` appear ONLY at line 9 (this import) and line 47 (`_complexity_violations` signature/return). After deleting `_complexity_violations`, both names are fully orphaned → **DELETE line 9 entirely**.
- `Path` (line 7) + `ROOT` (line 13): VERIFIED `grep -n "ROOT"` shows `ROOT` used ONLY at line 13 (def) and line 31 (inside `_module_text`); `grep -n "Path"` shows `Path` used ONLY at lines 7 (import) and 13. After deleting `_module_text`, `ROOT` is orphaned, and `Path` is used only by `ROOT` → **DELETE both line 7 (`from pathlib import Path`) and line 13 (`ROOT = ...`)**. Confirmed safe (no other consumers in 126-1117).

Anchors for the four function deletions (each: delete from its `def` line through its last assert):
```
def test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers() -> None:
    text = _module_text("core/services/scheduler/run/schedule_optimizer.py")
    ...
    assert "from core.algorithms.greedy.scheduler import build_normalized_batches_map" not in text
```
```
def test_dispatch_modules_do_not_call_scheduler_private_callbacks() -> None:
    ...
        assert "scheduler.calendar" not in text
```
```
def test_refactored_files_and_entry_functions_stay_under_quality_gate() -> None:
    ...
        assert _function_span(relative_path, function_name) <= max_lines
```
```
def test_refactored_algorithm_files_stay_under_complexity_threshold() -> None:
    assert _complexity_violations(REFACTORED_ALGORITHM_FILES, threshold=15) == []
```
Keep context: `test_scheduler_keeps_legacy_ordering_helper_export` (66-72) stays between the deletions. The `class _Calendar:` block (106+) and everything below is the real algorithm suite — fully KEPT.

est_lines_removed: ~70 (4 functions ≈ 36 lines + 5 helpers/tuple ≈ 30 lines + 2-3 import lines). Conservative net ≈ 65-72. risk LOW — file not registry-coupled; deletions are line-count/complexity/source-grep gates whose behavioral equivalents are retained; orphan-helper cleanup is mechanical with verify-greps specified.

---

## File 8: tests/test_scheduler_run_view_result_contract.py — 910 lines — risk LOW

L3 reason (TSV line 106, "high"): "build_run_schedule_view_result headline/status/warning-filter/overdue-sample/secret-sanitization+route flash behavior (line 23-908) deep viewmodel logic but trim source-grep test asserting route symbols absent (line 372-380)".

Re-mapping: the source-grep test is now `test_scheduler_run_route_does_not_parse_display_state_inline` at **lines 374-382**.

### Brittle item 8a — DELETE WHOLE FUNCTION: `test_scheduler_run_route_does_not_parse_display_state_inline` (lines 374-382)
Reads `web/routes/domains/scheduler/scheduler_run.py` source, slices the `run_schedule()` body, and asserts symbol absence (`"build_summary_display_state" not in run_body`, `"overdue_batches" not in run_body`, etc.). Pure source-grep "route doesn't inline parsing" contract — brittle (breaks on any refactor that reorganizes the route even when behavior is unchanged). The behavioral equivalent (the route delegates classification to the viewmodel and flashes the right category) is covered by the route-flash tests below it (`test_scheduler_run_route_flashes_failed_result_and_overdue_sample_limit` 385+, etc.).
Grep `grep -rn "test_scheduler_run_route_does_not_parse_display_state_inline" tools/ tests/` → no hits. Delete whole function.

Anchor (delete from `def` through last assert):
```
def test_scheduler_run_route_does_not_parse_display_state_inline() -> None:
    route_source = (REPO_ROOT / "web/routes/domains/scheduler/scheduler_run.py").read_text(encoding="utf-8")
    run_body = route_source.split("def run_schedule():", 1)[1]

    assert "build_summary_display_state" not in run_body
    assert "summary_display" not in run_body
    assert 'result.get("summary")' not in run_body
    assert 'result.get("overdue_batches")' not in run_body
    assert "overdue_batches" not in run_body
```
Keep context: function ABOVE = `test_run_schedule_view_result_rejects_unscheduled_batch_warning_with_any_sample_tail` (ends line 371). Function BELOW = `test_scheduler_run_route_flashes_failed_result_and_overdue_sample_limit` (starts 385). Both KEPT. `REPO_ROOT` is still used by the other route tests (e.g. sys.path insert at 386-387) so do NOT remove it. Collapse blank lines to one.

### Everything else KEPT
All `build_run_schedule_view_result` tests (25-371) are deep viewmodel logic: success/failed/unknown classification (never-default-to-success), internal-warning filtering, secret/path sanitization (`/tmp/private.db`/`SECRET_TOKEN` not leaked — SECURITY), overdue-sample-limit-10, field-warning-raw-tail rejection. All route tests (385-908) assert real flash category + gantt redirect + version validation + ValidationError-vs-unexpected-exception boundary. KEEP all.

est_lines_removed: ~10 (function 8a ≈ 9 + 1 blank). risk LOW — single source-grep function; all viewmodel + route behavioral coverage retained; not per-function registry coupled.

---

## Batch summary

| File | lines | trim type | est removed | whole-fn deleted | b4 |
|---|---|---|---|---|---|
| bp_result_summary_guard | 104 | none (KEEP all) | 0 | — | no |
| config_route_contract | 1155 | doc_snapshot + within-fn copy trim | ~22 | template_graph_copy gate fn | no |
| dispatch_plan_identity_guardrails | 498 | js/template source grep (within-fn) | ~6 | — | no |
| historical_plan_label_contract | 210 | none (KEEP all — full-page/regex contract) | 0 | — | no |
| plan_identity_summary_guardrail | 411 | none (KEEP all — fail-soft gate) | 0 | — | no |
| route_enforce_ready_tristate | 487 | template+vm source grep (within-fn) | ~15 | — | no |
| test_greedy_refactor_contracts | 1118 | line-count/complexity/source-grep gates | ~70 | 4 gate fns + 5 helpers | no |
| test_scheduler_run_view_result_contract | 910 | route source grep | ~10 | does_not_parse_display_state_inline | no |

No B-4 red-line files in this batch (B-4 cites only test_enum_display_consistency.py and regression_schedule_result_view_context.py, neither here).

Registry coupling: 7 of 8 files are listed by FILE PATH in tools/test_registry_data.py + tools/test_registry_groups_scheduler.py; greedy is not registry-listed. No registry references any function nodeid. All proposed deletions keep their file non-empty, so no registry reference dangles. registry_refs_found is empty for every deletion (per-function grep returned zero hits in all cases).

Net est lines removed across batch: ~123.
