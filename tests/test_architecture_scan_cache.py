"""回归测试：architecture_scan_cache 塌缩后的直扫门面契约——scan_files_with_cache 对每个请求路径直扫并保持旧签名（cache_path/force 为无作用遗留参数、绝不再写磁盘缓存文件）、fact 字段齐备且 silent 处理器不带 id（id 仅在聚合层赋予并与直扫结果一致）、architecture_scan_cache_metadata 保持指纹系统依赖的字段集；并守护 ledger 校验/刷新按 fact_kinds 分桶调用扫描门面、architecture_fitness 长门禁保持 planned/不可复用且新旧缓存产物路径仍被 git hook 拦截提交。"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, List, Tuple

from tools import (
    architecture_scan_cache as scan_cache,
)
from tools import (
    git_hook_checks,
    long_gate_manifest,
    quality_gate_shared,
)
from tools import (
    quality_gate_operations as operations,
)
from tools.quality_gate_scan import ScanContext, scan_silent_fallback_entries


def _source(*, marker: str = "") -> str:
    extra = f"\n# {marker}\n" if marker else "\n"
    return (
        "def fallback(value):\n"
        "    try:\n"
        "        return int(value)\n"
        "    except Exception:\n"
        "        return 0\n"
        "\n"
        "def assemble(g):\n"
        "    return BatchService(g.db)\n"
        "\n"
        "def repo_drift(self):\n"
        "    return self._repos.scheduler\n"
        + extra
    )


def _complex_source() -> str:
    lines = ["def complicated(value):"]
    for index in range(18):
        lines.append(f"    if value == {index}:")
        lines.append(f"        return {index}")
    lines.append("    return -1")
    return "\n".join(lines) + "\n"


def _context(sources: Dict[str, str]) -> ScanContext:
    return ScanContext(
        read_text=lambda path: sources[str(path).replace("\\", "/")],
        collect_globbed=lambda _patterns: sorted(sources),
    )


def _spy_single_file_scan(monkeypatch) -> List[str]:
    calls: List[str] = []
    original = scan_cache.scan_single_file_architecture_fact

    def spy(rel_path, context=None, fact_kinds=None):
        calls.append(str(rel_path))
        return original(rel_path, context=context, fact_kinds=fact_kinds)

    monkeypatch.setattr(scan_cache, "scan_single_file_architecture_fact", spy)
    return calls


def test_scan_returns_valid_fact_and_never_writes_cache_file(tmp_path: Path, monkeypatch) -> None:
    sources = {"core/services/example.py": _source()}
    cache_path = tmp_path / "architecture_scan_cache.json"
    calls = _spy_single_file_scan(monkeypatch)

    facts = scan_cache.scan_files_with_cache(
        ["core/services/example.py"], cache_path=str(cache_path), context=_context(sources)
    )

    assert calls == ["core/services/example.py"]
    assert not cache_path.exists(), "塌缩后绝不再写磁盘缓存文件"
    fact = facts[0]
    assert fact["schema_version"] == scan_cache.ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION
    assert fact["path"] == "core/services/example.py"
    assert sorted(fact["fact_kinds"]) == ["complexity", "repository", "request", "silent"]
    assert fact["line_count"] > 0
    assert fact["silent_fallback_handlers_without_global_id"]
    assert "id" not in fact["silent_fallback_handlers_without_global_id"][0]
    assert fact["request_service_direct_assembly_entries"]
    assert fact["repository_bundle_drift_entries"]

    # force=True 是塌缩前遗留参数：结果一致，也不产生缓存文件
    forced = scan_cache.scan_files_with_cache(
        ["core/services/example.py"], cache_path=str(cache_path), force=True, context=_context(sources)
    )
    assert forced == facts
    assert not cache_path.exists()


def test_every_call_rescans_each_requested_path(monkeypatch) -> None:
    sources = {
        "core/services/example.py": _source(),
        "core/services/other.py": "def other():\n    return 1\n",
    }
    calls = _spy_single_file_scan(monkeypatch)

    scan_cache.scan_files_with_cache(sorted(sources), context=_context(sources))
    scan_cache.scan_files_with_cache(["core/services/example.py"], context=_context(sources))

    assert calls == [
        "core/services/example.py",
        "core/services/other.py",
        "core/services/example.py",
    ]


def test_scan_scope_controls_aggregate_membership(tmp_path: Path) -> None:
    sources = {
        "core/services/example.py": _source(),
        "core/services/added.py": _complex_source(),
    }

    facts = scan_cache.scan_files_with_cache(sorted(sources), context=_context(sources))
    aggregate = scan_cache.aggregate_architecture_scan(facts)
    assert any(str(item.get("path")) == "core/services/added.py" for item in aggregate["complexity_entries"])

    remaining_facts = scan_cache.scan_files_with_cache(["core/services/example.py"], context=_context(sources))
    remaining_aggregate = scan_cache.aggregate_architecture_scan(remaining_facts, include_all_complexity=True)
    paths = {str(item.get("path")) for item in remaining_aggregate["complexity_entries"]}
    assert "core/services/added.py" not in paths


def test_metadata_keeps_fingerprint_fields(tmp_path: Path) -> None:
    metadata = scan_cache.architecture_scan_cache_metadata()

    assert metadata["schema_version"] == scan_cache.ARCHITECTURE_SCAN_CACHE_SCHEMA_VERSION
    assert metadata["scanner_schema_version"] == scan_cache.ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION
    assert metadata["scanner_version_hash"]
    assert metadata["python_version"]
    assert metadata["radon_version_or_behavior_hash"]
    assert set(metadata) == {
        "schema_version",
        "scanner_version_hash",
        "scanner_schema_version",
        "python_version",
        "radon_version_or_behavior_hash",
    }


def test_ledger_validation_and_refresh_use_architecture_scan(monkeypatch) -> None:
    silent_path = "web/bootstrap/sample.py"
    silent_handler = {
        "path": silent_path,
        "symbol": "boot",
        "handler_fingerprint": "sha1:1234567890abcdef",
        "handler_context_hash": "sha1:ctx",
        "except_ordinal": 1,
        "line_start": 10,
        "line_end": 11,
        "legacy_swallow_hit": True,
        "fallback_kind": "silent_swallow",
        "signature": "return-constant",
        "scope_tag": "startup_guard",
    }
    silent_id = scan_cache.aggregate_architecture_scan(
        [
            {
                "schema_version": scan_cache.ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION,
                "path": silent_path,
                "fact_kinds": ["silent"],
                "line_count": 20,
                "silent_fallback_handlers_without_global_id": [silent_handler],
                "complexity_blocks_all": [],
                "request_service_direct_assembly_entries": [],
                "repository_bundle_drift_entries": [],
            }
        ]
    )["silent_fallback_entries"][0]["id"]
    ledger = {
        "oversize_allowlist": [
            {
                "id": "oversize:sample-large",
                "path": "sample_large.py",
                "status": "open",
                "owner": "NEXT-8",
                "batch": "NEXT-8",
                "exit_condition": "drop below limit",
                "last_verified_at": "2026-05-15T00:00:00+08:00",
                "current_value": quality_gate_shared.FILE_SIZE_LIMIT + 1,
                "limit": quality_gate_shared.FILE_SIZE_LIMIT,
            }
        ],
        "complexity_allowlist": [
            {
                "id": "complexity:sample-complex-too_complex",
                "path": "sample_complex.py",
                "symbol": "too_complex",
                "status": "open",
                "owner": "NEXT-8",
                "batch": "NEXT-8",
                "exit_condition": "drop below threshold",
                "last_verified_at": "2026-05-15T00:00:00+08:00",
                "current_value": quality_gate_shared.COMPLEXITY_THRESHOLD + 1,
                "threshold": quality_gate_shared.COMPLEXITY_THRESHOLD,
            }
        ],
        "silent_fallback": {
            "scope": ["web/bootstrap/**/*.py"],
            "entries": [
                {
                    "id": silent_id,
                    **silent_handler,
                    "status": "open",
                    "owner": "NEXT-8",
                    "batch": "NEXT-8",
                    "exit_condition": "keep observable",
                    "last_verified_at": "2026-05-15T00:00:00+08:00",
                    "source": "baseline_scan",
                }
            ],
        },
        "accepted_risks": [],
    }
    calls: List[Tuple[str, ...]] = []

    def fake_fact(path: str) -> Dict[str, object]:
        if path == "sample_large.py":
            line_count = quality_gate_shared.FILE_SIZE_LIMIT + 1
        else:
            line_count = 20
        return {
            "schema_version": scan_cache.ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION,
            "path": path,
            "fact_kinds": ["complexity", "silent"],
            "line_count": line_count,
            "silent_fallback_handlers_without_global_id": [silent_handler] if path == silent_path else [],
            "complexity_blocks_all": [
                {
                    "path": "sample_complex.py",
                    "symbol": "too_complex",
                    "current_value": quality_gate_shared.COMPLEXITY_THRESHOLD + 1,
                    "threshold": quality_gate_shared.COMPLEXITY_THRESHOLD,
                    "line": 1,
                    "rank": "C",
                }
            ] if path == "sample_complex.py" else [],
            "request_service_direct_assembly_entries": [],
            "repository_bundle_drift_entries": [],
        }

    def fake_scan_files(paths, cache_path=None, force=False, context=None, fact_kinds=None):
        del cache_path, force, context
        calls.append(tuple(fact_kinds or ()))
        return [fake_fact(str(path)) for path in paths]

    monkeypatch.setattr(operations, "scan_files_with_cache", fake_scan_files)
    monkeypatch.setattr(operations, "validate_ledger", lambda _ledger: None)
    monkeypatch.setattr(operations, "_direct_validate_startup_samples", lambda _entries=None: {"matched": 0})
    monkeypatch.setattr(operations, "finalize_ledger_update", lambda current: current)

    operations.validate_ledger_against_current_scan(copy.deepcopy(ledger))
    operations.refresh_auto_fields(copy.deepcopy(ledger))

    assert () in calls
    assert ("complexity",) in calls
    assert ("silent",) in calls


def test_silent_fallback_id_assignment_stays_in_aggregate(tmp_path: Path) -> None:
    sources = {"core/services/example.py": _source()}
    context = _context(sources)

    facts = scan_cache.scan_files_with_cache(["core/services/example.py"], context=context)
    raw_handler = facts[0]["silent_fallback_handlers_without_global_id"][0]
    aggregate = scan_cache.aggregate_architecture_scan(facts)
    direct_entries = scan_silent_fallback_entries(["core/services/example.py"], context=context)

    assert "id" not in raw_handler
    assert [entry["id"] for entry in aggregate["silent_fallback_entries"]] == [entry["id"] for entry in direct_entries]


def test_architecture_fitness_stays_planned_and_artifact_is_blocked() -> None:
    manifest = long_gate_manifest.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(),
        repo_root=quality_gate_shared.REPO_ROOT,
    )
    entries = {entry["entry_id"]: entry for entry in manifest["entries"]}

    assert entries["architecture_fitness"]["cache_status"] == "planned"
    assert entries["architecture_fitness"]["reuse_allowed"] is False
    enabled = [entry["entry_id"] for entry in manifest["entries"] if entry["reuse_allowed"]]
    assert enabled == [
        "pytest_collect_all",
        "full_test_debt",
        "ruff_check_full",
        "pyright_gate_full",
        "pyright_tools_full",
        "required_regressions",
        "debt_ledger_sync",
        "startup_runtime_regressions",
        "quickref_vs_routes",
    ]
    assert git_hook_checks._blocked_paths(["evidence/QualityGate/long_gate/results/architecture_fitness.success.json"]) == [
        (
            "evidence/QualityGate/long_gate/results/architecture_fitness.success.json",
            "长耗时门禁缓存是本地运行产物，不应该混进普通提交",
        )
    ]
    assert git_hook_checks._blocked_paths([scan_cache.ARCHITECTURE_SCAN_CACHE_REL]) == [
        (
            scan_cache.ARCHITECTURE_SCAN_CACHE_REL,
            "architecture scan 文件级缓存是运行产物，应由当前门禁重新生成",
        )
    ]
