from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LEDGER_PATH = os.path.join(REPO_ROOT, "开发文档", "技术债务治理台账.md")
STAGE_RECORD_PATH = os.path.join(REPO_ROOT, "开发文档", "阶段留痕与验收记录.md")
TEST_ARCH_FITNESS_PATH = os.path.join(REPO_ROOT, "tests", "test_architecture_fitness.py")
QUALITY_GATE_SELFTEST_PATH = "tests/test_run_quality_gate.py"
QUALITY_GATE_MANIFEST_REL = os.path.join("evidence", "QualityGate", "quality_gate_manifest.json")
QUALITY_GATE_RECEIPTS_DIR_REL = os.path.join("evidence", "QualityGate", "receipts")
QUALITY_GATE_PYRIGHT_GATE_CONFIG = "pyrightconfig.gate.json"
QUALITY_GATE_PROOF_SCOPE = {
    "claim": "required_registry_bound_to_clean_worktree",
    "does_not_claim": "risk_coverage_complete",
}
QUALITY_GATE_PROOF_SCHEMA_VERSION = 2
QUALITY_GATE_TOOL_PATHS = [
    "scripts/run_quality_gate.py",
    "scripts/sync_debt_ledger.py",
    "tools/quality_gate_entries.py",
    "tools/quality_gate_ledger.py",
    "tools/quality_gate_operations.py",
    "tools/quality_gate_scan.py",
    "tools/quality_gate_shared.py",
    "tools/quality_gate_support.py",
]
QUALITY_GATE_SOURCE_FILES = (
    ".github/workflows/quality.yml",
    ".limcode/skills/aps-full-selftest/scripts/run_full_selftest.py",
    "scripts/run_quality_gate.py",
    "scripts/sync_debt_ledger.py",
    "tools/quality_gate_entries.py",
    "tools/quality_gate_ledger.py",
    "tools/quality_gate_operations.py",
    "tools/quality_gate_scan.py",
    "tools/quality_gate_shared.py",
    "tools/quality_gate_support.py",
)
QUALITY_GATE_STARTUP_REGRESSION_ARGS = [
    "tests/regression_runtime_probe_resolution.py",
    "tests/test_win7_launcher_runtime_paths.py",
    "tests/regression_runtime_contract_launcher.py",
    "tests/regression_runtime_lock_reloader_parent_skip.py",
    "tests/regression_startup_host_portfile.py",
    "tests/regression_startup_host_portfile_new_ui.py",
    "tests/regression_plugin_bootstrap_config_failure_visible.py",
    "tests/regression_plugin_bootstrap_injects_config_reader.py",
    "tests/regression_plugin_bootstrap_telemetry_failure_visible.py",
    "tests/regression_app_new_ui_secret_key_runtime_ensure.py",
    "tests/regression_app_new_ui_session_contract.py",
    "tests/regression_app_new_ui_security_hardening_enabled.py",
    "tests/test_app_factory_runtime_env_refresh.py",
    "tests/regression_runtime_stop_cli.py",
]
QUALITY_GATE_GUARD_TESTS = (
    "tests/test_sp05_path_topology_contract.py",
    "tests/test_schedule_input_builder_strict_hours_and_ext_days.py",
    "tests/regression_scheduler_wrapper_import_order_contract.py",
    "tests/regression_schedule_orchestrator_contract.py",
    "tests/test_schedule_summary_observability.py",
    "tests/regression_sp06_no_duplicate_defs.py",
    "tests/test_schedule_params_direct_call_contract.py",
    "tests/regression_config_field_metadata_shape.py",
    "tests/regression_scheduler_config_route_contract.py",
    "tests/regression_config_field_spec_contract.py",
    "tests/regression_scheduler_config_manual_url_normalization.py",
    "tests/regression_config_service_active_preset_custom_sync.py",
    "tests/regression_config_snapshot_strict_numeric.py",
    "tests/regression_config_snapshot_projection_sync.py",
    "tests/regression_config_service_component_contract.py",
    "tests/regression_config_service_relaxed_missing_visibility.py",
    "tests/regression_apply_preset_adjusted_marks_custom.py",
    "tests/regression_scheduler_batches_degraded_visibility.py",
    "tests/regression_scheduler_objective_labels.py",
    "tests/regression_objective_projection_contract.py",
    "tests/regression_scheduler_analysis_route_contract.py",
    "tests/regression_scheduler_analysis_observability.py",
    "tests/regression_analysis_page_version_default_latest.py",
    "tests/regression_scheduler_analysis_vm_legacy_summary_bridge.py",
    "tests/regression_scheduler_week_plan_summary_observability.py",
    "tests/regression_system_history_route_contract.py",
    "tests/regression_sp05_followup_contracts.py",
    "tests/regression_scheduler_user_visible_messages.py",
    "tests/regression_route_version_normalizers_contract.py",
    "tests/regression_gantt_page_version_default_latest.py",
    "tests/regression_reports_page_version_default_latest.py",
    "tests/regression_reports_export_version_default_latest.py",
    "tests/regression_week_plan_filename_uses_normalized_version.py",
    "tests/regression_gantt_calendar_load_failed_degraded.py",
    "tests/regression_gantt_bad_time_rows_surface_degraded.py",
    "tests/regression_gantt_contract_snapshot.py",
    "tests/regression_gantt_critical_chain_unavailable.py",
    "tests/regression_quality_gate_scan_contract.py",
    "tests/regression_request_services_contract.py",
    "tests/regression_request_services_lazy_construction.py",
    "tests/regression_request_services_failure_propagation.py",
    "tests/regression_optimizer_seed_results_contract.py",
    "tests/regression_schedule_input_collector_contract.py",
    "tests/regression_schedule_params_read_failure_visible.py",
    "tests/regression_schedule_service_strict_snapshot_guard.py",
    "tests/regression_schedule_service_facade_delegation.py",
    "tests/regression_schedule_persistence_reject_empty_actionable_schedule.py",
    "tests/regression_schedule_persistence_reschedulable_contract.py",
    "tests/regression_schedule_optimizer_cfg_snapshot_contract.py",
    "tests/regression_schedule_summary_cfg_snapshot_contract.py",
    "tests/regression_schedule_summary_algo_warnings_union.py",
    "tests/regression_schedule_summary_v11_contract.py",
    "tests/regression_schedule_summary_merge_context_degraded_code.py",
    "tests/regression_schedule_summary_input_fallback_contract.py",
    "tests/regression_scheduler_run_surfaces_resource_pool_warning.py",
    "tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py",
    "tests/regression_error_field_label_source.py",
    "tests/test_run_full_selftest_report_metadata.py",
    "tests/test_ui_mode.py",
    "tests/regression_safe_next_url_hardening.py",
    "tests/regression_safe_next_url_observability.py",
    "tests/test_holiday_default_efficiency_read_guard.py",
    "tests/regression_error_boundary_contract.py",
    "tests/regression_gantt_critical_outline_sync.py",
)
QUALITY_GATE_REQUIRED_TESTS = (QUALITY_GATE_SELFTEST_PATH, *QUALITY_GATE_GUARD_TESTS)

