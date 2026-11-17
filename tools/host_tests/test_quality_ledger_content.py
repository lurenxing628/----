from __future__ import annotations

import ast
import copy

import pytest

from tools import architecture_scan_cache
from tools import quality_gate_ledger as ledger_tools
from tools import quality_gate_operations as operations
from tools import quality_gate_scan as scan
from tools import quality_gate_scan_primitives as primitives
from tools.long_gate_paths import GateContext
from tools.quality_gate_entries import build_complexity_entry, build_oversize_entry, build_silent_entry
from tools.quality_gate_shared import QualityGateError

PATH = "web/bootstrap/content_sample.py"


def _write(root, rel_path, source):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _handler_source(message="before"):
    return (
        "def sample():\n"
        "    try:\n"
        "        work()\n"
        "    except Exception:\n"
        f"        logger.warning({message!r})\n"
    )


def _scan(root, source, rel_path=PATH):
    """把源码写进 root 这个仓库，再用一份新扫描快照扫它。"""
    _write(root, rel_path, source)
    return primitives.scan_silent_fallback_entries(rel_path, context=primitives.ScanContext(str(root)))


def _scan_entry(root, message="before"):
    return _scan(root, _handler_source(message))[0]


def _count_scan_contexts(monkeypatch):
    """记录生产扫描链建的扫描快照，用来断言一次刷新只建一个快照。"""
    contexts = []
    real_context = architecture_scan_cache.ScanContext

    def make_context(repo_root):
        context = real_context(repo_root)
        contexts.append(context)
        return context

    monkeypatch.setattr(architecture_scan_cache, "ScanContext", make_context)
    return contexts


def _stub_startup_samples(monkeypatch, count):
    """启动链样本期望写的是本仓库真实文件；临时仓库里只断言样本校验收到的条目。"""
    monkeypatch.setattr(operations, "validate_startup_samples", lambda _entries: {"count": count})
    monkeypatch.setattr(scan, "validate_startup_samples", lambda _entries: {"count": count})


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


def _legacy_entry(root):
    entry = build_silent_entry(_scan_entry(root), source="baseline_scan")
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


def test_scan_retains_original_content_with_business_identity(tmp_path):
    before = _scan_entry(tmp_path, "before")
    after = _scan_entry(tmp_path, "after")

    assert before["id"] == after["id"] == "fallback:web/bootstrap/content_sample.py:sample:except:1"
    assert before["handler_signature"] == after["handler_signature"]
    assert "signature" not in before
    try_node = ast.parse("try:\n    work()\nexcept Exception:\n    logger.warning('before')\n").body[0]
    assert isinstance(try_node, ast.Try)
    handler = try_node.handlers[0]
    assert before["handler_context"] == ast.dump(handler, include_attributes=False)
    assert not ledger_tools.silent_entry_content_equal(before, after)
    assert "handler_fingerprint" not in before and "handler_context_hash" not in before


def test_explicit_baseline_preserves_legacy_identity_and_risk(tmp_path, monkeypatch):
    original = _ledger(_legacy_entry(tmp_path))
    current = _scan_entry(tmp_path)
    _stub_startup_samples(monkeypatch, 1)
    contexts = _count_scan_contexts(monkeypatch)
    root = str(tmp_path)

    ledger_tools.validate_ledger_for_refresh(original)
    assert ledger_tools.sort_ledger(original)["silent_fallback"]["entries"] == original["silent_fallback"]["entries"]
    refreshed = operations.refresh_scan_startup_baseline(root, copy.deepcopy(original))
    assert len(contexts) == 1
    entry = refreshed["silent_fallback"]["entries"][0]
    previous = original["silent_fallback"]["entries"][0]
    assert entry["handler_signature"] == current["handler_signature"]
    assert entry["handler_context"] == current["handler_context"]
    for field in ("id", "handler_fingerprint", "handler_context_hash", "owner", "status", "notes", "exit_condition"):
        assert entry[field] == previous[field]
    assert refreshed["accepted_risks"] == original["accepted_risks"]
    _write(tmp_path, PATH, "def sample():\n    work()\n")
    with pytest.raises(QualityGateError, match="请先显式复核风险"):
        operations.refresh_scan_startup_baseline(root, copy.deepcopy(original))


