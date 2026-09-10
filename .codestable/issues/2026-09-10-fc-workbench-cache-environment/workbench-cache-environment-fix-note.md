---
doc_type: issue-fix
status: fixed
created: 2026-09-10
summary: FC binds workbench cache environment inputs to registry metadata and versions secret digest semantics
tags: [workbench, cache, environment, fingerprint, Python38, FC]
---

# Scope

- Authorized local repair in the shared dirty checkout. Existing staged, unstaged and untracked work was preserved; no stage or commit.
- FC wrote only tools/long_gate_manifest.py, tools/long_gate_manifest_environment.py, tools/long_gate_fingerprint.py, tests/gate_meta/test_workbench_cache_environment.py, tests/gate_meta/workbench_cache_environment_support.py, and this note.
- No registry, shared quality_gate, product, build, preview, real browser, or whole-repository gate change/run. Neighboring gate tests use temporary repositories and fake command execution, not a real full gate.

# Reproduction And Cause

- Before repair, the new dedicated test ran twice against the real quality_gate command plan and isolated success-cache files: pytest_collect_all and full_test_debt both failed because ER_RUN_BROWSER=0 -> 1 left their fingerprint hash unchanged. The cached fixture was reusable before the toggle.
- tools/long_gate_manifest.py used fixed environment key lists for collection/full debt, while workbench runtime selectors and opt-in controls were already declared in required/supplemental registry metadata. fingerprint_entry could only hash keys supplied by the manifest.
- The failure is missing input semantics, not permission to treat skipped tests as successful browser execution.

# Actual Command Semantics

| Entry | Actual input and new behavior |
| --- | --- |
| pytest_collect_all | python -m pytest --collect-only -q tests; inherits parent environment. Includes declared test environment keys because collection can inspect decorators and parameters. Does not acquire Node/Chrome execution probes from registry metadata. |
| full_test_debt | python tools/check_full_test_debt.py --sharded --shard-count 3; checker and workers inherit environment, with command overlay applied first. Runs the full pytest inventory, including supplemental opt-in cases. Includes declared required+supplemental environment keys. |
| startup_runtime_regressions | Direct pytest over iter_startup_regressions(); only matching registry target metadata contributes new keys. Existing startup environment/runtime policy is retained. |
| required_regressions | python tools/verify_required_regressions_from_full_test_debt.py; verifies actual required reports from the full-debt payload, not a separate browser run. Existing required groups remain separate from supplemental groups. The direct required-pytest legacy form retains that separation. |

- Explicit --sharded and --shard-count override APS_FULL_TEST_DEBT_SHARDED/APS_FULL_TEST_DEBT_SHARD_COUNT; the default command ignores changes to those fallbacks. Legacy commands lacking these options fingerprint the fallback keys.
- Input values are resolved after env_overlay. Unrelated parent variables, including unrelated credentials, do not enter persisted fingerprints. No second test-path inventory or prefix-based environment dump was added.
- Registry and the new environment-policy helper are themselves file-fingerprint inputs. New registry declarations automatically reach collect/full debt without editing another key list.

# Existing Cache And Secret Semantics

- SECRET_KEY is represented by sha256(stable_json(value)), not a fixed redaction. Different values, the empty string and an unset variable remain distinguishable; tests inspect persisted cache JSON for absence of fixture plaintext.
- tools/long_gate_fingerprint.py declares ENVIRONMENT_FINGERPRINT_SCHEMA_VERSION=2. Both the environment component and its hash include this version. Top-level cache/fingerprint schema constants are unchanged; the nested semantic version forces old environment representations to miss even if SECRET_KEY is unset.
- Regression fixtures construct internally self-consistent old environment hashes, retaining valid cache metadata. They first prove those old fixtures are reusable against themselves, then verify current fingerprints reject both old success and old failure results for nonempty, empty and unset secrets.
- Existing tools/long_gate_cache.py:519,557 and :732,770 also reject fingerprint-schema/tooling changes. tools/long_gate_schema.py includes long_gate_fingerprint.py and long_gate_manifest.py in tooling content hashes, independently invalidating pre-repair cache artifacts.
- Old receipts attached by long_gate_manifest.py:1151 remain observations only; they do not fill fingerprint/previous_success slots. The dedicated test locks that boundary.
- The separate failed-run receipt-resume path in scripts/run_quality_gate.py:636,663 checks HEAD and the dirty content fingerprint before examining receipts. A dedicated test changes the fingerprint implementation with the same HEAD/status paths and proves the old manifest is rejected before receipt resume. This confirms the upgrade transition; it is not a redesign or a general environment-binding claim for that independent dirty-resume path.

# Validation

- Runtime: .venv/bin/python is Python 3.8.10.
- Initial dedicated reproduction: 2 failed, as expected before repair.
- Dedicated final run after environment semantic versioning: 127 passed in 8.64s. Registry changes during the shared run automatically expanded the earlier 101/119-case parameterizations.
- First adjacent run: 454 passed, 2 failed in 75.25s. The failures were old assertions requiring SECRET_KEY plaintext and treating APS_ENV as startup-only. They were reported with exact locations to the main task; the user assigned FD to verify/update them. FC did not edit either file.
- Final combined run after FD's concurrent contract updates: 598 passed in 117.98s. Exact command: .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/gate_meta/test_workbench_cache_environment.py tests/gate_meta/test_long_gate_collect_cache.py tests/gate_meta/test_long_gate_cache.py tests/gate_meta/test_long_gate_full_test_debt_cache.py tests/gate_meta/test_long_gate_required_regression_cache.py tests/gate_meta/test_long_gate_startup_regression_cache.py tests/gate_meta/test_long_gate_manifest.py. This includes the formerly failing neighboring contracts; it is evidence for the combined dirty checkout, not sole attribution to FC.
- Scoped Ruff: all five FC Python files passed. Python 3.8 syntax scanner: five files, zero read failures, parser rejections or semantic-risk hits. git diff --check on the two edited tracked modules passed.
- Issue frontmatter validation: 1 passed. The initial --yaml-only invocation incorrectly treated the Markdown body as YAML; rerunning in Markdown/frontmatter mode passed without document changes.

# Handoff Boundaries

- No browser execution is claimed by these unit/cache tests; their success proves cache isolation, not browser acceptance or required-registry coverage.
- Registry completeness is owned by FD. FC reported observed missing metadata inputs (including AN_SCOPE, AY_BASELINE/AY_REACT_DEV/AY_UNSUSPENDED, WORKBENCH_EXPECT_BUILD, SYSTEM_CONFIG_SAVED_REPLAY_OLD_EFFECT, TRIAL_WIDGET_TARGET_ONLY and OUTSOURCING_UI_SCHEMA) without editing that registry.
- The registry was observed at 546 required / 33 required groups / 81 supplemental during the concurrent work, versus the user's starting 80 supplemental. FC did not change those counts.
- All results are local dirty-worktree verification, not final-HEAD or clean-worktree proof. No real cached evidence or production data was rewritten by the tests.
