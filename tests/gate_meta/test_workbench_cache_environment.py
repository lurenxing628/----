"""Workbench environment changes must not reuse a skipped browser execution cache."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from tests.gate_meta.workbench_cache_environment_support import (
    cache_success,
    legacy_plaintext_fingerprint,
    real_entries,
    seed_collect_proof,
    stub_execution_probes,
)
from tools import long_gate_fingerprint as fingerprint_mod
from tools import long_gate_manifest, test_registry
from tools.long_gate_cache import decide_failure_reuse, decide_reuse, write_failure
from tools.long_gate_fingerprint import RUNTIME_FINGERPRINT_KEYS, fingerprint_entry, fingerprint_environment

ALL_ENTRY_IDS = ("pytest_collect_all", "full_test_debt", "startup_runtime_regressions", "required_regressions")
ALL_GROUPS = (
    *test_registry.iter_required_regression_groups(),
    *test_registry.iter_required_regression_groups(test_registry.SUPPLEMENTAL_REGRESSION_GROUPS),
)
REGISTERED_ENV_KEYS = sorted({key for group in ALL_GROUPS for key in group["env_keys"]} - RUNTIME_FINGERPRINT_KEYS)
BROWSER_ONLY_KEYS = sorted(
    {key for group in test_registry.SUPPLEMENTAL_REGRESSION_GROUPS for key in group["env_keys"]}
    - {key for group in test_registry.iter_required_regression_groups() for key in group["env_keys"]}
)


@pytest.fixture(autouse=True)
def stable_execution_probes(monkeypatch):
    stub_execution_probes(monkeypatch)


@pytest.mark.parametrize("entry_id", ("pytest_collect_all", "full_test_debt"))
def test_browser_skip_to_run_invalidates_cached_success(tmp_path, monkeypatch, entry_id):
    seed_collect_proof(tmp_path)
    entry = real_entries(tmp_path)[entry_id]
    monkeypatch.setenv("ER_RUN_BROWSER", "0")
    before = fingerprint_entry(entry, str(tmp_path))
    cache_success(tmp_path, entry, before)
    assert decide_reuse(entry, before, repo_root=str(tmp_path))["decision"] == "reuse"

    monkeypatch.setenv("ER_RUN_BROWSER", "1")
    after = fingerprint_entry(entry, str(tmp_path))
    assert after["hash"] != before["hash"]
    decision = decide_reuse(entry, after, repo_root=str(tmp_path))
    assert decision["decision"] == "run"
    assert "environment changed: ER_RUN_BROWSER" in decision["invalidated_by"]


@pytest.mark.parametrize("entry_id", ("pytest_collect_all", "full_test_debt"))
@pytest.mark.parametrize("key", REGISTERED_ENV_KEYS)
def test_registered_environment_value_changes_fingerprint(tmp_path, monkeypatch, entry_id, key):
    entry = real_entries(tmp_path)[entry_id]
    assert key in entry["env_keys"]
    monkeypatch.setenv(key, "before")
    before = fingerprint_entry(entry, str(tmp_path))
    monkeypatch.setenv(key, "after")
    after = fingerprint_entry(entry, str(tmp_path))
    if key in entry["env_overlay"]:
        assert after["hash"] == before["hash"]
        assert after["components"]["environment"]["values"][key] == entry["env_overlay"][key]
    else:
        assert after["hash"] != before["hash"]


@pytest.mark.parametrize("entry_id", ALL_ENTRY_IDS)
def test_unrelated_values_are_not_serialized_or_hashed(tmp_path, monkeypatch, entry_id):
    entry = real_entries(tmp_path)[entry_id]
    before = fingerprint_entry(entry, str(tmp_path))
    for key in ("FC_UNRELATED_API_TOKEN", "WORKBENCH_UNREGISTERED_NOTE"):
        monkeypatch.setenv(key, "private-unrelated-value")
    after = fingerprint_entry(entry, str(tmp_path))
    assert after["hash"] == before["hash"]
    encoded = json.dumps(after)
    assert "private-unrelated-value" not in encoded
    assert "FC_UNRELATED_API_TOKEN" not in encoded
    assert "WORKBENCH_UNREGISTERED_NOTE" not in encoded


@pytest.mark.parametrize("entry_id", ("startup_runtime_regressions", "required_regressions"))
def test_browser_only_inputs_do_not_promote_required_or_startup(tmp_path, monkeypatch, entry_id):
    entry = real_entries(tmp_path)[entry_id]
    # Startup already observes this process guard independently of browser metadata.
    browser_only = set(BROWSER_ONLY_KEYS) - ({"WERKZEUG_RUN_MAIN"} if entry_id == "startup_runtime_regressions" else set())
    assert browser_only
    assert not browser_only.intersection(entry["env_keys"])
    before = fingerprint_entry(entry, str(tmp_path))
    for key in browser_only:
        monkeypatch.setenv(key, "1")
    assert fingerprint_entry(entry, str(tmp_path))["hash"] == before["hash"]
    supplemental_targets = {path for group in test_registry.SUPPLEMENTAL_REGRESSION_GROUPS
                            for path in group["target_paths"]}
    assert not supplemental_targets.intersection(entry["args"])
    if entry_id == "required_regressions":
        assert entry["args"] == ["python", "tools/verify_required_regressions_from_full_test_debt.py"]
    else:
        assert entry["args"][4:] == test_registry.iter_startup_regressions()


def test_direct_required_pytest_keeps_browser_only_environment_separate(tmp_path):
    command = {"args": ["python", "-m", "pytest", "-q", *test_registry.iter_required_tests()]}
    entry = long_gate_manifest.build_manifest_from_quality_gate_plan([command], repo_root=str(tmp_path))["entries"][0]
    assert entry["entry_id"] == "required_regressions"
    assert not set(BROWSER_ONLY_KEYS).intersection(entry["env_keys"])


def test_registry_metadata_is_the_only_new_environment_source(tmp_path, monkeypatch):
    before = real_entries(tmp_path)
    extra = {"group_id": "future_supplemental", "target_paths": ["tests/workbench/test_future.py"],
             "env_keys": ["FUTURE_BROWSER_MODE"]}
    monkeypatch.setattr(test_registry, "SUPPLEMENTAL_REGRESSION_GROUPS", (
        *test_registry.SUPPLEMENTAL_REGRESSION_GROUPS, extra,
    ))
    after = real_entries(tmp_path)
    for entry_id in ALL_ENTRY_IDS:
        expected = entry_id in {"pytest_collect_all", "full_test_debt"}
        assert ("FUTURE_BROWSER_MODE" in after[entry_id]["env_keys"]) == expected
        assert (fingerprint_entry(before[entry_id], str(tmp_path))["hash"]
                != fingerprint_entry(after[entry_id], str(tmp_path))["hash"]) == expected


def test_startup_environment_uses_only_matching_registry_targets(tmp_path, monkeypatch):
    extra = {"group_id": "startup_environment", "target_paths": test_registry.iter_startup_regressions()[:1],
             "env_keys": ["STARTUP_TEST_MODE"]}
    unmatched = {"group_id": "unmatched_environment", "target_paths": ["tests/workbench/test_future.py"],
                 "env_keys": ["UNMATCHED_BROWSER_MODE"]}
    monkeypatch.setattr(test_registry, "SUPPLEMENTAL_REGRESSION_GROUPS", (extra, unmatched))
    entry = real_entries(tmp_path)["startup_runtime_regressions"]
    assert "STARTUP_TEST_MODE" in entry["env_keys"]
    assert "UNMATCHED_BROWSER_MODE" not in entry["env_keys"]
    before = fingerprint_entry(entry, str(tmp_path))
    monkeypatch.setenv("UNMATCHED_BROWSER_MODE", "changed")
    assert fingerprint_entry(entry, str(tmp_path))["hash"] == before["hash"]
    monkeypatch.setenv("STARTUP_TEST_MODE", "changed")
    assert fingerprint_entry(entry, str(tmp_path))["hash"] != before["hash"]


def test_startup_process_guard_remains_a_shared_environment_input(tmp_path, monkeypatch):
    entries = real_entries(tmp_path)
    for entry_id in ("startup_runtime_regressions", "required_regressions"):
        entry = entries[entry_id]
        observes_guard = entry_id == "startup_runtime_regressions"
        assert ("WERKZEUG_RUN_MAIN" in entry["env_keys"]) == observes_guard
        monkeypatch.setenv("WERKZEUG_RUN_MAIN", "before")
        before = fingerprint_entry(entry, str(tmp_path))
        monkeypatch.setenv("WERKZEUG_RUN_MAIN", "after")
        assert (fingerprint_entry(entry, str(tmp_path))["hash"] != before["hash"]) == observes_guard


def test_collect_does_not_run_execution_probes(tmp_path, monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("collection must not probe an execution runtime")

    for name in ("_node_version", "_node_executable_realpath", "_node_browser_runtime_capability",
                 "_chrome_headless_preflight", "_chrome_version", "_git_version"):
        monkeypatch.setattr(fingerprint_mod, name, forbidden)
    entry = real_entries(tmp_path)["pytest_collect_all"]
    fingerprint_entry(entry, str(tmp_path))


@pytest.mark.parametrize("entry_id", ALL_ENTRY_IDS)
def test_registered_secret_is_hashed_without_losing_change_detection(tmp_path, monkeypatch, entry_id):
    entry = real_entries(tmp_path)[entry_id]
    monkeypatch.setenv("SECRET_KEY", "private-fixture-one")
    before = fingerprint_entry(entry, str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "private-fixture-two")
    after = fingerprint_entry(entry, str(tmp_path))
    assert before["hash"] != after["hash"]
    assert before["components"]["environment"]["values"]["SECRET_KEY"].startswith("sha256:")
    assert "private-fixture-one" not in json.dumps(before)
    assert "private-fixture-two" not in json.dumps(after)


def test_unset_and_empty_secret_remain_distinct():
    absent = fingerprint_environment(["SECRET_KEY"], environment={})
    empty = fingerprint_environment(["SECRET_KEY"], environment={"SECRET_KEY": ""})
    assert absent["values"]["SECRET_KEY"] is None
    assert empty["hash"] != absent["hash"]


@pytest.mark.parametrize("entry_id", ("pytest_collect_all", "full_test_debt"))
def test_old_cache_missing_key_cannot_reuse_even_when_variable_is_unset(tmp_path, monkeypatch, entry_id):
    seed_collect_proof(tmp_path)
    monkeypatch.delenv("ER_RUN_BROWSER", raising=False)
    entry = real_entries(tmp_path)[entry_id]
    old_entry = dict(entry, env_keys=[key for key in entry["env_keys"] if key != "ER_RUN_BROWSER"])
    old = fingerprint_entry(old_entry, str(tmp_path))
    cache_success(tmp_path, old_entry, old)
    assert decide_reuse(old_entry, old, repo_root=str(tmp_path))["decision"] == "reuse"
    current = fingerprint_entry(entry, str(tmp_path))
    assert decide_reuse(entry, current, repo_root=str(tmp_path))["decision"] == "run"


@pytest.mark.parametrize("first,second", ((None, "1"), ("0", "1"), ("1", "0")))
def test_browser_modes_do_not_reuse_failure_cache(tmp_path, monkeypatch, first, second):
    seed_collect_proof(tmp_path)
    entry = real_entries(tmp_path)["full_test_debt"]
    if first is None:
        monkeypatch.delenv("ER_RUN_BROWSER", raising=False)
    else:
        monkeypatch.setenv("ER_RUN_BROWSER", first)
    before = fingerprint_entry(entry, str(tmp_path))
    write_failure(entry, before, {"returncode": 1, "stdout": "failed fixture", "stderr": ""}, repo_root=str(tmp_path))
    assert decide_failure_reuse(entry, before, repo_root=str(tmp_path))["decision"] == "cached_failure"
    monkeypatch.setenv("ER_RUN_BROWSER", second)
    after = fingerprint_entry(entry, str(tmp_path))
    assert decide_failure_reuse(entry, after, repo_root=str(tmp_path))["decision"] == "run"


def test_real_full_debt_cli_overrides_environment_shard_fallbacks(tmp_path, monkeypatch):
    entry = real_entries(tmp_path)["full_test_debt"]
    assert entry["args"][2:] == ["--sharded", "--shard-count", "3"]
    before = fingerprint_entry(entry, str(tmp_path))
    monkeypatch.setenv("APS_FULL_TEST_DEBT_SHARDED", "0")
    monkeypatch.setenv("APS_FULL_TEST_DEBT_SHARD_COUNT", "17")
    assert fingerprint_entry(entry, str(tmp_path))["hash"] == before["hash"]


@pytest.mark.parametrize("options,keys", (
    ([], {"APS_FULL_TEST_DEBT_SHARDED", "APS_FULL_TEST_DEBT_SHARD_COUNT"}),
    (["--sharded"], {"APS_FULL_TEST_DEBT_SHARD_COUNT"}),
    (["--shard-count=4"], {"APS_FULL_TEST_DEBT_SHARDED"}),
    (["--sharded", "--shard-count=4"], set()),
))
def test_legacy_full_debt_fingerprints_only_unoverridden_shard_inputs(tmp_path, monkeypatch, options, keys):
    command = {"args": ["python", "tools/check_full_test_debt.py", *options]}
    entry = long_gate_manifest.build_manifest_from_quality_gate_plan([command], repo_root=str(tmp_path))["entries"][0]
    for key in ("APS_FULL_TEST_DEBT_SHARDED", "APS_FULL_TEST_DEBT_SHARD_COUNT"):
        assert (key in entry["env_keys"]) == (key in keys)
        monkeypatch.setenv(key, "0")
        before = fingerprint_entry(entry, str(tmp_path))
        monkeypatch.setenv(key, "1")
        assert (fingerprint_entry(entry, str(tmp_path))["hash"] != before["hash"]) == (key in keys)


@pytest.mark.parametrize("entry_id", ("pytest_collect_all", "full_test_debt", "startup_runtime_regressions"))
@pytest.mark.parametrize("path", (
    "tools/long_gate_manifest_environment.py", "tools/test_registry_groups_workbench.py",
    "tools/test_registry.py", "tools/test_registry_workbench_ui.py",
))
def test_environment_policy_source_changes_invalidate_fingerprint(tmp_path, entry_id, path):
    entry = real_entries(tmp_path)[entry_id]
    source = tmp_path / path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# before\n", encoding="utf-8")
    before = fingerprint_entry(entry, str(tmp_path))
    source.write_text("# after\n", encoding="utf-8")
    assert fingerprint_entry(entry, str(tmp_path))["hash"] != before["hash"]


@pytest.mark.parametrize("entry_id", ("pytest_collect_all", "full_test_debt"))
def test_strict_cache_uses_effective_environment_and_does_not_store_secret(tmp_path, monkeypatch, entry_id):
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    seed_collect_proof(tmp_path)
    entry = real_entries(tmp_path)[entry_id]
    monkeypatch.setenv("SECRET_KEY", "private-cache-fixture")
    monkeypatch.setenv("ER_RUN_BROWSER", "0")
    entry["env_overlay"] = dict(entry["env_overlay"], ER_RUN_BROWSER="1")
    before = fingerprint_entry(entry, str(tmp_path), strict=True)
    cache_success(tmp_path, entry, before)
    assert before["components"]["environment"]["values"]["ER_RUN_BROWSER"] == "1"
    monkeypatch.setenv("ER_RUN_BROWSER", "different-parent-value")
    after = fingerprint_entry(entry, str(tmp_path), strict=True)
    assert decide_reuse(entry, after, repo_root=str(tmp_path))["decision"] == "reuse"
    result_path = tmp_path / "evidence/QualityGate/long_gate/results" / (entry_id + ".success.json")
    assert "private-cache-fixture" not in result_path.read_text(encoding="utf-8")
    entry["env_overlay"]["ER_RUN_BROWSER"] = "0"
    assert decide_reuse(entry, fingerprint_entry(entry, str(tmp_path), strict=True), repo_root=str(tmp_path))["decision"] == "run"


@pytest.mark.parametrize("secret", (None, "", "private-old-secret"))
@pytest.mark.parametrize("cache_kind", ("success", "failure"))
def test_old_plaintext_cache_semantics_are_not_reused(tmp_path, monkeypatch, secret, cache_kind):
    seed_collect_proof(tmp_path)
    entry = real_entries(tmp_path)["full_test_debt"]
    if secret is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", secret)
    current = fingerprint_entry(entry, str(tmp_path))
    old = legacy_plaintext_fingerprint(current, secret)
    if cache_kind == "success":
        cache_success(tmp_path, entry, old)
        decide = decide_reuse
        expected = "reuse"
    else:
        write_failure(entry, old, {"returncode": 1, "stdout": "old fixture", "stderr": ""}, repo_root=str(tmp_path))
        decide = decide_failure_reuse
        expected = "cached_failure"
    # Prove this is a self-consistent old cache, not rejection of corrupt evidence.
    assert decide(entry, old, repo_root=str(tmp_path))["decision"] == expected
    decision = decide(entry, current, repo_root=str(tmp_path))
    assert decision["decision"] == "run"
    assert decision["reason"] == "input fingerprint changed"


def test_observed_old_receipt_is_not_a_reusable_manifest_proof(tmp_path):
    entry = real_entries(tmp_path)["pytest_collect_all"]
    receipt = {"display": entry["display"], "returncode": 0, "fingerprint": {"hash": "old"}}
    manifest = long_gate_manifest.build_manifest_from_quality_gate_plan([entry], [receipt], repo_root=str(tmp_path))
    observed = manifest["entries"][0]
    assert observed["local_receipts"] == [receipt]
    assert observed["fingerprint"] is None
    assert observed["previous_success"] is None
    assert observed["last_success_fingerprint"] is None


def test_fingerprint_implementation_change_rejects_old_manifest_before_receipt_resume(tmp_path, monkeypatch):
    from scripts import run_quality_gate as gate

    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    monkeypatch.setattr(gate, "REPO_ROOT", str(tmp_path))
    source = tmp_path / "tools/long_gate_fingerprint.py"
    source.parent.mkdir()
    source.write_text("# old plaintext implementation\n", encoding="utf-8")
    status = ["?? tools/long_gate_fingerprint.py"]
    previous = {
        "status": "failed", "head_sha": "same-head", **gate._repo_identity(),
        "python_executable": sys.executable, "python_version": sys.version.splitlines()[0].strip(),
        "dirty_worktree_fingerprint_before": gate._dirty_worktree_fingerprint(status),
    }
    manifest_path = tmp_path / "old-manifest.json"
    manifest_path.write_text(json.dumps(previous), encoding="utf-8")
    monkeypatch.setattr(gate, "_quality_gate_manifest_abs_path", lambda: str(manifest_path))
    source.write_text("# environment schema 2 with value-sensitive secret digest\n", encoding="utf-8")
    decision = gate._decide_resume_from_previous_failure(
        [], current_head_sha="same-head", current_git_status_short=status
    )
    assert not decision.enabled
    assert decision.reason == "\u810f\u5de5\u4f5c\u533a\u5185\u5bb9\u5df2\u53d8\u5316\uff0c\u672c\u6b21\u5b8c\u6574\u91cd\u8dd1"
