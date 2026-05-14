from __future__ import annotations

import json
import subprocess
import sys

from tools import long_gate_manifest as manifest_mod
from tools import quality_gate_shared
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_schema import (
    LONG_GATE_CACHE_SCHEMA_VERSION,
    LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
    LONG_GATE_MANIFEST_SCHEMA_VERSION,
)
from tools.test_registry import (
    iter_required_tests,
    iter_startup_regressions,
    validate_required_regression_group_coverage,
)


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


def test_manifest_uses_shared_long_gate_schema_versions():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    collect_entry = _entry_by_id(manifest, "pytest_collect_all")
    planned_entry = _entry_by_id(manifest, "full_test_debt")

    assert manifest["schema_version"] == LONG_GATE_MANIFEST_SCHEMA_VERSION
    assert collect_entry["schema_version"] == LONG_GATE_MANIFEST_SCHEMA_VERSION
    assert collect_entry["cache_schema_version"] == LONG_GATE_CACHE_SCHEMA_VERSION
    assert collect_entry["fingerprint_schema_version"] == LONG_GATE_FINGERPRINT_SCHEMA_VERSION
    assert planned_entry["schema_version"] == LONG_GATE_MANIFEST_SCHEMA_VERSION
    assert planned_entry["cache_schema_version"] == LONG_GATE_CACHE_SCHEMA_VERSION
    assert planned_entry["fingerprint_schema_version"] == LONG_GATE_FINGERPRINT_SCHEMA_VERSION


def test_required_and_startup_regression_args_come_from_dynamic_plan():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    required_entry = _entry_by_id(manifest, "required_regressions")
    startup_entry = _entry_by_id(manifest, "startup_runtime_regressions")

    assert required_entry["args"][4:] == quality_gate_shared.iter_quality_gate_required_tests()
    assert startup_entry["args"][4:] == iter_startup_regressions()


def test_required_groups_cover_required_registry():
    coverage = validate_required_regression_group_coverage(iter_required_tests())

    assert coverage["missing"] == []
    assert coverage["duplicates"] == []
    assert coverage["unknown"] == []
    assert coverage["required_target_count"] == len(iter_required_tests())
    assert coverage["group_target_count"] == len(iter_required_tests())
    assert coverage["group_count"] == 8
    assert coverage["required_registry_hash"]
    assert coverage["group_registry_hash"]


def test_required_group_registry_reports_missing_target():
    required = iter_required_tests()
    groups = [
        {
            "group_id": "almost_all",
            "target_paths": required[1:],
        }
    ]

    coverage = validate_required_regression_group_coverage(required, groups)

    assert coverage["missing"] == [required[0]]


def test_required_group_registry_reports_duplicate_target():
    required = iter_required_tests()
    groups = [
        {
            "group_id": "first",
            "target_paths": [required[0]],
        },
        {
            "group_id": "second",
            "target_paths": [required[0], *required[1:]],
        },
    ]

    coverage = validate_required_regression_group_coverage(required, groups)

    assert coverage["duplicates"] == [{"path": required[0], "groups": ["first", "second"]}]


def test_required_group_registry_reports_unknown_target():
    required = iter_required_tests()
    unknown = "tests/test_not_in_required_registry.py"
    groups = [
        {
            "group_id": "with_extra",
            "target_paths": [*required, unknown],
        }
    ]

    coverage = validate_required_regression_group_coverage(required, groups)

    assert coverage["unknown"] == [unknown]


def test_required_parent_entry_still_matches_real_command_plan():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    required_entry = _entry_by_id(manifest, "required_regressions")
    command_by_display = {command["display"]: command for command in command_plan}

    assert required_entry["display"] in command_by_display
    assert required_entry["args"] == command_by_display[required_entry["display"]]["args"]
    assert required_entry["args"][4:] == iter_required_tests()


def test_required_group_entries_have_stable_ids():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    required_entry = _entry_by_id(manifest, "required_regressions")

    assert [group["entry_id"] for group in required_entry["groups"]] == [
        "required_regressions.quality_gate",
        "required_regressions.scheduler_config",
        "required_regressions.scheduler_run_core",
        "required_regressions.scheduler_analysis_gantt_reports_week_plan",
        "required_regressions.scheduler_batches_material_resource",
        "required_regressions.request_services_runtime_error_boundary",
        "required_regressions.frontend_manual_excel",
        "required_regressions.ui_layout_presenters_system",
    ]
    assert required_entry["groups"][0]["output_result_files"] == [
        "evidence/QualityGate/required_regressions/groups/quality_gate.json"
    ]


