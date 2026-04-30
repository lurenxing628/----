from __future__ import annotations

import copy
import importlib
import json
import sys
import textwrap
from pathlib import Path

import pytest


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_sync_debt_ledger():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("tools.quality_gate_support", None)
    sys.modules.pop("tools.test_debt_registry", None)
    sys.modules.pop("scripts.sync_debt_ledger", None)
    return importlib.import_module("scripts.sync_debt_ledger")


def _import_quality_gate_support():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("tools.quality_gate_support", None)
    return importlib.import_module("tools.quality_gate_support")


def _import_test_debt_registry():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("tools.test_debt_registry", None)
    return importlib.import_module("tools.test_debt_registry")


BASELINE_BEGIN = "<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->"
BASELINE_END = "<!-- APS-FULL-PYTEST-BASELINE:END -->"
P0_TEST_DEBT_NODEIDS = [
    "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
    "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
    "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error",
    "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
    "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
]
BASELINE_SHA = "a" * 40
VERIFIED_SHA = "b" * 40


def _legacy_schema1_ledger() -> dict:
    support = _import_quality_gate_support()
    return {
        "schema_version": 1,
        "identity_strategy": support.LEDGER_IDENTITY_STRATEGY,
        "updated_at": "2026-04-27T08:00:00+08:00",
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {"scope": list(support.STARTUP_SCOPE_PATTERNS), "entries": []},
        "accepted_risks": [],
    }


def _test_debt_entry(
    debt_id: str = "test-debt:sample-one",
    nodeid: str = P0_TEST_DEBT_NODEIDS[0],
    *,
    mode: str = "xfail",
) -> dict:
    return {
        "debt_id": debt_id,
        "nodeid": nodeid,
        "mode": mode,
        "reason": "旧测试合同尚未更新",
        "domain": "personnel.operator_machine",
        "style": "stale_patch_target",
        "root": {"module": "core.services.personnel.operator_machine_service", "function": "list_by_operator"},
        "owner": "personnel.operator_machine",
        "exit_condition": "该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。",
        "last_verified_at": "2026-04-27T08:00:00+08:00",
        "debt_family": "operator_machine_normalization_contract_drift",
    }


def _schema2_ledger_with_test_debt(*entries: dict, max_registered_xfail: int = 1) -> dict:
    ledger = _legacy_schema1_ledger()
    ledger["schema_version"] = 2
    ledger["test_debt"] = {
        "ratchet": {"max_registered_xfail": max_registered_xfail},
        "entries": list(entries),
    }
    return ledger


def _write_baseline(path: Path, payload: dict) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            # baseline

            {BASELINE_BEGIN}
            ```json
            {json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}
            ```
            {BASELINE_END}
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _baseline_payload(**overrides) -> dict:
    payload = {
        "schema_version": 2,
        "baseline_kind": "after_main_style_isolation",
        "importable": True,
        "importable_blockers": [],
        "generated_at": "2026-04-27T08:00:00+08:00",
        "head_sha": BASELINE_SHA,
        "collector_argv": [
            "--baseline-kind",
            "after_main_style_isolation",
            "--importable-debt-baseline",
            "--write-baseline",
            "audit/2026-04/20260427_full_pytest_p0_debt_baseline.md",
            "--",
            "tests",
            "-q",
            "--tb=short",
            "-ra",
            "-p",
            "no:cacheprovider",
        ],
        "git_status_short_before": [],
        "worktree_clean_before": True,
        "python_executable": sys.executable,
        "python_version": sys.version.splitlines()[0],
        "pytest_version": "8.0.0",
        "pytest_args": ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
        "exitstatus": 1,
        "collected_nodeids": list(P0_TEST_DEBT_NODEIDS),
        "collection_errors": [],
        "reports": [],
        "classifications": {
            "candidate_test_debt": list(P0_TEST_DEBT_NODEIDS),
            "main_style_isolation_candidate": [],
            "required_or_quality_gate_self_failure": [],
        },
        "summary": {
            "collected_count": 588,
            "failed_nodeid_count": 5,
            "collection_error_count": 0,
            "classification_counts": {
                "candidate_test_debt": 5,
                "main_style_isolation_candidate": 0,
                "required_or_quality_gate_self_failure": 0,
            },
            "outcome_counts": {"call:failed": 5, "call:passed": 583},
        },
    }
    payload.update(overrides)
    return payload


def _zero_candidate_payload(**overrides) -> dict:
    payload = _baseline_payload(
        exitstatus=0,
        collected_nodeids=["tests/test_clean.py::test_clean"],
        classifications={
            "candidate_test_debt": [],
            "main_style_isolation_candidate": [],
            "required_or_quality_gate_self_failure": [],
        },
        summary={
            "collected_count": 1,
            "failed_nodeid_count": 0,
            "collection_error_count": 0,
            "classification_counts": {
                "candidate_test_debt": 0,
                "main_style_isolation_candidate": 0,
                "required_or_quality_gate_self_failure": 0,
            },
            "outcome_counts": {"call:passed": 1},
        },
    )
    payload.update(overrides)
    return payload


def test_check_command_validates_current_ledger(monkeypatch, capsys):
    module = _import_sync_debt_ledger()
    calls = {}
    current_ledger = {"schema_version": 1}

    def fake_load_ledger(required: bool = True):
        calls["load_required"] = required
        return current_ledger

    def fake_validate(ledger):
        calls["validated_ledger"] = ledger
        return {"samples": {"matched": 7}}

    monkeypatch.setattr(module, "load_ledger", fake_load_ledger)
    monkeypatch.setattr(module, "validate_ledger_against_current_scan", fake_validate)

    rc = module.main(["check"])

    assert rc == 0
    assert calls["load_required"] is True
    assert calls["validated_ledger"] is current_ledger
    stdout = capsys.readouterr().out
    assert "治理台账校验通过" in stdout
    assert '"matched": 7' in stdout


@pytest.mark.parametrize(
    ("mode", "handler_name", "expected_required"),
    [
        ("migrate-inline-facts", "refresh_migrate_inline_facts", False),
        ("scan-startup-baseline", "refresh_scan_startup_baseline", False),
        ("refresh-auto-fields", "refresh_auto_fields", True),
    ],
)
def test_refresh_command_dispatches_expected_mode(
    monkeypatch, capsys, mode: str, handler_name: str, expected_required: bool
):
    module = _import_sync_debt_ledger()
    calls = {}
    current_ledger = {"kind": "current"}
    next_ledger = {"updated_at": "2026-04-10T01:02:03+08:00"}

    def fake_load_ledger(required: bool = False):
        calls["load_required"] = required
        return current_ledger

    monkeypatch.setattr(module, "load_ledger_unvalidated", fake_load_ledger)
    monkeypatch.setattr(module, "now_shanghai_iso", lambda: "2026-04-10T01:02:03+08:00")

    def _unexpected(_ledger):
        raise AssertionError("调用了错误的刷新分支")

    monkeypatch.setattr(module, "refresh_migrate_inline_facts", _unexpected)
    monkeypatch.setattr(module, "refresh_scan_startup_baseline", _unexpected)
    monkeypatch.setattr(module, "refresh_auto_fields", _unexpected)

    def _selected(ledger):
        calls["handler_name"] = handler_name
        calls["handler_ledger"] = ledger
        return next_ledger

    monkeypatch.setattr(module, handler_name, _selected)
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["refresh", "--mode", mode])

    assert rc == 0
    assert calls["handler_name"] == handler_name
    assert calls["handler_ledger"] is current_ledger
    assert calls["load_required"] is expected_required
    assert calls["saved_ledger"] is next_ledger
    stdout = capsys.readouterr().out
    assert "治理台账已刷新" in stdout
    assert f'"mode": "{mode}"' in stdout


