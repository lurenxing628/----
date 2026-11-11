from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union, cast

from tools.long_gate_schema import (
    PRIVATE_ENVIRONMENT_KEYS,
    PUBLIC_ENVIRONMENT_KEYS,
    RUNTIME_FINGERPRINT_KEYS,
    SensitiveSourceError,
    canonical_content,
    content_equal,
    private_environment_value,
    read_file_content,
)
from tools.test_registry import (
    QUALITY_GATE_REQUIRED_TESTS,
    iter_required_regression_common_scope_policy,
    iter_required_regression_groups,
)
from tools.test_registry import (
    iter_required_tests as _registry_required_tests,
)
from tools.test_registry import (
    normalize_test_paths as _normalize_test_paths,
)
from tools.test_registry import (
    required_test_nodeid_matches as _registry_required_test_nodeid_matches,
)
from tools.test_registry_data import ESBUILD_SCOPES as _ESBUILD_GATE_SCOPES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LEDGER_PATH = os.path.join(REPO_ROOT, "开发文档", "技术债务治理台账.md")
QUALITY_GATE_LEGACY_ROOT_REL = os.path.join("evidence", "QualityGate")
QUALITY_GATE_ROOT_REL = os.path.join(QUALITY_GATE_LEGACY_ROOT_REL, "v4")
QUALITY_GATE_MANIFEST_REL = os.path.join(QUALITY_GATE_ROOT_REL, "quality_gate_manifest.json")
QUALITY_GATE_RECEIPTS_DIR_REL = os.path.join(QUALITY_GATE_ROOT_REL, "receipts")
QUALITY_GATE_LOGS_DIR_REL = os.path.join(QUALITY_GATE_ROOT_REL, "logs")
QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "current_full_test_debt.json",
)
# 失败后把 current 明细改名留存到此处供事后排错（单文件覆盖、不堆积、随 .gitignore 隐身）。
QUALITY_GATE_FAILED_FULL_TEST_DEBT_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "current_full_test_debt.failed.json",
)
QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "full_test_debt_summary.json",
)
QUALITY_GATE_REQUIRED_REGRESSIONS_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "required_regressions.json",
)
QUALITY_GATE_DEBT_LEDGER_SYNC_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "debt_ledger_sync.json",
)
QUALITY_GATE_RUFF_CHECK_FULL_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "ruff_check_full.json",
)
QUALITY_GATE_PYRIGHT_GATE_FULL_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "pyright_gate_full.json",
)
QUALITY_GATE_PYRIGHT_TOOLS_FULL_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "pyright_tools_full.json",
)
QUALITY_GATE_QUICKREF_VS_ROUTES_REL = os.path.join(
    QUALITY_GATE_ROOT_REL,
    "quickref_vs_routes.md",
)
QUALITY_GATE_COLLECT_NODEIDS_REL = os.path.join(
    QUALITY_GATE_LEGACY_ROOT_REL,
    "collect_nodeids.v2.json",
).replace("\\", "/")

ENTRY_PYTEST_COLLECT_ALL = "pytest_collect_all"
ENTRY_FULL_TEST_DEBT = "full_test_debt"
ENTRY_RUFF_CHECK_FULL = "ruff_check_full"
ENTRY_PYRIGHT_GATE_FULL = "pyright_gate_full"
ENTRY_PYRIGHT_TOOLS_FULL = "pyright_tools_full"
ENTRY_REQUIRED_REGRESSIONS = "required_regressions"
ENTRY_DEBT_LEDGER_SYNC = "debt_ledger_sync"
ENTRY_QUICKREF_VS_ROUTES = "quickref_vs_routes"
ENTRY_IMPORT_CYCLES_PRODUCTION = "import_cycles_production"
ENTRY_IMPORT_CYCLES_WITH_TESTS = "import_cycles_with_tests"
ENTRY_VERSION_OR_ENV_PROBE = "version_or_env_probe"
ENTRY_ROADMAP_YAML_VALIDATION = "roadmap_yaml_validation"
ENTRY_PY38_SYNTAX_CHECK = "py38_syntax_check"
# The retained suite is the complete suite: no marker-based exclusions or browser lane.
FORMAL_FULL_TEST_PYTEST_ARGS = ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"]
REQUIRED_BROWSER_ENV_OVERLAY = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}
QUALITY_GATE_PYRIGHT_GATE_CONFIG = "pyrightconfig.gate.json"
QUALITY_GATE_PYRIGHT_TOOLS_CONFIG = "pyrightconfig.tools.json"
QUALITY_GATE_PROOF_SCOPE = {
    "claim": "required_registry_bound_to_clean_worktree",
    "does_not_claim": "risk_coverage_complete",
}
# Schema 2/3 records remain historical; new verification binds complete original content.
QUALITY_GATE_PROOF_SCHEMA_VERSION = 4
IMPORT_CYCLE_PRODUCTION_DISPLAY = (
    "python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean"
)
IMPORT_CYCLE_WITH_TESTS_DISPLAY = (
    "python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --quiet-when-clean"
)
IMPORT_CYCLE_PRODUCTION_ARGS = (
    "-m",
    "tools.scan_import_cycles",
    "--fail-on-new-cycle",
    "--quiet-when-clean",
)
IMPORT_CYCLE_WITH_TESTS_ARGS = (
    "-m",
    "tools.scan_import_cycles",
    "--include-tests",
    "--fail-on-new-cycle",
    "--quiet-when-clean",
)
QUALITY_GATE_TOOL_PATHS = [
    "scripts/run_daily_quality_gate.py",
    "scripts/run_quality_gate.py",
    "scripts/sync_debt_ledger.py",
    "tools/fast_static_precheck.py",
    "tools/git_hook_blocked_paths.py",
    "tools/git_hook_cache.py",
    "tools/git_hook_checks.py",
    "tools/check_full_test_debt.py",
    "tools/collect_full_test_debt.py",
    "tools/full_test_debt_shards.py",
    "tools/benchmark_full_test_debt_shards.py",
    "tools/verify_required_regressions_from_full_test_debt.py",
    "tools/architecture_scan_cache.py",
    "tools/long_gate_cache.py",
    "tools/long_gate_collect.py",
    "tools/long_gate_fingerprint.py",
    "tools/long_gate_manifest.py",
    "tools/long_gate_paths.py",
    "tools/long_gate_schema.py",
    "tools/long_gate_summary.py",
    "tools/quality_gate_entries.py",
    "tools/quality_gate_ledger.py",
    "tools/quality_gate_operations.py",
    "tools/quality_gate_scan.py",
    "tools/quality_gate_shared.py",
    "tools/scan_dead_code_islands.py",
    "tools/import_cycle_analysis.py",
    "tools/import_cycle_baseline.py",
    "tools/import_cycle_graph.py",
    "tools/scan_import_cycles.py",
    "tools/boundary_baseline.py",
    "tools/scan_sql_boundary.py",
    "tools/scan_private_imports.py",
    "tools/scan_dead_path_literals.py",
    "tools/scan_over_defense.py",
    ".codestable/checkup/scripts/callgraph_call_sites.py",
    ".codestable/checkup/scripts/callgraph_dataflow.py",
    ".codestable/checkup/scripts/callgraph_extract.py",
    ".codestable/checkup/scripts/callgraph_function_index.py",
    "tools/dead_code_usage/__init__.py",
    "tools/dead_code_usage/ast_nodes.py",
    "tools/dead_code_usage/ast_usage.py",
    "tools/dead_code_usage/imports.py",
    "tools/dead_code_usage/model.py",
    "tools/dead_code_usage/scip_usage.py",
    "tools/dead_code_usage/scope.py",
    "tools/dead_code_usage/type_hints.py",
    "tools/scan_py38plus_syntax.py",
    "tools/test_debt_registry.py",
    "tools/test_registry.py",
    "tools/test_registry_data.py",
    "tests/conftest.py",
    ".codestable/tools/_yaml_frontmatter.py",
    ".codestable/tools/search-yaml.py",
    ".codestable/tools/validate-yaml.py",
    ".limcode/skills/aps-full-selftest/scripts/run_full_selftest.py",
    "tests/app_runtime/test_frontend_offline_static_assets.py",
    "scripts/workbench/asset_sources.py",
    "scripts/workbench/entry_bundle.py",
    "scripts/workbench/vendor_react.py",
    "scripts/workbench/build.py",
    ".limcode/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py",
]
QUALITY_GATE_SOURCE_FILES = tuple(
    dict.fromkeys(
        (
            ".pre-commit-config.yaml",
            ".github/workflows/quality.yml",
            "pyproject.toml",
            "开发文档/技术债务治理台账.md",
            QUALITY_GATE_PYRIGHT_GATE_CONFIG,
            QUALITY_GATE_PYRIGHT_TOOLS_CONFIG,
            ".codestable/checkup/baseline.json",
            ".codestable/checkup/data_policy_baseline.json",
            ".codestable/checkup/dead_code_islands_baseline.json",
            ".codestable/checkup/dead_path_literal_baseline.json",
            ".codestable/checkup/import_cycles_production_baseline.json",
            ".codestable/checkup/import_cycles_with_tests_baseline.json",
            ".codestable/checkup/over_defense_baseline.json",
            ".codestable/checkup/private_import_baseline.json",
            ".codestable/checkup/sql_boundary_baseline.json",
            *QUALITY_GATE_TOOL_PATHS,
            *QUALITY_GATE_REQUIRED_TESTS,
            "tests/gate_meta/check_quickref_vs_routes.py",
        )
    )
)

