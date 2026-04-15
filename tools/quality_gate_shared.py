from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LEDGER_PATH = os.path.join(REPO_ROOT, "开发文档", "技术债务治理台账.md")
STAGE_RECORD_PATH = os.path.join(REPO_ROOT, "开发文档", "阶段留痕与验收记录.md")
TEST_ARCH_FITNESS_PATH = os.path.join(REPO_ROOT, "tests", "test_architecture_fitness.py")

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
    "web/routes/domains/scheduler/scheduler_excel_batches.py",
    "web/routes/system_backup.py",
    "web/routes/system_history.py",
    "web/routes/system_logs.py",
    "web/routes/system_plugins.py",
    "web/routes/system_ui_mode.py",
    "web/routes/system_utils.py",
    "web/ui_mode.py",
]
REQUEST_SERVICE_TARGET_SYMBOLS = {
    "tests/run_real_db_replay_e2e.py": ["_create_test_app", "_open_db"],
    "tests/run_complex_excel_cases_e2e.py": ["create_test_app", "_open_db"],
}
# 当前目标文件已无批准保留的 helper 直连；如后续需要新增例外，必须以精确坐标登记。
REQUEST_SERVICE_TARGET_ALLOWED_HELPERS = []
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
        line_start=351,
        line_end=352,
        fallback_kind="cleanup_best_effort",
    ),
    SilentFallbackSample(
        path="web/bootstrap/launcher.py",
        symbol="stop_runtime_from_dir",
        line_start=981,
        line_end=983,
        fallback_kind="silent_default_fallback",
    ),
    SilentFallbackSample(
        path="web/ui_mode.py",
        symbol="_read_ui_mode_from_db",
        line_start=242,
        line_end=244,
        fallback_kind="observable_degrade",
        scope_tag="startup_guard",
    ),
    SilentFallbackSample(
        path="web/ui_mode.py",
        symbol="safe_url_for",
        line_start=348,
        line_end=355,
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