def test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger(monkeypatch, capsys):
    module = _import_sync_debt_ledger()
    calls = {}
    current_ledger = {"kind": "current"}
    next_ledger = {"updated_at": "2026-04-10T01:02:03+08:00"}

    def fake_load_ledger(required: bool = False):
        calls["load_required"] = required
        return current_ledger

    def fake_refresh_auto_fields(ledger):
        calls["refreshed_ledger"] = ledger
        return next_ledger

    monkeypatch.setattr(module, "load_ledger_unvalidated", fake_load_ledger)
    monkeypatch.setattr(
        module,
        "validate_ledger_against_current_scan",
        lambda _ledger: (_ for _ in ()).throw(AssertionError("refresh-auto-fields 不应先做当前扫描校验")),
    )
    monkeypatch.setattr(module, "refresh_auto_fields", fake_refresh_auto_fields)
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["refresh", "--mode", "refresh-auto-fields"])

    assert rc == 0
    assert calls["load_required"] is True
    assert calls["refreshed_ledger"] is current_ledger
    assert calls["saved_ledger"] is next_ledger
    stdout = capsys.readouterr().out
    assert "治理台账已刷新" in stdout
    assert '"mode": "refresh-auto-fields"' in stdout


def test_refresh_auto_fields_rejects_silent_entry_when_except_ordinal_drifted(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:web-bootstrap-factory-_open_db-42cf3c7f221e",
                    "path": "web/bootstrap/factory.py",
                    "symbol": "_open_db",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:42cf3c7f221e2bcafa3ca2f57a514825d0645f89",
                    "handler_context_hash": "sha1:ctx-stable",
                    "except_ordinal": 7,
                    "line_start": 346,
                    "line_end": 353,
                    "fallback_kind": "cleanup_best_effort",
                    "scope_tag": "startup_guard",
                    "source": "baseline_scan",
                }
            ],
        },
    }
    scan_entry = {
        "id": "fallback:web-bootstrap-factory-_open_db-42cf3c7f221e",
        "path": "web/bootstrap/factory.py",
        "symbol": "_open_db",
        "handler_fingerprint": "sha1:42cf3c7f221e2bcafa3ca2f57a514825d0645f89",
        "handler_context_hash": "sha1:ctx-stable",
        "except_ordinal": 8,
        "line_start": 375,
        "line_end": 382,
        "fallback_kind": "cleanup_best_effort",
        "scope_tag": "startup_guard",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(
        refresh_globals,
        "build_silent_entry",
        lambda scan_item, source, existing=None: {
            **dict(existing or {}),
            **dict(scan_item),
            "id": (existing or {}).get("id", scan_item.get("id")),
            "source": source,
        },
    )
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    with pytest.raises(module.QualityGateError, match="except ordinal changed|handler_context_hash changed"):
        module.refresh_auto_fields(ledger)


def test_refresh_auto_fields_realigns_silent_entry_when_handler_fingerprint_changed(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:web-bootstrap-launcher-contracts-read_runtime_contract-old",
                    "path": "web/bootstrap/launcher_contracts.py",
                    "symbol": "read_runtime_contract",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:old-fingerprint",
                    "handler_context_hash": "sha1:ctx-contract",
                    "except_ordinal": 1,
                    "line_start": 388,
                    "line_end": 389,
                    "fallback_kind": "silent_default_fallback",
                    "source": "baseline_scan",
                }
            ],
        },
        "accepted_risks": [
            {
                "id": "risk:launcher-runtime-lock-contract-win7",
                "entry_ids": ["fallback:web-bootstrap-launcher-contracts-read_runtime_contract-old"],
                "owner": "techdebt",
                "reason": "Win7 现场复核前保留",
                "review_after": "2026-05-31",
                "exit_condition": "Win7 现场复核后删除。",
            }
        ],
    }
    scan_entry = {
        "id": "fallback:web-bootstrap-launcher-contracts-read_runtime_contract-new",
        "path": "web/bootstrap/launcher_contracts.py",
        "symbol": "read_runtime_contract",
        "handler_fingerprint": "sha1:new-fingerprint",
        "handler_context_hash": "sha1:ctx-contract",
        "except_ordinal": 1,
        "line_start": 390,
        "line_end": 392,
        "fallback_kind": "observable_degrade",
    }
    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    refreshed = module.refresh_auto_fields(ledger)
    entry = refreshed["silent_fallback"]["entries"][0]

    assert entry["id"] == "fallback:web-bootstrap-launcher-contracts-read_runtime_contract-new"
    assert entry["handler_fingerprint"] == "sha1:new-fingerprint"
    assert entry["fallback_kind"] == "observable_degrade"
    assert entry["owner"] == "SP03"
    assert entry["realigned_from"] == "fallback:web-bootstrap-launcher-contracts-read_runtime_contract-old"
    assert "kind silent_default_fallback->observable_degrade" in entry["realignment_reason"]
    assert refreshed["accepted_risks"][0]["entry_ids"] == [
        "fallback:web-bootstrap-launcher-contracts-read_runtime_contract-new"
    ]


def test_refresh_auto_fields_rejects_silent_entries_when_earlier_handler_left_scan(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:registry-query-old",
                    "path": "web/bootstrap/launcher_paths.py",
                    "symbol": "read_shared_data_root_from_registry",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:old-query",
                    "handler_context_hash": "sha1:ctx-query",
                    "except_ordinal": 2,
                    "line_start": 69,
                    "line_end": 70,
                    "fallback_kind": "silent_default_fallback",
                    "source": "baseline_scan",
                },
                {
                    "id": "fallback:registry-close-old",
                    "path": "web/bootstrap/launcher_paths.py",
                    "symbol": "read_shared_data_root_from_registry",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:old-close",
                    "handler_context_hash": "sha1:ctx-close",
                    "except_ordinal": 3,
                    "line_start": 74,
                    "line_end": 75,
                    "fallback_kind": "silent_swallow",
                    "source": "baseline_scan",
                },
            ],
        },
        "accepted_risks": [
            {
                "id": "risk:launcher-runtime-root-owner-win7",
                "entry_ids": ["fallback:registry-query-old", "fallback:registry-close-old"],
                "owner": "techdebt",
                "reason": "Win7 现场复核前保留",
                "review_after": "2026-05-31",
                "exit_condition": "Win7 现场复核后删除。",
            }
        ],
    }
    scan_entries = [
        {
            "id": "fallback:registry-query-new",
            "path": "web/bootstrap/launcher_paths.py",
            "symbol": "read_shared_data_root_from_registry",
            "handler_fingerprint": "sha1:new-query",
            "handler_context_hash": "sha1:ctx-query",
            "except_ordinal": 1,
            "line_start": 73,
            "line_end": 75,
            "fallback_kind": "observable_degrade",
        },
        {
            "id": "fallback:registry-close-new",
            "path": "web/bootstrap/launcher_paths.py",
            "symbol": "read_shared_data_root_from_registry",
            "handler_fingerprint": "sha1:new-close",
            "handler_context_hash": "sha1:ctx-close",
            "except_ordinal": 2,
            "line_start": 79,
            "line_end": 80,
            "fallback_kind": "observable_degrade",
        },
    ]

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: scan_entries)
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    with pytest.raises(module.QualityGateError, match="except ordinal changed|handler_context_hash changed"):
        module.refresh_auto_fields(ledger)


