# KEEP_TRIM Spec — Batch B09_sched_a

Scope: 20 scheduler/optimizer regression files. L3 verdict = KEEP_TRIM (high value mixed with brittle tails).

## Global findings (apply to all 20 files)

- **No registry/contract/debt coupling at the function level.** `tools/test_registry_data.py` (a pure data module) and `tools/test_registry_groups_scheduler.py` pin only **file paths**, never `::test_func` nodeids (grep for `::` in both files = 0). So:
  - Never delete a whole FILE in this batch (every file is registry-pinned by path).
  - Deleting individual test FUNCTIONS is safe **provided each file keeps ≥1 test function** so the file stays non-empty.
  - `registry_refs_found` is therefore empty for every file.
- **Shared helpers must survive.** `tests/regression_scheduler_analysis_diagnostic_error_contract.py` imports `_full_graph_summary`, `_iter_text`, `_summary_with_graph` from `regression_scheduler_analysis_diagnostic_contract.py` (line 9-13). Do NOT delete those three helpers in the contract file.
- **Trim granularity:** this batch is overwhelmingly **(a) assert-line trims inside kept functions**, not whole-function deletion. Most files are tight, single-contract regressions where the only brittle thing is one Chinese-substring assert. Several files have **nothing to trim** (pure behavioral contracts) and are listed as KEEP-WHOLE.
- **Security `X not in html/text` asserts are NOT brittle** — they catch real data-leak regressions. Always KEEP them. Only positive `"完整中文文案" in/== rendered` snapshots are trim candidates, and only when a structural sibling already covers the contract.

---

## 1. tests/regression_auto_assign_empty_resource_pool.py — 94 lines — KEEP WHOLE (no trim)

Single test `test_auto_assign_empty_resource_pool`. Reason flags line:106 (`assert any("缺少自动派工所需工种信息" ...)`, now at **line 92**) as a Chinese-substring assert.

**Decision: KEEP the Chinese assert.** This is the central behavioral contract of the test — that an explicit empty `resource_pool={}` still enters the auto-assign branch and surfaces the op-type-missing reason. There is **no ErrorCode anchor** on `summary.errors` (it is a free-text error list), so the substring fragment IS the only contract anchor. The surrounding counts (lines 86-89: total_ops/scheduled_ops/failed_ops/len(results)) are real structural invariants. Nothing brittle to remove.

Risk: low. est removed: 0.

---

## 2. tests/regression_optimizer_ortools_logging_exc_info_safe.py — 51 lines — TRIM 1 line

Single test `test_optimizer_ortools_logging_exc_info_safe`. Reason flags line:58 (now **line 47**) exact Chinese warning phrase.

Structural asserts (KEEP): line 44 `fallback_counts.get("ortools_warmstart_failed_count") == 1`, line 45 `len(logger.warnings) == 1` (the load-bearing "only called once / no second crash" contract), line 48 `"ortools boom (test)" in warning`, line 49 `"RuntimeError: ortools boom (test)" in warning` (exception type+message propagation — real).

**BRITTLE (trim):** the pure UI-copy line.
- Anchor (delete this exact line):
  ```
      assert "OR-Tools 预热失败（已忽略）" in warning, warning
  ```
- Keep context: the line immediately above (`warning = logger.warnings[0]`) and the two lines below (`"ortools boom (test)" in warning` / `"RuntimeError: ..." in warning`) stay. After trim the function still asserts call-count==1, the exception class is rendered, and the message is rendered — the only thing dropped is the fixed Chinese prefix copy.
- Why brittle: the prefix `OR-Tools 预热失败（已忽略）` is decorative copy with no code/key; renaming the prefix is cosmetic and would not indicate a regression in the logging-robustness behavior the test exists to guard.

Risk: low. est removed: 1.

---

## 3. tests/regression_optimizer_public_summary_projection_contract.py — 391 lines — KEEP WHOLE (no trim)

5 tests. Reason flags line:96,202 (`source_label == "多起点方案"`, now at **line 98** and **line 204**).

