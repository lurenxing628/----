from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Dict, List

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


def _read_cache(cache_path: Path) -> dict:
    return json.loads(cache_path.read_text(encoding="utf-8"))


def _write_cache(cache_path: Path, payload: dict) -> None:
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _spy_single_file_scan(monkeypatch) -> List[str]:
    calls: List[str] = []
    original = scan_cache.scan_single_file_architecture_fact

    def spy(rel_path, context=None, fact_kinds=None):
        calls.append(str(rel_path))
        return original(rel_path, context=context, fact_kinds=fact_kinds)

    monkeypatch.setattr(scan_cache, "scan_single_file_architecture_fact", spy)
    return calls


def test_cache_miss_scans_single_file_and_writes_fact(tmp_path: Path, monkeypatch) -> None:
    sources = {"core/services/example.py": _source()}
    cache_path = tmp_path / "architecture_scan_cache.json"
    calls = _spy_single_file_scan(monkeypatch)

    facts = scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))

    assert calls == ["core/services/example.py"]
    assert cache_path.exists()
    payload = _read_cache(cache_path)
    assert payload["schema_version"] == scan_cache.ARCHITECTURE_SCAN_CACHE_SCHEMA_VERSION
    assert payload["scanner_version_hash"]
    assert payload["scanner_schema_version"] == scan_cache.ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION
    assert payload["python_version"]
    assert payload["radon_version_or_behavior_hash"]
    row = payload["files"]["core/services/example.py"]
    assert row["file_sha256"]
    assert row["fact"] == facts[0]
    assert row["fact"]["silent_fallback_handlers_without_global_id"]
    assert "id" not in row["fact"]["silent_fallback_handlers_without_global_id"][0]


def test_unchanged_file_reuses_fact_and_generated_at_is_only_record(tmp_path: Path, monkeypatch) -> None:
    sources = {"core/services/example.py": _source()}
    cache_path = tmp_path / "architecture_scan_cache.json"
    first_calls = _spy_single_file_scan(monkeypatch)
    first_facts = scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    assert first_calls == ["core/services/example.py"]

    payload = _read_cache(cache_path)
    payload["generated_at"] = "1999-01-01T00:00:00+08:00"
    _write_cache(cache_path, payload)
    second_calls = _spy_single_file_scan(monkeypatch)
    second_facts = scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))

    assert second_calls == []
    assert second_facts == first_facts


def test_file_content_change_rescans_only_that_file(tmp_path: Path, monkeypatch) -> None:
    sources = {
        "core/services/example.py": _source(),
        "core/services/other.py": "def other():\n    return 1\n",
    }
    cache_path = tmp_path / "architecture_scan_cache.json"
    scan_cache.scan_files_with_cache(sorted(sources), cache_path=str(cache_path), context=_context(sources))
    sources["core/services/example.py"] = _source(marker="changed")
    calls = _spy_single_file_scan(monkeypatch)

    scan_cache.scan_files_with_cache(sorted(sources), cache_path=str(cache_path), context=_context(sources))

    assert calls == ["core/services/example.py"]


def test_added_file_enters_aggregate_and_deleted_file_is_ignored(tmp_path: Path, monkeypatch) -> None:
    sources = {"core/services/example.py": _source()}
    cache_path = tmp_path / "architecture_scan_cache.json"
    scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    sources["core/services/added.py"] = _complex_source()
    calls = _spy_single_file_scan(monkeypatch)

    facts = scan_cache.scan_files_with_cache(sorted(sources), cache_path=str(cache_path), context=_context(sources))
    aggregate = scan_cache.aggregate_architecture_scan(facts)

    assert calls == ["core/services/added.py"]
    assert any(str(item.get("path")) == "core/services/added.py" for item in aggregate["complexity_entries"])

    remaining_facts = scan_cache.scan_files_with_cache(
        ["core/services/example.py"],
        cache_path=str(cache_path),
        context=_context(sources),
    )
    remaining_aggregate = scan_cache.aggregate_architecture_scan(remaining_facts, include_all_complexity=True)
    paths = {str(item.get("path")) for item in remaining_aggregate["complexity_entries"]}
    assert "core/services/added.py" not in paths