def test_refresh_auto_fields_realigns_silent_entries_when_symbol_was_split_for_state_result(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:pid-exists-old",
                    "path": "web/bootstrap/launcher_processes.py",
                    "symbol": "_pid_exists",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:old-pid",
                    "handler_context_hash": "sha1:ctx-pid",
                    "except_ordinal": 1,
                    "line_start": 15,
                    "line_end": 16,
                    "fallback_kind": "silent_default_fallback",
                    "source": "baseline_scan",
                }
            ],
        },
        "accepted_risks": [
            {
                "id": "risk:launcher-process-probe-kill-win7",
                "entry_ids": ["fallback:pid-exists-old"],
                "owner": "techdebt",
                "reason": "Win7 现场复核前保留",
                "review_after": "2026-05-31",
                "exit_condition": "Win7 现场复核后删除。",
            }
        ],
    }
    scan_entry = {
        "id": "fallback:pid-state-new",
        "path": "web/bootstrap/launcher_processes.py",
        "symbol": "_pid_state",
        "handler_fingerprint": "sha1:new-pid",
        "handler_context_hash": "sha1:ctx-pid",
        "except_ordinal": 1,
        "line_start": 27,
        "line_end": 29,
        "fallback_kind": "observable_degrade",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    refreshed = module.refresh_auto_fields(ledger)

    assert refreshed["silent_fallback"]["entries"][0]["id"] == "fallback:pid-state-new"
    assert refreshed["silent_fallback"]["entries"][0]["symbol"] == "_pid_state"
    assert refreshed["silent_fallback"]["entries"][0]["realigned_from"] == "fallback:pid-exists-old"
    assert refreshed["accepted_risks"][0]["entry_ids"] == ["fallback:pid-state-new"]


def test_refresh_auto_fields_rejects_silent_realign_when_context_hash_changed(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:contract-old",
                    "path": "web/bootstrap/launcher_contracts.py",
                    "symbol": "read_runtime_contract",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:old-contract",
                    "handler_context_hash": "sha1:ctx-old",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 12,
                    "fallback_kind": "silent_default_fallback",
                    "source": "baseline_scan",
                }
            ],
        },
    }
    scan_entry = {
        "id": "fallback:contract-new",
        "path": "web/bootstrap/launcher_contracts.py",
        "symbol": "read_runtime_contract",
        "handler_fingerprint": "sha1:new-contract",
        "handler_context_hash": "sha1:ctx-new",
        "except_ordinal": 1,
        "line_start": 20,
        "line_end": 22,
        "fallback_kind": "observable_degrade",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    with pytest.raises(module.QualityGateError, match="handler_context_hash changed"):
        module.refresh_auto_fields(ledger)


def test_refresh_auto_fields_rejects_same_id_when_context_hash_changed(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:runtime-probe-same",
                    "path": "web/bootstrap/runtime_probe.py",
                    "symbol": "probe_health_result",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:same-fingerprint",
                    "handler_context_hash": "sha1:ctx-old",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 12,
                    "fallback_kind": "observable_degrade",
                    "source": "baseline_scan",
                }
            ],
        },
        "accepted_risks": [
            {
                "id": "risk:runtime-probe-win7",
                "entry_ids": ["fallback:runtime-probe-same"],
                "owner": "techdebt",
                "reason": "Win7 现场复核前保留",
                "review_after": "2026-05-31",
                "exit_condition": "Win7 现场复核后删除。",
            }
        ],
    }
    scan_entry = {
        "id": "fallback:runtime-probe-same",
        "path": "web/bootstrap/runtime_probe.py",
        "symbol": "probe_health_result",
        "handler_fingerprint": "sha1:same-fingerprint",
        "handler_context_hash": "sha1:ctx-new",
        "except_ordinal": 1,
        "line_start": 20,
        "line_end": 22,
        "fallback_kind": "observable_degrade",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    with pytest.raises(module.QualityGateError, match="handler_context_hash changed"):
        module.refresh_auto_fields(ledger)


def test_refresh_auto_fields_rejects_silent_kind_regression(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:runtime-probe-old",
                    "path": "web/bootstrap/runtime_probe.py",
                    "symbol": "probe_health",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:old-probe",
                    "handler_context_hash": "sha1:ctx-probe",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 12,
                    "fallback_kind": "observable_degrade",
                    "source": "baseline_scan",
                }
            ],
        },
    }
    scan_entry = {
        "id": "fallback:runtime-probe-new",
        "path": "web/bootstrap/runtime_probe.py",
        "symbol": "probe_health",
        "handler_fingerprint": "sha1:new-probe",
        "handler_context_hash": "sha1:ctx-probe",
        "except_ordinal": 1,
        "line_start": 20,
        "line_end": 22,
        "fallback_kind": "silent_swallow",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    with pytest.raises(module.QualityGateError, match="fallback kind transition"):
        module.refresh_auto_fields(ledger)


def test_refresh_auto_fields_allows_legacy_non_startup_cleanup_reclassify(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:legacy-backup-cleanup",
                    "path": "core/infrastructure/backup.py",
                    "symbol": "cleanup_old_backups",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "legacy architecture counter",
                    "handler_fingerprint": "sha1:old-cleanup",
                    "handler_context_hash": "sha1:ctx-cleanup",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 12,
                    "fallback_kind": "silent_swallow",
                    "source": "migrated_from_architecture_fitness_counter",
                }
            ],
        },
    }
    scan_entry = {
        "id": "fallback:legacy-backup-cleanup-new",
        "path": "core/infrastructure/backup.py",
        "symbol": "cleanup_old_backups",
        "handler_fingerprint": "sha1:new-cleanup",
        "handler_context_hash": "sha1:ctx-cleanup",
        "except_ordinal": 1,
        "line_start": 20,
        "line_end": 22,
        "fallback_kind": "cleanup_best_effort",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    refreshed = module.refresh_auto_fields(ledger)

    entry = refreshed["silent_fallback"]["entries"][0]
    assert entry["id"] == "fallback:legacy-backup-cleanup-new"
    assert entry["realigned_from"] == "fallback:legacy-backup-cleanup"
    assert "legacy architecture silent entry reclassified" in entry["realignment_reason"]


def test_refresh_auto_fields_rejects_startup_cleanup_reclassify(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:legacy-startup-cleanup",
                    "path": "web/bootstrap/launcher_stop.py",
                    "symbol": "_wait_for_runtime_stop",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "legacy architecture counter",
                    "handler_fingerprint": "sha1:old-startup-cleanup",
                    "handler_context_hash": "sha1:ctx-startup-cleanup",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 12,
                    "fallback_kind": "silent_swallow",
                    "source": "migrated_from_architecture_fitness_counter",
                }
            ],
        },
    }
    scan_entry = {
        "id": "fallback:legacy-startup-cleanup-new",
        "path": "web/bootstrap/launcher_stop.py",
        "symbol": "_wait_for_runtime_stop",
        "handler_fingerprint": "sha1:new-startup-cleanup",
        "handler_context_hash": "sha1:ctx-startup-cleanup",
        "except_ordinal": 1,
        "line_start": 20,
        "line_end": 22,
        "fallback_kind": "cleanup_best_effort",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    with pytest.raises(module.QualityGateError, match="fallback kind transition"):
        module.refresh_auto_fields(ledger)


def test_refresh_auto_fields_prunes_resolved_silent_entry_and_risk_reference(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:chrome-log-old",
                    "path": "web/bootstrap/launcher_stop.py",
                    "symbol": "_log_chrome_stop_failure",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:old-log",
                    "handler_context_hash": "sha1:ctx-log",
                    "except_ordinal": 1,
                    "line_start": 207,
                    "line_end": 208,
                    "fallback_kind": "silent_swallow",
                    "source": "baseline_scan",
                },
                {
                    "id": "fallback:still-open",
                    "path": "web/bootstrap/launcher_stop.py",
                    "symbol": "_request_runtime_shutdown",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "keep tracking",
                    "last_verified_at": "2026-04-15T08:26:05+08:00",
                    "notes": "startup baseline",
                    "handler_fingerprint": "sha1:old-request",
                    "handler_context_hash": "sha1:ctx-request",
                    "except_ordinal": 1,
                    "line_start": 60,
                    "line_end": 61,
                    "fallback_kind": "silent_default_fallback",
                    "source": "baseline_scan",
                },
            ],
        },
        "accepted_risks": [
            {
                "id": "risk:launcher-process-probe-kill-win7",
                "entry_ids": ["fallback:chrome-log-old", "fallback:still-open"],
                "owner": "techdebt",
                "reason": "Win7 现场复核前保留",
                "review_after": "2026-05-31",
                "exit_condition": "Win7 现场复核后删除。",
            }
        ],
    }
    scan_entry = {
        "id": "fallback:still-open-new",
        "path": "web/bootstrap/launcher_stop.py",
        "symbol": "_request_runtime_shutdown",
        "handler_fingerprint": "sha1:new-request",
        "handler_context_hash": "sha1:ctx-request",
        "except_ordinal": 1,
        "line_start": 72,
        "line_end": 74,
        "fallback_kind": "observable_degrade",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    refreshed = module.refresh_auto_fields(ledger)

    assert [entry["id"] for entry in refreshed["silent_fallback"]["entries"]] == ["fallback:still-open-new"]
    assert refreshed["accepted_risks"][0]["entry_ids"] == ["fallback:still-open-new"]


def test_refresh_auto_fields_prunes_fixed_silent_entry_when_scan_no_longer_matches(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["core/infrastructure/*.py"],
            "entries": [
                {
                    "id": "fallback:fixed-old",
                    "path": "core/infrastructure/database.py",
                    "symbol": "ensure_schema",
                    "status": "fixed",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "fixed entry should be pruned",
                    "last_verified_at": "2026-04-30T21:27:43+08:00",
                    "notes": "已修复",
                    "handler_fingerprint": "sha1:old-fixed",
                    "handler_context_hash": "sha1:ctx-fixed",
                    "except_ordinal": 3,
                    "line_start": 136,
                    "line_end": 137,
                    "fallback_kind": "silent_swallow",
                    "source": "migrated_from_architecture_fitness_counter",
                }
            ],
        },
        "accepted_risks": [],
    }
    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    refreshed = module.refresh_auto_fields(ledger)

    assert refreshed["silent_fallback"]["entries"] == []
    assert refreshed["accepted_risks"] == []