def test_automatic_refresh_and_check_reject_missing_legacy_content(tmp_path, monkeypatch):
    original = _ledger(_legacy_entry(tmp_path))
    _stub_startup_samples(monkeypatch, 1)
    with pytest.raises(QualityGateError, match="缺少 handler_signature / handler_context 原文"):
        ledger_tools.validate_ledger(original)
    candidate = copy.deepcopy(original)
    with pytest.raises(QualityGateError, match="handler_signature / handler_context"):
        operations.refresh_auto_fields(str(tmp_path), candidate)
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


def test_current_content_comparison_preserves_old_id_and_detects_literal_change(tmp_path, monkeypatch):
    ctx = GateContext(str(tmp_path))
    current = _scan_entry(tmp_path)
    entry = build_silent_entry(current, source="baseline_scan", existing=_legacy_entry(tmp_path))
    stored = _ledger(entry)
    ledger_tools.save_ledger(ctx.ledger_path, stored)
    _stub_startup_samples(monkeypatch, 1)
    assert operations.validate_ledger_against_current_scan(ctx.repo_root, stored) == {"samples": {"count": 1}}
    assert operations.refresh_auto_fields(ctx.repo_root, copy.deepcopy(stored))["accepted_risks"] == stored["accepted_risks"]
    assert scan.run_strict_silent_fallback_gate(ctx, emit_json=False) == 0

    _write(tmp_path, PATH, _handler_source("after"))
    with pytest.raises(QualityGateError, match="与当前扫描不一致"):
        operations.validate_ledger_against_current_scan(ctx.repo_root, stored)
    with pytest.raises(QualityGateError, match="handler_signature / handler_context changed"):
        operations.refresh_auto_fields(ctx.repo_root, copy.deepcopy(stored))
    with pytest.raises(QualityGateError, match="handler content drift"):
        scan.run_strict_silent_fallback_gate(ctx, emit_json=False)
    _write(tmp_path, PATH, "def sample():\n    work()\n")
    with pytest.raises(QualityGateError, match="请先显式复核风险"):
        operations.refresh_auto_fields(ctx.repo_root, copy.deepcopy(stored))


def test_ledger_check_scans_each_file_once_for_samples_and_silent_entries(tmp_path, monkeypatch):
    other_path = "web/bootstrap/paths.py"
    other_scan = _scan(
        tmp_path,
        "def other():\n    try:\n        work()\n    except Exception:\n        logger.warning('other')\n",
        rel_path=other_path,
    )[0]
    stored = _ledger(build_silent_entry(_scan_entry(tmp_path), source="baseline_scan"))
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

    monkeypatch.setattr(architecture_scan_cache, "scan_silent_fallback_entries", counting_scan)
    monkeypatch.setattr(operations, "validate_startup_samples", record_samples)
    root = str(tmp_path)

    assert operations.validate_ledger_against_current_scan(root, stored) == {"samples": {"count": 2}}
    assert sorted(scanned) == [PATH, other_path]
    assert sample_paths == [[PATH, other_path]]

    unregistered = copy.deepcopy(stored)
    unregistered["silent_fallback"]["entries"] = [unregistered["silent_fallback"]["entries"][0]]
    with pytest.raises(QualityGateError, match="启动链静默回退未在治理台账登记"):
        operations.validate_ledger_against_current_scan(root, unregistered)

    retired_non_startup_path = "/".join(("core", "services", "retired_sample.py"))
    _write(tmp_path, retired_non_startup_path, "def clean():\n    return 1\n")
    fixed_entry = dict(
        build_silent_entry(_scan_entry(tmp_path), source="migrated_from_architecture_fitness_counter"),
        id="fallback:retired-non-startup",
        path=retired_non_startup_path,
        status="fixed",
    )
    with_fixed = copy.deepcopy(stored)
    with_fixed["silent_fallback"]["entries"].append(fixed_entry)
    assert operations.validate_ledger_against_current_scan(root, with_fixed) == {"samples": {"count": 2}}


