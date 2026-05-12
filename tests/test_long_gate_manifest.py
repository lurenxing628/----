from __future__ import annotations

import json
import subprocess
import sys

from tools import long_gate_manifest as manifest_mod
from tools import quality_gate_shared
from tools.test_registry import iter_startup_regressions


def _entry_by_id(manifest, entry_id):
    entries = list(manifest["entries"])
    for entry in entries:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing entry_id: {entry_id}")


def test_build_long_gate_manifest_uses_real_quality_gate_plan(monkeypatch, tmp_path):
    real_plan_builder = quality_gate_shared.build_quality_gate_command_plan
    real_plan = real_plan_builder()
    calls = []

    def spy_plan():
        calls.append("called")
        return real_plan_builder()

    monkeypatch.setattr(manifest_mod.quality_gate_shared, "build_quality_gate_command_plan", spy_plan)

    manifest = manifest_mod.build_long_gate_manifest(str(tmp_path))

    assert calls == ["called"]
    assert [entry["display"] for entry in manifest["entries"]] == [command["display"] for command in real_plan]
    assert manifest["quality_gate_plan_hash"] == quality_gate_shared.hash_quality_gate_commands(real_plan)


def test_manifest_contains_current_quality_gate_long_entries():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    entry_ids = {entry["entry_id"] for entry in manifest["entries"]}

    assert "pytest_collect_all" in entry_ids
    assert "full_test_debt" in entry_ids
    assert "ruff_check_full" in entry_ids
    assert "pyright_gate_full" in entry_ids
    assert "pyright_tools_full" in entry_ids
    assert "architecture_fitness" in entry_ids
    assert "required_regressions" in entry_ids
    assert "debt_ledger_sync" in entry_ids
    assert "startup_runtime_regressions" in entry_ids
    assert "quickref_vs_routes" in entry_ids


def test_manifest_entry_keeps_current_and_previous_fingerprint_slots():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    collect_entry = _entry_by_id(manifest, "pytest_collect_all")

    assert "fingerprint" in collect_entry
    assert "previous_success" in collect_entry
    assert "last_success_fingerprint" in collect_entry
    assert collect_entry["fingerprint"] is None
    assert collect_entry["previous_success"] is None
    assert collect_entry["last_success_fingerprint"] is None


def test_required_and_startup_regression_args_come_from_dynamic_plan():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    required_entry = _entry_by_id(manifest, "required_regressions")
    startup_entry = _entry_by_id(manifest, "startup_runtime_regressions")

    assert required_entry["args"][4:] == quality_gate_shared.iter_quality_gate_required_tests()
    assert startup_entry["args"][4:] == iter_startup_regressions()


def test_only_collect_entry_is_currently_reuse_enabled():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    enabled = [entry["entry_id"] for entry in manifest["entries"] if entry["reuse_allowed"]]
    planned_candidates = [
        entry["entry_id"]
        for entry in manifest["entries"]
        if entry.get("long_gate_candidate") and not entry.get("reuse_allowed")
    ]

    assert enabled == ["pytest_collect_all"]
    assert "full_test_debt" in planned_candidates
    assert "ruff_check_full" in planned_candidates
    assert _entry_by_id(manifest, "full_test_debt")["cache_status"] == "planned"


def test_pyright_tools_entry_tracks_quality_gate_tool_paths():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    pyright_tools = _entry_by_id(manifest, "pyright_tools_full")

    assert pyright_tools["input_file_scopes"] == quality_gate_shared.QUALITY_GATE_TOOL_PATHS
    assert set(quality_gate_shared.QUALITY_GATE_TOOL_PATHS) <= set(pyright_tools["tool_file_scopes"])


def test_include_local_receipts_reports_missing_history(tmp_path, capsys):
    assert manifest_mod.main(["--print", "--include-local-receipts", "--repo-root", str(tmp_path)]) == 0

    stdout = capsys.readouterr().out

    assert "No local QualityGate receipts found." in stdout
    assert "using command-plan based long-gate candidates" in stdout
    assert "pytest_collect_all" in stdout


def test_long_gate_manifest_can_run_as_script():
    result = subprocess.run(
        [sys.executable, "tools/long_gate_manifest.py", "--print"],
        cwd=quality_gate_shared.REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )

    assert "Long gate manifest" in result.stdout
    assert "pytest_collect_all" in result.stdout