def test_refresh_auto_fields_rejects_fixed_silent_entry_still_in_scan(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["core/infrastructure/*.py"],
            "entries": [
                {
                    "id": "fallback:fixed-old",
                    "path": "core/infrastructure/database.py",
                    "symbol": "ensure_schema",
                    "status": "fixed",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "fixed entry should not be current",
                    "last_verified_at": "2026-04-30T21:27:43+08:00",
                    "notes": "已修复",
                    "handler_fingerprint": "sha1:old-fixed",
                    "handler_context_hash": "sha1:ctx-fixed",
                    "except_ordinal": 3,
                    "line_start": 136,
                    "line_end": 137,
                    "fallback_kind": "silent_swallow",
                    "source": "migrated_from_architecture_fitness_counter",
                }
            ],
        },
        "accepted_risks": [],
    }
    scan_entry = {
        "id": "fallback:current-handler",
        "path": "core/infrastructure/database.py",
        "symbol": "ensure_schema",
        "handler_fingerprint": "sha1:old-fixed",
        "handler_context_hash": "sha1:ctx-fixed",
        "except_ordinal": 1,
        "line_start": 90,
        "line_end": 91,
        "fallback_kind": "silent_swallow",
    }

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])

    with pytest.raises(module.QualityGateError, match="不能标记为 fixed"):
        module.refresh_auto_fields(ledger)


def test_check_rejects_fixed_silent_entry_still_in_scan(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:fixed-startup",
                    "path": "web/bootstrap/launcher_stop.py",
                    "symbol": "_request_runtime_shutdown",
                    "status": "fixed",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "fixed entry should not be current",
                    "last_verified_at": "2026-04-30T21:27:43+08:00",
                    "notes": "已修复",
                    "handler_fingerprint": "sha1:fixed-startup",
                    "handler_context_hash": "sha1:ctx-fixed-startup",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 11,
                    "fallback_kind": "observable_degrade",
                    "source": "baseline_scan",
                    "scope_tag": "startup_guard",
                }
            ],
        },
        "accepted_risks": [],
    }
    scan_entry = {
        "id": "fallback:fixed-startup",
        "path": "web/bootstrap/launcher_stop.py",
        "symbol": "_request_runtime_shutdown",
        "handler_fingerprint": "sha1:fixed-startup",
        "handler_context_hash": "sha1:ctx-fixed-startup",
        "except_ordinal": 1,
        "line_start": 10,
        "line_end": 11,
        "fallback_kind": "observable_degrade",
        "scope_tag": "startup_guard",
    }

    check_globals = module.validate_ledger_against_current_scan.__globals__
    monkeypatch.setitem(check_globals, "validate_ledger", lambda _ledger: None)
    monkeypatch.setitem(check_globals, "validate_startup_samples", lambda: {"matched": 0})
    monkeypatch.setitem(check_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])

    with pytest.raises(module.QualityGateError, match="不能标记为 fixed"):
        module.validate_ledger_against_current_scan(ledger)


def test_scan_startup_baseline_rejects_fixed_silent_entry_still_in_scan(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:fixed-startup",
                    "path": "web/bootstrap/launcher_stop.py",
                    "symbol": "_request_runtime_shutdown",
                    "status": "fixed",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "fixed entry should not be current",
                    "last_verified_at": "2026-04-30T21:27:43+08:00",
                    "notes": "已修复",
                    "handler_fingerprint": "sha1:fixed-startup",
                    "handler_context_hash": "sha1:ctx-fixed-startup",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 11,
                    "fallback_kind": "observable_degrade",
                    "source": "baseline_scan",
                    "scope_tag": "startup_guard",
                }
            ],
        },
        "accepted_risks": [],
    }
    scan_entry = {
        "id": "fallback:fixed-startup",
        "path": "web/bootstrap/launcher_stop.py",
        "symbol": "_request_runtime_shutdown",
        "handler_fingerprint": "sha1:fixed-startup",
        "handler_context_hash": "sha1:ctx-fixed-startup",
        "except_ordinal": 1,
        "line_start": 10,
        "line_end": 11,
        "fallback_kind": "observable_degrade",
        "scope_tag": "startup_guard",
    }

    refresh_globals = module.refresh_scan_startup_baseline.__globals__
    monkeypatch.setitem(refresh_globals, "validate_startup_samples", lambda: {"matched": 0})
    monkeypatch.setitem(refresh_globals, "collect_startup_scope_files", lambda: ["web/bootstrap/launcher_stop.py"])
    monkeypatch.setitem(refresh_globals, "scan_oversize_entries", lambda _paths: [])
    monkeypatch.setitem(refresh_globals, "scan_complexity_entries", lambda _paths: [])
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])

    with pytest.raises(module.QualityGateError, match="不能标记为 fixed"):
        module.refresh_scan_startup_baseline(ledger)


def test_migrate_inline_facts_rejects_fixed_silent_entry_still_in_scan(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["core/infrastructure/*.py"],
            "entries": [
                {
                    "id": "fallback:fixed-old",
                    "path": "core/infrastructure/database.py",
                    "symbol": "ensure_schema",
                    "status": "fixed",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "fixed entry should not be current",
                    "last_verified_at": "2026-04-30T21:27:43+08:00",
                    "notes": "已修复",
                    "handler_fingerprint": "sha1:fixed-old",
                    "handler_context_hash": "sha1:ctx-fixed-old",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 11,
                    "fallback_kind": "silent_swallow",
                    "source": "migrated_from_architecture_fitness_counter",
                }
            ],
        },
        "accepted_risks": [],
    }
    scan_entry = {
        "id": "fallback:fixed-old",
        "path": "core/infrastructure/database.py",
        "symbol": "ensure_schema",
        "handler_fingerprint": "sha1:fixed-old",
        "handler_context_hash": "sha1:ctx-fixed-old",
        "except_ordinal": 1,
        "line_start": 10,
        "line_end": 11,
        "fallback_kind": "silent_swallow",
        "legacy_swallow_hit": True,
    }

    refresh_globals = module.refresh_migrate_inline_facts.__globals__
    monkeypatch.setitem(
        refresh_globals,
        "load_sp02_facts_snapshot",
        lambda: {
            "legacy_inline_facts": {
                "oversize_allowlist": [],
                "complexity_allowlist": [],
                "silent_fallback_counter": {"core/infrastructure/database.py:ensure_schema": 1},
            }
        },
    )
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])

    with pytest.raises(module.QualityGateError, match="不能标记为 fixed"):
        module.refresh_migrate_inline_facts(ledger)


def test_refresh_auto_fields_prunes_resolved_complexity_entry(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [
            {
                "id": "complexity:web-bootstrap-plugins-_status_degradation_collector",
                "path": "web/bootstrap/plugins.py",
                "symbol": "_status_degradation_collector",
                "status": "open",
                "owner": "SP03",
                "batch": "SP03",
                "exit_condition": "复杂度回落到 15 及以下后移出白名单",
                "last_verified_at": "2026-04-09T23:35:44+08:00",
                "notes": "旧登记",
                "current_value": 16,
                "threshold": 15,
            }
        ],
        "silent_fallback": {"scope": ["web/bootstrap/**/*.py"], "entries": []},
        "accepted_risks": [],
    }

    def fake_complexity_scan_map(_paths, include_all=False):
        if include_all:
            return {
                "web/bootstrap/plugins.py:_status_degradation_collector": {
                    "path": "web/bootstrap/plugins.py",
                    "symbol": "_status_degradation_collector",
                    "current_value": 12,
                    "threshold": 15,
                }
            }
        return {}

    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "complexity_scan_map", fake_complexity_scan_map)
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    refreshed = module.refresh_auto_fields(ledger)

    assert refreshed["complexity_allowlist"] == []


