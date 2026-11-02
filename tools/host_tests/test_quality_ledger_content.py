from __future__ import annotations

import ast
import copy

import pytest

from tools import architecture_scan_cache
from tools import quality_gate_ledger as ledger_tools
from tools import quality_gate_operations as operations
from tools import quality_gate_scan as scan
from tools.quality_gate_entries import build_complexity_entry, build_oversize_entry, build_silent_entry
from tools.quality_gate_shared import QualityGateError

PATH = "web/bootstrap/content_sample.py"


def _handler_source(message="before"):
    return (
        "def sample():\n"
        "    try:\n"
        "        work()\n"
        "    except Exception:\n"
        f"        logger.warning({message!r})\n"
    )


def _scan_entry(message="before"):
    context = scan.ScanContext(read_text={PATH: _handler_source(message)}.__getitem__)
    return scan.scan_silent_fallback_entries(PATH, context=context)[0]


def _patch_source(monkeypatch, source):
    """让生产扫描链读到内存源码；返回扫描快照的构造记录，用来断言一次刷新只建一个快照。"""
    contexts = []

    def make_context():
        context = scan.ScanContext(read_text={PATH: source}.__getitem__)
        contexts.append(context)
        return context

    monkeypatch.setattr(architecture_scan_cache, "ScanContext", make_context)
    return contexts


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


def _mock_scan(monkeypatch, stored):
    contexts = _patch_source(monkeypatch, _handler_source())
    monkeypatch.setattr(operations, "collect_startup_scope_files", lambda: [PATH])
    monkeypatch.setattr(operations, "validate_startup_samples", lambda _entries: {"count": 1})
    return contexts


def test_scan_retains_original_content_with_business_identity():
    before = _scan_entry("before")
    after = _scan_entry("after")

    assert before["id"] == after["id"] == "fallback:web/bootstrap/content_sample.py:sample:except:1"
    assert before["handler_signature"] == after["handler_signature"]
    assert "signature" not in before
    try_node = ast.parse("try:\n    work()\nexcept Exception:\n    logger.warning('before')\n").body[0]
    assert isinstance(try_node, ast.Try)
    handler = try_node.handlers[0]
    assert before["handler_context"] == ast.dump(handler, include_attributes=False)
    assert not ledger_tools.silent_entry_content_equal(before, after)
    assert "handler_fingerprint" not in before and "handler_context_hash" not in before


def test_explicit_baseline_preserves_legacy_identity_and_risk(monkeypatch):
    original = _ledger(_legacy_entry())
    current = _scan_entry()
    contexts = _mock_scan(monkeypatch, original)

    ledger_tools.validate_ledger_for_refresh(original)
    assert ledger_tools.sort_ledger(original)["silent_fallback"]["entries"] == original["silent_fallback"]["entries"]
    refreshed = operations.refresh_scan_startup_baseline(copy.deepcopy(original))
    assert len(contexts) == 1
    entry = refreshed["silent_fallback"]["entries"][0]
    previous = original["silent_fallback"]["entries"][0]
    assert entry["handler_signature"] == current["handler_signature"]
    assert entry["handler_context"] == current["handler_context"]
    for field in ("id", "handler_fingerprint", "handler_context_hash", "owner", "status", "notes", "exit_condition"):
        assert entry[field] == previous[field]
    assert refreshed["accepted_risks"] == original["accepted_risks"]
    _patch_source(monkeypatch, "def sample():\n    work()\n")
    with pytest.raises(QualityGateError, match="请先显式复核风险"):
        operations.refresh_scan_startup_baseline(copy.deepcopy(original))


def test_automatic_refresh_and_check_reject_missing_legacy_content(monkeypatch):
    original = _ledger(_legacy_entry())
    _mock_scan(monkeypatch, original)
    with pytest.raises(QualityGateError, match="缺少 handler_signature / handler_context 原文"):
        ledger_tools.validate_ledger(original)
    candidate = copy.deepcopy(original)
    with pytest.raises(QualityGateError, match="handler_signature / handler_context"):
        operations.refresh_auto_fields(candidate)
    assert candidate == original

    dup_oversize = ledger_tools.default_ledger()
    dup_oversize["oversize_allowlist"] = [
        build_oversize_entry(PATH, 501),
        dict(build_oversize_entry(PATH, 502), id="oversize:duplicate-path"),
    ]
    with pytest.raises(QualityGateError, match="oversize_allowlist 存在重复登记"):
        ledger_tools.validate_ledger(dup_oversize)

    dup_complexity = ledger_tools.default_ledger()
    dup_complexity["complexity_allowlist"] = [
        build_complexity_entry(PATH, "A.shared", 16),
        dict(build_complexity_entry(PATH, "A.shared", 17), id="complexity:duplicate-key", lineno=99),
    ]
    with pytest.raises(QualityGateError, match=f"complexity_allowlist 存在重复登记：{PATH}:A.shared"):
        ledger_tools.validate_ledger(dup_complexity)