def test_unknown_local_receipt_emits_warning(tmp_path):
    receipts_dir = tmp_path / "evidence" / "QualityGate" / "receipts"
    receipts_dir.mkdir(parents=True)
    receipt_path = receipts_dir / "01_unknown.json"
    receipt_path.write_text(
        json.dumps(
            {
                "display": "python tools/unknown_slow_command.py",
                "command_index": 1,
                "returncode": 0,
                "duration_s": 12.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    receipts = manifest_mod.load_local_quality_gate_receipts(str(tmp_path))
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(
        [
            {
                "display": "python -m pytest --collect-only -q tests",
                "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
                "capture_output": True,
                "output_policy": "normalized",
            }
        ],
        receipts=receipts,
        repo_root=str(tmp_path),
    )

    assert manifest["warnings"] == [
        "local receipt command is not in current plan: python tools/unknown_slow_command.py"
    ]


def test_load_local_receipts_tolerates_bad_numeric_fields(tmp_path):
    receipts_dir = tmp_path / "evidence" / "QualityGate" / "receipts"
    receipts_dir.mkdir(parents=True)
    receipt_path = receipts_dir / "bad_numeric.json"
    receipt_path.write_text(
        json.dumps(
            {
                "display": "python -m pytest --collect-only -q tests",
                "command_index": "bad",
                "returncode": "bad",
                "duration_s": "bad",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    receipts = manifest_mod.load_local_quality_gate_receipts(str(tmp_path))

    assert receipts[0]["command_index"] == 0
    assert receipts[0]["returncode"] == 0
    assert receipts[0]["duration_unknown"] is True
    assert "invalid numeric field: command_index='bad'" in receipts[0]["warnings"]
    assert "invalid numeric field: returncode='bad'" in receipts[0]["warnings"]
    assert "invalid numeric field: duration_s='bad'" in receipts[0]["warnings"]


def test_local_receipts_report_reuse_overhead_and_original_duration(tmp_path):
    receipts_dir = tmp_path / "evidence" / "QualityGate" / "receipts"
    receipts_dir.mkdir(parents=True)
    receipt_path = receipts_dir / "reuse.json"
    receipt_path.write_text(
        json.dumps(
            {
                "display": "python -m pytest --collect-only -q tests",
                "command_index": 1,
                "returncode": 0,
                "duration_s": 0.12,
                "duration_kind": "reuse_overhead",
                "original_duration_s": 8.5,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    receipts = manifest_mod.load_local_quality_gate_receipts(str(tmp_path))
    line = manifest_mod._format_receipt_line(receipts[0])

    assert "0.120s" in line
    assert "kind=reuse_overhead" in line
    assert "original=8.500s" in line


def test_unrecognized_pytest_command_is_not_positionally_classified_as_required_or_startup():
    plan = [
        {
            "display": "python -m pytest --collect-only -q tests",
            "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python -m pytest -q tests/test_sentinel_before_debt.py",
            "args": ["python", "-m", "pytest", "-q", "tests/test_sentinel_before_debt.py"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python scripts/sync_debt_ledger.py check",
            "args": ["python", "scripts/sync_debt_ledger.py", "check"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python -m pytest -q tests/test_sentinel_after_debt.py",
            "args": ["python", "-m", "pytest", "-q", "tests/test_sentinel_after_debt.py"],
            "capture_output": True,
            "output_policy": "normalized",
        },
    ]

    manifest = manifest_mod.build_manifest_from_quality_gate_plan(plan, repo_root=quality_gate_shared.REPO_ROOT)

    assert manifest["entries"][1]["entry_id"] == "unknown_02"
    assert manifest["entries"][1]["entry_type"] == "unknown"
    assert manifest["entries"][3]["entry_id"] == "unknown_04"
    assert manifest["entries"][3]["entry_type"] == "unknown"


def test_version_probe_entries_are_not_marked_as_reusable_long_gate_items():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    ruff_probe = _entry_by_id(manifest, "ruff_version_probe")
    pyright_probe = _entry_by_id(manifest, "pyright_version_probe")
    radon_probe = _entry_by_id(manifest, "radon_import_probe")

    assert ruff_probe["entry_type"] == "version_or_env_probe"
    assert pyright_probe["entry_type"] == "version_or_env_probe"
    assert radon_probe["entry_type"] == "version_or_env_probe"
    assert ruff_probe["reuse_allowed"] is False
    assert pyright_probe["reuse_allowed"] is False
    assert radon_probe["reuse_allowed"] is False