def test_refresh_auto_fields_rejects_fixed_oversize_entry_still_over_limit(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [
            {
                "id": "oversize:sample-large",
                "path": "sample_large.py",
                "symbol": None,
                "status": "fixed",
                "owner": "SP03",
                "batch": "SP03",
                "exit_condition": "文件行数降到限制以下",
                "last_verified_at": "2026-04-30T21:27:43+08:00",
                "current_value": 999,
                "limit": 500,
            }
        ],
        "complexity_allowlist": [],
        "silent_fallback": {"scope": ["web/bootstrap/**/*.py"], "entries": []},
        "accepted_risks": [],
    }
    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "read_text_file", lambda _path: "\n".join(["x"] * 501))

    with pytest.raises(module.QualityGateError, match="不能标记为 fixed"):
        module.refresh_auto_fields(ledger)


def test_check_rejects_fixed_complexity_entry_still_over_threshold(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [
            {
                "id": "complexity:sample-too-complex",
                "path": "sample.py",
                "symbol": "too_complex",
                "status": "fixed",
                "owner": "SP03",
                "batch": "SP03",
                "exit_condition": "复杂度回落到阈值以下",
                "last_verified_at": "2026-04-30T21:27:43+08:00",
                "current_value": 16,
                "threshold": 15,
            }
        ],
        "silent_fallback": {"scope": ["web/bootstrap/**/*.py"], "entries": []},
        "accepted_risks": [],
    }

    check_globals = module.validate_ledger_against_current_scan.__globals__
    monkeypatch.setitem(check_globals, "validate_ledger", lambda _ledger: None)
    monkeypatch.setitem(check_globals, "validate_startup_samples", lambda: {"matched": 0})
    monkeypatch.setitem(
        check_globals,
        "complexity_scan_map",
        lambda _paths: {"sample.py:too_complex": {"path": "sample.py", "symbol": "too_complex", "current_value": 16}},
    )

    with pytest.raises(module.QualityGateError, match="不能标记为 fixed"):
        module.validate_ledger_against_current_scan(ledger)


def test_set_entry_fields_rejects_fixed_oversize_entry_still_over_limit(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [
            {
                "id": "oversize:sample-large",
                "path": "sample_large.py",
                "symbol": None,
                "status": "open",
                "owner": "SP03",
                "batch": "SP03",
                "exit_condition": "文件行数降到限制以下",
                "last_verified_at": "2026-04-30T21:27:43+08:00",
                "current_value": 999,
                "limit": 500,
            }
        ],
        "complexity_allowlist": [],
        "silent_fallback": {"scope": ["web/bootstrap/**/*.py"], "entries": []},
        "accepted_risks": [],
    }
    set_globals = module.set_entry_fields.__globals__
    monkeypatch.setitem(set_globals, "read_text_file", lambda _path: "\n".join(["x"] * 501))

    with pytest.raises(module.QualityGateError, match="不能标记为 fixed"):
        module.set_entry_fields(ledger, "oversize:sample-large", {"status": "fixed"})


def test_set_entry_fields_rejects_fixed_silent_entry_still_in_scan(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:fixed-startup",
                    "path": "web/bootstrap/launcher_stop.py",
                    "symbol": "_request_runtime_shutdown",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "去除静默吞异常，或改为可观测降级并从本分类移出",
                    "last_verified_at": "2026-04-30T21:27:43+08:00",
                    "notes": "启动链基线冻结",
                    "handler_fingerprint": "sha1:fixed-startup",
                    "handler_context_hash": "sha1:ctx-fixed-startup",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 11,
                    "fallback_kind": "observable_degrade",
                    "source": "baseline_scan",
                    "scope_tag": "startup_guard",
                }
            ],
        },
        "accepted_risks": [],
    }
    scan_entry = {
        "id": "fallback:fixed-startup",
        "path": "web/bootstrap/launcher_stop.py",
        "symbol": "_request_runtime_shutdown",
        "handler_fingerprint": "sha1:fixed-startup",
        "handler_context_hash": "sha1:ctx-fixed-startup",
        "except_ordinal": 1,
        "line_start": 10,
        "line_end": 11,
        "fallback_kind": "observable_degrade",
        "scope_tag": "startup_guard",
    }
    set_globals = module.set_entry_fields.__globals__
    monkeypatch.setitem(set_globals, "scan_silent_fallback_entries", lambda _paths: [scan_entry])

    with pytest.raises(module.QualityGateError, match="不能标记为 fixed"):
        module.set_entry_fields(ledger, "fallback:fixed-startup", {"status": "fixed"})


def test_refresh_auto_fields_rejects_auto_emptying_accepted_risk(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["core/infrastructure/*.py"],
            "entries": [
                {
                    "id": "fallback:fixed-old",
                    "path": "core/infrastructure/database.py",
                    "symbol": "ensure_schema",
                    "status": "fixed",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "fixed entry should be pruned",
                    "last_verified_at": "2026-04-30T21:27:43+08:00",
                    "notes": "已修复",
                    "handler_fingerprint": "sha1:old-fixed",
                    "handler_context_hash": "sha1:ctx-fixed",
                    "except_ordinal": 3,
                    "line_start": 136,
                    "line_end": 137,
                    "fallback_kind": "silent_swallow",
                    "source": "migrated_from_architecture_fitness_counter",
                }
            ],
        },
        "accepted_risks": [
            {
                "id": "risk:fixed-old",
                "entry_ids": ["fallback:fixed-old"],
                "owner": "techdebt",
                "reason": "旧风险",
                "review_after": "2026-05-31",
                "exit_condition": "fixed 后显式删除风险。",
            }
        ],
    }
    refresh_globals = module.refresh_auto_fields.__globals__
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [])
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    with pytest.raises(module.QualityGateError, match="显式 delete-risk"):
        module.refresh_auto_fields(ledger)


def test_scan_startup_baseline_rejects_auto_emptying_accepted_risk(monkeypatch):
    module = _import_quality_gate_support()
    ledger = {
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": "fallback:old-startup",
                    "path": "web/bootstrap/launcher_stop.py",
                    "symbol": "_request_runtime_shutdown",
                    "status": "open",
                    "owner": "SP03",
                    "batch": "SP03",
                    "exit_condition": "去除静默吞异常，或改为可观测降级并从本分类移出",
                    "last_verified_at": "2026-04-30T21:27:43+08:00",
                    "notes": "启动链基线冻结",
                    "handler_fingerprint": "sha1:old-startup",
                    "handler_context_hash": "sha1:ctx-old-startup",
                    "except_ordinal": 1,
                    "line_start": 10,
                    "line_end": 11,
                    "fallback_kind": "observable_degrade",
                    "source": "baseline_scan",
                    "scope_tag": "startup_guard",
                }
            ],
        },
        "accepted_risks": [
            {
                "id": "risk:old-startup",
                "entry_ids": ["fallback:old-startup"],
                "owner": "techdebt",
                "reason": "旧风险",
                "review_after": "2026-05-31",
                "exit_condition": "显式删除风险。",
            }
        ],
    }
    refresh_globals = module.refresh_scan_startup_baseline.__globals__
    monkeypatch.setitem(refresh_globals, "validate_startup_samples", lambda: {"matched": 0})
    monkeypatch.setitem(refresh_globals, "collect_startup_scope_files", lambda: ["web/bootstrap/launcher_stop.py"])
    monkeypatch.setitem(refresh_globals, "scan_oversize_entries", lambda _paths: [])
    monkeypatch.setitem(refresh_globals, "scan_complexity_entries", lambda _paths: [])
    monkeypatch.setitem(refresh_globals, "scan_silent_fallback_entries", lambda _paths: [])

    with pytest.raises(module.QualityGateError, match="显式 delete-risk"):
        module.refresh_scan_startup_baseline(ledger)


