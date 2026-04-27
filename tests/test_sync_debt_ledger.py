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
        "head_sha": "baseline-sha",
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

    monkeypatch.setattr(module, "load_ledger", fake_load_ledger)
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

    monkeypatch.setattr(module, "load_ledger", fake_load_ledger)
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


def test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted(monkeypatch):
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
            "source": source,
        },
    )
    monkeypatch.setitem(refresh_globals, "finalize_ledger_update", lambda current: current)

    refreshed = module.refresh_auto_fields(ledger)
    entry = refreshed["silent_fallback"]["entries"][0]

    assert entry["id"] == "fallback:web-bootstrap-factory-_open_db-42cf3c7f221e"
    assert entry["except_ordinal"] == 8
    assert entry["line_start"] == 375
    assert entry["line_end"] == 382
    assert entry["owner"] == "SP03"


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
    monkeypatch.setattr(module, "current_git_head_sha", lambda: "verified-sha")
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha="verified-sha"))
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
    assert '"baseline_head_sha": "baseline-sha"' in stdout
    assert '"verified_head_sha": "verified-sha"' in stdout


def test_importable_baseline_contract_accepts_zero_candidate_current_proof(tmp_path: Path):
    registry = _import_test_debt_registry()
    baseline_path = tmp_path / "zero_candidate_baseline.md"
    _write_baseline(baseline_path, _zero_candidate_payload())

    payload = registry.load_full_test_debt_baseline(str(baseline_path))

    assert registry.baseline_candidate_nodeids(payload) == []


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
    monkeypatch.setattr(module, "current_git_head_sha", lambda: "verified-sha")
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha="verified-sha"))
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
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha="verified-sha"))
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
    monkeypatch.setattr(module, "current_git_head_sha", lambda: "verified-sha")
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha="verified-sha"))
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
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha="verified-sha"))
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
    current_payload = _baseline_payload(importable=False, head_sha="verified-sha")
    current_payload["classifications"]["candidate_test_debt"] = ["tests/test_unknown.py::test_unknown"]
    current_payload["collected_nodeids"] = ["tests/test_unknown.py::test_unknown"]
    current_payload["summary"]["classification_counts"]["candidate_test_debt"] = 1
    current_payload["summary"]["failed_nodeid_count"] = 1
    _write_baseline(baseline_path, payload)
    calls = {}

    monkeypatch.setattr(module, "load_ledger_for_test_debt_import", lambda: _legacy_schema1_ledger())
    monkeypatch.setattr(module, "current_git_head_sha", lambda: "verified-sha")
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
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha="verified-sha"))
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
    current_payload = _baseline_payload(importable=False, head_sha="verified-sha")
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
    monkeypatch.setattr(module, "collect_current_test_debt_payload", lambda: _baseline_payload(importable=False, head_sha="verified-sha"))
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
            verified_head_sha="verified-sha",
            last_verified_at="2026-04-27T08:00:00+08:00",
        )