def _kinds(root, source):
    return [(entry["except_ordinal"], entry["fallback_kind"]) for entry in _scan(root, source)]


def test_reraising_handler_is_not_registered_and_keeps_later_ordinals(tmp_path):
    source = (
        "def sample():\n"
        "    try:\n"
        "        work()\n"
        "    except Exception:\n"
        "        try:\n"
        "            rollback_partial()\n"
        "        except Exception:\n"
        "            logger.warning('cleanup failed')\n"
        "        raise\n"
        "    try:\n"
        "        other()\n"
        "    except Exception:\n"
        "        logger.warning('other')\n"
    )
    assert _kinds(tmp_path, source) == [(2, "observable_degrade"), (3, "observable_degrade")]


_IO_HANDLER = "    except Exception:\n        logger.warning('failed')\n"


@pytest.mark.parametrize(
    ("source", "expected_kind"),
    [
        ("import os\n\ndef sample(pid):\n    try:\n        os.kill(pid, 0)\n" + _IO_HANDLER, "broad_io_boundary"),
        (
            "from core.infrastructure.safe_files import read_fixed_text\n\ndef sample(path):\n    try:\n"
            "        key = read_fixed_text(path).strip()\n        size = len(key)\n" + _IO_HANDLER,
            "broad_io_boundary",
        ),
        ("import sys\n\ndef sample(text):\n    try:\n        print(text.strip(), file=sys.stderr)\n" + _IO_HANDLER, "broad_io_boundary"),
        ("import os\n\ndef sample(pid):\n    try:\n        os.kill(pid, 0)\n        notify(pid)\n" + _IO_HANDLER, "observable_degrade"),
        ("def sample(text):\n    try:\n        return int(text)\n    except Exception:\n        return 0\n", "silent_default_fallback"),
        ("from app.helpers import write_fixed_text\n\ndef sample(path):\n    try:\n        write_fixed_text(path, '')\n" + _IO_HANDLER, "observable_degrade"),
        ("from .safe_files import write_fixed_text\n\ndef sample(path):\n    try:\n        write_fixed_text(path, '')\n" + _IO_HANDLER, "observable_degrade"),
    ],
    ids=["stdlib-io", "project-io-wrapper-and-pure-conversions", "builtin-io-and-local-value-method",
         "business-call-mixed-in", "no-io-call", "same-name-other-module", "same-name-relative-sibling"],
)
def test_broad_io_boundary_requires_every_try_call_resolved_to_io_or_pure_conversion(tmp_path, source, expected_kind):
    assert _kinds(tmp_path, source) == [(1, expected_kind)]


def test_startup_baseline_rejects_new_broad_io_entry_and_rebases_existing_one(tmp_path, monkeypatch):
    before = "import os\n\ndef sample(pid):\n    try:\n        os.kill(pid, 0)\n        notify(pid)\n" + _IO_HANDLER
    after = "import os\n\ndef sample(pid):\n    try:\n        os.kill(pid, 0)\n" + _IO_HANDLER
    existing = dict(build_silent_entry(_scan(tmp_path, before)[0], source="baseline_scan"), id="fallback:permanent-id")
    _write(tmp_path, PATH, after)
    _stub_startup_samples(monkeypatch, 1)
    root = str(tmp_path)

    with pytest.raises(QualityGateError, match="不登记台账"):
        operations.refresh_scan_startup_baseline(root, ledger_tools.default_ledger())
    stored = _ledger(existing)
    refreshed = operations.refresh_scan_startup_baseline(root, copy.deepcopy(stored))["silent_fallback"]["entries"]
    assert [(entry["id"], entry["fallback_kind"]) for entry in refreshed] == [("fallback:permanent-id", "broad_io_boundary")]


_DEGRADE_WITH_DEFAULT = (
    "def sample():\n    try:\n        work()\n    except Exception:\n        logger.warning('failed')\n        return None\n"
)


