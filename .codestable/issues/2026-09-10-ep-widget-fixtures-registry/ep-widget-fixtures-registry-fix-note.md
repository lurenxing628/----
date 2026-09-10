---
doc_type: issue-fix
status: fixed
created: 2026-09-10
summary: EP fixture repairs and completed-only registration; external discovery and tracked-proof failures retained
tags: [workbench, fixtures, registry, Python38, Chrome109, EP]
---

# Scope and conclusion

- The two delegated widget failures and the later authorized report fixture failure are fixed.
- Product files, PlanQueries, PointPlanQuery and PlanContract were not edited by EP.
- EN was notified before helper edits. TRIAL_WIDGET_SOURCES is unchanged from the EN delivery.
- No stage, commit, full gate, whole-repository pyright, global asset build, old preview or business database operation.
- All evidence is from the dirty shared checkout, not clean-worktree or final-HEAD proof.
- Seven Python files and this note are EP's manual changes. Earlier shared changes remain intact.

# Root causes and repairs

1. tests/workbench/run_baseline_widgets_support.py:61 now uses UNREADY, quantity=3, ready_status=no. The former ZERO/quantity=0 operation is a valid scheduled point, so it no longer proves unscheduled behavior. Actual admission/worker exclusion supplies the unscheduled comparison; no candidate rows or result statuses are injected for this repair.
2. tests/workbench/trial_widgets_support.py:62 keeps B1/B2 at quantity=3 and makes B3 quantity=1, matching its single piece-A. The original quantity=3 plus one piece caused piece_scope_incomplete in piece_adoption_scope.py:53; trial_base.py:195 called the complete-piece adapter and preserved no predecessor refs after that failure. This is an obsolete fixture, not evidence authorizing a product change.
3. tests/workbench/test_ep_trial_fixture_contracts.py locks all four candidates in mixed/execution cases, null improvement deltas, and the real readiness control that makes the same operation schedulable again. Plan/candidate/saved trial reads retain exact predecessor task/operation refs and persisted source rows.
4. tests/workbench/test_report_read.py:81 uses BEGIN plus PRAGMA defer_foreign_keys=ON only inside a rollback-only corruption fixture. The real HTTP route reads that same connection with query_only=ON. identity_missing still must occur; the damaged snapshot cannot be repaired by GET; separate connections retain the original state; rollback restores the complete iterdump and clears FK violations. foreign_keys stays ON.

The original probe and precise-source assertions were preserved byte-for-byte:

| File | SHA-256 before and after |
| --- | --- |
| run_baseline_widgets_probe.cjs | fa4fb899a3ecc7562f76b2a13dbceb0cffb00cdd2cd53d8af9db345992cac7c2 |
| trial_widgets_probe.cjs | f65ebcf0b8096d7e40d69d70f1ba9b6aa83d580d19fbc64f56faa7f1c5326891 |
| test_trial_widgets.py | b2923956fe1a9a957c57ade66d644e41f4cf2be138a324e55add4d15f14616c4 |

Pre-edit owned-file copies: /tmp/ep-owned-before-pnYopy.

# Fixed registration

tools/test_registry_groups_workbench.py uses fixed filenames, not discovery-generated targets.

| Group | Appended files under tests/workbench/ |
| --- | --- |
| required/workbench_piece_adoption | test_piece_chain_input.py, test_piece_chain_end_to_end.py, test_piece_chain_execution.py, test_piece_chain_external.py, test_piece_chain_boundaries.py |
| required/workbench_process | test_merged_cycle_projection.py, test_merged_cycle_projection_api.py |
| required/workbench_field | test_point_downstream_api.py |
| required/workbench_zero_duration | test_point_public_contract.py |
| required/workbench_trial | test_ep_trial_fixture_contracts.py |
| supplemental/workbench_browser | test_point_frontend.py, test_point_downstream_browser.py, test_el_material_contracts.py, test_point_dense_canvas.py |
| supplemental/workbench_browser_opt_in | test_ed_material_process_browser.py, test_el_material_browser.py, test_reports_review_browser.py |