LEDGER_BEGIN = "<!-- APS-DEBT-LEDGER:BEGIN -->"
LEDGER_END = "<!-- APS-DEBT-LEDGER:END -->"

LEDGER_SCHEMA_VERSION = 2
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
STARTUP_SCOPE_PATTERNS = ["web/bootstrap/**/*.py"]

FALLBACK_KIND_VALUES = {
    "silent_swallow",
    "silent_default_fallback",
    "observable_degrade",
    "cleanup_best_effort",
}
ENTRY_STATUS_VALUES = {"open", "in_progress", "blocked", "fixed"}
TEST_DEBT_MODE_VALUES = {"xfail", "fixed", "retired"}
FULL_TEST_DEBT_ALLOWED_ACTIVE_XFAIL_NODEIDS = (
    "tests/excel_data_io/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors",
    "tests/excel_data_io/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error",
    "tests/excel_data_io/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error",
    "tests/models_domain/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows",
)
# These real socket tests require Windows. Their existing skipif permits POSIX
# collection; the Windows gate must execute them and obtain passed reports.
REQUIRED_REGRESSION_ALLOWED_SKIPPED_PLATFORMS: Dict[str, Tuple[str, ...]] = {
    "tests/app_runtime/test_runtime_server_binding.py::test_listener_rejects_even_a_reusable_competing_bind": ("posix",),
    "tests/app_runtime/test_runtime_server_binding.py::test_competing_reusable_listener_is_not_stolen": ("posix",),
    "tests/app_runtime/test_runtime_server_binding.py::test_fallback_serves_on_the_same_reserved_socket": ("posix",),
    "tests/app_runtime/test_runtime_server_binding.py::test_failed_bind_does_not_leak_a_socket": ("posix",),
    "tests/app_runtime/test_runtime_server_binding.py::test_failed_listen_releases_the_bound_socket": ("posix",),
}
REQUIRED_REGRESSION_ALLOWED_SKIPPED_NODEIDS = tuple(REQUIRED_REGRESSION_ALLOWED_SKIPPED_PLATFORMS)

ENTRY_MANUAL_FIELDS = ["status", "owner", "batch", "notes", "exit_condition"]
ENTRY_COMMON_FIELDS = ["id", "path", "symbol", "status", "owner", "batch", "exit_condition", "last_verified_at"]