def test_current_content_comparison_preserves_old_id_and_detects_literal_change(monkeypatch):
    current = _scan_entry()
    entry = build_silent_entry(current, source="baseline_scan", existing=_legacy_entry())
    stored = _ledger(entry)
    _mock_scan(monkeypatch, stored)
    assert operations.validate_ledger_against_current_scan(stored) == {"samples": {"count": 1}}
    assert operations.refresh_auto_fields(copy.deepcopy(stored))["accepted_risks"] == stored["accepted_risks"]
    monkeypatch.setattr(scan, "load_ledger", lambda required=True: copy.deepcopy(stored))
    monkeypatch.setattr(scan, "_strict_silent_fallback_scan_entries", lambda: [copy.deepcopy(current)])
    monkeypatch.setattr(scan, "validate_startup_samples", lambda _entries: {"count": 1})
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


def test_ledger_check_scans_each_file_once_for_samples_and_silent_entries(monkeypatch):
    other_path = "web/bootstrap/paths.py"
    sources = {
        PATH: "def sample():\n    try:\n        work()\n    except Exception:\n        logger.warning('before')\n",
        other_path: "def other():\n    try:\n        work()\n    except Exception:\n        logger.warning('other')\n",
    }
    other_scan = scan.scan_silent_fallback_entries(
        other_path, context=scan.ScanContext(read_text=sources.__getitem__)
    )[0]
    stored = _ledger(build_silent_entry(_scan_entry(), source="baseline_scan"))
    stored["silent_fallback"]["entries"].append(build_silent_entry(other_scan, source="baseline_scan"))
    scanned = []
    real_scan = architecture_scan_cache.scan_silent_fallback_entries

    def counting_scan(rel_path, *, context):
        scanned.append(rel_path)
        return real_scan(rel_path, context=context)

    sample_paths = []

    def record_samples(entries):
        sample_paths.append(sorted({entry["path"] for entry in entries}))
        return {"count": len(entries)}

    monkeypatch.setattr(operations, "collect_startup_scope_files", lambda: [PATH, other_path])
    monkeypatch.setattr(architecture_scan_cache, "ScanContext", lambda: scan.ScanContext(read_text=sources.__getitem__))
    monkeypatch.setattr(architecture_scan_cache, "scan_silent_fallback_entries", counting_scan)
    monkeypatch.setattr(operations, "validate_startup_samples", record_samples)

    assert operations.validate_ledger_against_current_scan(stored) == {"samples": {"count": 2}}
    assert sorted(scanned) == [PATH, other_path]
    assert sample_paths == [[PATH, other_path]]

    unregistered = copy.deepcopy(stored)
    unregistered["silent_fallback"]["entries"] = [unregistered["silent_fallback"]["entries"][0]]
    with pytest.raises(QualityGateError, match="启动链静默回退未在治理台账登记"):
        operations.validate_ledger_against_current_scan(unregistered)

    retired_non_startup_path = "/".join(("core", "services", "retired_sample.py"))
    sources[retired_non_startup_path] = "def clean():\n    return 1\n"
    fixed_entry = dict(
        build_silent_entry(_scan_entry(), source="migrated_from_architecture_fitness_counter"),
        id="fallback:retired-non-startup",
        path=retired_non_startup_path,
        status="fixed",
    )
    with_fixed = copy.deepcopy(stored)
    with_fixed["silent_fallback"]["entries"].append(fixed_entry)
    assert operations.validate_ledger_against_current_scan(with_fixed) == {"samples": {"count": 2}}


