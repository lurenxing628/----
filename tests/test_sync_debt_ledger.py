from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_sync_debt_ledger():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("scripts.sync_debt_ledger", None)
    return importlib.import_module("scripts.sync_debt_ledger")


def _import_quality_gate_support():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("tools.quality_gate_support", None)
    return importlib.import_module("tools.quality_gate_support")


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

    monkeypatch.setattr(module, "scan_silent_fallback_entries", lambda _paths: [scan_entry])
    monkeypatch.setattr(
        module,
        "build_silent_entry",
        lambda scan_item, source, existing=None: {
            **dict(existing or {}),
            **dict(scan_item),
            "source": source,
        },
    )
    monkeypatch.setattr(module, "finalize_ledger_update", lambda current: current)

    refreshed = module.refresh_auto_fields(ledger)
    entry = refreshed["silent_fallback"]["entries"][0]

    assert entry["id"] == "fallback:web-bootstrap-factory-_open_db-42cf3c7f221e"
    assert entry["except_ordinal"] == 8
    assert entry["line_start"] == 375
    assert entry["line_end"] == 382
    assert entry["owner"] == "SP03"


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