def test_kind_change_with_unchanged_handler_is_not_auto_aligned_and_needs_explicit_rebuild(tmp_path, monkeypatch):
    """处理器内容不变、只是分类器口径变了：自动刷新拒绝对齐，经 scan-startup-baseline 显式重建并保留永久 id。"""
    ctx = GateContext(str(tmp_path))
    _stub_startup_samples(monkeypatch, 1)
    current = _scan(tmp_path, _DEGRADE_WITH_DEFAULT)[0]
    stored = _ledger(dict(build_silent_entry(current, source="baseline_scan"), fallback_kind="silent_default_fallback"))
    ledger_tools.save_ledger(ctx.ledger_path, stored)

    with pytest.raises(QualityGateError, match="fallback_kind 与当前扫描不一致"):
        operations.validate_ledger_against_current_scan(ctx.repo_root, stored)
    with pytest.raises(QualityGateError, match="fallback_kind drift"):
        scan.run_strict_silent_fallback_gate(ctx, emit_json=False)
    with pytest.raises(QualityGateError, match="自动对齐被拒绝.*silent_default_fallback->observable_degrade"):
        operations.refresh_auto_fields(ctx.repo_root, copy.deepcopy(stored))

    rebuilt = operations.refresh_scan_startup_baseline(ctx.repo_root, copy.deepcopy(stored))["silent_fallback"]["entries"]
    assert [(entry["id"], entry["fallback_kind"]) for entry in rebuilt] == [(current["id"], "observable_degrade")]


_LEGACY_PATH = "/".join(("core", "services", "legacy_sample.py"))
_LEGACY_SWALLOW = "def sample(conn):\n    try:\n        conn.close()\n    except Exception:\n        pass\n"


def _legacy_scan(root):
    return _scan(root, _LEGACY_SWALLOW, rel_path=_LEGACY_PATH)


def test_architecture_view_marks_non_startup_legacy_swallow_without_rewriting_scan_entries(tmp_path):
    scanned = _legacy_scan(tmp_path)

    assert [entry["fallback_kind"] for entry in operations.architecture_silent_scan_entries(str(tmp_path), [_LEGACY_PATH])] == [
        "silent_swallow"
    ]
    assert [entry["fallback_kind"] for entry in scanned] == ["cleanup_best_effort"]


def test_check_auto_refresh_and_strict_gate_compare_through_one_scope_view(tmp_path, monkeypatch):
    """非启动链遗留吞异常原始扫描归 cleanup_best_effort、台账按 silent_swallow 登记；三处都经同一范围视图比较。"""
    ctx = GateContext(str(tmp_path))
    stored = _ledger(
        dict(
            build_silent_entry(_legacy_scan(tmp_path)[0], source="migrated_from_architecture_fitness_counter"),
            fallback_kind="silent_swallow",
        )
    )
    ledger_tools.save_ledger(ctx.ledger_path, stored)
    _stub_startup_samples(monkeypatch, 0)

    assert operations.validate_ledger_against_current_scan(ctx.repo_root, stored) == {"samples": {"count": 0}}
    assert scan.run_strict_silent_fallback_gate(ctx, emit_json=False) == 0
    refreshed = operations.refresh_auto_fields(ctx.repo_root, copy.deepcopy(stored))["silent_fallback"]["entries"]
    assert [(entry["id"], entry["fallback_kind"]) for entry in refreshed] == [
        (stored["silent_fallback"]["entries"][0]["id"], "silent_swallow"),
    ]


def _group_source(messages):
    return "def sample():\n" + "".join(
        "    try:\n"
        f"        work_{index}()\n"
        "    except Exception:\n"
        f"        logger.warning({message!r})\n"
        for index, message in enumerate(messages)
    )


def _scan_group(root, messages):
    return _scan(root, _group_source(messages))


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


def _refresh_against(root, stored, current_messages):
    """台账按旧源码登记，仓库里换成 current_messages 这份源码后自动刷新。"""
    _write(root, PATH, _group_source(current_messages))
    return operations.refresh_auto_fields(str(root), stored)


