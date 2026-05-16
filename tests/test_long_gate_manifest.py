from __future__ import annotations

import json
import os
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

    assert required_entry["args"] == ["python", "tools/verify_required_regressions_from_full_test_debt.py"]
    for required_path in quality_gate_shared.iter_quality_gate_required_tests():
        assert required_path in required_entry["input_file_scopes"]
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
    for required_path in iter_required_tests():
        assert required_path in required_entry["input_file_scopes"]


def test_required_parent_scope_includes_group_specific_scope_union():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    required_entry = _entry_by_id(manifest, "required_regressions")

    assert "web/routes/domains/scheduler/scheduler_config*.py" in required_entry["input_file_scopes"]
    assert "tools/long_gate_cache.py" in required_entry["tool_file_scopes"]
    assert "node_version" in required_entry["env_keys"]
    assert "node_browser_runtime_capability" in required_entry["env_keys"]
    assert "NODE_OPTIONS" in required_entry["env_keys"]
    assert "git_executable_realpath" in required_entry["env_keys"]
    assert "git_version" in required_entry["env_keys"]
    assert "APS_BROWSER_SMOKE_REQUIRED" in required_entry["env_keys"]
    assert "chrome_version" in required_entry["env_keys"]
    assert "chrome_executable_identity" in required_entry["env_keys"]
    assert "chrome_headless_preflight" in required_entry["env_keys"]
    assert "tests/ui_geometry_contract_data.py" in required_entry["input_file_scopes"]
    assert ".gitignore" in required_entry["config_file_scopes"]
    assert required_entry["output_result_files"] == ["evidence/QualityGate/required_regressions.json"]


def test_required_parent_fingerprint_tracks_group_specific_scope_union(tmp_path):
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=str(tmp_path))
    required_entry = _entry_by_id(manifest, "required_regressions")

    before_parent = fingerprint_entry(required_entry, str(tmp_path))
    changed = tmp_path / "web" / "routes" / "domains" / "scheduler" / "scheduler_config_feedback.py"
    changed.parent.mkdir(parents=True)
    changed.write_text("CONFIG_MARKER = True\n", encoding="utf-8")
    after_parent = fingerprint_entry(required_entry, str(tmp_path))

    assert before_parent["hash"] != after_parent["hash"]


def test_required_groups_do_not_enter_formal_manifest_contract():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)
    entry_ids = [entry["entry_id"] for entry in manifest["entries"]]
    required = _entry_by_id(manifest, "required_regressions")

    assert len(manifest["entries"]) == len(command_plan)
    assert "required_regressions" in entry_ids
    assert all(not entry_id.startswith("required_regressions.") for entry_id in entry_ids)
    assert "groups" not in required
    assert "required_regression_group_coverage" not in required
    assert "required_regression_group_scope_policy" not in required


