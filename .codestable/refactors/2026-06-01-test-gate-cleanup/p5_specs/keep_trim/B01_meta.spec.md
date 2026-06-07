# P5.2 KEEP_TRIM Spec — Batch B01_meta

Branch: `cleanup/p3-main-style-to-pytest`
Author: recon analyst (P5.2)
Scope: 18 META / gate / contract test files. This batch is special: many files ARE
enforcement gates (doc-consistency, debt ratchet, blocked-artifact guard, required-suite
coverage, cache-invalidation contracts). Per META-GATE CAUTION the default is **KEEP**;
trims are surgical and only target assertions whose sole failure mode is cosmetic drift.

## Cross-cutting findings (read first)

1. **Stale TSV anchors.** Several TSV `reason` line numbers and even function NAMES no
   longer exist (`test_manifest_tracks_required_scopes`, `test_collect_full_test_debt_static_gate`,
   `test_startup_scope_tracks`, `test_required_scope_tracks`). Those "giant scope-list
   snapshot" targets the TSV wanted trimmed have ALREADY been refactored away. Do NOT invent
   trims to match the stale names. Re-mapped every cited anchor to current content below.

2. **Registry coupling.** `tests/regression_quality_gate_scan_contract.py` and
   `tests/test_codestable_tools_contract.py` are FILE-registered in
   `tools/test_registry_data.py` (lines 126, 129) and `tools/test_registry_groups_scheduler.py`.
   The FILES must keep existing and stay collectable (>=1 test). All trims below delete
   only SOME functions per file — never the whole file, never to zero tests. No function
   nodeid I propose to delete is referenced by any registry/contract/debt machinery
   (grep verified, see registry_refs_found in summary = empty for all).

3. **Many "可瘦身 / 并簇" TSV reasons are MERGE suggestions, not brittle-trim flags.** The
   long_gate cache-invalidation parametrize lists encode the load-bearing safety property
   "changing tracked input X invalidates the cache" — silently dropping rows reduces
   invalidation coverage (a real-bug class). These are KEPT, not trimmed.

---

## File-by-file

### 1. tests/regression_aps_three_gap_docs_quality_gate.py  (222 lines) — META-GATE, risk=mid
TSV(low): brittle doc-snapshots; only `test_quality_gate_plan_runs` has real value.

This file IS the doc⊆md consistency gate. Trimming it REDUCES enforcement that the
user-guide stays free of internal terms and the dev-guide lists every roadmap feature /
regression test / key .py file / Win7 manual. Enforcement that would be LOST if trimmed:
detection of internal-jargon leaking into the user guide, and dev-guide coverage drift.

Decision: **KEEP ALL.** The "brittle" doc-snapshot lists (`USER_REQUIRED_PHRASES`,
`USER_FORBIDDEN_TERMS`, `DEV_REQUIRED_TERMS`, `ROADMAP_FEATURES`, `REGRESSION_TESTS`,
`KEY_PYTHON_FILES`) are the gate's entire purpose; they are consistency invariants, not
cosmetic. `test_quality_gate_plan_runs_codestable_yaml_and_py38_scan` (the TSV-blessed real
contract) is also kept. No trim. (If a future pass insists, the only defensible trim is the
`USER_FORBIDDEN_TERMS` negative list — but it is the security-relevant half, so KEEP.)

est_lines_removed: 0

---

### 2. tests/regression_quality_gate_scan_contract.py  (745 lines) — risk=mid
TSV(mid): "夹杂 REQUEST_SERVICE_TARGET_FILES 成员清单快照:417/434/599 脆,删快照保算法".

Re-mapped current anchors:
- `test_request_service_target_files_cover_history_and_system_routes` (current ~L419):
  `expected_targets.issubset(REQUEST_SERVICE_TARGET_FILES)` — system + history routes.
- `test_request_service_target_files_cover_scheduler_calendar_and_resource_residuals` (~L436):
  subset snapshot PLUS unique behavioral asserts `architecture_request_service_direct_assembly_entries() == []`
  and `REQUEST_SERVICE_TARGET_ALLOWED_HELPERS == []`.