def test_required_group_scope_policy_is_recorded():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    required_entry = _entry_by_id(manifest, "required_regressions")
    quality_gate = next(group for group in required_entry["groups"] if group["group_id"] == "quality_gate")
    scheduler_config = next(group for group in required_entry["groups"] if group["group_id"] == "scheduler_config")
    analysis = next(
        group
        for group in required_entry["groups"]
        if group["group_id"] == "scheduler_analysis_gantt_reports_week_plan"
    )
    ui_layout = next(group for group in required_entry["groups"] if group["group_id"] == "ui_layout_presenters_system")

    assert required_entry["required_regression_group_scope_policy"]["common_input_file_scopes"] == [
        "tests/conftest.py",
        "conftest.py",
        "tests/main_style_regression_runner.py",
        "tests/runtime_cleanup_helper.py",
    ]
    assert required_entry["required_regression_group_scope_policy"]["scope_policy_hash"]
    assert scheduler_config["scope_policy_hash"]
    assert scheduler_config["common_config_file_scopes"] == [
        "pytest.ini",
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        "tools/test_registry.py",
        "tools/quality_gate_shared.py",
        "tools/quality_gate_support.py",
        "scripts/run_quality_gate.py",
    ]
    assert set(scheduler_config["target_paths"]) <= set(scheduler_config["input_file_scopes"])
    assert "tests/long_gate_cache_helpers.py" in quality_gate["group_input_file_scopes"]
    assert "web/routes/domains/scheduler/scheduler_config*.py" in scheduler_config["group_input_file_scopes"]
    assert "web/routes/domains/scheduler/scheduler_config*.py" not in analysis["group_input_file_scopes"]
    assert {"node_executable_realpath", "node_version", "PATH"} <= set(analysis["group_env_keys"])
    assert "CI" in ui_layout["group_env_keys"]
    assert "tools/test_registry.py" in scheduler_config["config_file_scopes"]
    assert "tools/test_registry.py" in analysis["config_file_scopes"]


def test_required_group_scopes_do_not_include_other_group_test_targets():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    required_entry = _entry_by_id(manifest, "required_regressions")
    groups = [dict(group) for group in required_entry["groups"]]

    for group in groups:
        other_targets = {
            str(target)
            for other in groups
            if other["group_id"] != group["group_id"]
            for target in list(other.get("target_paths") or [])
        }
        assert not (set(group["input_file_scopes"]) & other_targets)


def test_required_parent_scope_includes_group_specific_scope_union():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    required_entry = _entry_by_id(manifest, "required_regressions")

    assert "web/routes/domains/scheduler/scheduler_config*.py" in required_entry["input_file_scopes"]
    assert "tools/long_gate_cache.py" in required_entry["tool_file_scopes"]
    assert "node_version" in required_entry["env_keys"]


def test_required_group_specific_scope_not_leaked_to_other_group_fingerprints(tmp_path):
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=str(tmp_path))
    required_entry = _entry_by_id(manifest, "required_regressions")
    scheduler_config = next(group for group in required_entry["groups"] if group["group_id"] == "scheduler_config")
    analysis = next(
        group
        for group in required_entry["groups"]
        if group["group_id"] == "scheduler_analysis_gantt_reports_week_plan"
    )

    before_parent = fingerprint_entry(required_entry, str(tmp_path))
    before_config = fingerprint_entry(scheduler_config, str(tmp_path))
    before_analysis = fingerprint_entry(analysis, str(tmp_path))
    changed = tmp_path / "web" / "routes" / "domains" / "scheduler" / "scheduler_config_feedback.py"
    changed.parent.mkdir(parents=True)
    changed.write_text("CONFIG_MARKER = True\n", encoding="utf-8")
    after_parent = fingerprint_entry(required_entry, str(tmp_path))
    after_config = fingerprint_entry(scheduler_config, str(tmp_path))
    after_analysis = fingerprint_entry(analysis, str(tmp_path))

    assert before_parent["hash"] != after_parent["hash"]
    assert before_config["hash"] != after_config["hash"]
    assert before_analysis["hash"] == after_analysis["hash"]


def test_required_groups_are_not_top_level_commands():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    entry_ids = [entry["entry_id"] for entry in manifest["entries"]]

    assert len(manifest["entries"]) == len(command_plan)
    assert "required_regressions" in entry_ids
    assert all(not entry_id.startswith("required_regressions.") for entry_id in entry_ids)
    assert _entry_by_id(manifest, "required_regressions")["groups"]