def test_bad_cache_json_missing_fields_and_file_sha_mismatch_rescan(tmp_path: Path, monkeypatch) -> None:
    sources = {"core/services/example.py": _source()}
    cache_path = tmp_path / "architecture_scan_cache.json"

    cache_path.write_text("{not json", encoding="utf-8")
    corrupt_calls = _spy_single_file_scan(monkeypatch)
    scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    assert corrupt_calls == ["core/services/example.py"]

    payload = _read_cache(cache_path)
    payload.pop("files")
    _write_cache(cache_path, payload)
    missing_top_calls = _spy_single_file_scan(monkeypatch)
    scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    assert missing_top_calls == ["core/services/example.py"]

    payload = _read_cache(cache_path)
    payload.pop("generated_at")
    _write_cache(cache_path, payload)
    missing_generated_at_calls = _spy_single_file_scan(monkeypatch)
    scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    assert missing_generated_at_calls == ["core/services/example.py"]

    payload = _read_cache(cache_path)
    payload["files"]["core/services/example.py"]["fact"].pop("line_count")
    _write_cache(cache_path, payload)
    missing_fact_calls = _spy_single_file_scan(monkeypatch)
    scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    assert missing_fact_calls == ["core/services/example.py"]

    payload = _read_cache(cache_path)
    payload["files"]["core/services/example.py"]["fact"]["fact_kinds"] = ["not_a_kind"]
    _write_cache(cache_path, payload)
    unknown_kind_calls = _spy_single_file_scan(monkeypatch)
    scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    assert unknown_kind_calls == ["core/services/example.py"]

    detail_mutations = [
        ("silent_fallback_handlers_without_global_id", "handler_context_hash"),
        ("complexity_blocks_all", "current_value"),
        ("request_service_direct_assembly_entries", "target"),
        ("repository_bundle_drift_entries", "chain"),
    ]
    for field, missing_field in detail_mutations:
        payload = _read_cache(cache_path)
        row = payload["files"]["core/services/example.py"]["fact"]
        assert row[field]
        row[field][0].pop(missing_field)
        _write_cache(cache_path, payload)
        detail_calls = _spy_single_file_scan(monkeypatch)
        scan_cache.scan_files_with_cache(
            ["core/services/example.py"],
            cache_path=str(cache_path),
            context=_context(sources),
        )
        assert detail_calls == ["core/services/example.py"]

    payload = _read_cache(cache_path)
    payload["files"]["core/services/example.py"]["file_sha256"] = "bad"
    _write_cache(cache_path, payload)
    bad_sha_calls = _spy_single_file_scan(monkeypatch)
    scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    assert bad_sha_calls == ["core/services/example.py"]


def test_metadata_changes_rescan_all_files(tmp_path: Path, monkeypatch) -> None:
    sources = {"core/services/example.py": _source()}
    cache_path = tmp_path / "architecture_scan_cache.json"
    scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))

    for field, value in [
        ("scanner_version_hash", "sha256:old"),
        ("schema_version", scan_cache.ARCHITECTURE_SCAN_CACHE_SCHEMA_VERSION + 1),
        ("scanner_schema_version", scan_cache.ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION + 1),
        ("python_version", "3.8.0-old"),
        ("radon_version_or_behavior_hash", "version:old"),
    ]:
        payload = _read_cache(cache_path)
        payload[field] = value
        _write_cache(cache_path, payload)
        calls = _spy_single_file_scan(monkeypatch)
        scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
        assert calls == ["core/services/example.py"]


def test_ledger_allowlist_change_reaggregates_without_rescanning_ast(tmp_path: Path, monkeypatch) -> None:
    sources = {"core/services/example.py": _source()}
    cache_path = tmp_path / "architecture_scan_cache.json"
    facts = scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    aggregate = scan_cache.aggregate_architecture_scan(facts)
    entry_id = str(aggregate["silent_fallback_entries"][0]["id"])

    calls = _spy_single_file_scan(monkeypatch)
    reused_facts = scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=_context(sources))
    reused_aggregate = scan_cache.aggregate_architecture_scan(reused_facts)
    allowlist_empty = {}
    allowlist_with_entry = {entry_id: {"id": entry_id}}

    assert calls == []
    assert [entry["id"] for entry in reused_aggregate["silent_fallback_entries"] if entry["id"] not in allowlist_empty] == [entry_id]
    assert [entry["id"] for entry in reused_aggregate["silent_fallback_entries"] if entry["id"] not in allowlist_with_entry] == []


def test_ledger_validation_and_refresh_use_architecture_scan_cache(monkeypatch) -> None:
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
    calls: List[tuple[str, ...]] = []

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
    cache_path = tmp_path / "architecture_scan_cache.json"

    facts = scan_cache.scan_files_with_cache(["core/services/example.py"], cache_path=str(cache_path), context=context)
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