- `test_request_service_target_files_keep_system_route_gate_coverage` (~L601):
  system-route subset snapshot — **fully subsumed** by the system-route half of the L419 test.

These membership snapshots are coverage contracts (security-relevant route files MUST be
scanned). The whole-algorithm body (ScanContext single-read, g.db/conn/alias detection,
repository-bundle drift, ui_mode scope_tag, strict CLI exit codes) is REAL and KEPT.

**TRIM (1 whole function):** delete `test_request_service_target_files_keep_system_route_gate_coverage`.
- Unique anchor (delete the whole def, blank line before/after):
  ```
  def test_request_service_target_files_keep_system_route_gate_coverage() -> None:
      system_targets = {
          "web/routes/system_backup.py",
          ...
      }

      assert set(shared_mod.REQUEST_SERVICE_TARGET_FILES) & system_targets == system_targets
  ```
- Keep-context: KEEP `test_request_service_target_files_cover_history_and_system_routes`
  (asserts the SAME 5 system routes + history + error routes — superset) and KEEP
  `test_request_service_target_files_cover_scheduler_calendar_and_resource_residuals`
  (its `== []` / helpers-empty asserts are unique behavioral contracts).
- grep result: no external refs (verified). registry_refs_found: empty.
- Why safe: pure redundant subset snapshot; system-route coverage still asserted by L419.

Do NOT trim L419 or L436 — L419 is the broader coverage anchor, L436 carries unique behavior.

est_lines_removed: ~10

---

### 3. tests/test_architecture_scan_cache.py  (312 lines) — risk=mid (gate-adjacent)
TSV(mid): "末 test_architecture_fitness_stays_planned:389 是 manifest enabled 清单逐条快照脆,删该条".

Re-mapped: `test_architecture_fitness_stays_planned_and_artifact_is_blocked` (current L280).
Three parts:
- L287-288: `architecture_fitness cache_status=="planned"` + `reuse_allowed is False` — the
  REAL reason this test exists (architecture_fitness must stay planned/non-reusable). KEEP.
- L289-300: `enabled == [9-item ordered list]` — structural invariant; appears in 3 sibling
  files too. Mildly redundant but encodes the enabled-entry ordering contract.
- L301-312: `_blocked_paths(...) == [(path, "长耗时门禁缓存是本地运行产物…")]` and
  `_blocked_paths([ARCHITECTURE_SCAN_CACHE_REL]) == [(rel, "architecture scan 文件级缓存…")]`
  — these assert the blocked-artifact gate (the named contract "artifact_is_blocked").

Decision: **KEEP ALL (no trim).** The TSV calls the enabled-list a snapshot, but this test's
load-bearing assertions are the planned/non-reusable status and the artifact-block decision
(the gate). The Chinese block-reason strings are the gate's source-of-truth output (also
mirrored in `tools/git_hook_blocked_paths.py` and `test_git_hook_checks.py`). Trimming the
enabled-list alone is not worth a structural rewrite; the function's real contract is intact.
Risk of over-trim (deleting block-gate coverage) outweighs the cosmetic benefit. The other 6
functions are pure scan-algorithm logic (single-read, rescan-each-path, id-assignment,
metadata fingerprint fields) — KEEP.

est_lines_removed: 0

---

### 4. tests/test_benchmark_full_test_debt_shards.py  (82 lines) — risk=low
TSV(mid): "argv 解析:46 价值低,核心保留".

All 3 functions are real behavioral logic: `build_distribution` serial/parallel counts +
imbalance; `_parse_counts` dedupe + empty-reject; `test_main` argv→run_shard_count dispatch
with allow-dirty passthrough (`calls == [(2, True), (5, True)]`). The "argv parsing low value"
note is wrong — argv dispatch + passthrough is a real contract.

Decision: **KEEP ALL.** No brittle content.

est_lines_removed: 0

---

### 5. tests/test_check_quickref_vs_routes.py  (100 lines) — risk=low
TSV(mid): "_render_report 断言 '稳定快照' in 报告:46 是文案快照,删该尾".