def test_set_entry_fields_command_updates_manual_fields(monkeypatch, capsys):
    module = _import_sync_debt_ledger()
    calls = {}
    current_ledger = {"kind": "current"}
    next_ledger = {"updated_at": "2026-04-10T02:03:04+08:00"}

    monkeypatch.setattr(module, "load_ledger", lambda required=True: current_ledger)

    def fake_set_entry_fields(ledger, entry_id: str, updates):
        calls["ledger"] = ledger
        calls["entry_id"] = entry_id
        calls["updates"] = dict(updates)
        return next_ledger

    monkeypatch.setattr(module, "set_entry_fields", fake_set_entry_fields)
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(
        [
            "set-entry-fields",
            "--id",
            "fallback:test-entry",
            "--owner",
            "alice",
            "--status",
            "in_progress",
            "--notes",
            "需要继续处理",
        ]
    )

    assert rc == 0
    assert calls["ledger"] is current_ledger
    assert calls["entry_id"] == "fallback:test-entry"
    assert calls["updates"] == {
        "owner": "alice",
        "batch": None,
        "status": "in_progress",
        "notes": "需要继续处理",
        "exit_condition": None,
    }
    assert calls["saved_ledger"] is next_ledger
    stdout = capsys.readouterr().out
    assert "主条目人工字段已更新" in stdout
    assert '"status": "in_progress"' in stdout


def test_set_entry_fields_rejects_invalid_status_choice():
    module = _import_sync_debt_ledger()

    with pytest.raises(SystemExit):
        module.main(["set-entry-fields", "--id", "fallback:test-entry", "--status", "anything"])


def test_upsert_risk_command_dispatches(monkeypatch, capsys):
    module = _import_sync_debt_ledger()
    calls = {}
    current_ledger = {"kind": "current"}
    next_ledger = {"updated_at": "2026-04-10T03:04:05+08:00"}

    monkeypatch.setattr(module, "load_ledger", lambda required=True: current_ledger)

    def fake_upsert_risk(ledger, risk_id, entry_ids, owner, reason, review_after, exit_condition, notes=None):
        calls["args"] = {
            "ledger": ledger,
            "risk_id": risk_id,
            "entry_ids": list(entry_ids),
            "owner": owner,
            "reason": reason,
            "review_after": review_after,
            "exit_condition": exit_condition,
            "notes": notes,
        }
        return next_ledger

    monkeypatch.setattr(module, "upsert_risk", fake_upsert_risk)
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(
        [
            "upsert-risk",
            "--id",
            "risk:test",
            "--entry-id",
            "fallback:test-entry",
            "--entry-id",
            "complexity:test-entry",
            "--owner",
            "alice",
            "--reason",
            "暂缓处理",
            "--review-after",
            "2026-05-01",
            "--exit-condition",
            "相关治理完成",
            "--notes",
            "记录在案",
        ]
    )

    assert rc == 0
    assert calls["args"] == {
        "ledger": current_ledger,
        "risk_id": "risk:test",
        "entry_ids": ["fallback:test-entry", "complexity:test-entry"],
        "owner": "alice",
        "reason": "暂缓处理",
        "review_after": "2026-05-01",
        "exit_condition": "相关治理完成",
        "notes": "记录在案",
    }
    assert calls["saved_ledger"] is next_ledger
    stdout = capsys.readouterr().out
    assert "accepted_risks 已更新" in stdout
    assert '"id": "risk:test"' in stdout


def test_delete_risk_command_dispatches(monkeypatch, capsys):
    module = _import_sync_debt_ledger()
    calls = {}
    current_ledger = {"kind": "current"}
    next_ledger = {"updated_at": "2026-04-10T04:05:06+08:00"}

    monkeypatch.setattr(module, "load_ledger", lambda required=True: current_ledger)

    def fake_delete_risk(ledger, risk_id: str):
        calls["ledger"] = ledger
        calls["risk_id"] = risk_id
        return next_ledger

    monkeypatch.setattr(module, "delete_risk", fake_delete_risk)
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["delete-risk", "--id", "risk:test"])

    assert rc == 0
    assert calls["ledger"] is current_ledger
    assert calls["risk_id"] == "risk:test"
    assert calls["saved_ledger"] is next_ledger
    stdout = capsys.readouterr().out
    assert "accepted_risks 已删除" in stdout
    assert '"id": "risk:test"' in stdout


def test_import_test_debt_baseline_command_imports_seed_entries(monkeypatch, tmp_path: Path, capsys):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "debt_baseline.md"
    _write_baseline(baseline_path, _baseline_payload())
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "current_git_head_sha", lambda: VERIFIED_SHA)
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha=VERIFIED_SHA))
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 0
    saved = calls["saved_ledger"]
    assert saved["schema_version"] == 2
    assert saved["test_debt"]["ratchet"] == {"max_registered_xfail": 5}
    assert [entry["nodeid"] for entry in saved["test_debt"]["entries"]] == sorted(P0_TEST_DEBT_NODEIDS)
    assert {entry["mode"] for entry in saved["test_debt"]["entries"]} == {"xfail"}
    assert all(entry["reason"] and entry["last_verified_at"] for entry in saved["test_debt"]["entries"])
    assert all(entry["debt_family"] == "operator_machine_normalization_contract_drift" for entry in saved["test_debt"]["entries"])
    stdout = capsys.readouterr().out
    assert "测试债务 baseline 已导入治理台账" in stdout
    assert f'"baseline_head_sha": "{BASELINE_SHA}"' in stdout
    assert f'"verified_head_sha": "{VERIFIED_SHA}"' in stdout


def test_importable_baseline_contract_rejects_zero_candidate_current_proof(tmp_path: Path):
    registry = _import_test_debt_registry()
    baseline_path = tmp_path / "zero_candidate_baseline.md"
    _write_baseline(baseline_path, _zero_candidate_payload())

    with pytest.raises(registry.QualityGateError, match="0 候选"):
        registry.load_full_test_debt_baseline(str(baseline_path))