def test_collect_full_test_debt_required_and_startup_entries_are_currently_reuse_enabled():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    enabled = [entry["entry_id"] for entry in manifest["entries"] if entry["reuse_allowed"]]
    planned_candidates = [
        entry["entry_id"]
        for entry in manifest["entries"]
        if entry.get("long_gate_candidate") and not entry.get("reuse_allowed")
    ]

    full_test_debt = _entry_by_id(manifest, "full_test_debt")
    required = _entry_by_id(manifest, "required_regressions")
    startup = _entry_by_id(manifest, "startup_runtime_regressions")

    assert enabled == ["pytest_collect_all", "full_test_debt", "required_regressions", "startup_runtime_regressions"]
    assert "ruff_check_full" in planned_candidates
    assert "codestable/tools/**/*.py" in full_test_debt["config_file_scopes"]
    assert full_test_debt["cache_status"] == "enabled"
    assert "evidence/QualityGate/collect_nodeids.json" in full_test_debt["input_file_scopes"]
    assert "scripts/**/*.py" in full_test_debt["input_file_scopes"]
    assert "desktop/**/*.py" in full_test_debt["input_file_scopes"]
    assert "audit/**/*.py" in full_test_debt["input_file_scopes"]
    assert "assets/**/*" in full_test_debt["input_file_scopes"]
    assert "installer/**/*" in full_test_debt["input_file_scopes"]
    assert "build_win7*.bat" in full_test_debt["input_file_scopes"]
    assert required["cache_status"] == "enabled"
    assert required["input_file_scopes"][: len(required["args"][4:])] == required["args"][4:]
    assert "core/**/*.py" in required["input_file_scopes"]
    assert "templates/**/*.html" in required["input_file_scopes"]
    assert "templates_excel/**/*" in required["input_file_scopes"]
    assert "evidence/QualityGate/required_regressions.json" in required["output_result_files"]
    assert {
        group["output_result_files"][0] for group in required["groups"]
    } <= set(required["output_result_files"])
    assert "templates/**/*.html" in full_test_debt["input_file_scopes"]
    assert "templates_excel/**/*" in full_test_debt["input_file_scopes"]
    assert "static/**/*" in full_test_debt["input_file_scopes"]
    assert "audit/**/*.md" in full_test_debt["input_file_scopes"]
    assert "docs/**/*.md" in full_test_debt["input_file_scopes"]
    assert "evidence/current/README.md" in full_test_debt["input_file_scopes"]
    assert ".limcode/skills/**/*" in full_test_debt["input_file_scopes"]
    assert ".limcode/plans/**/*" in full_test_debt["input_file_scopes"]
    assert "开发文档/**/*.md" in full_test_debt["input_file_scopes"]
    assert "validate_dist_exe.py" in full_test_debt["input_file_scopes"]
    assert full_test_debt["output_result_files"] == [
        "evidence/QualityGate/current_full_test_debt.json",
        "evidence/QualityGate/full_test_debt_summary.json",
        "evidence/QualityGate/full_test_debt_node_cache.json",
    ]
    assert startup["cache_status"] == "enabled"
    assert startup["args"][4:] == iter_startup_regressions()
    assert startup["output_result_files"] == ["evidence/QualityGate/startup_runtime_regressions.json"]
    assert "web/bootstrap/**/*.py" in startup["input_file_scopes"]
    assert "templates/**/*.html" in startup["input_file_scopes"]
    assert "static/**/*" in startup["input_file_scopes"]
    assert "schema.sql" in startup["input_file_scopes"]
    assert "docs/**/*.md" not in startup["input_file_scopes"]
    assert "audit/**/*.md" not in startup["input_file_scopes"]
    assert "开发文档/**/*.md" not in startup["input_file_scopes"]
    assert "APS_ENV" in startup["env_keys"]
    assert "APS_DB_PATH" in startup["env_keys"]
    assert "APS_LOG_DIR" in startup["env_keys"]
    assert "APS_BACKUP_DIR" in startup["env_keys"]
    assert "APS_EXCEL_TEMPLATE_DIR" in startup["env_keys"]
    assert "APS_CHROME_PATH" in startup["env_keys"]
    assert "PYTHONPATH" in startup["env_keys"]
    assert "PYTHONUTF8" in startup["env_keys"]
    assert "PYTHONIOENCODING" in startup["env_keys"]


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


def test_local_receipts_without_duration_display_duration_unknown(tmp_path):
    receipts_dir = tmp_path / "evidence" / "QualityGate" / "receipts"
    receipts_dir.mkdir(parents=True)
    receipt_path = receipts_dir / "missing_duration.json"
    receipt_path.write_text(
        json.dumps(
            {
                "display": "python -m pytest --collect-only -q tests",
                "command_index": 1,
                "returncode": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    receipts = manifest_mod.load_local_quality_gate_receipts(str(tmp_path))
    line = manifest_mod._format_receipt_line(receipts[0])

    assert receipts[0]["duration_unknown"] is True
    assert "duration_unknown" in line


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