`test_render_report_uses_repo_relative_path_and_stable_metadata` (L33):
- KEEP `assert "开发文档/系统速查表.md" in report` (repo-relative path contract)
- KEEP `assert "D:\\" not in report`, `"C:\\" not in report`, `"生成时间" not in report`
  (no-drive-letter / no-timestamp stability invariants — the real reproducibility contract)
- **TRIM (1 assert line):** `assert "稳定快照" in report`

**TRIM anchor (single line, in-function):**
```
    assert "稳定快照" in report
```
Keep-context: it is the last assert in the function; remove just that line. The function
still has 4 meaningful asserts (path present + 3 stability negatives). `"稳定快照"` is a
doc-copy marker; the no-timestamp guarantee is already covered by `"生成时间" not in report`.
The other two functions (`_diff_endpoints` missing/extra/method-mismatch, `main` repo-relative
stdout `== ["evidence/QualityGate/quickref_vs_routes.md", "OK"]`) are real behavior — KEEP.

est_lines_removed: 1

---

### 6. tests/test_codestable_tools_contract.py  (656 lines) — risk=mid (self-ref / CodeStable infra)
TSV(self-ref): "夹真实 .codestable doc 成员快照:234/273 脆,且属 CodeStable 基建非 APS".

The pure search/validate TOOL contract is exhaustively covered by ~18 synthetic tmp_path
tests (exclude-dir, exit-2-on-empty, PyYAML fallback, bad/unclosed/non-line frontmatter,
unterminated quote, md/yaml required-field split). Three functions instead snapshot LIVE
`.codestable` docs (CodeStable infra that drifts independently of APS code):

- **TRIM (whole function):** `test_review_fix_notes_use_searchable_issue_fix_frontmatter`
  (L236) — iterates 3 hardcoded real issue dirs (`2026-05-25-*`) and validates frontmatter.
  Pure live-doc snapshot; tool behavior fully covered synthetically.
  Anchor (delete whole def):
  ```
  def test_review_fix_notes_use_searchable_issue_fix_frontmatter() -> None:
      issues = [
          "2026-05-25-quality-gate-timeout",
          ...
          assert str(note.relative_to(REPO_ROOT / ".codestable" / "issues")) in search.stdout
  ```
- **TRIM (whole function):** `test_aps_three_gap_roadmap_related_fields_are_slug_searchable`
  (L275) — asserts the live roadmap doc carries specific related-* slugs. Pure doc snapshot.
  Anchor (delete whole def):
  ```
  def test_aps_three_gap_roadmap_related_fields_are_slug_searchable() -> None:
      filters = [
          "related_requirements~=schedule-delay-diagnosis",
          ...
          assert "aps-three-gap-directions-roadmap.md" in proc.stdout
  ```
- **TRIM (assert-block within KEPT function):** in
  `test_compound_superseded_documents_use_hyphenated_field` (L179) delete ONLY the live-doc
  scan first half (L180-193) and KEEP the synthetic tmp_path tool-behavior half (L195-233).
  Delete anchor:
  ```
      compound_dir = REPO_ROOT / ".codestable" / "compound"
      docs = list(compound_dir.glob("*.md"))
      offenders = []
      missing = []
      for doc in docs:
          text = doc.read_text(encoding="utf-8")
          frontmatter = text.split("---", 2)[1] if text.startswith("---") and text.count("---") >= 2 else text
          if "superseded_by:" in frontmatter:
              offenders.append(doc.name)
          if "\nstatus: superseded\n" in frontmatter and "superseded-by:" not in frontmatter:
              missing.append(doc.name)

      assert offenders == []
      assert missing == []

  ```
  Keep-context: after deletion the function body starts at `docs_dir = tmp_path / "compound"`
  and keeps the synthetic search-tool `superseded-by~=roadmap-target` filter assertions — a
  real tool-behavior contract with non-zero meaningful asserts.

grep results: all 3 names have no external refs (verified). registry_refs_found: empty.
The FILE stays registered (test_registry_data:129) and keeps ~16 tests — registration safe.

est_lines_removed: ~55

---