def _scan_group(messages):
    body = "".join(
        "    try:\n"
        f"        work_{index}()\n"
        "    except Exception:\n"
        f"        logger.warning({message!r})\n"
        for index, message in enumerate(messages)
    )
    context = scan.ScanContext(read_text={PATH: "def sample():\n" + body}.__getitem__)
    return scan.scan_silent_fallback_entries(PATH, context=context)


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


def _branchy_body(indent, subject, branch_count=16):
    """branch_count 个 if 分支，radon 复杂度为 branch_count + 1（默认 17）。"""
    branches = "".join(f"{indent}if {subject} == {index}:\n{indent}    return {index}\n" for index in range(branch_count))
    return branches + f"{indent}return -1\n"


_CLASS_SOURCES = {
    "A": "class A:\n    def shared(self, x):\n" + _branchy_body("        ", "x") + "".join(
        f"    def trivial_{index}(self):\n        return {index}\n" for index in range(5)
    ),
    "B": "class B:\n    def shared(self, x):\n        return x\n",
}


@pytest.mark.parametrize("class_order", [("A", "B"), ("B", "A")])
def test_complexity_identity_keeps_same_named_methods_of_different_classes(monkeypatch, class_order):
    stored = ledger_tools.default_ledger()
    stored["complexity_allowlist"] = [build_complexity_entry(PATH, "A.shared", 17)]
    entry_id = stored["complexity_allowlist"][0]["id"]
    _patch_source(monkeypatch, "".join(_CLASS_SOURCES[name] for name in class_order))
    monkeypatch.setattr(operations, "collect_startup_scope_files", lambda: [PATH])
    monkeypatch.setattr(operations, "validate_startup_samples", lambda _entries: {"count": 0})

    complexity_map = architecture_scan_cache.aggregate_architecture_scan(
        architecture_scan_cache.scan_files_with_cache([PATH], fact_kinds=("complexity",)), include_all_complexity=True
    )["complexity_map"]
    assert complexity_map[f"{PATH}:A.shared"]["current_value"] == 17
    assert complexity_map[f"{PATH}:B.shared"]["current_value"] == 1
    assert operations.validate_ledger_against_current_scan(copy.deepcopy(stored)) == {"samples": {"count": 0}}
    refreshed = operations.refresh_auto_fields(copy.deepcopy(stored))["complexity_allowlist"]
    assert [(entry["id"], entry["current_value"]) for entry in refreshed] == [(entry_id, 17)]
    with pytest.raises(QualityGateError, match="不能标记为 fixed"):
        operations.set_entry_fields(copy.deepcopy(stored), entry_id, {"status": "fixed"})


@pytest.mark.parametrize(
    ("source", "expected_key"),
    [
        (
            "class C:\n    @property\n    def value(self):\n" + _branchy_body("        ", "self.x")
            + "    @value.setter\n    def value(self, x):\n        self.x = x\n",
            "C.value",
        ),
        (
            "class C:\n    @property\n    def value(self):\n        return self.x\n"
            "    @value.setter\n    def value(self, x):\n" + _branchy_body("        ", "x"),
            "C.value",
        ),
        (
            "from typing import overload\n\n@overload\ndef f(x: int) -> int: ...\n"
            "@overload\ndef f(x: str) -> str: ...\ndef f(x):\n" + _branchy_body("    ", "x"),
            "f",
        ),
    ],
    ids=["property-getter-highest", "property-setter-highest", "overload-implementation"],
)
def test_complexity_same_qualified_name_counts_highest_definition(monkeypatch, source, expected_key):
    _patch_source(monkeypatch, source)

    complexity_map = architecture_scan_cache.aggregate_architecture_scan(
        architecture_scan_cache.scan_files_with_cache([PATH], fact_kinds=("complexity",))
    )["complexity_map"]

    assert {key: item["current_value"] for key, item in complexity_map.items()} == {f"{PATH}:{expected_key}": 17}


def _legacy_complexity_entry(entry_id):
    entry = build_complexity_entry(PATH, "A.shared", 18)
    entry.update(id=entry_id, owner="legacy-owner", status="blocked", notes="已登记的人工复核结论")
    return entry