def test_deleted_handler_retires_its_entry_and_shifts_survivor_ordinals(tmp_path):
    stored = _group_ledger(_scan_group(tmp_path, ["a", "b", "c"]))
    current = _scan_group(tmp_path, ["b", "c"])

    entries = _refresh_against(tmp_path, copy.deepcopy(stored), ["b", "c"])["silent_fallback"]["entries"]

    assert [(entry["id"], entry["except_ordinal"]) for entry in entries] == [
        ("fallback:sample-1", 1), ("fallback:sample-2", 2),
    ]
    assert [entry["handler_context"] for entry in entries] == [item["handler_context"] for item in current]


def test_deletion_alignment_rejects_changed_survivor_ambiguous_group_and_accepted_risk(tmp_path):
    with pytest.raises(QualityGateError, match="自动对齐被拒绝"):
        _refresh_against(tmp_path, _group_ledger(_scan_group(tmp_path, ["a", "b", "c"])), ["b", "changed"])

    with pytest.raises(QualityGateError, match="自动对齐被拒绝"):
        _refresh_against(tmp_path, _group_ledger(_scan_group(tmp_path, ["a", "a", "b"])), ["a", "b"])

    with pytest.raises(QualityGateError, match="请先显式复核风险"):
        _refresh_against(
            tmp_path,
            _group_ledger(_scan_group(tmp_path, ["a", "b", "c"]), risk_entry_ids=["fallback:sample-0"]),
            ["b", "c"],
        )


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
def test_complexity_identity_keeps_same_named_methods_of_different_classes(tmp_path, monkeypatch, class_order):
    stored = ledger_tools.default_ledger()
    stored["complexity_allowlist"] = [build_complexity_entry(PATH, "A.shared", 17)]
    entry_id = stored["complexity_allowlist"][0]["id"]
    _write(tmp_path, PATH, "".join(_CLASS_SOURCES[name] for name in class_order))
    _stub_startup_samples(monkeypatch, 0)
    root = str(tmp_path)

    complexity_map = architecture_scan_cache.aggregate_architecture_scan(
        architecture_scan_cache.scan_files_with_cache(root, [PATH], fact_kinds=("complexity",)), include_all_complexity=True
    )["complexity_map"]
    assert complexity_map[f"{PATH}:A.shared"]["current_value"] == 17
    assert complexity_map[f"{PATH}:B.shared"]["current_value"] == 1
    assert operations.validate_ledger_against_current_scan(root, copy.deepcopy(stored)) == {"samples": {"count": 0}}
    refreshed = operations.refresh_auto_fields(root, copy.deepcopy(stored))["complexity_allowlist"]
    assert [(entry["id"], entry["current_value"]) for entry in refreshed] == [(entry_id, 17)]
    with pytest.raises(QualityGateError, match="不能标记为 fixed"):
        operations.set_entry_fields(root, copy.deepcopy(stored), entry_id, {"status": "fixed"})


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
def test_complexity_same_qualified_name_counts_highest_definition(tmp_path, source, expected_key):
    _write(tmp_path, PATH, source)

    complexity_map = architecture_scan_cache.aggregate_architecture_scan(
        architecture_scan_cache.scan_files_with_cache(str(tmp_path), [PATH], fact_kinds=("complexity",))
    )["complexity_map"]

    assert {key: item["current_value"] for key, item in complexity_map.items()} == {f"{PATH}:{expected_key}": 17}


def _legacy_complexity_entry(entry_id):
    entry = build_complexity_entry(PATH, "A.shared", 18)
    entry.update(id=entry_id, owner="legacy-owner", status="blocked", notes="已登记的人工复核结论")
    return entry