### 7. tests/test_full_test_debt_registry_contract.py  (1450 lines) — risk=high (DEBT RATCHET)
TSV(high): "首 test_allowed_active_xfail_nodeids:23 是硬编码 nodeid 清单快照 + save 文案
'测试债务历史登记' 断言:1399 脆,删此两尾".

**DO NOT trim `test_allowed_active_xfail_nodeids_are_locked_to_historical_baseline` (L25).**
The TSV mislabels it. This is the **debt-ratchet baseline lock**: the 5-nodeid list is
deliberately pinned so that ANY new active-xfail addition breaks the test and forces review.
The constant `FULL_TEST_DEBT_ALLOWED_ACTIVE_XFAIL_NODEIDS` is consumed by
`tools/quality_gate_shared.py`, `tools/quality_gate_ledger.py`, `tools/check_full_test_debt.py`,
`tests/test_check_full_test_debt.py`. Deleting this lock removes the ratchet anchor.
**KEEP — risk=high if touched.** registry_refs_found (the constant): 4 tools/test files.

**TRIM (1 assert line, in KEPT function):** in
`test_save_ledger_writes_test_debt_snapshot_and_machine_block` (L1389) delete ONLY L1401:
```
    assert "测试债务历史登记：1，当前 active xfail：1" in writes["text"]
```
Keep-context: KEEP L1400 (`writes["path"] == "开发文档/技术债务治理台账.md"`),
L1402 (`'"test_debt": {' in writes["text"]` — machine block present), L1403
(`entry["nodeid"] in writes["text"]`). The exact Chinese count-phrase is a rendered-text
snapshot; the structural machine-block + nodeid assertions already prove the snapshot was
written. Function retains 3 meaningful asserts.

Everything else (subprocess-real xfail/xpass/skip classification, baseline fail-closed rules,
nodeid/owner/root/exit_condition validation, duplicate/negative-ratchet rejection, conftest
exact-nodeid xfail marking, strict-xpass error) is the high-value behavioral core — KEEP.

est_lines_removed: 1

---

### 8. tests/test_git_hook_checks.py  (971 lines) — risk=high (BLOCKED-ARTIFACT GATE)
TSV(high): "_blocked_paths 的 reason 逐字快照:316/324/387 与 .pre-commit-config 断言:948 脆,删这些尾".

Re-mapped:
- `test_blocked_paths_include_launcher_log` (L318), `test_blocked_paths_include_long_gate_runtime_artifacts`
  (L326, the big 11-path tuple), `test_blocked_paths_normalize_windows_separators` (L389):
  each asserts `_blocked_paths(...) == [(path, "<exact Chinese reason>")]`.
- `test_pre_commit_config_wires_quality_gate_and_ruff_hooks` (L950).