LEDGER_BEGIN = "<!-- APS-DEBT-LEDGER:BEGIN -->"
LEDGER_END = "<!-- APS-DEBT-LEDGER:END -->"
SP02_FACT_BEGIN = "<!-- SP02-FACT-START -->"
SP02_FACT_END = "<!-- SP02-FACT-END -->"

LEDGER_SCHEMA_VERSION = 1
FILE_SIZE_LIMIT = 500
COMPLEXITY_THRESHOLD = 15

CORE_DIRS = [
    "web/routes",
    "core/services",
    "data/repositories",
    "core/models",
    "core/infrastructure",
    "web/viewmodels",
]
STARTUP_SCOPE_PATTERNS = ["web/bootstrap/**/*.py", "web/ui_mode.py"]
UI_MODE_STARTUP_GUARD_SYMBOLS = {"init_ui_mode", "_read_ui_mode_from_db", "get_ui_mode"}

REQUEST_SERVICE_SCAN_SCOPE_PATTERNS = [
    "web/routes/**/*.py",
    "web/error_handlers.py",
    "web/error_boundary.py",
    "web/ui_mode.py",
    "tests/run_real_db_replay_e2e.py",
    "tests/run_complex_excel_cases_e2e.py",
]
REQUEST_SERVICE_TARGET_FILES = [
    "web/routes/domains/scheduler/scheduler_run.py",
    "web/routes/dashboard.py",
    "web/routes/domains/scheduler/scheduler_analysis.py",
    "web/routes/material.py",
    "web/routes/domains/scheduler/scheduler_batches.py",
    "web/routes/domains/scheduler/scheduler_batch_detail.py",
    "web/routes/domains/scheduler/scheduler_ops.py",
    "web/routes/domains/scheduler/scheduler_gantt.py",
    "web/routes/domains/scheduler/scheduler_week_plan.py",
    "web/routes/domains/scheduler/scheduler_config.py",
    "web/routes/domains/scheduler/scheduler_resource_dispatch.py",
    "web/routes/domains/scheduler/scheduler_calendar_pages.py",
    "web/routes/domains/scheduler/scheduler_excel_batches.py",
    "web/routes/domains/scheduler/scheduler_excel_calendar.py",
    "web/routes/system_backup.py",
    "web/routes/system_history.py",
    "web/routes/system_logs.py",
    "web/routes/system_plugins.py",
    "web/routes/system_ui_mode.py",
    "web/routes/system_utils.py",
    "web/error_handlers.py",
    "web/error_boundary.py",
    "web/ui_mode.py",
]
REQUEST_SERVICE_TARGET_SYMBOLS = {
    "tests/run_real_db_replay_e2e.py": ["_create_test_app", "_open_db"],
    "tests/run_complex_excel_cases_e2e.py": ["create_test_app", "_open_db"],
}
REQUEST_SERVICE_TARGET_ALLOWED_HELPERS: List[Dict[str, Any]] = []
REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS = ["core/services/scheduler/**/*.py", "tests/**/*.py", "tools/**/*.py", "web/routes/**/*.py"]

FALLBACK_KIND_VALUES = {
    "silent_swallow",
    "silent_default_fallback",
    "observable_degrade",
    "cleanup_best_effort",
}
ENTRY_STATUS_VALUES = {"open", "in_progress", "blocked", "fixed"}
UI_MODE_SCOPE_TAG_VALUES = {"startup_guard", "render_bridge"}

ENTRY_MANUAL_FIELDS = ["status", "owner", "batch", "notes", "exit_condition"]
ENTRY_COMMON_FIELDS = ["id", "path", "symbol", "status", "owner", "batch", "exit_condition", "last_verified_at"]