**Decision: KEEP both `source_label` asserts.** `"多起点方案"` is not a UI-copy snapshot — it is the public projection's contract label that distinguishes a *public* attempt from a *diagnostic* attempt. The projection rule "every public attempt gets `source_label='多起点方案'`" is exactly what `project_public_algo_summary` guarantees; in `test_candidate_rejected_attempt_is_diagnostic_only` (line 196-206) the label is part of a full-dict equality that also encodes which fields survive projection. Removing it would weaken the field-set contract. Everything else (field-stripping `algo_stats/used_params/tag not in`, compaction `len==11`, `SUMMARY_SIZE_LIMIT_BYTES` truncation) is hard behavioral contract.

Risk: low. est removed: 0.

---

## 4. tests/regression_resource_reference_guard_schedule.py — 118 lines (119 incl. trailing) — TRIM 3 lines

4 tests. Real DB guard contract: ErrorCode assertions (`MACHINE_IN_USE`/`OPERATOR_IN_USE`/`MACHINE_NOT_FOUND`) at lines 55, 79, 103, 116 — all KEEP. Reason flags line:54,78,102 Chinese message substrings.

**BRITTLE (trim) — three message-substring asserts, each paired with a kept ErrorCode assert on the line above:**
- Anchor A (delete):
  ```
        assert "排程结果引用" in exc_info.value.message
  ```
  (immediately after `assert exc_info.value.code == ErrorCode.MACHINE_IN_USE`, line 55, in `test_machine_delete_blocks_schedule_only_reference`)
- Anchor B (delete):
  ```
        assert "排程结果引用了设备" in exc_info.value.message
  ```
  (after MACHINE_IN_USE in `test_machine_replace_blocks_schedule_only_reference`)
- Anchor C (delete):
  ```
        assert "排程结果引用了人员" in exc_info.value.message
  ```
  (after OPERATOR_IN_USE in `test_operator_replace_blocks_schedule_only_reference`)
- Keep context: in each case the `assert exc_info.value.code == ErrorCode.X` line directly above stays and remains the contract anchor; each function keeps a meaningful assertion (the ErrorCode). `test_machine_delete_missing_raises_not_found` has no message assert and is untouched.
- Why brittle: the ErrorCode is the stable contract; the Chinese phrase is reworded copy. The codes already differentiate machine-vs-operator and in-use-vs-not-found.

Risk: low. est removed: 3.

---

## 5. tests/regression_schedule_history_not_created_for_empty_schedule.py — 83 lines — KEEP WHOLE (no trim)

Single test. Reason flags line:89 (`"所选批次没有可重排工序，本次未执行排产。" in message`, now at **line 68**).

**Decision: KEEP the message assert.** The no-op safety contract has no ErrorCode anchor (ValidationError message is free text), and the surrounding DB-snapshot invariants (lines 71-76: `before==after`, latest_version/history/schedule/log/version_seq all 0) are the real value — but the message assert is what proves the *correct* ValidationError fired (vs an unrelated one). Dropping it would let any ValidationError pass. The exact string IS the contract. KEEP.

Risk: low. est removed: 0.

---

## 6. tests/regression_schedule_params_read_failure_visible.py — 89 lines — KEEP WHOLE (no trim)

Single test driving a helper `_assert_visible_read_failure`. Reason flags line:74,90 public-label text.

**Decision: KEEP.** The helper asserts `exc.field == expected_field` (the real field-routing contract) AND `expected_text in str(exc.message)` where `expected_text` ∈ {`排产策略`,`优先级权重`}. The localized field label is the fail-visible guarantee (the whole point of the test is "do NOT silently fallback — surface WHICH field"). The field name + label together are the contract; the label is the user-facing half with no separate code. KEEP both. Note: this file is registry-pinned (test_registry_data.py:144, test_registry_groups_scheduler.py:171) at file level — fine, not touched.

Risk: low. est removed: 0.

---

## 7. tests/regression_schedule_persistence_reject_empty_actionable_schedule.py — 366 lines — KEEP WHOLE (no trim)

`main()` legacy runner (line 39-120, not collected by pytest, no `test_` prefix) + 8 pytest tests. Reason flags the `@pytest.mark.parametrize` block line:122-146 (the 6 long Chinese root-error rows feeding `test_no_actionable_schedule_prefers_root_error_over_missing_resource_hint`).