@pytest.mark.parametrize(
    ("payload_update", "expected_message"),
    [
        ({"schema_version": 999}, "schema_version"),
        ({"schema_version": "2"}, "schema_version"),
        ({"baseline_kind": "raw_before_isolation"}, "baseline_kind"),
        ({"importable": False}, "importable"),
        ({"importable": "false"}, "importable"),
        ({"importable": 1}, "importable"),
        ({"exitstatus": 4}, "pytest_exitstatus"),
        (
            {
                "reports": [
                    {
                        "nodeid": P0_TEST_DEBT_NODEIDS[0],
                        "when": "call",
                        "outcome": "failed",
                        "duration": 0.0,
                        "longrepr": "[XPASS(strict)] test-debt:sample",
                        "xfail_marker_present": True,
                        "xfail_marker_reason": "test-debt:sample: 旧测试合同尚未更新",
                        "xfail_marker_strict": True,
                        "xfail_marker_run": True,
                        "wasxfail_reason": "",
                        "strict_xpass": True,
                    }
                ],
            },
            "xfail_signal",
        ),
        (
            {
                "reports": [
                    {
                        "nodeid": P0_TEST_DEBT_NODEIDS[0],
                        "when": "call",
                        "outcome": "failed",
                        "duration": 0.0,
                        "longrepr": "[XPASS(strict)] test-debt:sample",
                        "xfail_marker_present": True,
                        "xfail_marker_reason": "test-debt:sample: 旧测试合同尚未更新",
                        "xfail_marker_strict": True,
                        "xfail_marker_run": True,
                        "wasxfail_reason": "",
                    }
                ],
            },
            "reports[0] 缺少字段 strict_xpass",
        ),
        (
            {
                "reports": [
                    {
                        "nodeid": "tests/test_hidden_xfail.py::test_hidden_xfail",
                        "when": "call",
                        "outcome": "skipped",
                        "duration": 0.0,
                        "longrepr": "",
                        "xfail_marker_present": True,
                        "xfail_marker_reason": "test-debt:hidden: 不允许隐藏登记",
                        "xfail_marker_strict": True,
                        "xfail_marker_run": True,
                        "wasxfail_reason": "test-debt:hidden: 不允许隐藏登记",
                        "strict_xpass": False,
                    },
                    {
                        "nodeid": P0_TEST_DEBT_NODEIDS[0],
                        "when": "call",
                        "outcome": "failed",
                        "duration": 0.0,
                        "longrepr": "known candidate",
                        "xfail_marker_present": False,
                        "xfail_marker_reason": "",
                        "xfail_marker_strict": False,
                        "xfail_marker_run": False,
                        "wasxfail_reason": "",
                        "strict_xpass": False,
                    },
                ],
            },
            "xfail_signal",
        ),
    ],
)
def test_import_test_debt_baseline_command_rejects_invalid_baseline(
    monkeypatch, tmp_path: Path, capsys, payload_update: dict, expected_message: str
):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "bad_baseline.md"
    _write_baseline(baseline_path, _baseline_payload(**payload_update))
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "current_git_head_sha", lambda: VERIFIED_SHA)
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha=VERIFIED_SHA))
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert expected_message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("payload_mutator", "expected_message"),
    [
        (lambda payload: payload.pop("schema_version"), "schema_version"),
        (lambda payload: payload["classifications"].pop("candidate_test_debt"), "classifications"),
        (lambda payload: payload["classifications"].__setitem__("candidate_test_debt", [""]), "candidate_test_debt"),
        (lambda payload: payload["summary"]["classification_counts"].__setitem__("candidate_test_debt", "5"), "candidate_test_debt"),
        (lambda payload: payload["summary"].__setitem__("failed_nodeid_count", "5"), "failed_nodeid_count"),
        (lambda payload: payload.__setitem__("collected_nodeids", "not-a-list"), "collected_nodeids"),
        (lambda payload: payload.__setitem__("collection_errors", "not-a-list"), "collection_errors"),
        (lambda payload: payload.__setitem__("reports", "not-a-list"), "reports"),
        (lambda payload: payload.__setitem__("worktree_clean_before", False), "worktree_clean_before"),
        (lambda payload: payload.pop("head_sha"), "head_sha"),
        (lambda payload: payload.__setitem__("head_sha", ""), "head_sha"),
        (lambda payload: payload.__setitem__("head_sha", "abc"), "head_sha"),
    ],
)
def test_import_test_debt_baseline_command_rejects_malformed_machine_contract(
    monkeypatch, tmp_path: Path, capsys, payload_mutator, expected_message: str
):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "malformed_baseline.md"
    payload = _baseline_payload()
    payload_mutator(payload)
    _write_baseline(baseline_path, payload)
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha=VERIFIED_SHA))
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert expected_message in capsys.readouterr().err


def test_import_test_debt_baseline_command_rejects_blocked_classifications(monkeypatch, tmp_path: Path, capsys):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "blocked_baseline.md"
    payload = _baseline_payload()
    payload["classifications"]["required_or_quality_gate_self_failure"] = ["tests/test_run_quality_gate.py::test_self"]
    payload["summary"]["classification_counts"]["required_or_quality_gate_self_failure"] = 1
    payload["summary"]["failed_nodeid_count"] = 6
    _write_baseline(baseline_path, payload)
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "current_git_head_sha", lambda: VERIFIED_SHA)
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha=VERIFIED_SHA))
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert "required_or_quality_gate_self_failure" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("payload_mutator", "expected_message"),
    [
        (
            lambda payload: payload["classifications"].__setitem__(
                "required_or_quality_gate_self_failure",
                ["tests/test_run_quality_gate.py::test_self"],
            ),
            "required_or_quality_gate_self_failure",
        ),
        (
            lambda payload: payload["classifications"].__setitem__(
                "main_style_isolation_candidate",
                ["tests/regression_polluted.py::regression_polluted"],
            ),
            "main_style_isolation_candidate",
        ),
        (
            lambda payload: payload.__setitem__(
                "collection_errors",
                [{"nodeid": "tests/test_collect_error.py", "outcome": "failed", "longrepr": "collect boom"}],
            ),
            "collection_error_count",
        ),
    ],
)
def test_import_test_debt_baseline_command_rejects_actual_blocker_lists_even_when_counts_are_zero(
    monkeypatch, tmp_path: Path, capsys, payload_mutator, expected_message: str
):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "inconsistent_blockers.md"
    payload = _baseline_payload()
    payload_mutator(payload)
    _write_baseline(baseline_path, payload)
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha=VERIFIED_SHA))
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert expected_message in capsys.readouterr().err


def test_import_test_debt_baseline_command_rejects_unknown_candidate_nodeid(monkeypatch, tmp_path: Path, capsys):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "unknown_nodeid_baseline.md"
    payload = _baseline_payload()
    payload["classifications"]["candidate_test_debt"] = ["tests/test_unknown.py::test_unknown"]
    payload["collected_nodeids"] = ["tests/test_unknown.py::test_unknown"]
    payload["summary"]["classification_counts"]["candidate_test_debt"] = 1
    payload["summary"]["failed_nodeid_count"] = 1
    current_payload = _baseline_payload(importable=False, head_sha=VERIFIED_SHA)
    current_payload["classifications"]["candidate_test_debt"] = ["tests/test_unknown.py::test_unknown"]
    current_payload["collected_nodeids"] = ["tests/test_unknown.py::test_unknown"]
    current_payload["summary"]["classification_counts"]["candidate_test_debt"] = 1
    current_payload["summary"]["failed_nodeid_count"] = 1
    _write_baseline(baseline_path, payload)
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "current_git_head_sha", lambda: VERIFIED_SHA)
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: current_payload)
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert "缺少测试债务登记元数据" in capsys.readouterr().err


def test_import_test_debt_baseline_command_rejects_empty_candidate_nodeid(monkeypatch, tmp_path: Path, capsys):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "empty_nodeid_baseline.md"
    payload = _baseline_payload()
    payload["classifications"]["candidate_test_debt"] = [*P0_TEST_DEBT_NODEIDS, ""]
    _write_baseline(baseline_path, payload)
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha=VERIFIED_SHA))
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert "candidate_test_debt" in capsys.readouterr().err


def test_import_test_debt_baseline_command_rejects_current_dry_run_candidate_drift(
    monkeypatch, tmp_path: Path, capsys
):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "debt_baseline.md"
    _write_baseline(baseline_path, _baseline_payload())
    current_payload = _baseline_payload(importable=False, head_sha=VERIFIED_SHA)
    current_payload["classifications"]["candidate_test_debt"] = ["tests/test_unknown.py::test_unknown"]
    current_payload["summary"]["classification_counts"]["candidate_test_debt"] = 1
    current_payload["summary"]["failed_nodeid_count"] = 1
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: current_payload)
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert "candidate_test_debt" in capsys.readouterr().err


def test_import_test_debt_baseline_command_does_not_overwrite_existing_test_debt(
    monkeypatch, tmp_path: Path, capsys
):
    module = _import_sync_debt_ledger()
    baseline_path = tmp_path / "debt_baseline.md"
    _write_baseline(baseline_path, _baseline_payload())
    existing_ledger = _legacy_schema1_ledger()
    existing_ledger["schema_version"] = 2
    existing_ledger["test_debt"] = {
        "ratchet": {"max_registered_xfail": 1},
        "entries": [
            {
                "debt_id": "test-debt:kept",
                "nodeid": P0_TEST_DEBT_NODEIDS[0],
                "mode": "fixed",
                "reason": "已经人工治理过，不能被 seed 覆盖",
                "domain": "personnel.operator_machine",
                "style": "stale_patch_target",
                "root": {"module": "core.services.personnel.operator_machine_service", "function": "list_by_operator"},
                "owner": "personnel.operator_machine",
                "exit_condition": "保留人工结果",
                "last_verified_at": "2026-04-27T08:00:00+08:00",
                "debt_family": "operator_machine_normalization_contract_drift",
            }
        ],
    }
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: existing_ledger)
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha=VERIFIED_SHA))
    monkeypatch.setattr(module, "save_ledger", lambda ledger: calls.setdefault("saved_ledger", ledger))

    rc = module.main(["import-test-debt-baseline", "--baseline", str(baseline_path)])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert "不得覆盖" in capsys.readouterr().err