LEDGER_IDENTITY_STRATEGY = (
    "silent_fallback.id 使用 path + symbol + handler_fingerprint 稳定键；"
    "except_ordinal 仅用于同函数内同构处理器次级消歧；"
    "line_start/line_end 仅作证据坐标"
)

_SHANGHAI_TZ = timezone(timedelta(hours=8))
_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
_CLEANUP_KEYWORDS = {
    "cleanup",
    "clear",
    "close",
    "delete",
    "dispose",
    "kill",
    "purge",
    "release",
    "remove",
    "shutdown",
    "stop",
    "terminate",
    "unlink",
}
_OBSERVABLE_TARGET_KEYWORDS = {
    "degrad",
    "error",
    "logged",
    "missing_eps",
    "status",
    "telemetry",
    "warn",
    "warning",
    "ui_template_env_degraded",
}


class QualityGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class SilentFallbackSample:
    path: str
    symbol: str
    line_start: int
    line_end: int
    fallback_kind: str
    scope_tag: Optional[str] = None


STARTUP_SAMPLE_EXPECTATIONS = [
    SilentFallbackSample(
        path="web/ui_mode.py",
        symbol="_log_warning",
        line_start=49,
        line_end=50,
        fallback_kind="silent_swallow",
        scope_tag="render_bridge",
    ),
    SilentFallbackSample(
        path="web/bootstrap/runtime_probe.py",
        symbol="read_runtime_host_port",
        line_start=53,
        line_end=54,
        fallback_kind="silent_default_fallback",
    ),
    SilentFallbackSample(
        path="web/bootstrap/plugins.py",
        symbol="bootstrap_plugins",
        line_start=160,
        line_end=169,
        fallback_kind="observable_degrade",
    ),
    SilentFallbackSample(
        path="web/bootstrap/factory.py",
        symbol="_close_db",
        line_start=395,
        line_end=396,
        fallback_kind="cleanup_best_effort",
    ),
    SilentFallbackSample(
        path="web/bootstrap/launcher.py",
        symbol="stop_runtime_from_dir",
        line_start=1202,
        line_end=1203,
        fallback_kind="silent_swallow",
    ),
    SilentFallbackSample(
        path="web/ui_mode.py",
        symbol="_read_ui_mode_from_db",
        line_start=272,
        line_end=274,
        fallback_kind="observable_degrade",
        scope_tag="startup_guard",
    ),
    SilentFallbackSample(
        path="web/ui_mode.py",
        symbol="safe_url_for",
        line_start=402,
        line_end=409,
        fallback_kind="observable_degrade",
        scope_tag="render_bridge",
    ),
]


def now_shanghai_iso() -> str:
    return datetime.now(_SHANGHAI_TZ).replace(microsecond=0).isoformat()


def repo_rel(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT).replace("\\", "/")


def repo_abs(rel_path: str) -> str:
    return os.path.join(REPO_ROOT, str(rel_path).replace("/", os.sep))


def read_text_file(rel_path: str) -> str:
    with open(repo_abs(rel_path), encoding="utf-8", errors="strict") as f:
        return f.read()