def test_startup_baseline_refresh_matches_complexity_entry_by_path_and_symbol(tmp_path, monkeypatch):
    stored = ledger_tools.default_ledger()
    stored["complexity_allowlist"] = [_legacy_complexity_entry("complexity:legacy-permanent-id")]
    _write(tmp_path, PATH, _CLASS_SOURCES["A"] + _CLASS_SOURCES["B"])
    _stub_startup_samples(monkeypatch, 0)
    root = str(tmp_path)

    refreshed = operations.refresh_scan_startup_baseline(root, copy.deepcopy(stored))["complexity_allowlist"]

    assert [
        (entry["id"], entry["symbol"], entry["owner"], entry["status"], entry["notes"], entry["current_value"])
        for entry in refreshed
    ] == [("complexity:legacy-permanent-id", "A.shared", "legacy-owner", "blocked", "已登记的人工复核结论", 17)]

    stored["complexity_allowlist"].append(_legacy_complexity_entry("complexity:legacy-duplicate-id"))
    with pytest.raises(QualityGateError, match="多条旧登记"):
        operations.refresh_scan_startup_baseline(root, copy.deepcopy(stored))


def test_startup_baseline_refresh_matches_oversize_entry_by_path(tmp_path, monkeypatch):
    stored = ledger_tools.default_ledger()
    legacy = build_oversize_entry(PATH, 600)
    legacy.update(id="oversize:legacy-permanent", owner="legacy-owner", status="blocked", notes="已登记的人工复核结论")
    stored["oversize_allowlist"] = [legacy]
    _write(tmp_path, PATH, "x = 1\n" * 501)
    _stub_startup_samples(monkeypatch, 0)

    refreshed = operations.refresh_scan_startup_baseline(str(tmp_path), copy.deepcopy(stored))["oversize_allowlist"]

    assert [
        (entry["id"], entry["owner"], entry["status"], entry["notes"], entry["current_value"]) for entry in refreshed
    ] == [("oversize:legacy-permanent", "legacy-owner", "blocked", "已登记的人工复核结论", 501)]


@pytest.mark.parametrize("complexity", [1, 15, 16, None], ids=["exit-1", "exit-15", "keep-16", "symbol-missing"])
def test_refresh_auto_fields_complexity_exit_alignment_and_fixed_rejection(tmp_path, complexity):
    """阈值严格大于 15：先判退出（open 与 fixed 都移除），仍超限的 fixed 才被拒；找不到符号直接报错。"""
    root = str(tmp_path)
    if complexity is None:
        _write(tmp_path, PATH, _CLASS_SOURCES["B"])
    else:
        _write(tmp_path, PATH, "class A:\n    def shared(self, x):\n" + _branchy_body("        ", "x", complexity - 1))
    open_ledger = ledger_tools.default_ledger()
    open_ledger["complexity_allowlist"] = [build_complexity_entry(PATH, "A.shared", 17)]
    entry_id = open_ledger["complexity_allowlist"][0]["id"]
    fixed_ledger = copy.deepcopy(open_ledger)
    fixed_ledger["complexity_allowlist"][0]["status"] = "fixed"
    risk_ledger = _group_ledger([], risk_entry_ids=[entry_id])
    risk_ledger["complexity_allowlist"] = copy.deepcopy(open_ledger["complexity_allowlist"])

    if complexity is None:
        with pytest.raises(QualityGateError, match="已无法通过当前扫描对齐"):
            operations.refresh_auto_fields(root, copy.deepcopy(open_ledger))
    elif complexity <= 15:
        for stored in (open_ledger, fixed_ledger):
            assert operations.refresh_auto_fields(root, copy.deepcopy(stored))["complexity_allowlist"] == []
        with pytest.raises(QualityGateError, match="已达成退出条件但仍被 accepted_risks 引用"):
            operations.refresh_auto_fields(root, risk_ledger)
        marked = operations.set_entry_fields(root, copy.deepcopy(open_ledger), entry_id, {"status": "fixed"})
        assert marked["complexity_allowlist"][0]["status"] == "fixed"
    else:
        refreshed = operations.refresh_auto_fields(root, copy.deepcopy(open_ledger))["complexity_allowlist"]
        assert [(entry["id"], entry["current_value"]) for entry in refreshed] == [(entry_id, 16)]
        with pytest.raises(QualityGateError, match="不能标记为 fixed"):
            operations.refresh_auto_fields(root, fixed_ledger)
