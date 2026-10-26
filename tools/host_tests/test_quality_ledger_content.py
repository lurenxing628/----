from __future__ import annotations

import ast
import copy

import pytest

from tools import quality_gate_ledger as ledger_tools
from tools import quality_gate_operations as operations
from tools import quality_gate_scan as scan
from tools.quality_gate_entries import build_silent_entry
from tools.quality_gate_shared import QualityGateError

PATH = "web/bootstrap/content_sample.py"


def _scan_entry(message="before"):
    source = (
        "def sample():\n"
        "    try:\n"
        "        work()\n"
        "    except Exception:\n"
        f"        logger.warning({message!r})\n"
    )
    context = scan.ScanContext(read_text=lambda _path: source)
    return scan.scan_silent_fallback_entries([PATH], context=context)[0]


def _ledger(entry):
    ledger = ledger_tools.default_ledger()
    ledger["silent_fallback"]["entries"] = [entry]
    ledger["accepted_risks"] = [
        {
            "id": "risk:sample",
            "entry_ids": [entry["id"]],
            "owner": "reviewer",
            "reason": "保留已登记目标机复测责任",
            "review_after": "2026-12-01",
            "exit_condition": "目标机完成复测",
        }
    ]
    return ledger


def _legacy_entry():
    entry = build_silent_entry(_scan_entry(), source="baseline_scan")
    entry.pop("handler_signature")
    entry.pop("handler_context")
    entry.update(
        id="fallback:historical-id",
        handler_fingerprint="sha1:stored-signature",
        handler_context_hash="sha1:stored-context",
        owner="existing-owner",
        status="blocked",
        notes="已记录的目标机限制",
    )
    return entry


def _mock_scan(monkeypatch, current, stored):
    monkeypatch.setattr(operations, "collect_startup_scope_files", lambda: [PATH])
    monkeypatch.setattr(operations, "_cached_silent_scan_entries", lambda _paths: [copy.deepcopy(current)])
    monkeypatch.setattr(operations, "_cached_oversize_entries", lambda _paths: [])
    monkeypatch.setattr(operations, "_cached_complexity_entries", lambda _paths: [])
    monkeypatch.setattr(operations, "_validate_startup_samples_from_entries", lambda _entries: {"count": 1})
    monkeypatch.setattr(operations, "architecture_validate_startup_samples", lambda: {"count": 1})
    monkeypatch.setattr(ledger_tools, "load_ledger_unvalidated", lambda required=False: copy.deepcopy(stored))


def test_scan_retains_original_content_with_business_identity():
    before = _scan_entry("before")
    after = _scan_entry("after")

    assert before["id"] == after["id"] == "fallback:web/bootstrap/content_sample.py:sample:except:1"
    assert before["handler_signature"] == before["signature"] == after["handler_signature"]
    try_node = ast.parse("try:\n    work()\nexcept Exception:\n    logger.warning('before')\n").body[0]
    assert isinstance(try_node, ast.Try)
    handler = try_node.handlers[0]
    assert before["handler_context"] == ast.dump(handler, include_attributes=False)
    assert not ledger_tools.silent_entry_content_equal(before, after)
    assert "handler_fingerprint" not in before and "handler_context_hash" not in before


def test_explicit_baseline_preserves_legacy_identity_and_risk(monkeypatch):
    original = _ledger(_legacy_entry())
    current = _scan_entry()
    _mock_scan(monkeypatch, current, original)

    ledger_tools.validate_ledger(original)
    assert ledger_tools.sort_ledger(original)["silent_fallback"]["entries"] == original["silent_fallback"]["entries"]
    refreshed = operations.refresh_scan_startup_baseline(copy.deepcopy(original))
    entry = refreshed["silent_fallback"]["entries"][0]
    previous = original["silent_fallback"]["entries"][0]
    assert entry["handler_signature"] == current["handler_signature"]
    assert entry["handler_context"] == current["handler_context"]
    for field in ("id", "handler_fingerprint", "handler_context_hash", "owner", "status", "notes", "exit_condition"):
        assert entry[field] == previous[field]
    assert refreshed["accepted_risks"] == original["accepted_risks"]
    monkeypatch.setattr(operations, "_cached_silent_scan_entries", lambda _paths: [])
    with pytest.raises(QualityGateError, match="请先显式复核风险"):
        operations.refresh_scan_startup_baseline(copy.deepcopy(original))


def test_automatic_refresh_and_check_reject_missing_legacy_content():
    original = _ledger(_legacy_entry())
    for operation in (operations.refresh_auto_fields, operations.validate_ledger_against_current_scan):
        candidate = copy.deepcopy(original)
        with pytest.raises(QualityGateError, match="缺少 handler_signature / handler_context 原文"):
            operation(candidate)
        assert candidate == original