def write_text_file(rel_path: str, content: str) -> None:
    abs_path = repo_abs(rel_path)
    parent = os.path.dirname(abs_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def slugify(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    text = text.replace("\\", "/")
    if text.endswith(".py"):
        text = text[:-3]
    text = text.replace(":", "-")
    text = text.replace("/", "-")
    text = re.sub(r"[^0-9A-Za-z_\-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-").lower()
    return text or "item"


def collect_py_files(*rel_dirs: str) -> List[str]:
    files = []
    for rel_dir in rel_dirs:
        base = repo_abs(rel_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                if name != "__init__.py" and name.startswith("__"):
                    continue
                files.append(repo_rel(os.path.join(dirpath, name)))
    return sorted(set(files))


def collect_globbed_files(patterns: Sequence[str]) -> List[str]:
    files = []
    for pattern in patterns:
        abs_pattern = os.path.join(REPO_ROOT, pattern.replace("/", os.sep))
        for matched in glob.glob(abs_pattern, recursive=True):
            if os.path.isfile(matched):
                files.append(repo_rel(matched))
    return sorted(set(files))


def collect_startup_scope_files() -> List[str]:
    return collect_globbed_files(STARTUP_SCOPE_PATTERNS)


def _stable_json_hash(payload: Any) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _normalize_command_rows(commands: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in list(commands or []):
        args = [str(arg) for arg in list(row.get("args") or [])]
        output_policy = str(row.get("output_policy") or "exact").strip().lower()
        if output_policy not in {"exact", "normalized"}:
            output_policy = "exact"
        normalized.append(
            {
                "display": str(row.get("display") or "").strip(),
                "args": args,
                "capture_output": bool(row.get("capture_output")),
                "output_policy": output_policy,
            }
        )
    return normalized


def _normalize_source_rows(gate_sources: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in list(gate_sources or []):
        rows.append(
            {
                "path": str(row.get("path") or "").replace("\\", "/"),
                "exists": bool(row.get("exists")),
                "sha256": str(row.get("sha256") or ""),
            }
        )
    rows.sort(key=lambda item: item["path"])
    return rows


def _normalize_required_tests(required_tests: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for rel_path in list(required_tests or []):
        normalized = str(rel_path or "").strip().replace("\\", "/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _normalize_collection_proof(collection_proof: Dict[str, Any]) -> Dict[str, Any]:
    default_collect_nodeids = []
    seen = set()
    for nodeid in list(collection_proof.get("default_collect_nodeids") or []):
        normalized = str(nodeid or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        default_collect_nodeids.append(normalized)

    key_tests = []
    for row in list(collection_proof.get("key_tests") or []):
        key_tests.append(
            {
                "path": str(row.get("path") or "").replace("\\", "/"),
                "execution_mode": str(row.get("execution_mode") or "").strip(),
            }
        )
    key_tests.sort(key=lambda item: item["path"])
    return {
        "default_collect_nodeids": default_collect_nodeids,
        "key_tests": key_tests,
    }


def _normalize_command_receipt_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": int(payload.get("schema_version") or 0),
        "run_id": str(payload.get("run_id") or "").strip(),
        "command_index": int(payload.get("command_index") or 0),
        "command_hash": str(payload.get("command_hash") or "").strip(),
        "display": str(payload.get("display") or "").strip(),
        "args": [str(arg) for arg in list(payload.get("args") or [])],
        "capture_output": bool(payload.get("capture_output")),
        "output_policy": str(payload.get("output_policy") or "").strip().lower(),
        "returncode": int(payload.get("returncode") or 0),
        "stdout_sha256": str(payload.get("stdout_sha256") or "").strip(),
        "stderr_sha256": str(payload.get("stderr_sha256") or "").strip(),
    }


def _normalize_command_receipt_index(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in list(rows or []):
        out.append(
            {
                "path": str(row.get("path") or "").replace("\\", "/"),
                "sha256": str(row.get("sha256") or "").strip(),
            }
        )
    return out


def parse_pytest_collect_nodeids(output: str) -> List[str]:
    nodeids: List[str] = []
    seen = set()
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("="):
            continue
        if "collected " in line:
            continue
        token = line.split()[0]
        if not token.startswith("tests/") or token in seen:
            continue
        seen.add(token)
        nodeids.append(token)
    return nodeids


def collect_current_pytest_nodeids(repo_root: Union[os.PathLike, str]) -> tuple[bool, List[str], str, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=os.fspath(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    stdout = str(proc.stdout or "")
    stderr = str(proc.stderr or "")
    if int(proc.returncode) != 0:
        return False, [], stdout, stderr, "UNBOUND: current pytest collect failed"
    return True, parse_pytest_collect_nodeids(stdout), stdout, stderr, ""


def _resolve_quality_gate_command_args(command: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    for index, raw_arg in enumerate(list(command.get("args") or [])):
        arg = str(raw_arg)
        args.append(sys.executable if index == 0 and arg == "python" else arg)
    return args


def _command_output_policy(command: Dict[str, Any]) -> str:
    policy = str(command.get("output_policy") or "exact").strip().lower()
    return policy if policy in {"exact", "normalized"} else "exact"


def _normalize_command_output_for_policy(text: str, *, policy: str) -> str:
    output = str(text or "")
    if policy != "normalized":
        return output
    output = output.replace("\r\n", "\n").replace("\r", "\n")
    output = re.sub(r"in [0-9]+(?:\.[0-9]+)?s", "in <seconds>s", output)
    output = re.sub(r"[0-9]+(?:\.[0-9]+)? seconds", "<seconds> seconds", output)
    output = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", "<iso-timestamp>", output)
    output = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "<log-timestamp>", output)
    output = re.sub(r"aps_quickref_check_[A-Za-z0-9_]+", "aps_quickref_check_<tmp>", output)
    output = re.sub(
        r"\n?WARNING: there is a new pyright version available \(v[^\n]+\)\.\n"
        r"Please install the new version or set PYRIGHT_PYTHON_FORCE_VERSION to `latest`\n*",
        "\n",
        output,
    )
    return "\n".join(line.rstrip() for line in output.splitlines()).strip() + ("\n" if output.strip() else "")


def _hash_command_output(text: str, *, policy: str) -> str:
    return _sha256_text(_normalize_command_output_for_policy(text, policy=policy))


def replay_quality_gate_command_plan(
    repo_root: Union[os.PathLike, str],
    commands: Sequence[Dict[str, Any]],
    *,
    timeout_s: int = 900,
    compare_receipts: bool = True,
) -> Optional[str]:
    for index, command in enumerate(_normalize_command_rows(commands), start=1):
        display = str(command.get("display") or "").strip()
        proc = subprocess.run(
            _resolve_quality_gate_command_args(command),
            cwd=os.fspath(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(timeout_s),
        )
        if int(proc.returncode) != 0:
            return f"UNBOUND: quality gate command replay failed: {display}"
        if compare_receipts:
            receipt_rel = build_quality_gate_receipt_rel_path(index, display)
            receipt_abs = os.path.join(os.fspath(repo_root), receipt_rel.replace("/", os.sep))
            if not os.path.isfile(receipt_abs):
                return "UNBOUND: quality gate command receipt missing during replay"
            try:
                receipt_payload = json.loads(read_text_file(receipt_abs))
            except Exception:
                return "UNBOUND: quality gate command receipt unreadable during replay"
            receipt = _normalize_command_receipt_payload(receipt_payload if isinstance(receipt_payload, dict) else {})
            policy = _command_output_policy(command)
            if receipt.get("stdout_sha256") != _hash_command_output(str(proc.stdout or ""), policy=policy):
                return f"UNBOUND: quality gate command receipt stdout replay mismatch: {display}"
            if receipt.get("stderr_sha256") != _hash_command_output(str(proc.stderr or ""), policy=policy):
                return f"UNBOUND: quality gate command receipt stderr replay mismatch: {display}"
    return None


def iter_quality_gate_required_tests() -> List[str]:
    return list(_normalize_required_tests(QUALITY_GATE_REQUIRED_TESTS))


def iter_non_regression_guard_tests() -> List[str]:
    out: List[str] = []
    for rel_path in QUALITY_GATE_REQUIRED_TESTS:
        name = os.path.basename(str(rel_path or ""))
        if name.startswith("regression_"):
            continue
        out.append(str(rel_path))
    return out


def build_quality_gate_command_plan() -> List[Dict[str, Any]]:
    required_tests = iter_quality_gate_required_tests()
    return [
        {
            "display": "python -m pytest --collect-only -q tests",
            "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": "python -m ruff --version",
            "args": ["python", "-m", "ruff", "--version"],
            "capture_output": True,
            "output_policy": "exact",
        },
        {
            "display": "python -m pyright --version",
            "args": ["python", "-m", "pyright", "--version"],
            "capture_output": True,
            "output_policy": "normalized",
        },
        {
            "display": 'python -c "import radon"',
            "args": ["python", "-c", "import radon"],
            "capture_output": False,
            "output_policy": "normalized",
        },
        {
            "display": "python -m ruff check",
            "args": ["python", "-m", "ruff", "check"],
            "capture_output": False,
            "output_policy": "normalized",
        },
        {
            "display": f"python -m pyright -p {QUALITY_GATE_PYRIGHT_GATE_CONFIG}",
            "args": ["python", "-m", "pyright", "-p", QUALITY_GATE_PYRIGHT_GATE_CONFIG],
            "capture_output": False,
            "output_policy": "normalized",
        },
        {
            "display": "python -m pyright " + " ".join(QUALITY_GATE_TOOL_PATHS),
            "args": ["python", "-m", "pyright"] + list(QUALITY_GATE_TOOL_PATHS),
            "capture_output": False,
            "output_policy": "normalized",
        },
        {
            "display": "python -m pytest -q tests/test_architecture_fitness.py",
            "args": ["python", "-m", "pytest", "-q", "tests/test_architecture_fitness.py"],
            "capture_output": False,
            "output_policy": "normalized",
        },
        {
            "display": "python -m pytest -q " + " ".join(required_tests),
            "args": ["python", "-m", "pytest", "-q"] + list(required_tests),
            "capture_output": False,
            "output_policy": "normalized",
        },
        {
            "display": "python scripts/sync_debt_ledger.py check",
            "args": ["python", "scripts/sync_debt_ledger.py", "check"],
            "capture_output": False,
            "output_policy": "normalized",
        },
        {
            "display": "python -m pytest -q " + " ".join(QUALITY_GATE_STARTUP_REGRESSION_ARGS),
            "args": ["python", "-m", "pytest", "-q"] + list(QUALITY_GATE_STARTUP_REGRESSION_ARGS),
            "capture_output": False,
            "output_policy": "normalized",
        },
        {
            "display": "python tests/check_quickref_vs_routes.py",
            "args": ["python", "tests/check_quickref_vs_routes.py"],
            "capture_output": False,
            "output_policy": "normalized",
        },
    ]


def build_quality_gate_receipt_rel_path(index: int, display: str) -> str:
    slug = slugify(display) or f"command-{int(index)}"
    short_slug = slug[:48].rstrip("-") or f"command-{int(index)}"
    digest = hashlib.sha256(str(display or "").encode("utf-8")).hexdigest()[:10]
    return os.path.join(QUALITY_GATE_RECEIPTS_DIR_REL, f"{int(index):02d}_{short_slug}_{digest}.json").replace("\\", "/")


def build_quality_gate_command_receipt(
    command: Dict[str, Any],
    *,
    run_id: str = "",
    command_index: int = 0,
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> Dict[str, Any]:
    normalized_command = _normalize_command_rows([command])[0]
    output_policy = _command_output_policy(normalized_command)
    return _normalize_command_receipt_payload(
        {
            "schema_version": QUALITY_GATE_PROOF_SCHEMA_VERSION,
            "run_id": str(run_id or "").strip(),
            "command_index": int(command_index or 0),
            "command_hash": _stable_json_hash(normalized_command),
            "display": normalized_command["display"],
            "args": list(normalized_command["args"]),
            "capture_output": bool(normalized_command["capture_output"]),
            "output_policy": output_policy,
            "returncode": int(returncode),
            "stdout_sha256": _hash_command_output(str(stdout or ""), policy=output_policy),
            "stderr_sha256": _hash_command_output(str(stderr or ""), policy=output_policy),
        }
    )


def build_quality_gate_collection_proof(
    default_collect_nodeids: Sequence[str],
    *,
    required_tests: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    collected = [str(item).strip() for item in list(default_collect_nodeids or []) if str(item).strip()]
    key_test_rows: List[Dict[str, Any]] = []
    for path in _normalize_required_tests(required_tests or iter_quality_gate_required_tests()):
        in_default_collect = any(nodeid == path or nodeid.startswith(f"{path}::") for nodeid in collected)
        key_test_rows.append(
            {
                "path": path,
                "execution_mode": "default_collect" if in_default_collect else "explicit_run",
            }
        )
    return _normalize_collection_proof(
        {
            "default_collect_nodeids": collected,
            "key_tests": key_test_rows,
        }
    )


def _sha256_file(abs_path: str) -> str:
    hasher = hashlib.sha256()
    with open(abs_path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def build_quality_gate_source_proof(repo_root: Optional[Union[os.PathLike, str]] = None) -> List[Dict[str, Any]]:
    root = os.path.abspath(os.fspath(repo_root) if repo_root is not None else REPO_ROOT)
    rows: List[Dict[str, Any]] = []
    for rel_path in QUALITY_GATE_SOURCE_FILES:
        abs_path = os.path.join(root, rel_path.replace("/", os.sep))
        exists = os.path.isfile(abs_path)
        rows.append(
            {
                "path": str(rel_path).replace("\\", "/"),
                "exists": bool(exists),
                "sha256": _sha256_file(abs_path) if exists else "",
            }
        )
    return _normalize_source_rows(rows)


def hash_required_tests_registry(required_tests: Sequence[str]) -> str:
    return _stable_json_hash(_normalize_required_tests(required_tests))


def hash_quality_gate_commands(commands: Sequence[Dict[str, Any]]) -> str:
    return _stable_json_hash(_normalize_command_rows(commands))


def hash_quality_gate_collection_proof(collection_proof: Dict[str, Any]) -> str:
    return _stable_json_hash(_normalize_collection_proof(collection_proof))


def hash_quality_gate_source_proof(gate_sources: Sequence[Dict[str, Any]]) -> str:
    return _stable_json_hash(_normalize_source_rows(gate_sources))


def hash_quality_gate_command_receipts(command_receipts: Sequence[Dict[str, Any]]) -> str:
    return _stable_json_hash(_normalize_command_receipt_index(command_receipts))


def apply_quality_gate_manifest_proof_fields(
    manifest: Dict[str, Any],
    *,
    repo_root: Optional[Union[os.PathLike, str]] = None,
) -> Dict[str, Any]:
    manifest["schema_version"] = QUALITY_GATE_PROOF_SCHEMA_VERSION
    manifest["proof_scope"] = dict(QUALITY_GATE_PROOF_SCOPE)
    required_tests = _normalize_required_tests(manifest.get("required_tests") or iter_quality_gate_required_tests())
    manifest["required_tests"] = required_tests
    manifest["required_tests_hash"] = hash_required_tests_registry(required_tests)

    commands = _normalize_command_rows(manifest.get("commands") or [])
    manifest["commands"] = commands
    manifest["commands_hash"] = hash_quality_gate_commands(commands)

    collection_proof = _normalize_collection_proof(manifest.get("collection_proof") or {})
    manifest["collection_proof"] = collection_proof
    manifest["collection_proof_hash"] = hash_quality_gate_collection_proof(collection_proof)

    command_receipts = _normalize_command_receipt_index(manifest.get("command_receipts") or [])
    manifest["command_receipts"] = command_receipts
    manifest["command_receipts_hash"] = hash_quality_gate_command_receipts(command_receipts)

    gate_sources = _normalize_source_rows(manifest.get("gate_sources") or build_quality_gate_source_proof(repo_root))
    manifest["gate_sources"] = gate_sources
    manifest["gate_sources_hash"] = hash_quality_gate_source_proof(gate_sources)
    return manifest


def _git_rev_parse_path(repo_root: str, *args: str, fallback: str) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    raw_value = str(proc.stdout or "").strip()
    if int(proc.returncode) == 0 and raw_value:
        path_text = raw_value
        if not os.path.isabs(path_text):
            path_text = os.path.join(repo_root, path_text)
        return os.path.realpath(path_text)
    return os.path.realpath(fallback)


def repo_identity(repo_root: Optional[Union[os.PathLike, str]] = None) -> Dict[str, str]:
    root = os.path.abspath(os.fspath(repo_root) if repo_root is not None else REPO_ROOT)
    return {
        "checkout_root_realpath": _git_rev_parse_path(root, "--show-toplevel", fallback=root),
        "git_common_dir_realpath": _git_rev_parse_path(root, "--git-common-dir", fallback=os.path.join(root, ".git")),
    }


def _verify_quality_gate_collection_proof(
    manifest: Dict[str, Any],
    *,
    current_collect_nodeids: Sequence[str],
    expected_required_tests: Sequence[str],
) -> Optional[str]:
    collection_proof = _normalize_collection_proof(manifest.get("collection_proof") or {})
    expected_collection_proof = build_quality_gate_collection_proof(
        current_collect_nodeids,
        required_tests=expected_required_tests,
    )
    if collection_proof != expected_collection_proof:
        return "UNBOUND: quality gate collection proof mismatch"
    if str(manifest.get("collection_proof_hash") or "") != hash_quality_gate_collection_proof(collection_proof):
        return "UNBOUND: quality gate collection_proof_hash mismatch"
    return None


def _load_verified_quality_gate_receipt(
    repo_root: Union[os.PathLike, str],
    receipt_entry: Dict[str, Any],
    command: Dict[str, Any],
    *,
    index: int,
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    expected_path = build_quality_gate_receipt_rel_path(index, str(command.get("display") or ""))
    if receipt_entry.get("path") != expected_path:
        return None, "UNBOUND: quality gate command receipt path mismatch"
    abs_path = os.path.join(os.fspath(repo_root), expected_path.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        return None, "UNBOUND: quality gate command receipt missing"
    if str(receipt_entry.get("sha256") or "") != _sha256_file(abs_path):
        return None, "UNBOUND: quality gate command receipt hash mismatch"
    try:
        payload = json.loads(read_text_file(abs_path))
    except Exception:
        return None, "UNBOUND: quality gate command receipt unreadable"
    if not isinstance(payload, dict) or not payload:
        return None, "UNBOUND: quality gate command receipt unreadable"
    return payload, None


def _verify_quality_gate_receipt_payload(
    receipt_payload: Dict[str, Any],
    command: Dict[str, Any],
    *,
    index: int,
    run_id: str,
    current_collect_stdout: str,
    current_collect_stderr: str,
) -> Optional[str]:
    receipt = _normalize_command_receipt_payload(receipt_payload)
    normalized_command = _normalize_command_rows([command])[0]
    if int(receipt.get("schema_version") or 0) != QUALITY_GATE_PROOF_SCHEMA_VERSION:
        return "UNBOUND: quality gate command receipt schema_version mismatch"
    if str(receipt.get("run_id") or "").strip() != str(run_id or "").strip() or not str(run_id or "").strip():
        return "UNBOUND: quality gate command receipt run_id mismatch"
    if int(receipt.get("command_index") or 0) != int(index):
        return "UNBOUND: quality gate command receipt command_index mismatch"
    if str(receipt.get("command_hash") or "").strip() != _stable_json_hash(normalized_command):
        return "UNBOUND: quality gate command receipt command_hash mismatch"
    expected_values = (
        ("display", str(command.get("display") or "").strip()),
        ("args", [str(arg) for arg in list(command.get("args") or [])]),
        ("capture_output", bool(command.get("capture_output"))),
        ("output_policy", _command_output_policy(normalized_command)),
    )
    for key, expected_value in expected_values:
        if receipt[key] != expected_value:
            return f"UNBOUND: quality gate command receipt {key} mismatch"
    if int(receipt["returncode"]) != 0:
        return "UNBOUND: quality gate command receipt returncode mismatch"
    for key in ("stdout_sha256", "stderr_sha256"):
        if len(str(receipt.get(key) or "")) != 64:
            return f"UNBOUND: quality gate command receipt {key.replace('_sha256', '')} hash mismatch"
    collect_policy = _command_output_policy(normalized_command)
    if index == 1 and receipt.get("stdout_sha256") != _hash_command_output(current_collect_stdout, policy=collect_policy):
        return "UNBOUND: quality gate collect receipt stdout hash mismatch"
    if index == 1 and receipt.get("stderr_sha256") != _hash_command_output(current_collect_stderr, policy=collect_policy):
        return "UNBOUND: quality gate collect receipt stderr hash mismatch"
    return None


def _verify_quality_gate_command_receipts(
    repo_root: Union[os.PathLike, str],
    manifest: Dict[str, Any],
    *,
    expected_commands: Sequence[Dict[str, Any]],
    run_id: str,
    current_collect_stdout: str,
    current_collect_stderr: str,
) -> Optional[str]:
    command_receipts = _normalize_command_receipt_index(manifest.get("command_receipts") or [])
    if len(command_receipts) != len(expected_commands):
        return "UNBOUND: quality gate command receipts mismatch"
    if str(manifest.get("command_receipts_hash") or "") != hash_quality_gate_command_receipts(command_receipts):
        return "UNBOUND: quality gate command_receipts_hash mismatch"

    for index, (receipt_entry, command) in enumerate(zip(command_receipts, expected_commands), start=1):
        receipt_payload, load_error = _load_verified_quality_gate_receipt(
            repo_root,
            receipt_entry,
            command,
            index=index,
        )
        if load_error:
            return load_error
        payload_error = _verify_quality_gate_receipt_payload(
            receipt_payload or {},
            command,
            index=index,
            run_id=run_id,
            current_collect_stdout=current_collect_stdout,
            current_collect_stderr=current_collect_stderr,
        )
        if payload_error:
            return payload_error
    return None


def verify_quality_gate_manifest(
    *,
    repo_root: Union[os.PathLike, str],
    manifest: Dict[str, Any],
    head_sha: str,
    git_status_lines: Sequence[str],
    replay_commands: bool = True,
) -> tuple[bool, str]:
    if not isinstance(manifest, dict):
        return False, "UNBOUND: quality gate manifest 非法"

    current_identity = repo_identity(repo_root)
    manifest_checkout_root = os.path.realpath(str(manifest.get("checkout_root_realpath") or "").strip())
    manifest_git_common_dir = os.path.realpath(str(manifest.get("git_common_dir_realpath") or "").strip())
    if manifest_checkout_root != current_identity["checkout_root_realpath"]:
        return False, "UNBOUND: quality gate checkout root mismatch"
    if manifest_git_common_dir != current_identity["git_common_dir_realpath"]:
        return False, "UNBOUND: quality gate git common dir mismatch"
    if str(manifest.get("status") or "").strip().lower() != "passed":
        return False, f"UNBOUND: quality gate status={manifest.get('status') or 'unknown'}"
    if int(manifest.get("schema_version") or 0) != QUALITY_GATE_PROOF_SCHEMA_VERSION:
        return False, "UNBOUND: quality gate schema_version mismatch"
    run_id = str(manifest.get("run_id") or "").strip()
    if not run_id:
        return False, "UNBOUND: quality gate run_id missing"
    if str(manifest.get("head_sha") or "").strip() != str(head_sha or "").strip():
        return False, "UNBOUND: quality gate head_sha 不匹配"

    manifest_git_status_before = [
        str(line).rstrip() for line in list(manifest.get("git_status_short_before") or []) if str(line).strip()
    ]
    manifest_git_status_after = [
        str(line).rstrip() for line in list(manifest.get("git_status_short_after") or []) if str(line).strip()
    ]
    current_git_status = [str(line).rstrip() for line in list(git_status_lines or []) if str(line).strip()]
    if bool(manifest.get("is_dirty_before")) or manifest_git_status_before:
        return False, "UNBOUND: quality gate started dirty"
    if bool(manifest.get("tracked_drift_detected")):
        return False, "UNBOUND: quality gate tracked drift detected"
    if bool(manifest.get("is_dirty_after")) or manifest_git_status_after:
        return False, "UNBOUND: quality gate finished dirty"
    if manifest_git_status_after != current_git_status:
        return False, "UNBOUND: quality gate git status --short 不匹配"

    if dict(manifest.get("proof_scope") or {}) != dict(QUALITY_GATE_PROOF_SCOPE):
        return False, "UNBOUND: quality gate proof_scope mismatch"

    required_tests = _normalize_required_tests(manifest.get("required_tests") or [])
    expected_required_tests = iter_quality_gate_required_tests()
    if required_tests != expected_required_tests:
        return False, "UNBOUND: quality gate required tests mismatch"
    if str(manifest.get("required_tests_hash") or "") != hash_required_tests_registry(required_tests):
        return False, "UNBOUND: quality gate required_tests_hash mismatch"

    commands = _normalize_command_rows(manifest.get("commands") or [])
    expected_commands = build_quality_gate_command_plan()
    if commands != expected_commands:
        return False, "UNBOUND: quality gate commands mismatch"
    if str(manifest.get("commands_hash") or "") != hash_quality_gate_commands(commands):
        return False, "UNBOUND: quality gate commands_hash mismatch"

    collect_ok, current_collect_nodeids, current_collect_stdout, current_collect_stderr, collect_note = (
        collect_current_pytest_nodeids(repo_root)
    )
    if not collect_ok:
        return False, collect_note

    collection_error = _verify_quality_gate_collection_proof(
        manifest,
        current_collect_nodeids=current_collect_nodeids,
        expected_required_tests=expected_required_tests,
    )
    if collection_error:
        return False, collection_error

    receipt_error = _verify_quality_gate_command_receipts(
        repo_root,
        manifest,
        expected_commands=expected_commands,
        run_id=run_id,
        current_collect_stdout=current_collect_stdout,
        current_collect_stderr=current_collect_stderr,
    )
    if receipt_error:
        return False, receipt_error

    gate_sources = _normalize_source_rows(manifest.get("gate_sources") or [])
    expected_gate_sources = build_quality_gate_source_proof(repo_root)
    if gate_sources != expected_gate_sources:
        return False, "UNBOUND: quality gate gate sources mismatch"
    if not all(bool(row.get("exists")) for row in gate_sources):
        return False, "UNBOUND: quality gate gate sources missing"
    if str(manifest.get("gate_sources_hash") or "") != hash_quality_gate_source_proof(gate_sources):
        return False, "UNBOUND: quality gate gate_sources_hash mismatch"

    if not replay_commands:
        return False, "STRUCTURAL_ONLY: quality gate command replay disabled"

    replay_error = replay_quality_gate_command_plan(repo_root, expected_commands, compare_receipts=True)
    if replay_error:
        return False, replay_error
    post_replay_status = git_status_short_lines(repo_root)
    if post_replay_status:
        sample = ", ".join(post_replay_status[:5])
        suffix = " ..." if len(post_replay_status) > 5 else ""
        return False, f"UNBOUND: quality gate replay left dirty worktree: {sample}{suffix}"

    return True, "BOUND"


def git_status_short_lines(repo_root: Union[os.PathLike, str]) -> List[str]:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        return [f"!! git status --short failed: {str(completed.stderr or '').strip()}".rstrip()]
    return [str(line).rstrip() for line in str(completed.stdout or "").splitlines() if str(line).strip()]


def collect_quality_rule_files() -> List[str]:
    return sorted(set(collect_py_files(*CORE_DIRS) + collect_startup_scope_files()))


def is_startup_scope_path(path: str) -> bool:
    rel_path = str(path).replace("\\", "/")
    return rel_path == "web/ui_mode.py" or rel_path.startswith("web/bootstrap/")


def ensure_single_marker(text: str, marker: str, label: str) -> None:
    count = text.count(marker)
    if count != 1:
        raise QualityGateError(f"{label} 标记 {marker} 出现次数非法：{count}")


def extract_marked_block(text: str, begin_marker: str, end_marker: str, label: str) -> str:
    ensure_single_marker(text, begin_marker, label)
    ensure_single_marker(text, end_marker, label)
    start = text.index(begin_marker) + len(begin_marker)
    end = text.index(end_marker)
    if end < start:
        raise QualityGateError(f"{label} 标记顺序非法")
    return text[start:end].strip()


def extract_json_code_block(text: str, begin_marker: str, end_marker: str, label: str) -> Dict[str, Any]:
    block = extract_marked_block(text, begin_marker, end_marker, label)
    match = re.search(r"```json\s*(.*?)\s*```", block, re.S)
    if not match:
        raise QualityGateError(f"{label} 缺少唯一 json 结构块")
    json_text = match.group(1).strip()
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise QualityGateError(f"{label} json 解析失败：{exc}") from exc
    if not isinstance(payload, dict):
        raise QualityGateError(f"{label} json 顶层必须是对象")
    return payload


def render_marked_json_block(begin_marker: str, end_marker: str, payload: Dict[str, Any]) -> str:
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    return f"{begin_marker}\n```json\n{json_text}\n```\n{end_marker}"