**Decision: KEEP the parametrize and all rows.** Although the rows are long Chinese strings, the contract under test is *security/redaction + root-error-preference*, and the exact text IS the user-facing guarantee:
- The test asserts `expected_public_text in user_message` (root error surfaced verbatim) AND `"批次工序补充页补齐" not in user_message` (hint suppressed when a root error exists). These are real behavior, not cosmetic.
- The 6 rows deliberately cover **format-robustness** variants (trailing `。` vs not, nested punctuation `数车。精加工`, sequence-format vs op-code format). Trimming rows = deleting format-coverage of the redaction/extraction logic.
- The security tests `test_no_actionable_schedule_does_not_expose_unsafe_auto_assign_root_error` and `..._uses_later_safe_...` (lines 263-333) assert `Traceback/sqlite/password/path not in user_message` — pure behavioral, KEEP.

Per the spec's own rule ("if the exact string IS the contract with no other anchor, KEEP it") and BIAS=KEEP, no trim. (`main()` is dead-but-harmless; not in scope for de-brittling.)

Risk: low. est removed: 0.

---

## 8. tests/regression_schedule_result_view_context.py — 303 lines (304 incl. trailing) — TRIM 3 lines — **B-4 RED LINE**

10 tests. Reason + B-COMPAT note: trim region is the Chinese **notice** substrings inside the plan-role tests (stale :160/:183/:202, remapped below); the R22 bad-role oracle at stale :294-300 is OUTSIDE the trim region and **must NOT be touched**.

**B-4 protected (DO NOT TOUCH):** `test_gantt_plan_query_wrapper_keeps_legacy_bad_role_message` (current **lines 296-304**), specifically:
```
    assert "未知的排产方案角色：bad" in exc_info.value.message
    assert exc_info.value.field == "plan_role"
```
This is the R22 differential oracle. Leave the entire function intact.

**BRITTLE (trim) — the three `plan_role_notice` Chinese-copy asserts**, each sitting among real role/status asserts that already prove the branch:
- Anchor A (delete), in `test_context_falls_back_to_adopted_when_requested_role_is_missing` (current **line 162**):
  ```
      assert "正式采用方案" in context.plan_role_notice
  ```
  Keep context: lines 157-161 (`requested_role==BASELINE_BEST`, `selected_role==ADOPTED`, `plan_resolution["status"]=="fallback_to_adopted"`, `is_fallback is True`, `is_comparison is True`) stay — they fully encode the fallback contract.
- Anchor B (delete), in `test_context_marks_non_adopted_schedule_source_as_comparison` (current **line 185**):
  ```
      assert "只用来和正式采用方案比一比" in context.plan_role_notice
  ```
  Keep context: lines 180-184 (`source_table==SOURCE_SCHEDULE`, `is_comparison is True`, `fields["is_comparison"] is True`) stay.
- Anchor C (delete), in `test_context_no_history_uses_default_adopted_with_visible_fallback` (current **line 204**):
  ```
      assert "正式采用方案" in context.plan_role_notice
  ```
  Keep context: lines 198-203 (`has_history is False`, `selected_version is None`, role asserts, `is_fallback`, `is_comparison`) stay.
- Why brittle: `plan_role_notice` is user-facing copy; the *status/role/flag* asserts (`fallback_to_adopted`, `is_fallback`, `is_comparison`) are the structural contract and already differentiate the branches. The notice wording can be reworded without any behavior change.

Risk: mid (B-4 file; the trim is narrow and the protected oracle is in a separate function — clearly delineated). est removed: 3. b4_redline=true.

---

## 9. tests/regression_schedule_service_all_frozen_short_circuit.py — 224 lines — KEEP WHOLE (no trim)

Single test + helpers, monkeypatches module globals with finally-restore. Reason flags line:214,224 exact Chinese `expected_message` (now the two `_run_case(... expected_message=...)` calls at **lines 204 and 213**).

**Decision: KEEP both expected_message values.** The test's core value is the short-circuit call-count contract (lines 109-116: build_algo==1, build_freeze==1, downtime/pool/extend/optimize/persist/allocate all ==0). The two messages differ ONLY by `排产` vs `模拟排产` — that *is* the behavioral distinction being verified (simulate flag routes to the right wording). Both are passed as the `expected_message` parameter and consumed by `assert expected_message in message` (line 107), which proves the *correct* ValidationError fired. Removing them would make `_run_case` accept any ValidationError. No separate ErrorCode anchor. KEEP.

Risk: low. est removed: 0.

---

## 10. tests/regression_schedule_service_empty_reschedulable_rejected.py — 180 lines — KEEP WHOLE (no trim)