def test_current_content_comparison_preserves_old_id_and_detects_literal_change(monkeypatch):
    current = _scan_entry()
    entry = build_silent_entry(current, source="baseline_scan", existing=_legacy_entry())
    stored = _ledger(entry)
    _mock_scan(monkeypatch, current, stored)
    assert operations.validate_ledger_against_current_scan(stored) == {"samples": {"count": 1}}
    assert operations.refresh_auto_fields(copy.deepcopy(stored))["accepted_risks"] == stored["accepted_risks"]
    monkeypatch.setattr(scan, "load_ledger", lambda required=True: copy.deepcopy(stored))
    monkeypatch.setattr(scan, "_strict_silent_fallback_scan_entries", lambda: [copy.deepcopy(current)])
    monkeypatch.setattr(scan, "validate_startup_samples", lambda: {"count": 1})
    assert scan.run_strict_silent_fallback_gate() == 0

    changed = _scan_entry("after")
    monkeypatch.setattr(operations, "_cached_silent_scan_entries", lambda _paths: [copy.deepcopy(changed)])
    monkeypatch.setattr(scan, "_strict_silent_fallback_scan_entries", lambda: [copy.deepcopy(changed)])
    with pytest.raises(QualityGateError, match="与当前扫描不一致"):
        operations.validate_ledger_against_current_scan(stored)
    with pytest.raises(QualityGateError, match="handler_signature / handler_context changed"):
        operations.refresh_auto_fields(copy.deepcopy(stored))
    with pytest.raises(QualityGateError, match="handler content drift"):
        scan.run_strict_silent_fallback_gate()
    monkeypatch.setattr(operations, "_cached_silent_scan_entries", lambda _paths: [])
    with pytest.raises(QualityGateError, match="请先显式复核风险"):
        operations.refresh_auto_fields(copy.deepcopy(stored))


def _scan_group(messages):
    body = "".join(
        "    try:\n"
        f"        work_{index}()\n"
        "    except Exception:\n"
        f"        logger.warning({message!r})\n"
        for index, message in enumerate(messages)
    )
    context = scan.ScanContext(read_text=lambda _path: "def sample():\n" + body)
    return scan.scan_silent_fallback_entries([PATH], context=context)


def _group_ledger(entries, *, risk_entry_ids=()):
    ledger = ledger_tools.default_ledger()
    ledger["silent_fallback"]["entries"] = [
        dict(build_silent_entry(entry, source="baseline_scan"), id=f"fallback:sample-{index}")
        for index, entry in enumerate(entries)
    ]
    if risk_entry_ids:
        ledger["accepted_risks"] = [{
            "id": "risk:sample", "entry_ids": list(risk_entry_ids), "owner": "reviewer",
            "reason": "保留已登记目标机复测责任", "review_after": "2026-12-01", "exit_condition": "目标机完成复测",
        }]
    return ledger


def _mock_group_scan(monkeypatch, current):
    monkeypatch.setattr(operations, "collect_startup_scope_files", lambda: [PATH])
    monkeypatch.setattr(operations, "_cached_silent_scan_entries", lambda _paths: copy.deepcopy(current))
    monkeypatch.setattr(operations, "_cached_oversize_entries", lambda _paths: [])
    monkeypatch.setattr(operations, "_cached_complexity_entries", lambda _paths: [])


def test_deleted_handler_retires_its_entry_and_shifts_survivor_ordinals(monkeypatch):
    stored = _group_ledger(_scan_group(["a", "b", "c"]))
    current = _scan_group(["b", "c"])
    _mock_group_scan(monkeypatch, current)

    entries = operations.refresh_auto_fields(copy.deepcopy(stored))["silent_fallback"]["entries"]

    assert [(entry["id"], entry["except_ordinal"]) for entry in entries] == [
        ("fallback:sample-1", 1), ("fallback:sample-2", 2),
    ]
    assert [entry["handler_context"] for entry in entries] == [item["handler_context"] for item in current]


def test_deletion_alignment_rejects_changed_survivor_ambiguous_group_and_accepted_risk(monkeypatch):
    _mock_group_scan(monkeypatch, _scan_group(["b", "changed"]))
    with pytest.raises(QualityGateError, match="自动对齐被拒绝"):
        operations.refresh_auto_fields(_group_ledger(_scan_group(["a", "b", "c"])))

    _mock_group_scan(monkeypatch, _scan_group(["a", "b"]))
    with pytest.raises(QualityGateError, match="自动对齐被拒绝"):
        operations.refresh_auto_fields(_group_ledger(_scan_group(["a", "a", "b"])))

    _mock_group_scan(monkeypatch, _scan_group(["b", "c"]))
    with pytest.raises(QualityGateError, match="请先显式复核风险"):
        operations.refresh_auto_fields(_group_ledger(_scan_group(["a", "b", "c"]), risk_entry_ids=["fallback:sample-0"]))