The Chinese block-reasons are the GATE's user-facing output and the source of truth lives in
`tools/git_hook_blocked_paths.py` (also mirrored by `test_architecture_scan_cache.py`). The
path→block DECISION is the contract these tests exist for; trimming the reason text would
require rewriting `== [(path, reason)]` into paths-only — a structural rewrite that risks
weakening the block-reason contract. **KEEP the `_blocked_paths` functions** (Windows-normalize
test included — `\`→`/` is real behavior).

**TRIM (1 assert line, in KEPT function):** in
`test_pre_commit_config_wires_quality_gate_and_ruff_hooks` (L950) delete ONLY L966:
```
    assert hooks["aps-quality-gate"]["name"] == "APS daily fast gate before push"
```
Keep-context: KEEP every other assert — `default_install_hook_types`, every `entry` /
`stages` / `pass_filenames` / `always_run` wiring assert (L958-971 minus L966). The hook
`name` human-readable label has zero behavioral weight; the `entry`/`stages` asserts on the
same hook (L967-971) fully cover wiring. Function keeps ~13 meaningful asserts.

Enforcement lost if you over-trim here: the blocked-artifact pre-commit gate (prevents
committing local QualityGate run-products / launcher logs) and the hook-wiring contract.
So trim is limited to the one cosmetic label.

est_lines_removed: 1

---

### 9. tests/test_long_gate_collect_cache.py  (210 lines) — risk=low
TSV(mid): "失效用例与 file17 指纹引擎同契约,可并簇" (MERGE suggestion, not brittle).

All functions are real cache-invalidation algorithm. The `invalidated_by` reason strings
("added input file: …", "modified input file: …", "removed input file: …") are branch
oracles (which invalidation rule fired), NOT brittle copy. The `nodeids_by_file` grouping and
parameterized-name-with-spaces preservation are real parsing contracts.

Decision: **KEEP ALL.** "并簇" is a merge concern for P5.1, out of scope for KEEP_TRIM.

est_lines_removed: 0

---

### 10. tests/test_long_gate_debt_ledger_cache.py  (436 lines) — risk=low
TSV(mid): "test_manifest_tracks_required_scopes:53 是 scope 清单逐条快照脆,删该条".

**Stale anchor — that function does NOT exist in this file (or anywhere).** Current content
is entirely real proof-write-ordering / tamper-rejection / dirty-vs-planned-vs-explain branch
logic. The only list-ish asserts are `output_result_files == ["…debt_ledger_sync.json"]`,
`display`, `args` — declared-command contracts, not snapshots.

Decision: **KEEP ALL.** No brittle target present.

est_lines_removed: 0

---

### 11. tests/test_long_gate_manifest.py  (474 lines) — risk=low
TSV(mid): "test_collect_full_test_debt_static_gate:228 是巨型 scope 清单逐条快照 + enabled
清单 verbatim:247 脆,删大块快照".

**Stale anchor — `test_collect_full_test_debt_static_gate` does NOT exist here.** The "giant
scope-list snapshot" was already refactored away. Current scope asserts are in
`test_required_parent_scope_includes_group_specific_scope_union` (L181) — targeted membership
+ meaningful NEGATIVE invariants (`chrome_* not in env_keys`), not a verbatim dump. Receipt
format asserts (`0.120s`, `kind=reuse_overhead`) encode the duration_kind computation.

Decision: **KEEP ALL.** No giant-snapshot target present.

est_lines_removed: 0

---

### 12. tests/test_long_gate_quickref_cache.py  (117 lines) — risk=low
TSV(mid): "fingerprint_tracks 清单:47 可瘦身并簇" (MERGE/slim suggestion).

The `@pytest.mark.parametrize changed_path` list (15 paths) is the cache-INVALIDATION
contract: each path, when changed, MUST flip the fingerprint. Dropping rows silently reduces
which inputs invalidate the quickref cache (real-bug class — stale reuse). The
`output_result_files == [...]` is the declared-output contract.

Decision: **KEEP ALL.** "瘦身并簇" is a merge concern, not a brittle-trim.

est_lines_removed: 0

---

### 13. tests/test_long_gate_required_regression_cache.py  (640 lines) — risk=mid
TSV(mid): "test_required_scope_tracks:102 + tracked_scope:366 是巨型 scope 清单快照脆,删大块快照".

Re-mapped:
- `test_required_scope_tracks_real_inputs_without_unrelated_markdown` (L104): ~44-path
  membership list + ~20 env-key list + NEGATIVE exclusions (`audit/**/*.md not in`,
  `开发文档/**/*.md not in`).
- `test_required_tracked_scope_changes_update_fingerprint` (L351): ~64-path parametrize where
  each path MUST flip the fingerprint.

These are the required-regressions cache INVALIDATION + scope-declaration contracts. If a
tracked input stops invalidating the cache, the gate falsely reuses stale required-regression
proofs = a real safety bug. The negative exclusions are deliberate scope boundaries.

Decision: **KEEP ALL (no trim).** This is exactly the over-trim danger META-GATE caution
warns about: deleting these rows silently deletes invalidation coverage. The "删大块快照"
instruction is rejected as unsafe for a cache-correctness contract. Under-trim here is correct.

est_lines_removed: 0

---

### 14. tests/test_long_gate_startup_regression_cache.py  (446 lines) — risk=mid
TSV(mid): "test_startup_scope_tracks:90 + enabled 清单 verbatim:60 脆,删 scope 快照".

**Stale anchor — `test_startup_scope_tracks` does NOT exist.** Current: the 9-item ordered
`enabled == [...]` list (L62) is a structural invariant (which entries are reuse-enabled, in
canonical order) shared across 3 sibling files; the `test_startup_tracked_scope_changes_update_fingerprint`
(L276) parametrize list is the same invalidation contract as the required file.

Decision: **KEEP ALL.** Same reasoning as #13 — invalidation + enabled-order contracts are
load-bearing; the enabled-list is small and structural, not a cosmetic dump.

est_lines_removed: 0

---

### 15. tests/test_long_gate_summary_output.py  (621 lines) — risk=mid
TSV(mid): "markdown 整行断言:650/698 是渲染文案快照,删这些" (line numbers stale; file is 621).

Re-mapped two markdown-snapshot spots:
- `test_successful_run_writes_json_md_counts_and_reasons` (L182): L221-223 assert
  `"## Duration"`, `"## Slow entries"` (cheap structural section markers — KEEP) and L223
  `"For local profiling, run the exact final proof command"` (doc-copy phrase — brittle).
- `test_summary_duration_keeps_counts_and_ranks_slow_entries` (L564): L619-620 section
  headers (KEEP) and L621 the FULL exact-format markdown table row.

**TRIM (assert line) #1:** in `test_successful_run_writes_json_md_counts_and_reasons` delete L223:
```
    assert "For local profiling, run the exact final proof command" in markdown
```
Keep-context: KEEP L221-222 (`## Duration` / `## Slow entries`) and all JSON-structure
asserts (counts dict, duration fields, top_entries[0], entry execution_mode/duration_kind,
output_files path). Brittle copy phrase only.

**TRIM (assert line) #2:** in `test_summary_duration_keeps_counts_and_ranks_slow_entries`
delete L621:
```
    assert "| 2 | required_regressions | reused_success_cache | 0.120 | 98.340 | success cache reusable |" in markdown
```
Keep-context: KEEP L611 (`counts ==`), L612-614 (`total_s/executed_total_s/reuse_overhead_total_s`
via pytest.approx), L615-618 (`top_entries == [full_test_debt, required_regressions]`), L619-620
(section headers). The full pipe-delimited row is an openpyxl-style layout snapshot; every value
in it (0.120, 98.340, reused_success_cache mode, ordering) is already asserted structurally
above. Function retains all behavioral asserts.

Everything else (copyable-failure nodeid extraction + quoting, tail_text, interrupted/partial
flags, dirty-worktree-no-success-cache, summary-write-failure-blocks-cache) is real — KEEP.

est_lines_removed: 2

---

### 16. tests/test_report_full_test_debt_durations.py  (52 lines) — risk=low
TSV(low): "断言为格式化文本子串(9.500s/category 名),夹报告文案快照,保聚合删文案细节".

Single function `test_duration_report_groups_call_file_and_category_totals`. The Top-N
selection logic (call_section in/out membership) and the aggregation values are real. The
exact format strings `"9.500s  tests/…"` / `"9.000s  tests/…"` / `"9.500s  browser"` encode
the two-space-padded float-format LAYOUT (brittle) — but the NUMBERS encode aggregation
correctness (9.5 = 0.5 setup + 9.0 call grouped by file; 9.5 grouped to "browser" category).

Decision: **KEEP ALL (no trim).** This file has only ONE function with ~12 asserts; trimming
the `"9.500s …"` lines would strip the aggregation oracle (no other assert proves the
0.5+9.0→9.5 file-grouping or the category roll-up). Removing them risks leaving the function
without its core aggregation check. The format coupling is mild and the under-trim is safe.
If forced, the only defensible micro-trim is collapsing `"browser" in report` (L50, redundant
with L49 `"9.500s  browser"`), but the saving (1 line) is not worth the churn. KEEP.

est_lines_removed: 0

---

### 17. tests/test_run_quality_gate.py  (2955 lines) — risk=high (CRITICAL STATE MACHINE)
TSV(high): "少量成员快照如 required-suite 覆盖:618 + workflow artifact:778 可瘦身" (soft "可瘦身").

This is the resume / dirty-worktree-fingerprint / manifest-state-machine / evidence-retention
core. The two flagged spots:

(A) `test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions` (L616):
~70 `high_value_path in REQUIRED_TEST_ARGS` membership asserts + a `lower_frequency not in`
exclusion list. **KEEP (no trim).** This is the required-suite COVERAGE contract: a high-risk
regression silently dropping out of the required suite = the gate stops enforcing it (real
regression). The registry-single-source tie (`REQUIRED_TEST_ARGS == iter_required_tests()`,
L624), dedup (L629), and ordering (L718-719) are also kept. META-GATE caution applies; "可瘦身"
is a soft suggestion, and the enforcement value outweighs the cosmetic cost.

(B) `test_quality_workflow_uploads_quality_gate_manifest_artifact` (L764): greps
`.github/workflows/quality.yml`. **TRIM 3 assert lines** (CI-text-grep brittle category —
exact SHA pins drift on every dependabot bump; exact Chrome path is a literal):
- delete L778:
  ```
      assert re.search(r"(?m)^      APS_CHROME_PATH:\s*C:\\Program Files\\Google\\Chrome\\Application\\chrome\.exe\s*$", quality_gate_job.group("body"))
  ```
- delete L785:
  ```
      assert "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4" in quality_gate_job.group("body")
  ```
- delete L787:
  ```
      assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4" in quality_gate_job.group("body")
  ```
Keep-context: KEEP the behavioral asserts — `"actions/upload-artifact" in content` (L768,
unpinned), `"evidence/QualityGate/" in content`, `--require-clean-worktree` / `--long-gate-cache`
flags, the `env:` + PYTHON* env regexes (L774-777), the Chrome-check/version/gate-run ORDERING
(L780-784), and `"node-version: '24'"` (L786). These prove CI uploads evidence and runs the
gate with the right flags/env/order. Only the exact pinned SHAs and the exact Chrome path
literal are removed. Function retains all behavioral asserts.
NOTE: keep `"安装 Node.js 24"` (L779)? It is a Chinese step-name copy snapshot, mildly brittle,
but it is load-bearing-adjacent (confirms the Node-install step exists before the gate). Given
HIGH risk + KEEP bias, KEEP L779 — do not trim it.

est_lines_removed: 3

---

### 18. tests/test_verify_required_regressions_from_full_test_debt.py  (168 lines) — risk=low
TSV(mid): "末 stdout 整串断言:119 是文案快照,删该尾" (line stale; L119 is `assert not output_path.exists()`).

Re-mapped: the stdout snapshot is L117:
```
    assert stdout == "required_regressions verified targets=2 nodeids=2\n"
```
**TRIM (1 assert line):** delete L117.
Keep-context: KEEP `verifier.main(...) == 0` (L114, proves exit 0 + no crash), the
no-file-written asserts (L119-120, the P2-retirement contract), and the entire structural
`verify_required_regressions_from_payload(...)` block (L122-134: `required_target_paths`,
`required_nodeids` WITH ordering, count-by-path, group_coverage missing/unknown, counts) —
which fully covers the `targets=2 nodeids=2` numbers behaviorally. The exact stdout phrasing
`"required_regressions verified targets=…"` is rendered-copy; the counts it embeds are proven
structurally. Function retains many meaningful asserts.

Do NOT trim the `pytest.raises(..., match="没有被 full-test-debt 覆盖" / "非通过 reports" /
"classifications.candidate_test_debt 非空")` — those Chinese substrings are error-BRANCH
oracles (distinguish which rejection fired), not cosmetic copy. KEEP.

est_lines_removed: 1

---

## Batch totals
- Whole functions deleted: 3 (all in files #2 and #6; none registry-referenced).
- Assert-line / assert-block trims within kept functions: file #5(1), #6(block ~14 lines),
  #7(1), #8(1), #15(2), #17(3), #18(1).
- Files with ZERO trim (KEEP-all, mostly stale-anchor or invalidation-contract): #1, #3, #4,
  #9, #10, #11, #12, #13, #14, #16.
- Net est lines removed across batch: ~75.
- No imports/fixtures/shared-helpers broken; both registry-registered files keep >=1 test.