Single test + helpers. Reason flags line:163-185 exact Chinese `expected_message`.

**Decision: KEEP.** Same rationale as #9: the three `_run_case` calls (lines 153, 163, 173) pass `expected_message` strings that differ by `排产`/`模拟排产` and are the only proof the right ValidationError fired before the short-circuit (build/optimize/persist/allocate all asserted ==0). They also encode the empty-vs-terminal-only cases. KEEP all.

Risk: low. est removed: 0.

---

## 11. tests/regression_schedule_service_reject_no_actionable_schedule_rows.py — 150 lines — KEEP WHOLE (no trim)

Single test (uses `monkeypatch`). Reason flags line:135 exact Chinese `user_message`.

**Decision: KEEP.** The structured-detail contract is the value: `reason=="no_actionable_schedule_rows"`, `missing_internal_resource_count==1`, `missing_ops[0].batch_id/seq/op_type_name/missing_fields==["设备","人员"]`, and zero DB writes (schedule/history/version_seq==0, statuses stay pending). The `user_message` substring `"B_NOACT / 工序10 / 工序A 缺设备、人员"` (line 137) interpolates the *computed* missing-resource detail — it is a data-correctness assertion, not static copy. The `"本次排产没有生成可保存的结果" in message` / `"有效可落库排程行" not in message` pair (lines 126-127) is a positive+negative behavior check. All KEEP.

Risk: low. est removed: 0.

---

## 12. tests/regression_schedule_summary_algo_warnings_union.py — 135 lines — TRIM 2 lines

2 tests. Reason flags line:103,105,133 exact Chinese `degradation_reason`. Remapping to current content: the degradation-reason equality asserts are at **lines 105, 107, 135**.