def test_startup_baseline_refresh_matches_complexity_entry_by_path_and_symbol(monkeypatch):
    stored = ledger_tools.default_ledger()
    stored["complexity_allowlist"] = [_legacy_complexity_entry("complexity:legacy-permanent-id")]
    _patch_source(monkeypatch, _CLASS_SOURCES["A"] + _CLASS_SOURCES["B"])
    monkeypatch.setattr(operations, "collect_startup_scope_files", lambda: [PATH])
    monkeypatch.setattr(operations, "validate_startup_samples", lambda _entries: {"count": 0})

    refreshed = operations.refresh_scan_startup_baseline(copy.deepcopy(stored))["complexity_allowlist"]

    assert [
        (entry["id"], entry["symbol"], entry["owner"], entry["status"], entry["notes"], entry["current_value"])
        for entry in refreshed
    ] == [("complexity:legacy-permanent-id", "A.shared", "legacy-owner", "blocked", "已登记的人工复核结论", 17)]

    stored["complexity_allowlist"].append(_legacy_complexity_entry("complexity:legacy-duplicate-id"))
    with pytest.raises(QualityGateError, match="多条旧登记"):
        operations.refresh_scan_startup_baseline(copy.deepcopy(stored))


def test_startup_baseline_refresh_matches_oversize_entry_by_path(monkeypatch):
    stored = ledger_tools.default_ledger()
    legacy = build_oversize_entry(PATH, 600)
    legacy.update(id="oversize:legacy-permanent", owner="legacy-owner", status="blocked", notes="已登记的人工复核结论")
    stored["oversize_allowlist"] = [legacy]
    _patch_source(monkeypatch, "x = 1\n" * 501)
    monkeypatch.setattr(operations, "collect_startup_scope_files", lambda: [PATH])
    monkeypatch.setattr(operations, "validate_startup_samples", lambda _entries: {"count": 0})

    refreshed = operations.refresh_scan_startup_baseline(copy.deepcopy(stored))["oversize_allowlist"]

    assert [
        (entry["id"], entry["owner"], entry["status"], entry["notes"], entry["current_value"]) for entry in refreshed
    ] == [("oversize:legacy-permanent", "legacy-owner", "blocked", "已登记的人工复核结论", 501)]


@pytest.mark.parametrize("complexity", [1, 15, 16, None], ids=["exit-1", "exit-15", "keep-16", "symbol-missing"])
def test_refresh_auto_fields_complexity_exit_alignment_and_fixed_rejection(monkeypatch, complexity):
    """阈值严格大于 15：先判退出（open 与 fixed 都移除），仍超限的 fixed 才被拒；找不到符号直接报错。"""
    if complexity is None:
        _patch_source(monkeypatch, _CLASS_SOURCES["B"])
    else:
        _patch_source(monkeypatch, "class A:\n    def shared(self, x):\n" + _branchy_body("        ", "x", complexity - 1))
    open_ledger = ledger_tools.default_ledger()
    open_ledger["complexity_allowlist"] = [build_complexity_entry(PATH, "A.shared", 17)]
    entry_id = open_ledger["complexity_allowlist"][0]["id"]
    fixed_ledger = copy.deepcopy(open_ledger)
    fixed_ledger["complexity_allowlist"][0]["status"] = "fixed"
    risk_ledger = _group_ledger([], risk_entry_ids=[entry_id])
    risk_ledger["complexity_allowlist"] = copy.deepcopy(open_ledger["complexity_allowlist"])

    if complexity is None:
        with pytest.raises(QualityGateError, match="已无法通过当前扫描对齐"):
            operations.refresh_auto_fields(copy.deepcopy(open_ledger))
    elif complexity <= 15:
        for stored in (open_ledger, fixed_ledger):
            assert operations.refresh_auto_fields(copy.deepcopy(stored))["complexity_allowlist"] == []
        with pytest.raises(QualityGateError, match="已达成退出条件但仍被 accepted_risks 引用"):
            operations.refresh_auto_fields(risk_ledger)
        marked = operations.set_entry_fields(copy.deepcopy(open_ledger), entry_id, {"status": "fixed"})
        assert marked["complexity_allowlist"][0]["status"] == "fixed"
    else:
        refreshed = operations.refresh_auto_fields(copy.deepcopy(open_ledger))["complexity_allowlist"]
        assert [(entry["id"], entry["current_value"]) for entry in refreshed] == [(entry_id, 16)]
        with pytest.raises(QualityGateError, match="不能标记为 fixed"):
            operations.refresh_auto_fields(fixed_ledger)