LEDGER_IDENTITY_STRATEGY = (
    "silent_fallback.id 保留已有永久编号，新编号使用 path + symbol + except_ordinal；"
    "handler_signature / handler_context 保存完整原文用于当前内容比较；"
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


STARTUP_SAMPLE_EXPECTATIONS = [
    SilentFallbackSample(
        path="web/bootstrap/launcher_observability.py",
        symbol="_format_message",
        line_start=64,
        line_end=65,
        fallback_kind="silent_default_fallback",
    ),
    SilentFallbackSample(
        path="web/bootstrap/plugins.py",
        symbol="bootstrap_plugins",
        line_start=80,
        line_end=96,
        fallback_kind="observable_degrade",
    ),
    SilentFallbackSample(
        path="web/bootstrap/launcher_shutdown.py",
        symbol="read_exit_backup_enabled",
        line_start=103,
        line_end=105,
        fallback_kind="cleanup_best_effort",
    ),
    SilentFallbackSample(
        path="web/bootstrap/launcher_stop.py",
        symbol="_request_runtime_shutdown",
        line_start=110,
        line_end=112,
        fallback_kind="observable_degrade",
    ),
]


def now_shanghai_iso() -> str:
    return datetime.now(_SHANGHAI_TZ).replace(microsecond=0).isoformat()


def repo_rel(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT).replace("\\", "/")


def repo_abs(rel_path: str) -> str:
    return os.path.join(REPO_ROOT, str(rel_path).replace("/", os.sep))


def read_text_file(rel_path: str) -> str:
    with open(repo_abs(rel_path), encoding="utf-8", errors="strict", newline="") as f:
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


_COMMAND_SPEC_METADATA_KEYS = (
    "check_id",
    "entry_type",
    "proof_kind",
    "reuse_policy",
    "runner_handler",
)


def normalize_quality_gate_command(command: Mapping[str, Any]) -> Dict[str, Any]:
    """One complete command identity for execution, receipts, resume and cache comparison."""
    normalized: Dict[str, Any] = {
        "display": str(command.get("display") or "").strip(),
        "args": [str(arg) for arg in list(command.get("args") or [])],
        "capture_output": bool(command.get("capture_output")),
        "output_policy": _command_output_policy(command),
        "env_overlay": _normalize_env_overlay(command.get("env_overlay")),
    }
    for key in _COMMAND_SPEC_METADATA_KEYS:
        if key not in command:
            continue
        value = command.get(key)
        normalized[key] = None if value is None else str(value).strip()
    return normalized


def _normalize_command_rows(commands: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_quality_gate_command(command) for command in list(commands or [])]


def _normalize_env_overlay(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: Dict[str, str] = {}
    for key in sorted(value):
        key_text = str(key or "").strip()
        if not key_text:
            continue
        text = str(value.get(key) or "")
        if key_text in PRIVATE_ENVIRONMENT_KEYS:
            raise QualityGateError(f"Sensitive environment overlay key is not allowed: {key_text}")
        if key_text not in PUBLIC_ENVIRONMENT_KEYS:
            raise QualityGateError(f"Environment overlay keys require a public allowlist entry: {key_text}")
        normalized[key_text] = text
    return normalized


def sanitize_quality_gate_output(text: str) -> str:
    """Remove current-process credential values before logs or receipts are persisted."""
    output = str(text or "")
    values = {
        value
        for key in PRIVATE_ENVIRONMENT_KEYS
        for value in (private_environment_value(os.environ, key),)
        if value
    }
    for value in sorted(values, key=len, reverse=True):
        output = output.replace(value, "[REDACTED]")
    return output


def _normalize_source_rows(gate_sources: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in list(gate_sources or []):
        normalized = {"path": str(row.get("path") or "").replace("\\", "/"), "exists": row.get("exists")}
        if "content_base64" in row:
            normalized["content_base64"] = row["content_base64"]
        rows.append(normalized)
    rows.sort(key=lambda item: item["path"])
    return rows


def _normalize_required_tests(required_tests: Sequence[str]) -> List[str]:
    return _normalize_test_paths(required_tests)


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
        "collected_count": len(default_collect_nodeids),
        "default_collect_nodeids": default_collect_nodeids,
        "key_tests": key_tests,
    }


def _normalize_command_receipt_index(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in list(rows or []):
        normalized = {"path": str(row.get("path") or "").replace("\\", "/")}
        if "content" in row:
            normalized["content"] = json.loads(canonical_content(row["content"]))
        out.append(normalized)
    return out


def parse_pytest_collect_nodeids(output: str) -> List[str]:
    nodeids: List[str] = []
    seen = set()
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("="):
            continue
        if not line.startswith("tests/") or line in seen:
            continue
        seen.add(line)
        nodeids.append(line)
    return nodeids


def _command_output_policy(command: Mapping[str, Any]) -> str:
    policy = str(command.get("output_policy") or "").strip().lower() or "exact"
    if policy not in {"exact", "normalized"}:
        raise ValueError(f"Unsupported quality gate output_policy: {policy!r}")
    return policy


def _normalize_command_output_for_policy(text: str, *, policy: str) -> str:
    output = sanitize_quality_gate_output(text)
    if policy != "normalized":
        return output
    output = output.replace("\r\n", "\n").replace("\r", "\n")
    output = re.sub(r"in [0-9]+(?:\.[0-9]+)?s", "in <seconds>s", output)
    # Try a digit run only at its start; huge numeric pytest IDs otherwise cost O(n²).
    output = re.sub(r"(?<![0-9])[0-9]+(?:\.[0-9]+)? seconds", "<seconds> seconds", output)
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


def iter_quality_gate_required_tests() -> List[str]:
    return _registry_required_tests()


def quality_gate_required_test_nodeid_matches(
    nodeid: str,
    required_tests: Sequence[str] = QUALITY_GATE_REQUIRED_TESTS,
) -> bool:
    return _registry_required_test_nodeid_matches(nodeid, required_tests)


def is_terminal_pytest_report(when: str, outcome: str) -> bool:
    return (
        (when == "call" and outcome in ("passed", "failed", "skipped"))
        or (when == "setup" and outcome in ("skipped", "failed"))
    )


def is_teardown_failure_report(when: str, outcome: str) -> bool:
    return when == "teardown" and outcome == "failed"


_XFAIL_SIGNAL_REPORT_KEYS = ("strict_xpass", "xfail_marker_present", "xfail_marker_reason", "wasxfail_reason")


def is_xfail_signal_report(report: Mapping[str, Any]) -> bool:
    """收集器 report 行是否带任一 xfail 信号；report 必须已经准入或由收集器自产。"""
    return any(report[key] for key in _XFAIL_SIGNAL_REPORT_KEYS)


@dataclass(frozen=True)
class GateCheckSpec:
    check_id: str
    entry_type: str
    display: str
    args: Tuple[str, ...]
    capture_output: bool = False
    output_policy: str = "exact"
    env_overlay: Tuple[Tuple[str, str], ...] = ()
    input_file_scopes: Tuple[str, ...] = ()
    config_file_scopes: Tuple[str, ...] = ()
    tool_file_scopes: Tuple[str, ...] = ()
    dependency_file_scopes: Tuple[str, ...] = ()
    env_keys: Tuple[str, ...] = ()
    output_result_files: Tuple[str, ...] = ()
    proof_kind: Optional[str] = None
    reuse_policy: str = "success"
    runner_handler: str = "default"

    @property
    def reuse_allowed(self) -> bool:
        return self.reuse_policy != "none"

    def to_command_dict(self) -> Dict[str, Any]:
        command: Dict[str, Any] = {
            "check_id": self.check_id,
            "entry_type": self.entry_type,
            "display": self.display,
            "args": list(self.args),
            "capture_output": bool(self.capture_output),
            "output_policy": self.output_policy,
            "proof_kind": self.proof_kind,
            "reuse_policy": self.reuse_policy,
            "runner_handler": self.runner_handler,
        }
        if self.env_overlay:
            command["env_overlay"] = dict(self.env_overlay)
        return command


_COMMON_DEPENDENCY_SCOPES = (
    "requirements*.txt",
    "requirements-dev*.txt",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "vendor/wheels/*.whl",
)


def _dedupe_tuple(items: Sequence[str]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _load_pyright_config(repo_root: Optional[str], config_path: str) -> Dict[str, Any]:
    root = os.path.abspath(repo_root or REPO_ROOT)
    abs_path = os.path.join(root, str(config_path).replace("\\", "/").replace("/", os.sep))
    with open(abs_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Pyright config must be a JSON object: {config_path}")
    return payload


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).replace("\\", "/").strip() for item in value if str(item).strip()]


def _pyright_path_scopes(path: str) -> List[str]:
    normalized = str(path or "").replace("\\", "/").strip().strip("/")
    if not normalized:
        return []
    if any(char in normalized for char in "*?["):
        return [normalized]
    if normalized in {".", "./"}:
        return []
    if normalized.endswith(".py"):
        return [normalized, normalized[:-3] + ".pyi"]
    if normalized.endswith(".pyi"):
        return [normalized]
    return [f"{normalized}/**/*.py", f"{normalized}/**/*.pyi", f"{normalized}/**/py.typed"]


def _pyright_extra_path_scopes(config: Mapping[str, Any]) -> List[str]:
    extras: List[str] = []
    extras.extend(_string_list(config.get("extraPaths")))
    for environment in list(config.get("executionEnvironments") or []):
        if isinstance(environment, dict):
            extras.extend(_string_list(environment.get("extraPaths")))
    scopes: List[str] = []
    for extra in extras:
        normalized = str(extra).replace("\\", "/").strip().strip("/")
        if not normalized or normalized in {".", "./"}:
            continue
        if normalized.startswith(".venv") or "/site-packages" in normalized:
            continue
        scopes.extend(_pyright_path_scopes(normalized))
    return scopes


def _pyright_gate_input_scopes(repo_root: Optional[str]) -> Tuple[str, ...]:
    config = _load_pyright_config(repo_root, QUALITY_GATE_PYRIGHT_GATE_CONFIG)
    includes = _string_list(config.get("include"))
    if not includes:
        raise ValueError(f"Pyright config must declare non-empty include list: {QUALITY_GATE_PYRIGHT_GATE_CONFIG}")
    scopes: List[str] = []
    for include in includes:
        scopes.extend(_pyright_path_scopes(include))
    stub_path = str(config.get("stubPath") or "typings").replace("\\", "/").strip().strip("/")
    if stub_path:
        scopes.append(f"{stub_path}/**/*.pyi")
    scopes.append("py.typed")
    scopes.extend(_pyright_extra_path_scopes(config))
    return _dedupe_tuple(scopes)


def _registry_test_environment_keys() -> List[str]:
    return sorted(
        {
            key
            for group in iter_required_regression_groups()
            for key in group["env_keys"]
            if key not in RUNTIME_FINGERPRINT_KEYS
        }
    )


def _required_regression_scopes() -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    required_targets = iter_quality_gate_required_tests()
    common_scope_policy = iter_required_regression_common_scope_policy()
    group_rows = iter_required_regression_groups()
    input_scopes = list(required_targets)
    input_scopes.append(QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/"))
    input_scopes.extend(common_scope_policy["input_file_scopes"])
    config_scopes = list(common_scope_policy["config_file_scopes"])
    tool_scopes = list(common_scope_policy["tool_file_scopes"])
    dependency_scopes = list(common_scope_policy["dependency_file_scopes"])
    env_keys = list(common_scope_policy["env_keys"])
    for group in group_rows:
        input_scopes.extend(group["input_file_scopes"])
        config_scopes.extend(group["config_file_scopes"])
        tool_scopes.extend(group["tool_file_scopes"])
        dependency_scopes.extend(group["dependency_file_scopes"])
        env_keys.extend(group["env_keys"])
    return (
        _dedupe_tuple(input_scopes),
        _dedupe_tuple(config_scopes),
        _dedupe_tuple(tool_scopes),
        _dedupe_tuple(dependency_scopes),
        _dedupe_tuple(env_keys),
    )


def build_quality_gate_check_specs(
    repo_root: Optional[str] = None,
    *,
    allow_dirty_worktree: bool = False,
) -> List[GateCheckSpec]:
    req_input, req_config, req_tool, req_dep, req_env = _required_regression_scopes()
    full_debt_result_rel = QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/")
    req_input_for_full_debt = tuple(item for item in req_input if item != full_debt_result_rel)
    browser_overlay = tuple(sorted(REQUIRED_BROWSER_ENV_OVERLAY.items()))
    full_debt_args: Tuple[str, ...] = (
        ("python", "tools/check_full_test_debt.py", "--allow-dirty-worktree-proof", "--sharded", "--shard-count", "3")
        if allow_dirty_worktree
        else ("python", "tools/check_full_test_debt.py", "--sharded", "--shard-count", "3")
    )
    full_debt_display = (
        "python tools/check_full_test_debt.py --sharded --shard-count 3 --allow-dirty-worktree-proof"
        if allow_dirty_worktree
        else "python tools/check_full_test_debt.py --sharded --shard-count 3"
    )
    import_cycle_base_inputs = (
        "*.py",
        "core/**/*.py",
        "data/**/*.py",
        "desktop/**/*.py",
        "plugins/**/*.py",
        "scripts/**/*.py",
        "tools/**/*.py",
        "web/**/*.py",
    )
    import_cycle_tools = (
        "tools/import_cycle_analysis.py",
        "tools/import_cycle_baseline.py",
        "tools/import_cycle_graph.py",
        "tools/scan_import_cycles.py",
    )
    import_cycle_env = (
        "python_executable_realpath",
        "python_version",
        "platform",
        "PYTHONPATH",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
    )
    pyright_env = (
        "python_executable_realpath",
        "python_version",
        "pyright_version",
        "platform",
        "PYTHONPATH",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
    )
    tracked_roadmap_scopes = (
        ".codestable/roadmap/aps-architecture-consolidation/*.md",
        ".codestable/roadmap/aps-architecture-consolidation/*.yaml",
        ".codestable/roadmap/foundation-boundary-governance/*.md",
        ".codestable/roadmap/foundation-boundary-governance/*.yaml",
    )
    return [
        GateCheckSpec(
            check_id="ruff_version_probe",
            entry_type=ENTRY_VERSION_OR_ENV_PROBE,
            display="python -m ruff --version",
            args=("python", "-m", "ruff", "--version"),
            capture_output=True,
            output_policy="exact",
            reuse_policy="none",
            runner_handler="ruff_version",
        ),
        GateCheckSpec(
            check_id="pyright_version_probe",
            entry_type=ENTRY_VERSION_OR_ENV_PROBE,
            display="python -m pyright --version",
            args=("python", "-m", "pyright", "--version"),
            capture_output=True,
            output_policy="normalized",
            reuse_policy="none",
            runner_handler="pyright_version",
        ),
        GateCheckSpec(
            check_id="radon_import_probe",
            entry_type=ENTRY_VERSION_OR_ENV_PROBE,
            display='python -c "import radon"',
            args=("python", "-c", "import radon"),
            capture_output=False,
            output_policy="normalized",
            reuse_policy="none",
            runner_handler="default",
        ),
        GateCheckSpec(
            check_id=ENTRY_RUFF_CHECK_FULL,
            entry_type=ENTRY_RUFF_CHECK_FULL,
            display="python -m ruff check",
            args=("python", "-m", "ruff", "check"),
            capture_output=False,
            output_policy="normalized",
            input_file_scopes=(
                "*.py",
                ".codestable/tools/**/*.py",
                "core/**/*.py",
                "data/**/*.py",
                "desktop/**/*.py",
                "plugins/**/*.py",
                "scripts/**/*.py",
                "tests/**/*.py",
                "tools/**/*.py",
                "web/**/*.py",
            ),
            config_file_scopes=(
                "pyproject.toml",
                "ruff.toml",
                ".ruff.toml",
                "setup.cfg",
                ".pre-commit-config.yaml",
                ".gitignore",
            ),
            dependency_file_scopes=_COMMON_DEPENDENCY_SCOPES,
            env_keys=(
                "python_executable_realpath",
                "python_version",
                "ruff_version",
                "platform",
                "PYTHONPATH",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
            ),
            output_result_files=(QUALITY_GATE_RUFF_CHECK_FULL_REL.replace("\\", "/"),),
            proof_kind="static_check",
            reuse_policy="success",
            runner_handler="default",
        ),
        GateCheckSpec(
            check_id=ENTRY_IMPORT_CYCLES_PRODUCTION,
            entry_type=ENTRY_IMPORT_CYCLES_PRODUCTION,
            display=IMPORT_CYCLE_PRODUCTION_DISPLAY,
            args=("python", *IMPORT_CYCLE_PRODUCTION_ARGS),
            capture_output=True,
            output_policy="normalized",
            input_file_scopes=(
                *import_cycle_base_inputs,
                ".codestable/checkup/import_cycles_production_baseline.json",
            ),
            config_file_scopes=(".codestable/checkup/import_cycles_production_baseline.json",),
            tool_file_scopes=import_cycle_tools,
            env_keys=import_cycle_env,
            reuse_policy="success",
            runner_handler="import_cycle_production",
        ),
        GateCheckSpec(
            check_id=ENTRY_IMPORT_CYCLES_WITH_TESTS,
            entry_type=ENTRY_IMPORT_CYCLES_WITH_TESTS,
            display=IMPORT_CYCLE_WITH_TESTS_DISPLAY,
            args=("python", *IMPORT_CYCLE_WITH_TESTS_ARGS),
            capture_output=True,
            output_policy="normalized",
            input_file_scopes=(
                *import_cycle_base_inputs,
                "tests/**/*.py",
                ".codestable/checkup/import_cycles_with_tests_baseline.json",
            ),
            config_file_scopes=(".codestable/checkup/import_cycles_with_tests_baseline.json",),
            tool_file_scopes=import_cycle_tools,
            env_keys=import_cycle_env,
            reuse_policy="success",
            runner_handler="import_cycle_with_tests",
        ),
        GateCheckSpec(
            check_id=ENTRY_PYTEST_COLLECT_ALL,
            entry_type=ENTRY_PYTEST_COLLECT_ALL,
            display="python -m pytest --collect-only -q tests",
            args=("python", "-m", "pytest", "--collect-only", "-q", "tests"),
            capture_output=True,
            output_policy="normalized",
            input_file_scopes=_dedupe_tuple(
                (
                    "tests/**/*.py",
                    "tests/**/conftest.py",
                    "core/**/*.py",
                    "web/**/*.py",
                    "data/**/*.py",
                    "plugins/**/*.py",
                    "scripts/**/*.py",
                    "*.py",
                    "app.py",
                    "schema.sql",
                )
            ),
            config_file_scopes=(
                "pytest.ini",
                "pyproject.toml",
                "setup.cfg",
                "tox.ini",
                "tools/quality_gate_shared.py",
                "tools/test_debt_registry.py",
                "tools/test_registry.py",
                "scripts/run_quality_gate.py",
                "开发文档/技术债务治理台账.md",
            ),
            tool_file_scopes=(
                "tools/quality_gate_ledger.py",
                "tools/test_registry*.py",
            ),
            dependency_file_scopes=_COMMON_DEPENDENCY_SCOPES,
            env_keys=_dedupe_tuple(
                (
                    "python_executable_realpath",
                    "python_version",
                    "pytest_version",
                    "pytest_plugin_distribution_versions",
                    "platform",
                    "PYTHONPATH",
                    "PYTHONUTF8",
                    "PYTHONIOENCODING",
                    "PYTEST_ADDOPTS",
                    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                    "PYTEST_PLUGINS",
                    *_registry_test_environment_keys(),
                )
            ),
            output_result_files=(QUALITY_GATE_COLLECT_NODEIDS_REL,),
            proof_kind="collect_nodeids",
            reuse_policy="success",
            runner_handler="pytest_collect_all",
        ),
        GateCheckSpec(
            check_id=ENTRY_ROADMAP_YAML_VALIDATION,
            entry_type=ENTRY_ROADMAP_YAML_VALIDATION,
            display="python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-architecture-consolidation/aps-architecture-consolidation-items.yaml --yaml-only --require roadmap --require created --require items",
            args=(
                "python",
                ".codestable/tools/validate-yaml.py",
                "--file",
                ".codestable/roadmap/aps-architecture-consolidation/aps-architecture-consolidation-items.yaml",
                "--yaml-only",
                "--require",
                "roadmap",
                "--require",
                "created",
                "--require",
                "items",
            ),
            capture_output=True,
            output_policy="normalized",
            reuse_policy="none",
            runner_handler="default",
        ),
        GateCheckSpec(
            check_id=ENTRY_PY38_SYNTAX_CHECK,
            entry_type=ENTRY_PY38_SYNTAX_CHECK,
            display="python tools/scan_py38plus_syntax.py --fail-on-hit",
            args=("python", "tools/scan_py38plus_syntax.py", "--fail-on-hit"),
            capture_output=True,
            output_policy="normalized",
            reuse_policy="none",
            runner_handler="default",
        ),
        GateCheckSpec(
            check_id=ENTRY_QUICKREF_VS_ROUTES,
            entry_type=ENTRY_QUICKREF_VS_ROUTES,
            display="python tests/gate_meta/check_quickref_vs_routes.py",
            args=("python", "tests/gate_meta/check_quickref_vs_routes.py"),
            capture_output=False,
            output_policy="normalized",
            input_file_scopes=(
                "开发文档/系统速查表.md",
                "app.py",
                "schema.sql",
                "core/**/*.py",
                "data/**/*.py",
                "plugins/**/*.py",
                "web/**/*.py",
                "templates/**/*.html",
                "static/**/*",
            ),
            config_file_scopes=(
                "pytest.ini",
                "pyproject.toml",
                "setup.cfg",
                "tox.ini",
                ".pre-commit-config.yaml",
                ".gitignore",
                "tools/quality_gate_shared.py",
                "tools/long_gate_manifest.py",
                "tools/long_gate_fingerprint.py",
                "tools/long_gate_cache.py",
                "tools/long_gate_schema.py",
                "scripts/run_quality_gate.py",
            ),
            tool_file_scopes=("tests/gate_meta/check_quickref_vs_routes.py",),
            dependency_file_scopes=_COMMON_DEPENDENCY_SCOPES,
            env_keys=(
                "python_executable_realpath",
                "python_version",
                "platform",
                "APS_ENV",
                "APS_DB_PATH",
                "APS_LOG_DIR",
                "APS_BACKUP_DIR",
                "APS_EXCEL_TEMPLATE_DIR",
                "PYTHONPATH",
                "PYTHONDONTWRITEBYTECODE",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
            ),
            output_result_files=(QUALITY_GATE_QUICKREF_VS_ROUTES_REL.replace("\\", "/"),),
            reuse_policy="success",
            runner_handler="default",
        ),
        GateCheckSpec(
            check_id=ENTRY_PYRIGHT_GATE_FULL,
            entry_type=ENTRY_PYRIGHT_GATE_FULL,
            display=f"python -m pyright -p {QUALITY_GATE_PYRIGHT_GATE_CONFIG}",
            args=("python", "-m", "pyright", "-p", QUALITY_GATE_PYRIGHT_GATE_CONFIG),
            capture_output=False,
            output_policy="normalized",
            input_file_scopes=_pyright_gate_input_scopes(repo_root),
            config_file_scopes=(
                QUALITY_GATE_PYRIGHT_GATE_CONFIG,
                "pyrightconfig.json",
                "pyproject.toml",
                "setup.cfg",
            ),
            dependency_file_scopes=_COMMON_DEPENDENCY_SCOPES,
            env_keys=pyright_env,
            output_result_files=(QUALITY_GATE_PYRIGHT_GATE_FULL_REL.replace("\\", "/"),),
            proof_kind="static_check",
            reuse_policy="success",
            runner_handler="default",
        ),
        GateCheckSpec(
            check_id=ENTRY_PYRIGHT_TOOLS_FULL,
            entry_type=ENTRY_PYRIGHT_TOOLS_FULL,
            display=f"python -m pyright -p {QUALITY_GATE_PYRIGHT_TOOLS_CONFIG}",
            args=("python", "-m", "pyright", "-p", QUALITY_GATE_PYRIGHT_TOOLS_CONFIG),
            capture_output=False,
            output_policy="normalized",
            input_file_scopes=_dedupe_tuple(
                (
                    *QUALITY_GATE_TOOL_PATHS,
                    "tools/__init__.py",
                    "web/bootstrap/**/*.py",
                    "core/infrastructure/logging.py",
                    "core/infrastructure/transaction.py",
                    "typings/**/*.pyi",
                    "py.typed",
                )
            ),
            config_file_scopes=(
                QUALITY_GATE_PYRIGHT_TOOLS_CONFIG,
                QUALITY_GATE_PYRIGHT_GATE_CONFIG,
                "pyrightconfig.json",
                "pyproject.toml",
                "setup.cfg",
            ),
            tool_file_scopes=_dedupe_tuple(QUALITY_GATE_TOOL_PATHS),
            dependency_file_scopes=_COMMON_DEPENDENCY_SCOPES,
            env_keys=pyright_env,
            output_result_files=(QUALITY_GATE_PYRIGHT_TOOLS_FULL_REL.replace("\\", "/"),),
            proof_kind="static_check",
            reuse_policy="success",
            runner_handler="pyright_tools",
        ),
        GateCheckSpec(
            check_id=ENTRY_DEBT_LEDGER_SYNC,
            entry_type=ENTRY_DEBT_LEDGER_SYNC,
            display="python scripts/sync_debt_ledger.py check",
            args=("python", "scripts/sync_debt_ledger.py", "check"),
            capture_output=False,
            output_policy="normalized",
            input_file_scopes=(
                "开发文档/技术债务治理台账.md",
                *tracked_roadmap_scopes,
                "app.py",
                "schema.sql",
                "core/**/*.py",
                "data/**/*.py",
                "web/**/*.py",
                "plugins/**/*.py",
                "desktop/**/*.py",
                "scripts/**/*.py",
                "tools/**/*.py",
                "tests/**/*.py",
                "templates/**/*.html",
                "static/**/*",
                "docs/**/*.md",
                "开发文档/**/*.md",
            ),
            config_file_scopes=(
                "pyproject.toml",
                "setup.cfg",
                "pytest.ini",
                "tox.ini",
                ".pre-commit-config.yaml",
                ".gitignore",
                ".github/workflows/quality.yml",
                QUALITY_GATE_PYRIGHT_GATE_CONFIG,
                QUALITY_GATE_PYRIGHT_TOOLS_CONFIG,
                "pyrightconfig.json",
                ".codestable/roadmap/aps-architecture-consolidation/aps-architecture-consolidation-roadmap.md",
                ".codestable/roadmap/aps-architecture-consolidation/aps-architecture-consolidation-items.yaml",
            ),
            tool_file_scopes=(
                "scripts/sync_debt_ledger.py",
                "tools/quality_gate_ledger.py",
                "tools/quality_gate_operations.py",
                "tools/quality_gate_scan.py",
                "tools/quality_gate_entries.py",
                "tools/quality_gate_shared.py",
                "tools/architecture_scan_cache.py",
                "tools/test_debt_registry.py",
                "tools/test_registry.py",
                "tools/long_gate_manifest.py",
                "tools/long_gate_fingerprint.py",
                "tools/long_gate_cache.py",
                "tools/long_gate_schema.py",
                "tools/long_gate_paths.py",
                "tools/long_gate_summary.py",
                "scripts/run_quality_gate.py",
            ),
            dependency_file_scopes=_COMMON_DEPENDENCY_SCOPES,
            env_keys=(
                "python_executable_realpath",
                "python_version",
                "platform",
                "architecture_scan_cache_metadata",
                "git_executable_realpath",
                "git_version",
                "VIRTUAL_ENV",
                "PYTHONHOME",
                "PYTHONPATH",
                "PYTHONDONTWRITEBYTECODE",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
                "LANG",
                "CI",
            ),
            output_result_files=(QUALITY_GATE_DEBT_LEDGER_SYNC_REL.replace("\\", "/"),),
            proof_kind="debt_ledger_sync",
            reuse_policy="success",
        ),
        GateCheckSpec(
            check_id=ENTRY_FULL_TEST_DEBT,
            entry_type=ENTRY_FULL_TEST_DEBT,
            display=full_debt_display,
            args=full_debt_args,
            capture_output=True,
            output_policy="exact",
            env_overlay=browser_overlay,
            input_file_scopes=_dedupe_tuple(
                (
                    *req_input_for_full_debt,
                    "tests/**/*.py",
                    "tests/**/*.cjs",
                    "tests/**/fixtures/*.json",
                    "tests/**/conftest.py",
                    "core/**/*.py",
                    "web/**/*.py",
                    "data/**/*.py",
                    "plugins/**/*.py",
                    "scripts/**/*.py",
                    "scripts/workbench/*.cjs",
                    "desktop/**/*.py",
                    "app.py",
                    "check_manual_layout.py",
                    "schema.sql",
                    "validate_dist_exe.py",
                    "verify_manual_styles.py",
                    "assets/**/*",
                    "installer/**/*",
                    "build_win7*.bat",
                    "templates/**/*.html",
                    "static/**/*",
                    "frontend/workbench/app/**/*.js",
                    "frontend/workbench/app/**/*.jsx",
                    "tests/portable_sample/*.ps1",
                    "packaging/win7/**/*",
                    "packaging/win7/*.ps1",
                    "packaging/win7/*.cmd",
                    ".codex/hooks/**/*.py",
                    ".codex/hooks.json",
                    ".codestable/architecture/**/*.md",
                    ".codestable/requirements/**/*.md",
                    *tracked_roadmap_scopes,
                    "docs/**/*.md",
                    "docs/**/*.html",
                    "docs/**/*.css",
                    "docs/**/*.js",
                    "evidence/README.md",
                    "evidence/current/README.md",
                    ".github/workflows/*.yml",
                    ".gitignore",
                    ".limcode/skills/**/*.md",
                    ".limcode/skills/**/*.py",
                    ".limcode/skills/**/*.ps1",
                    "开发文档/**/*.md",
                    QUALITY_GATE_COLLECT_NODEIDS_REL,
                )
            ),
            config_file_scopes=(
                "pytest.ini",
                "pyproject.toml",
                "setup.cfg",
                "tox.ini",
                "开发文档/技术债务治理台账.md",
                "tools/check_full_test_debt.py",
                "tools/collect_full_test_debt.py",
                "tools/full_test_debt_shards.py",
                "tools/test_debt_registry.py",
                "tools/quality_gate_shared.py",
                ".codestable/tools/**/*.py",
                "scripts/run_quality_gate.py",
            ),
            tool_file_scopes=(
                "tools/test_registry*.py",
                "tools/generate_schema_sql.py",
                "tools/resolve_iscc.ps1",
                "tools/wufenchang_demo/**/*.py",
                *_ESBUILD_GATE_SCOPES,
            ),
            dependency_file_scopes=(
                *_COMMON_DEPENDENCY_SCOPES,
                *_ESBUILD_GATE_SCOPES,
            ),
            env_keys=_dedupe_tuple(
                (
                    "python_executable_realpath",
                    "python_version",
                    "pytest_version",
                    "pytest_plugin_distribution_versions",
                    "platform",
                    "git_executable_realpath",
                    "git_version",
                    "node_executable_realpath",
                    "node_version",
                    "powershell_executable_realpath",
                    "powershell_version",
                    "CI",
                    "NODE_OPTIONS",
                    "PYTHONPATH",
                    "PYTHONUTF8",
                    "PYTHONIOENCODING",
                    "PYTEST_ADDOPTS",
                    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                    "PYTEST_PLUGINS",
                    *_registry_test_environment_keys(),
                )
            ),
            output_result_files=(
                QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/"),
                QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL.replace("\\", "/"),
            ),
            proof_kind="full_test_debt",
            reuse_policy="success_or_failure",
        ),
        GateCheckSpec(
            check_id=ENTRY_REQUIRED_REGRESSIONS,
            entry_type=ENTRY_REQUIRED_REGRESSIONS,
            display="python tools/verify_required_regressions_from_full_test_debt.py",
            args=("python", "tools/verify_required_regressions_from_full_test_debt.py"),
            capture_output=True,
            output_policy="normalized",
            env_overlay=browser_overlay,
            input_file_scopes=req_input,
            config_file_scopes=req_config,
            tool_file_scopes=req_tool,
            dependency_file_scopes=req_dep,
            env_keys=req_env,
            output_result_files=(QUALITY_GATE_REQUIRED_REGRESSIONS_REL.replace("\\", "/"),),
            proof_kind="required_regressions",
            reuse_policy="success",
        ),
    ]


def build_quality_gate_receipt_rel_path(index: int, display: str) -> str:
    slug = slugify(display) or f"command-{int(index)}"
    short_slug = slug[:48].rstrip("-") or f"command-{int(index)}"
    return os.path.join(QUALITY_GATE_RECEIPTS_DIR_REL, f"{int(index):02d}_{short_slug}.json").replace("\\", "/")


def build_quality_gate_command_receipt(
    command: Dict[str, Any],
    *,
    run_id: str = "",
    command_index: int = 0,
    returncode: int,
    stdout: str = "",
    stderr: str = "",
    stdout_log_path: str = "",
    stderr_log_path: str = "",
) -> Dict[str, Any]:
    normalized_command = _normalize_command_rows([command])[0]
    output_policy = normalized_command["output_policy"]
    receipt: Dict[str, Any] = {
        "schema_version": int(QUALITY_GATE_PROOF_SCHEMA_VERSION),
        "run_id": str(run_id or "").strip(),
        "command_index": int(command_index or 0),
        "display": normalized_command["display"],
        "args": normalized_command["args"],
        "capture_output": normalized_command["capture_output"],
        "output_policy": output_policy,
        "env_overlay": normalized_command["env_overlay"],
        "returncode": int(returncode or 0),
        "stdout_content": _normalize_command_output_for_policy(str(stdout or ""), policy=output_policy),
        "stderr_content": _normalize_command_output_for_policy(str(stderr or ""), policy=output_policy),
        "stdout_log_path": str(stdout_log_path or "").replace("\\", "/"),
        "stderr_log_path": str(stderr_log_path or "").replace("\\", "/"),
        "execution_mode": "executed",
        "reused_from": {},
        "timed_out": False,
        "interrupted": False,
        "partial_write": False,
    }
    for key in _COMMAND_SPEC_METADATA_KEYS:
        if key in normalized_command:
            receipt[key] = normalized_command[key]
    return receipt


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


def build_quality_gate_source_proof(repo_root: Optional[Union[os.PathLike, str]] = None) -> List[Dict[str, Any]]:
    root = os.path.abspath(os.fspath(repo_root) if repo_root is not None else REPO_ROOT)
    rows: List[Dict[str, Any]] = []
    for rel_path in QUALITY_GATE_SOURCE_FILES:
        abs_path = os.path.join(root, rel_path.replace("/", os.sep))
        exists = os.path.isfile(abs_path)
        try:
            content_base64 = read_file_content(abs_path) if exists else ""
        except SensitiveSourceError as exc:
            raise QualityGateError(f"门禁来源文件包含敏感内容（{rel_path}）：{exc}") from exc
        rows.append(
            {
                "path": str(rel_path).replace("\\", "/"),
                "exists": bool(exists),
                "content_base64": content_base64,
            }
        )
    return _normalize_source_rows(rows)


def apply_quality_gate_manifest_proof_fields(
    manifest: Dict[str, Any],
    *,
    repo_root: Optional[Union[os.PathLike, str]] = None,
) -> Dict[str, Any]:
    manifest["proof_scope"] = dict(QUALITY_GATE_PROOF_SCOPE)
    required_tests = _normalize_required_tests(manifest.get("required_tests") or iter_quality_gate_required_tests())
    manifest["required_tests"] = required_tests

    commands = _normalize_command_rows(manifest.get("commands") or [])
    manifest["commands"] = commands

    collection_proof = _normalize_collection_proof(manifest.get("collection_proof") or {})
    manifest["collection_proof"] = collection_proof

    command_receipts = _normalize_command_receipt_index(manifest.get("command_receipts") or [])
    if any(not isinstance(row.get("content"), dict) for row in command_receipts):
        raise QualityGateError("Legacy quality gate receipt content is unavailable; execute a new run.")
    manifest["command_receipts"] = command_receipts

    gate_sources = _normalize_source_rows(manifest.get("gate_sources") or build_quality_gate_source_proof(repo_root))
    if any(not isinstance(row.get("content_base64"), str) for row in gate_sources):
        raise QualityGateError("Legacy quality gate source content is unavailable; execute a new run.")
    manifest["gate_sources"] = gate_sources
    manifest["schema_version"] = QUALITY_GATE_PROOF_SCHEMA_VERSION
    return manifest


def _load_verified_quality_gate_receipt(
    repo_root: Union[os.PathLike, str],
    receipt_entry: Dict[str, Any],
    command: Dict[str, Any],
    *,
    index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(receipt_entry.get("content"), dict):
        return None, "UNBOUND: quality gate command receipt content missing"
    receipt_path = str(receipt_entry.get("path") or "").replace("\\", "/")
    expected_path = build_quality_gate_receipt_rel_path(index, str(command.get("display") or ""))
    if receipt_path != expected_path:
        return None, "UNBOUND: quality gate command receipt path mismatch"
    allowed_directory = os.path.realpath(os.path.join(os.fspath(repo_root), QUALITY_GATE_RECEIPTS_DIR_REL))
    abs_path = os.path.realpath(os.path.join(os.fspath(repo_root), receipt_path.replace("/", os.sep)))
    if not receipt_path or not abs_path.startswith(allowed_directory + os.sep):
        return None, "UNBOUND: quality gate command receipt path mismatch"
    if not os.path.isfile(abs_path):
        return None, "UNBOUND: quality gate command receipt missing"
    try:
        with open(abs_path, "rb") as handle:
            receipt_bytes = handle.read()
        payload = json.loads(receipt_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, "UNBOUND: quality gate command receipt unreadable"
    if not isinstance(payload, dict) or not payload:
        return None, "UNBOUND: quality gate command receipt unreadable"
    if not content_equal(payload, receipt_entry["content"]):
        return None, "UNBOUND: quality gate command receipt content mismatch"
    return payload, None


def _verify_receipt_header(
    receipt: Dict[str, Any],
    *,
    index: int,
    run_id: str,
) -> Optional[str]:
    schema_version = int(receipt.get("schema_version") or 0)
    if schema_version != QUALITY_GATE_PROOF_SCHEMA_VERSION:
        return "UNBOUND: quality gate command receipt schema_version mismatch"
    if str(receipt.get("run_id") or "").strip() != str(run_id or "").strip() or not str(run_id or "").strip():
        return "UNBOUND: quality gate command receipt run_id mismatch"
    if int(receipt.get("command_index") or 0) != int(index):
        return "UNBOUND: quality gate command receipt command_index mismatch"
    return None


def _verify_receipt_command_fields(receipt: Dict[str, Any], normalized_command: Dict[str, Any]) -> Optional[str]:
    for key in ("display", "args", "capture_output", "output_policy", "env_overlay", *_COMMAND_SPEC_METADATA_KEYS):
        if key in normalized_command or key in receipt:
            if (
                key not in receipt
                or key not in normalized_command
                or not content_equal(receipt.get(key), normalized_command[key])
            ):
                return f"UNBOUND: quality gate command receipt {key} mismatch"
    return None


def _verify_receipt_execution_fields(receipt: Dict[str, Any]) -> Optional[str]:
    execution_mode = str(receipt.get("execution_mode") or "").strip()
    if execution_mode not in {
        "executed",
        "reused_success_cache",
        "resumed_success_prefix",
    }:
        return "UNBOUND: quality gate command receipt execution_mode mismatch"
    for field_name in ("timed_out", "interrupted", "partial_write"):
        if not isinstance(receipt.get(field_name), bool):
            return f"UNBOUND: quality gate command receipt {field_name} mismatch"
    if any(bool(receipt.get(field_name)) for field_name in ("timed_out", "interrupted", "partial_write")):
        return "UNBOUND: quality gate command receipt incomplete execution"
    reused_from_obj = receipt.get("reused_from")
    reused_from = cast(Mapping[str, Any], reused_from_obj if isinstance(reused_from_obj, dict) else {})
    if execution_mode == "reused_success_cache":
        if not str(reused_from.get("result_path") or "").strip():
            return "UNBOUND: quality gate command receipt reused_from result_path missing"
        if not isinstance(reused_from.get("fingerprint"), dict) or not reused_from["fingerprint"]:
            return "UNBOUND: quality gate command receipt reused_from fingerprint content missing"
    if execution_mode == "resumed_success_prefix":
        if not str(reused_from.get("receipt_path") or "").strip():
            return "UNBOUND: quality gate command receipt reused_from receipt_path missing"
        if not str(reused_from.get("run_id") or "").strip():
            return "UNBOUND: quality gate command receipt reused_from run_id missing"
    return None


def collect_quality_rule_files() -> List[str]:
    return sorted(set(collect_py_files(*CORE_DIRS) + collect_startup_scope_files()))


def is_startup_scope_path(path: str) -> bool:
    rel_path = str(path).replace("\\", "/")
    return rel_path.startswith("web/bootstrap/")


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
