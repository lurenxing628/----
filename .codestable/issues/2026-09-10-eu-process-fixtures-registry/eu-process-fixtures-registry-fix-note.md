---
doc_type: issue-fix
status: fixed
created: 2026-09-10
summary: EU process DTO fixture repair and delivered-only registry extension; discovery and tracked-proof failures retained
tags: [workbench, fixtures, registry, Python38, Chrome109, EU]
---

# Scope

- Eight code/test files and this note are EU's manual changes. Pre-existing shared changes remain intact.
- Added process_stage_widgets_probe.cjs and process_widgets_probe.cjs only after mainline received the exact paths and authorized them.
- No product, main, build, schema, old-preview or production-database edit. No stage, commit, full gate or full pyright.
- All execution evidence is from the dirty shared checkout, not a final-HEAD or clean-worktree proof.

# Repairs and fixed registration

| File | EU change |
| --- | --- |
| tests/workbench/process_detail_files_probe.cjs:30 | Internal operations with no external cycle explicitly expose external_days_source=null. |
| tests/workbench/process_widgets_probe.cjs:42 | This is a projection DTO, not raw storage: external/group raw zero becomes null plus value_invalid; visible error assertions remain. |
| tests/workbench/process_stage_widgets_probe.cjs:32 | Existing cycle 2 stays source=operation; later source changes update DTO provenance. |
| tests/workbench/process_stage_widgets_probe.cjs:55 | Saving a blank external member requires its valid merged group before setting source=group. |
| tests/workbench/process_stage_widgets_probe.cjs:156 | Keep clearing the operation input, saving null, group-total and receipt assertions. The new UI uses an exact group label, not the obsolete placeholder; also assert the operation input disappears. |
| tests/workbench/test_eu_process_fixture_contracts.py:67 | Nine Node/real SQLite projection contracts: internal null, illegal zero with unchanged stored zero, four workflow stages, and saved group delegation. Missing source and false internal group provenance are rejected by the actual ProcessContract. |
| tests/workbench/run_baseline_widgets_support.py:84 | Only three UP031 string formats changed; all 100 batch/machine/operator names match the original and every other AST node is unchanged. |
| tools/test_registry_groups_workbench.py:230 | New fixed required EU fixture target in workbench_process; actual Node/Babel/contract/probe inputs included. |
| tools/test_registry_groups_workbench.py:566 | Mainline's delivered test_point_adoption_host.py is required in workbench_zero_duration; imported host-test helper remains owned by workbench_run_jobs and is also an input. |
| tools/test_registry_groups_workbench.py:739 | Delivered test_merged_cycle_ui.py and test_secondary_copy_contrast.py are opt-in supplemental; exact helper files and environment switches included. |
| tests/gate_meta/test_workbench_registry_contract.py:811 | Exact counts, owners, sources, helper-only boundary and actual daily consumers locked. |
| tests/gate_meta/test_long_gate_manifest.py:147 | Count and required-parent fingerprint invalidation include delivered host and repaired fixture inputs. |

- Required: 540 -> 542 targets, still 33 groups. Supplemental: 75 -> 77 targets.
- test_point_dense_canvas.py was already registered by EP and was not duplicated or reassigned.
- Support/case_support files are not new pytest targets. No skip/perf policy, discovery assertion or tracked precondition was relaxed.
- Coverage missing, duplicates and unknown are all empty. See /tmp/aps-eu-20260910-D6XKZV/final-state.json.

# Actual validation

Runtime: .venv/bin/python is Python 3.8.10; Node contract runtime is v24.15.0; browser probes used real Chromium 109.0.5414.46.
All temporary SQLite files and pytest basetemp directories are exclusive to /tmp/aps-eu-20260910-D6XKZV.

| Scope | Result | Evidence under the exclusive root |
| --- | --- | --- |
| Original detail-files browser before repair | 1 failed at initial detail mount | before-detail.xml |
| All three pre-edit probe snapshots through current ProcessContract | All rejected with incomplete detail | Original .cjs snapshots retained in the root |
| Detail-files + read/preview browsers | 2 passed; stage's intermediate obsolete-placeholder failure retained | process-browsers.xml |
| Stage browser after semantic fixture correction | 1 passed; 84 cases, four variants, 24 screenshots | stage-final.xml |
| Final unified run of all three process browsers | 3 passed, no skips; 160.08 seconds | all-process-final.xml |
| EU fixtures, merged-cycle Node/SQL/API, three adoption-host files, EP fixtures and secondary-copy source | 62 passed, 3 intentional opt-in skips | contracts-final.xml |
| Real collect-only for EU + three newly delivered targets + existing dense canvas | 30 nodeids collected | discovery.xml |
| Registry, manifest and real shared-registry consumer | 703 passed, 2 expected boundary failures | registry-final.xml |
| Latest unchanged discovery and tracked assertions | 2 expected failures; late EV file also remains unregistered | boundaries-final.xml |
| Five touched Python files, scoped Ruff | Passed | No full-repository lint/pyright |
| Baseline helper equivalence | All generated identifiers equal; all other AST nodes equal | Compared to the retained pre-edit copy |

- Successful browser receipts total 196 cases (52 detail + 60 read/preview + 84 stage), 76 screenshots, no page/console errors or external requests.
- Screenshot inspection confirmed visible invalid-zero diagnostics and the original stage/receipt controls.
- The 62 passing tests contain five actual host cases, not a rerun claim for mainline's earlier 12-host receipt. ER's 40-case full page and EO's two browser tests remained opt-in and were not counted as executed by EU. EN's existing registration was only collected, not rerun.

# Preserved red items

1. Original discovery still fails on in-flight targets: tests/workbench/test_piece_main_browser.py, tests/workbench/test_piece_presentation.py, tests/workbench/test_piece_presentation_browser.py, tests/workbench/test_piece_production_connection.py. The final read also found tests/workbench/test_ev_piece_fixture_contracts.py. ES/ET/EQ/EV delivery was not claimed; mainline was notified of the exact late path.
2. tests/gate_meta/test_full_test_debt_registry_contract.py:1264 still rejects untracked required files, starting with tests/algorithm/test_busy_block_native_equivalence.py.
3. All 267 original required-untracked paths remain untracked. Adding the delivered point host and EU fixture contract makes 269; no staging was used to remove this red condition. Existing staged names are unchanged.
4. These are current dirty-worktree receipts only. Full gate, whole-repo pyright, global build and Win7 execution were not performed.