Real (KEEP): the aggregation contract — `freeze_window.get("degraded")` (104), `resource_pool.get("degraded")` (106), `"pool boom" not in str(...)` (108, internal-error redaction), `warning_pipeline.summary_merge_failed/error/algo_warning_count` (109-111), `degraded_success` (112), `degraded_causes` membership (114-117), `degradation_counters` (119-121). Also KEEP the warning-content check at line 97 (`"自动分配设备人员所需资料不完整" in item` — proves freeze_meta wins over legacy, the test's headline).

**BRITTLE (trim) — two full-string Chinese degradation_reason snapshots whose `degraded` boolean sibling already proves the branch:**
- Anchor A (delete), in `test_schedule_summary_prefers_freeze_meta_as_primary_fact_source` (current **line 105**):
  ```
      assert freeze_window.get("degradation_reason") == "冻结窗口资料不完整，本次排产未使用冻结窗口。"
  ```
  Keep context: line 104 `assert bool(freeze_window.get("degraded")), freeze_window` stays.
- Anchor B (delete), same function (current **line 107**):
  ```
      assert resource_pool.get("degradation_reason") == "自动分配设备人员所需资料不完整，本次排产先不自动补设备和人员。"
  ```
  Keep context: line 106 `assert bool(resource_pool.get("degraded")), resource_pool` stays.
- Why brittle: these are exact full-string copy equality on user-friendly text. The `degraded==True` flags plus the `degraded_causes`/`degradation_counters` membership asserts already prove the degradation was detected and classified. The exact normalized sentence is cosmetic.
- **KEEP** the identical-looking assert in `test_schedule_summary_keeps_narrow_freeze_warning_compat_when_meta_missing` (current **line 135**): in that function the `degradation_reason` equality is one of only TWO asserts (134 `degraded` + 135 reason). Trimming line 135 would leave the meta-missing-compat path proven only by a generic `degraded` bool, losing the "narrow freeze fallback still produces the friendly reason" coverage. To avoid a near-empty function and preserve the fallback-path differential, KEEP line 135. (Net trim = 2, not 3.)

Risk: low. est removed: 2.

---

## 13. tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py — 100 lines — KEEP WHOLE (no trim)

Single test. Reason flags line:108-109 Chinese warning substrings (now **lines 97-98**).

**Decision: KEEP.** The two warning asserts are `any("交期写法不对" in w ...)` (97) and `any("未形成完工结果" in w ...)` (98) — substring fragments, not full snapshots, and each is the *only* anchor proving the respective warning was appended for the invalid-due vs unscheduled cases. They pair with the count contract (invalid_due_count==1, unscheduled_batch_count==2, sample membership, counts/algo.metrics mirror) which is all real. The fragments distinguish the two warning kinds; dropping them removes coverage that the right warning text was emitted for the right cause. KEEP.

Risk: low. est removed: 0.

---

## 14. tests/regression_schedule_summary_overdue_warning_append_fallback.py — 45 lines — KEEP WHOLE (no trim)

Single test. Reason flags line:52 Chinese warning substring (now **line 41**).

**Decision: KEEP.** `any("交期写法不对" in str(item) ...)` is the only assert proving the invalid-due warning was *appended* (the headline behavior). It pairs with the meta contract (invalid_due_count==1, sample lists, `warnings` normalized to list, existing `"已有告警"` preserved). It is a short fragment, the sole anchor for "warning written back", and has no code. KEEP.

Risk: low. est removed: 0.

---

## 15. tests/regression_scheduler_analysis_diagnostic_contract.py — 432 lines (433 incl. trailing) — TRIM 2 lines

8 test functions + 3 SHARED helpers (`_full_graph_summary` 94-174, `_summary_with_graph` 177-195, `_iter_text` 198-207 — **DO NOT DELETE, imported by file #16**). Reason flags exact Chinese business-text at line:253-254,304-310,430.

Real (KEEP): all field-set invariants (`set(section)=={...}` 46-57, `set(item)`/`set(link)` 58-59), status-translation (status==warning/error/unknown/empty/unavailable), the security leak-prevention loop (264-275 `forbidden not in text_blob` incl. `priority_key`,`raw`,`不要展示`), bad-shape tolerance (315-352), parametrized health-status scenarios (395-432), `networkx not in health_text` (310, security). The `==` full-string snapshots are the only trim targets, and only where a structural sibling already proves the contract.

**BRITTLE (trim) — two full-string `== "中文整句"` snapshots backed by a sibling structural assert:**
- Anchor A (delete), in `test_diagnostic_sections_translate_statuses_to_business_levels` (current **line 256**):
  ```
      assert "以下只展示本次诊断采样，不是完整清单。" == by_key["impact_explanation"]["summary"]
  ```
  Keep context: the four `by_key[...]["status"] == "warning"` asserts above (lines 251-254) stay and prove the status-translation contract; the `impact_explanation` block is still exercised by them.
- Anchor B (delete), in `test_overall_health_unknown_graph_status_is_visible_and_not_ok` (current **line 432**):
  ```
      assert graph_status_item["value"] == "状态未知"
  ```
  Keep context: lines 429-431 (`health["key"]=="schedule_health"`, `health["status"]=="unknown"`, `graph_status_item["level"]=="unknown"`) stay — they fully encode "unknown status is visible and not ok". The `value=="状态未知"` is the display-copy half already implied by `level=="unknown"`.

**KEEP (do NOT trim) the other reason-cited Chinese asserts:**
- Line 255 `"第一批可排工序里有 1 道" in ... ["summary"]` — fragment that encodes the *computed* unmatched count (1). Keep (count interpolation is a rule).
- Lines 90-91 (`"本版本没有生成排产诊断数据"`, `"刷新页面"`), 264 (`"这轮还没排上的工序样本：3、4、5、6、7"`) — the sample one encodes the 5-of-8 **truncation rule** (computed); the empty-state ones are the only proof of the visible-empty-state contract for `diagnostic_unavailable`. Keep.
- Lines 306/309/312 (`"没有生成设备安排诊断"`, `"图分析组件暂不可用"`, `"本次未生成完整影响范围指标"`) — each is the sole text anchor for the unavailable/basic-report empty-state of its section, paired with a status assert but the status alone (`empty`/`unavailable`) does not prove the *user-facing* fallback rendered without leaking `networkx`. Keep (BIAS=KEEP).
- Lines 350-351 (`"设备安排诊断数据格式异常"` present / `"没有生成设备安排诊断"` absent) — a positive+negative pair distinguishing error-shape from empty-shape; behavioral. Keep.

Risk: low (helpers untouched; only 2 redundant full-string snapshots removed). est removed: 2.

---

## 16. tests/regression_scheduler_analysis_diagnostic_error_contract.py — 202 lines — KEEP WHOLE (no trim)

5 tests (mostly parametrized). Imports shared helpers from #15. Reason flags line:113-147 exact Chinese summary parametrization (the `expected_summary` column of `test_resource_bottleneck_section_status_scenarios`).

**Decision: KEEP all `== expected_summary` rows.** Each row's summary string interpolates a *computed* count (`有 1 道`, `有 162 道`) and selects among genuinely different business messages per `resource_matching` state (ok/warning-some/warning-capacity/empty/skipped/error). The assert pairs `status == expected_status` (structural) with `summary == expected_summary` (the text), but here the summary text encodes which branch + which count — trimming it would collapse 6 distinct message-selection rules into a bare status check and lose the count-interpolation coverage. The numeric-safety tests (safe_int/float/format_hours reject non-finite, `"无法安全展示"`, `"0 毫秒"/"0 分钟"/"0 小时" not in`, exceptions-not-swallowed via monkeypatched `boom`) are all hard behavioral contracts. KEEP whole.

Risk: low. est removed: 0.

---

## 17. tests/regression_scheduler_analysis_diagnostic_graph_score_contract.py — 60 lines — KEEP WHOLE (no trim)

Single test `test_graph_score_sample_does_not_expose_internal_operation_id`. Reason (mid) flags line:55 exact Chinese phrase (now **line 57**).

**Decision: KEEP.** The function has exactly 4 asserts (lines 57-60): one positive `"重点影响样本（影响 3 个后续，后续关键时长 180 分钟，排法参考值 530）" in text_blob` and three security negatives (`"工序 1" not in`, `"op_id" not in`, `"priority_key" not in`). The positive assert encodes **computed values** (impact_count 3, downstream_critical_minutes 180, bonus 530 from the input) — it is a data-rendering correctness check, not static copy. Trimming it would leave only the leak-negatives and lose proof that the human summary actually renders the right derived numbers. KEEP all 4 (deleting the positive would also leave a function that only proves absence, weakening the "shows human summary BUT not internals" dual contract).

Risk: low (mid per reason → keep). est removed: 0.

---

## 18. tests/regression_scheduler_analysis_observability.py — 385 lines — TRIM ~14 lines

Single huge test `test_scheduler_analysis_observability` (245-386) + data builders/helpers (11-242, all KEEP). Reason flags ~70 exact rendered-HTML Chinese UI-copy asserts (line:284-409). This is the file with the most trim.

**Keep classes (load-bearing, NOT brittle):**
1. All `build_analysis_context` **data-payload** asserts (lines 253-257, 282-309, 345-354): attempts extraction, `dispatch_mode/rule` passthrough/empty, `extra_cards` presence/absence, `freeze_display` state/state_label/counts/`sample_batches`(5)/`sample_more_count`(2), card `value`/`delta` (-3, -5, None) — these encode computed values and rules.
2. All **security/leak-prevention negatives** on HTML (KEEP every one): `"comparison_metric" not in`/`"best_score_schema" not in`/`"schema 字段" not in`/`"start:priority_first|batch_order:slack" not in`/`"start:priority_first|sgs:cr" not in`/`data-col-key="score" not in`/`"<td>[0, 1]</td>" not in`/`"sqlite" not in`/`"【冻结窗口】跳过批次 B001" not in`/`"-/-" not in`/`"裁剪后摘要" not in`/`"停机避让约束已降级" not in`/`"冻结窗口约束已降级" not in`/`"开始时间已规范化…" not in`/the four private-warning `not in` asserts (380-385), and the `stat-card-label not in`/`in` card-presence asserts.
3. Positive HTML asserts that encode a **rule or computed value** (KEEP): `"方案 1" in old_html` (anonymization rule, line 272), `"提醒：4 条"` / `"另有 1 条提醒…"` (warning_total/hidden_count counts, 314/318), `"对比上一版：-3"` / `"-5"` (delta values reach page, 326-327), `"600000" in new_html` (size value, 313), `"维护诊断：1 条" in` (379, internal-vs-business routing rule), `"提醒：1 条" not in`(378), `"方案来源未知" not in`(340), `"多起点方案" in`(339, safe source-label rendered).

**BRITTLE (trim) — positive exact-Chinese-COPY snapshots that only assert decorative rendered text and are NOT a computed value, where a data-payload sibling already covers the underlying behavior.** Delete these exact lines (each is a unique anchor):
- `    assert "排产优化分析" in old_html, "旧 summary 页面未成功渲染"` (line 260) — page-title-rendered smoke; the response/context build already proves render success.
- `    assert "这个历史版本缺少新的分析字段，页面只展示能确认的内容。" in old_html, "旧 summary 应展示中文兼容提示"` (line 265) — full-sentence copy snapshot; the compat behavior is covered by the `comparison_metric/best_score_schema not in` negatives + the `优化对比指标`/`系统比较顺序` field-name asserts.
- `    assert "本次结果数据量较大" in new_html, "未展示 summary_truncated 提示"` (line 312) — copy snapshot; `summary_truncated` already asserted in the payload (286) and the `"600000"` size value (313) is kept.
- `    assert "冻结窗口存在跳批风险" in new_html, "未展示 warnings_preview"` (line 315) — echoes an input warning string verbatim; warning *count* (`提醒：4 条`) and ordering rule are kept.
- `    assert "停机区间加载失败，本次先按常规能力继续" in new_html, "未展示第二条 warnings_preview"` (line 316) — same, second echoed input warning.
- `    assert "存在 1 个批次未命中首选技能" in new_html, "未展示第三条 warnings_preview"` (line 317) — same, third echoed input warning.
- `    assert "停机时间资料不完整" in new_html, "未展示停机提示"` (line 320) — degradation copy; `downtime_avoid.degraded` payload (288) + `summary_degradation_messages` code asserts (308) cover it.
- `    assert "冻结窗口资料不完整" in new_html, "未展示冻结窗口提示"` (line 322) — degradation copy; `freeze_window.degraded` payload (289) + freeze_display covers it.
- `    assert "示例批次：B001、B002、B003、B004、B005" in new_html, "未展示冻结示例批次"` (line 331) — rendered echo of `sample_batches`, already asserted in payload (305).
- `    assert "及其他 2 个…" in new_html, "未展示冻结示例批次剩余数量"` (line 332) — rendered echo of `sample_more_count`, already asserted (306).
- `    assert "排序策略" in new_html, "attempts 表头未更正为排序策略"` (line 333) — static table-header copy.
- `    assert "派工" in new_html, "attempts 表头未新增派工列"` (line 334) — static table-header copy.
- `    assert "智能派工 / 交期更紧的先做" in new_html, "attempts 派工列未闭环展示派工方式/智能派工策略"` (line 335) — long dispatch-label copy; the `dispatch_mode=="sgs"/rule=="cr"` payload asserts (283-284) cover the underlying mapping.

Keep-context note: every deleted line sits in a flat assert sequence inside the single test; deleting them does not break flow, and the function retains 40+ meaningful asserts (all data-payload + all security negatives + all count/delta/rule positives). Do NOT touch any `assert ... not in ...html` line and do NOT touch the data-builder functions (make_*_summary, build_case_inputs, render_analysis_html, card_by_key).

Borderline KEEP (intentionally NOT trimmed, to stay conservative): `"对比上一版：-3"/"-5"` (delta values), `"当前状态"/"部分未生效"` (freeze state_label, computed), `'<div class="aps-summary-value">4/7</div>'` (frozen counts, computed), `"暂无…"` n/a here. These echo computed values, so they guard real bugs.

Risk: low (only decorative copy removed; all leak-prevention and computed-value asserts retained). est removed: 13.

---

## 19. tests/regression_scheduler_analysis_read_context.py — 250 lines (251 incl. trailing) — TRIM 1 line

7 tests + helper `_assert_selected_version`. Reason flags Chinese HTML substring asserts. Most HTML substrings here are NOT decorative — they encode version-resolution rules.

Real (KEEP): `_assert_selected_version` (138-141: `"版本概览" in`, `aps-summary-label">版本`, `aps-summary-value">vN`) — selected-version routing; `"暂无排产历史" in`(162, no_history visible state); `'value="7"' in`(197, other-version-in-picker rule); `"v999 无对应排产历史" in`(208) + `'aps-summary-value">v999' not in`(210, missing-version handling — computed/negative); the parse-failure warning-log asserts (223-224, the headline of the invalid-summary test); status_code==200 everywhere; the plan-role-not-queried contract (248-250 + `_PlanRoleServiceMustNotBeCalled` raising).

**BRITTLE (trim) — one full-sentence copy snapshot whose rule is covered by a structural sibling:**
- Anchor (delete), in `test_analysis_read_context_missing_explicit_version_keeps_trends_visible` (current **line 209**):
  ```
      assert "版本趋势（最近 1 个有指标的版本）" in html
  ```
  Keep context: line 208 `assert "v999 无对应排产历史" in html` (missing-version notice) and line 210 `assert 'aps-summary-value">v999' not in html` (not selected) stay — together they prove "missing explicit version keeps trends visible but does not select v999". The exact trend-panel heading copy (with its parenthetical count phrasing) is decorative; the function keeps 3 meaningful asserts (200, notice, negative).
- Why brittle: the heading wording `版本趋势（最近 1 个有指标的版本）` is presentation copy; the behavioral guarantee (trends still rendered, v999 not selected) is held by the surrounding asserts.

KEEP (do NOT trim) `"排产优化分析" in html`(222) and the rest — in the invalid-summary test it is the only proof the page rendered (didn't crash) and pairs with the warning-log asserts.

Risk: low. est removed: 1.

---

## 20. tests/regression_scheduler_analysis_vm_legacy_summary_bridge.py — 107 lines — KEEP WHOLE (no trim)

5 tests. Reason flags line:47-49 Chinese objective-label asserts (now **lines 49-51**).

**Decision: KEEP.** Those asserts (`ctx["algo_objective_label"]=="最少换型次数"`, `best_score_schema_display[1]["display_label"]=="换型次数"`, `algo_config_snapshot_objective_label=="最少换型次数"`) are the **objective→label mapping contract** — the whole point of `build_analysis_context`'s label bridge. They are computed translations of `objective="min_changeover"`, not static page copy, and `test_build_analysis_context_returns_pure_data_payload` exists specifically to verify the label derivation + JSON-serializability. The other tests (comparison_metric inference, compat_fallback.missing_fields, degraded_causes→details bridging, events-preferred-over-causes) are all behavioral. The `"资源池资料不完整"`/`"组合并资料不完整"` fragments (87-88) are the only anchors proving the legacy-cause→detail bridge produced the right message. KEEP whole.

Risk: low. est removed: 0.

---

## Batch summary

| # | file | trim_type | est_removed | whole-func del | b4 | risk |
|---|------|-----------|-------------|----------------|----|----|
| 1 | auto_assign_empty_resource_pool | none | 0 | — | n | low |
| 2 | optimizer_ortools_logging_exc_info_safe | exact_chinese_snapshot | 1 | — | n | low |
| 3 | optimizer_public_summary_projection_contract | none | 0 | — | n | low |
| 4 | resource_reference_guard_schedule | exact_chinese_snapshot | 3 | — | n | low |
| 5 | schedule_history_not_created_for_empty_schedule | none | 0 | — | n | low |
| 6 | schedule_params_read_failure_visible | none | 0 | — | n | low |
| 7 | schedule_persistence_reject_empty_actionable_schedule | none | 0 | — | n | low |
| 8 | schedule_result_view_context | exact_chinese_snapshot | 3 | — | **y** | mid |
| 9 | schedule_service_all_frozen_short_circuit | none | 0 | — | n | low |
| 10 | schedule_service_empty_reschedulable_rejected | none | 0 | — | n | low |
| 11 | schedule_service_reject_no_actionable_schedule_rows | none | 0 | — | n | low |
| 12 | schedule_summary_algo_warnings_union | exact_chinese_snapshot | 2 | — | n | low |
| 13 | schedule_summary_invalid_due_and_unscheduled_counts | none | 0 | — | n | low |
| 14 | schedule_summary_overdue_warning_append_fallback | none | 0 | — | n | low |
| 15 | scheduler_analysis_diagnostic_contract | exact_chinese_snapshot | 2 | — | n | low |
| 16 | scheduler_analysis_diagnostic_error_contract | none | 0 | — | n | low |
| 17 | scheduler_analysis_diagnostic_graph_score_contract | none | 0 | — | n | low |
| 18 | scheduler_analysis_observability | full_page_text | 13 | — | n | low |
| 19 | scheduler_analysis_read_context | full_page_text | 1 | — | n | low |
| 20 | scheduler_analysis_vm_legacy_summary_bridge | none | 0 | — | n | low |

Total est net lines removed: ~29. No whole-function deletions. No registry/contract function-name coupling. Shared helpers in #15 preserved (imported by #16). B-4 oracle in #8 (lines 296-304) protected.