def test_mark_test_debt_fixed_command_marks_entry_fixed_and_decrements_ratchet(monkeypatch, capsys):
    module = _import_sync_debt_ledger()
    first = _test_debt_entry("test-debt:sample-one", P0_TEST_DEBT_NODEIDS[0])
    second = _test_debt_entry("test-debt:sample-two", P0_TEST_DEBT_NODEIDS[1])
    ledger = _schema2_ledger_with_test_debt(first, second, max_registered_xfail=2)
    original_ledger = copy.deepcopy(ledger)
    calls = {}

    monkeypatch.setattr(module, "load_ledger", lambda required=True: ledger)
    monkeypatch.setattr(module, "now_shanghai_iso", lambda: "2026-04-27T10:00:00+08:00")
    monkeypatch.setattr(module, "save_ledger", lambda next_ledger: calls.setdefault("saved_ledger", next_ledger))

    rc = module.main(["mark-test-debt-fixed", "--debt-id", "test-debt:sample-one"])

    assert rc == 0
    assert ledger == original_ledger
    saved = calls["saved_ledger"]
    assert saved["test_debt"]["ratchet"] == {"max_registered_xfail": 1}
    entries = {entry["debt_id"]: entry for entry in saved["test_debt"]["entries"]}
    assert entries["test-debt:sample-one"]["mode"] == "fixed"
    assert entries["test-debt:sample-one"]["last_verified_at"] == "2026-04-27T10:00:00+08:00"
    assert entries["test-debt:sample-two"]["mode"] == "xfail"
    stdout = capsys.readouterr().out
    assert "测试债务已标记为 fixed" in stdout
    assert '"previous_max_registered_xfail": 2' in stdout
    assert '"next_max_registered_xfail": 1' in stdout


@pytest.mark.parametrize(
    ("ledger", "expected_message"),
    [
        (_schema2_ledger_with_test_debt(_test_debt_entry("test-debt:other"), max_registered_xfail=1), "不存在"),
        (
            _schema2_ledger_with_test_debt(
                _test_debt_entry("test-debt:sample-one", P0_TEST_DEBT_NODEIDS[0]),
                _test_debt_entry("test-debt:sample-one", P0_TEST_DEBT_NODEIDS[1]),
                max_registered_xfail=2,
            ),
            "重复",
        ),
        (
            _schema2_ledger_with_test_debt(_test_debt_entry(mode="fixed"), max_registered_xfail=0),
            "已经是 fixed",
        ),
        (
            _schema2_ledger_with_test_debt(_test_debt_entry(), max_registered_xfail=2),
            "max_registered_xfail",
        ),
    ],
)
def test_mark_test_debt_fixed_command_rejects_invalid_state(monkeypatch, capsys, ledger: dict, expected_message: str):
    module = _import_sync_debt_ledger()
    original_ledger = copy.deepcopy(ledger)
    calls = {}

    monkeypatch.setattr(module, "load_ledger", lambda required=True: ledger)
    monkeypatch.setattr(module, "save_ledger", lambda next_ledger: calls.setdefault("saved_ledger", next_ledger))

    rc = module.main(["mark-test-debt-fixed", "--debt-id", "test-debt:sample-one"])

    assert rc == 2
    assert "saved_ledger" not in calls
    assert ledger == original_ledger
    assert expected_message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected_message"),
    [
        ("owner", "", "owner"),
        ("style", "untriaged", "untriaged"),
    ],
)
def test_import_seed_metadata_rejects_empty_and_untriaged_fields(monkeypatch, field_name: str, bad_value: str, expected_message: str):
    from tools.quality_gate_shared import QualityGateError

    test_debt_registry = _import_test_debt_registry()
    seed = test_debt_registry.P0_TEST_DEBT_SEED_METADATA[P0_TEST_DEBT_NODEIDS[0]]
    monkeypatch.setitem(seed, field_name, bad_value)

    with pytest.raises(QualityGateError, match=expected_message):
        test_debt_registry.build_test_debt_entries(_baseline_payload(), last_verified_at="2026-04-27T08:00:00+08:00")


def test_import_seed_metadata_rejects_duplicate_debt_id(monkeypatch):
    test_debt_registry = _import_test_debt_registry()
    first_seed = test_debt_registry.P0_TEST_DEBT_SEED_METADATA[P0_TEST_DEBT_NODEIDS[0]]
    second_seed = test_debt_registry.P0_TEST_DEBT_SEED_METADATA[P0_TEST_DEBT_NODEIDS[1]]
    monkeypatch.setitem(second_seed, "debt_id", first_seed["debt_id"])

    with pytest.raises(Exception, match="debt_id"):
        test_debt_registry.build_test_debt_ledger_from_baseline(
            _legacy_schema1_ledger(),
            _baseline_payload(),
            verified_head_sha=VERIFIED_SHA,
            last_verified_at="2026-04-27T08:00:00+08:00",
        )


def test_sort_ledger_does_not_fill_missing_test_debt_ratchet() -> None:
    support = _import_quality_gate_support()
    ledger = _schema2_ledger_with_test_debt(_test_debt_entry(), max_registered_xfail=1)
    del ledger["test_debt"]["ratchet"]["max_registered_xfail"]

    with pytest.raises(support.QualityGateError, match="max_registered_xfail"):
        support.sort_ledger(ledger)


@pytest.mark.parametrize(
    ("path", "scope_tag", "expected_message"),
    [
        ("web/ui_mode_store.py", "render_bridge", "startup_guard"),
        ("web/render_bridge.py", "startup_guard", "render_bridge"),
    ],
)
def test_validate_ledger_rejects_ui_mode_split_scope_drift(path: str, scope_tag: str, expected_message: str) -> None:
    support = _import_quality_gate_support()
    ledger = _schema2_ledger_with_test_debt(max_registered_xfail=0)
    ledger["silent_fallback"]["entries"] = [
        {
            "id": f"fallback:{path.replace('/', '-')}-sample",
            "path": path,
            "symbol": "sample",
            "status": "open",
            "owner": "techdebt",
            "batch": "phase5",
            "exit_condition": "keep tracking",
            "last_verified_at": "2026-04-30T13:30:00+08:00",
            "notes": "scope test",
            "handler_fingerprint": "sha1:sample",
            "handler_context_hash": "sha1:sample-context",
            "except_ordinal": 1,
            "line_start": 1,
            "line_end": 2,
            "fallback_kind": "observable_degrade",
            "scope_tag": scope_tag,
            "source": "baseline_scan",
        }
    ]

    with pytest.raises(support.QualityGateError, match=expected_message):
        support.validate_ledger(ledger)


def test_validate_ledger_requires_realignment_reason_when_entry_marks_realign() -> None:
    support = _import_quality_gate_support()
    ledger = _schema2_ledger_with_test_debt(max_registered_xfail=0)
    ledger["silent_fallback"]["entries"] = [
        {
            "id": "fallback:web-bootstrap-launcher-contracts-read-runtime-contract-new",
            "path": "web/bootstrap/launcher_contracts.py",
            "symbol": "read_runtime_contract",
            "status": "open",
            "owner": "techdebt",
            "batch": "phase5",
            "exit_condition": "keep tracking",
            "last_verified_at": "2026-04-30T13:30:00+08:00",
            "notes": "realign test",
            "handler_fingerprint": "sha1:sample",
            "handler_context_hash": "sha1:sample-context",
            "except_ordinal": 1,
            "line_start": 1,
            "line_end": 2,
            "fallback_kind": "observable_degrade",
            "source": "baseline_scan",
            "realigned_from": "fallback:web-bootstrap-launcher-contracts-read-runtime-contract-old",
            "realigned_at": "2026-04-30",
        }
    ]
    ledger["accepted_risks"] = [
        {
            "id": "accepted:test",
            "entry_ids": ["fallback:web-bootstrap-launcher-contracts-read-runtime-contract-new"],
            "owner": "techdebt",
            "reason": "test",
            "review_after": "2026-05-31",
            "exit_condition": "test",
        }
    ]

    with pytest.raises(support.QualityGateError, match="realignment_reason"):
        support.validate_ledger(ledger)