- Required: 33 groups, 530 -> 540 targets. Supplemental: 68 -> 75 targets. Coverage missing/unknown/duplicates are empty.
- EL's Node contracts still require runtime_tools' installed browser path, so remain supplemental. The main public contract requires Node only and remains required; its actual four parametrizations passed.
- ED/EL/EI retain their existing skipUnless and environment switches. ED_SCOPE/ED_STATES/EL_STATES and candidate switches are fingerprint inputs, not permission to silently shorten execution.
- Source/helper scopes and selection contracts are explicit. The obsolete algorithm fixture input path now names the actual core/algorithm_runtime/piece_input.py.
- tests/gate_meta/test_workbench_registry_contract.py and tests/gate_meta/test_long_gate_manifest.py synchronize counts, owners and real consumer contracts without changing skip/perf policies.
- EE/EK/ED/EL/EN/EI browser registration follows the user's completed-delivery confirmation; it is not a new EP execution receipt for those browser files. EP reran the relevant old baseline/trial browsers, backend deliveries and Node contracts listed below.

# Actual validation

Runtime: .venv/bin/python = Python 3.8.10; real browser = Chromium 109.0.5414.46. Temporary SQLite databases use real schema/worker/HTTP services.

| Command scope | Result | JUnit evidence |
| --- | --- | --- |
| New EP fixture tests before repair | 4 failed at the obsolete fixture conditions | /tmp/ep-fixtures-before.xml |
| Original short-task fixture before repair | 1 failed, predecessor refs empty | /tmp/ep-trial-before.xml |
| EP fixtures plus report_read before report repair | 20 passed / 1 FK setup failure | /tmp/ep-report-before.xml |
| test_ep_trial_fixture_contracts.py + test_report_read.py | 21 passed | /tmp/ep-fixture-regressions.xml |
| test_run_baseline_widgets.py + test_trial_widgets.py + test_trial_export_widgets.py | 5 passed, 135.83s | /tmp/ep-widget-regressions.xml |
| EF five files + EK API + EM two files + main public contract + EL Node contracts | 81 passed, 33.90s | /tmp/ep-delivered-targets.xml |
| workbench registry contract + long manifest | 670 passed / 1 external discovery failure | /tmp/ep-registry-contracts-final.xml |
| Existing full-debt shared-registry tracked precondition | 1 existing tracked-proof failure | /tmp/ep-tracked-registry-boundary.xml |

- The 81-pass receipt is EF 30 + EK API 17 + EM 28 + main public contract 4 + EL Node 2. No skips. Repeated earlier runs are not added to these counts.
- Widget results: baseline 172 checks/four variants; trial full 86 checks/four variants and 12 short-task dimension proofs; trial exports 10 checks/four variants; dedicated export probe 46 downloads/four variants.
- Baseline preserves both complete schema-31 database dumps, including the 5000-row case. Trial proofs preserve legacy rows/types and SQLite receipt/task counts. No mocked business results or external requests were reported.
- Fresh browser artifacts under /var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/: aps-run-baseline-widgets-z6r05kri, aps-cn-trial-widgets-bak3q8y_, aps-cn-trial-widgets-_1ugmebh, aps-cz-trial-export-jxz6zknn. Each contains sqlite-proof.json and probe results. Baseline 1920-light and trial 1392-dark screenshots were inspected.
- Ruff passes for the six other touched Python files. Baseline support still has exactly the same three pre-existing UP031 warnings in capacity_case (now lines 84/87); verified against the pre-edit copy. No unrelated format repair.
- Changed-file whitespace checks passed. The original discovery assertion remains unchanged.

# Remaining boundaries

1. Registry discovery still reports four files not authorized as completed in this task: tests/workbench/test_merged_cycle_ui.py, tests/workbench/test_piece_main_browser.py, tests/workbench/test_point_adoption_host.py, tests/workbench/test_secondary_copy_contrast.py. They were not silently registered or ignored.
2. Existing tests/gate_meta/test_full_test_debt_registry_contract.py:1264 still rejects untracked required tests (first failure: tests/algorithm/test_busy_block_native_equivalence.py). Read-only git ls-files comparison finds 267 required-untracked paths, the prior 257 plus these ten new required registrations. EP did not stage to remove that failure.
3. No Win7 execution, unified browser rebuild, full gate or clean-worktree proof was performed. The scoped repairs and registration are ready for mainline integration; the remaining files require their owners' completed delivery before registration.