def test_collect_full_test_debt_static_gate_required_startup_and_quickref_entries_are_reuse_enabled():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    enabled = [entry["entry_id"] for entry in manifest["entries"] if entry["reuse_allowed"]]
    planned_candidates = [
        entry["entry_id"]
        for entry in manifest["entries"]
        if entry.get("long_gate_candidate") and not entry.get("reuse_allowed")
    ]

    full_test_debt = _entry_by_id(manifest, "full_test_debt")
    ruff = _entry_by_id(manifest, "ruff_check_full")
    pyright_gate = _entry_by_id(manifest, "pyright_gate_full")
    debt_ledger = _entry_by_id(manifest, "debt_ledger_sync")
    required = _entry_by_id(manifest, "required_regressions")
    startup = _entry_by_id(manifest, "startup_runtime_regressions")
    quickref = _entry_by_id(manifest, "quickref_vs_routes")

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
    forbidden_planned = [
        "architecture_fitness",
    ]
    for entry_id in forbidden_planned:
        entry = _entry_by_id(manifest, entry_id)
        assert entry_id in planned_candidates
        assert entry["cache_status"] == "planned"
        assert entry["reuse_allowed"] is False
    assert debt_ledger["cache_status"] == "enabled"
    assert debt_ledger["reuse_allowed"] is True
    assert debt_ledger["output_result_files"] == ["evidence/QualityGate/debt_ledger_sync.json"]
    static_output_paths = {
        "ruff_check_full": quality_gate_shared.QUALITY_GATE_RUFF_CHECK_FULL_REL.replace("\\", "/"),
        "pyright_gate_full": quality_gate_shared.QUALITY_GATE_PYRIGHT_GATE_FULL_REL.replace("\\", "/"),
        "pyright_tools_full": quality_gate_shared.QUALITY_GATE_PYRIGHT_TOOLS_FULL_REL.replace("\\", "/"),
    }
    for entry_id, output_path in static_output_paths.items():
        assert _entry_by_id(manifest, entry_id)["output_result_files"] == [output_path]
    assert ruff["cache_status"] == "enabled"
    assert ruff["reuse_allowed"] is True
    for scope in [
        "*.py",
        "core/**/*.py",
        "data/**/*.py",
        "desktop/**/*.py",
        "web/**/*.py",
        "plugins/**/*.py",
        "scripts/**/*.py",
        "tools/**/*.py",
        "tests/**/*.py",
        "codestable/tools/**/*.py",
        "audit/**/*.py",
    ]:
        assert scope in ruff["input_file_scopes"]
    for scope in ["pyproject.toml", "ruff.toml", ".ruff.toml", "setup.cfg", ".pre-commit-config.yaml", ".gitignore"]:
        assert scope in ruff["config_file_scopes"]
    assert "requirements*.txt" in ruff["dependency_file_scopes"]
    assert "requirements-dev*.txt" in ruff["dependency_file_scopes"]
    assert "ruff_version" in ruff["env_keys"]
    assert "python_version" in ruff["env_keys"]
    assert ruff["output_result_files"] == ["evidence/QualityGate/ruff_check_full.json"]
    assert pyright_gate["cache_status"] == "enabled"
    assert pyright_gate["reuse_allowed"] is True
    for scope in [
        "app.py",
        "app.pyi",
        "app_new_ui.py",
        "app_new_ui.pyi",
        "config.py",
        "config.pyi",
        "core/**/*.py",
        "data/**/*.py",
        "web/**/*.py",
        "core/**/*.pyi",
        "data/**/*.pyi",
        "web/**/*.pyi",
    ]:
        assert scope in pyright_gate["input_file_scopes"]
    assert "tools/**/*.py" not in pyright_gate["input_file_scopes"]
    assert "scripts/**/*.py" not in pyright_gate["input_file_scopes"]
    assert "tests/**/*.py" not in pyright_gate["input_file_scopes"]
    for scope in ["pyrightconfig.gate.json", "pyrightconfig.json", "pyproject.toml", "setup.cfg"]:
        assert scope in pyright_gate["config_file_scopes"]
    assert "requirements*.txt" in pyright_gate["dependency_file_scopes"]
    assert "requirements-dev*.txt" in pyright_gate["dependency_file_scopes"]
    assert "pyright_version" in pyright_gate["env_keys"]
    assert "PYTHONPATH" in pyright_gate["env_keys"]
    assert pyright_gate["output_result_files"] == ["evidence/QualityGate/pyright_gate_full.json"]
    pyright_tools = _entry_by_id(manifest, "pyright_tools_full")
    assert pyright_tools["cache_status"] == "enabled"
    assert pyright_tools["reuse_allowed"] is True
    assert pyright_tools["args"] == ["python", "-m", "pyright", "-p", quality_gate_shared.QUALITY_GATE_PYRIGHT_TOOLS_CONFIG]
    assert pyright_tools["input_file_scopes"][: len(quality_gate_shared.QUALITY_GATE_TOOL_PATHS)] == (
        quality_gate_shared.QUALITY_GATE_TOOL_PATHS
    )
    for scope in [
        "tools/__init__.py",
        "tools/full_test_debt_shards.py",
        "web/bootstrap/**/*.py",
        "core/infrastructure/logging.py",
        "core/infrastructure/transaction.py",
    ]:
        assert scope in pyright_tools["input_file_scopes"]
    for scope in [
        "pyrightconfig.tools.json",
        "pyrightconfig.gate.json",
        "pyrightconfig.json",
        "pyproject.toml",
        "setup.cfg",
    ]:
        assert scope in pyright_tools["config_file_scopes"]
    assert "requirements*.txt" in pyright_tools["dependency_file_scopes"]
    assert "requirements-dev*.txt" in pyright_tools["dependency_file_scopes"]
    assert "pyright_version" in pyright_tools["env_keys"]
    assert "PYTHONPATH" in pyright_tools["env_keys"]
    assert pyright_tools["output_result_files"] == ["evidence/QualityGate/pyright_tools_full.json"]
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
    for required_path in iter_required_tests():
        assert required_path in required["input_file_scopes"]
    assert "core/**/*.py" in required["input_file_scopes"]
    assert "templates/**/*.html" in required["input_file_scopes"]
    assert "templates_excel/**/*" in required["input_file_scopes"]
    assert "evidence/QualityGate/required_regressions.json" in required["output_result_files"]
    assert required["output_result_files"] == ["evidence/QualityGate/required_regressions.json"]
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
    for env_key in [
        "APS_BROWSER_SMOKE_REQUIRED",
        "APS_CHROME_PATH",
        "git_executable_realpath",
        "git_version",
        "chrome_executable_resolution",
        "chrome_version",
        "chrome_executable_identity",
        "chrome_headless_preflight",
        "node_executable_realpath",
        "node_version",
        "node_browser_runtime_capability",
        "CI",
        "NODE_OPTIONS",
    ]:
        assert env_key in full_test_debt["env_keys"]
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
    assert quickref["cache_status"] == "enabled"
    assert quickref["reuse_allowed"] is True
    assert quickref["output_result_files"] == ["evidence/Conformance/quickref_vs_routes.md"]
    for scope in [
        "开发文档/系统速查表.md",
        "app.py",
        "web/**/*.py",
        "templates/**/*.html",
        "static/**/*",
        "config.py",
        "schema.sql",
    ]:
        assert scope in quickref["input_file_scopes"]
    for scope in [
        "tests/check_quickref_vs_routes.py",
        "tests/test_check_quickref_vs_routes.py",
        "tests/test_long_gate_quickref_cache.py",
    ]:
        assert scope in quickref["tool_file_scopes"]
    assert "requirements*.txt" in quickref["dependency_file_scopes"]
    assert "python_executable_realpath" in quickref["env_keys"]
    assert "PYTHONUTF8" in quickref["env_keys"]
    assert "PYTHONIOENCODING" in quickref["env_keys"]


def test_pyright_tools_entry_tracks_quality_gate_tool_paths():
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(command_plan, repo_root=quality_gate_shared.REPO_ROOT)

    pyright_tools = _entry_by_id(manifest, "pyright_tools_full")

    assert pyright_tools["input_file_scopes"][: len(quality_gate_shared.QUALITY_GATE_TOOL_PATHS)] == (
        quality_gate_shared.QUALITY_GATE_TOOL_PATHS
    )
    assert set(quality_gate_shared.QUALITY_GATE_TOOL_PATHS) <= set(pyright_tools["tool_file_scopes"])


def test_pyright_tools_config_include_matches_quality_gate_tool_paths():
    config_path = os.path.join(
        quality_gate_shared.REPO_ROOT,
        quality_gate_shared.QUALITY_GATE_PYRIGHT_TOOLS_CONFIG,
    )
    with open(config_path, encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["include"] == list(quality_gate_shared.QUALITY_GATE_TOOL_PATHS)


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
