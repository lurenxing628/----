"""为 UI 浏览器几何 smoke 测试提供运行时探测与环境失败上报夹具：解析/校验 Chrome（APS_CHROME_PATH 或默认候选，含 --version 探测与显式配置必硬失败）与 Node（含 fetch/WebSocket 能力检查）的 ChromeRuntimeInfo/NodeRuntimeInfo，并按 APS_BROWSER_SMOKE_REQUIRED/CI 决定 _fail_or_skip_env 是 fail 还是 skip，输出带 PATH/版本等上下文的 JSON 诊断。"""

from __future__ import annotations

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import pytest
from werkzeug.serving import make_server

from tests.ui_geometry_contract_data import ERROR_PAGE_KEYWORDS, EXPECTED_PAGE_SIGNALS, UI_GEOMETRY_PAGE_PATHS

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATHS = UI_GEOMETRY_PAGE_PATHS
UI_GEOMETRY_PROBE_SOURCE = REPO_ROOT / "tests" / "ui_geometry_probe.mjs"
REQUIRED_BROWSER_ENV_OVERLAY = {
    "APS_BROWSER_SMOKE_REQUIRED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}

@dataclass(frozen=True)
class ChromeRuntimeInfo:
    chrome_path: str
    chrome_source: str
    chrome_version_stdout: str = ""
    chrome_version_stderr: str = ""
    chrome_version_returncode: Optional[int] = None
    exists: bool = False
    failure_kind: str = ""
    message: str = ""
    explicit_config: bool = False


@dataclass(frozen=True)
class NodeRuntimeInfo:
    node_path: str
    node_realpath: str
    node_version_stdout: str = ""
    node_version_stderr: str = ""
    node_version_returncode: Optional[int] = None
    node_capability_stdout: str = ""
    node_capability_stderr: str = ""
    node_capability_returncode: Optional[int] = None
    failure_kind: str = ""
    message: str = ""


@dataclass(frozen=True)
class ServedApp:
    server: Any
    thread: threading.Thread
    base_url: str


def _tail_text(text: str, limit: int = 4096) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[-limit:]


def _timeout_output_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _path_excerpt() -> str:
    path_value = os.environ.get("PATH", "")
    if len(path_value) <= 500:
        return path_value
    return path_value[:240] + "...<truncated>..." + path_value[-240:]


def _browser_smoke_required() -> Tuple[bool, str]:
    if os.environ.get("APS_BROWSER_SMOKE_REQUIRED") == "1":
        return True, "APS_BROWSER_SMOKE_REQUIRED"
    if os.environ.get("CI"):
        return True, "CI"
    return False, "local"


def _format_browser_env_failure(
    failure_kind: str,
    *,
    message: str,
    chrome: Optional[ChromeRuntimeInfo] = None,
    node: Optional[NodeRuntimeInfo] = None,
    required_source: str = "",
) -> str:
    required, source = _browser_smoke_required()
    payload: Dict[str, Any] = {
        "failure_kind": failure_kind,
        "message": message,
        "required": required,
        "required_source": required_source or source,
        "APS_BROWSER_SMOKE_REQUIRED": os.environ.get("APS_BROWSER_SMOKE_REQUIRED"),
        "CI": os.environ.get("CI"),
        "APS_CHROME_PATH": os.environ.get("APS_CHROME_PATH"),
        "PATH_excerpt": _path_excerpt(),
    }
    if chrome is not None:
        payload["chrome"] = {
            "chrome_path": chrome.chrome_path,
            "chrome_source": chrome.chrome_source,
            "exists": chrome.exists,
            "explicit_config": chrome.explicit_config,
            "version_returncode": chrome.chrome_version_returncode,
            "version_stdout": chrome.chrome_version_stdout,
            "version_stderr": chrome.chrome_version_stderr,
            "message": chrome.message,
        }
    if node is not None:
        payload["node"] = {
            "node_path": node.node_path,
            "node_realpath": node.node_realpath,
            "version_returncode": node.node_version_returncode,
            "version_stdout": node.node_version_stdout,
            "version_stderr": node.node_version_stderr,
            "capability_returncode": node.node_capability_returncode,
            "capability_stdout": node.node_capability_stdout,
            "capability_stderr": node.node_capability_stderr,
            "message": node.message,
        }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _browser_runtime_context(
    *,
    chrome: Optional[ChromeRuntimeInfo] = None,
    node: Optional[NodeRuntimeInfo] = None,
) -> Dict[str, Any]:
    required, required_source = _browser_smoke_required()
    payload: Dict[str, Any] = {
        "required": required,
        "required_source": required_source,
        "APS_BROWSER_SMOKE_REQUIRED": os.environ.get("APS_BROWSER_SMOKE_REQUIRED"),
        "CI": os.environ.get("CI"),
        "APS_CHROME_PATH": os.environ.get("APS_CHROME_PATH"),
        "PATH_excerpt": _path_excerpt(),
    }
    if chrome is not None:
        payload["chrome"] = {
            "chrome_path": chrome.chrome_path,
            "chrome_source": chrome.chrome_source,
            "version_returncode": chrome.chrome_version_returncode,
            "version_stdout": chrome.chrome_version_stdout,
            "version_stderr": chrome.chrome_version_stderr,
        }
    if node is not None:
        payload["node"] = {
            "node_path": node.node_path,
            "node_realpath": node.node_realpath,
            "version_returncode": node.node_version_returncode,
            "version_stdout": node.node_version_stdout,
            "version_stderr": node.node_version_stderr,
            "capability_returncode": node.node_capability_returncode,
            "capability_stdout": node.node_capability_stdout,
            "capability_stderr": node.node_capability_stderr,
        }
    return payload


def _fail_or_skip_env(failure_kind: str, message: str, *, chrome: Optional[ChromeRuntimeInfo] = None, node: Optional[NodeRuntimeInfo] = None) -> None:
    required, required_source = _browser_smoke_required()
    formatted = _format_browser_env_failure(
        failure_kind,
        message=message,
        chrome=chrome,
        node=node,
        required_source=required_source,
    )
    if required:
        pytest.fail(formatted)
    pytest.skip(formatted)


def _run_probe_command(args: List[str], *, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _probe_chrome_version(chrome_path: str) -> subprocess.CompletedProcess:
    return _run_probe_command([chrome_path, "--version"], timeout=10)


def _chrome_default_candidates() -> Tuple[Tuple[str, Optional[str]], ...]:
    return (
        ("macos_google_chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ("macos_chromium", "/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ("PATH:google-chrome", shutil.which("google-chrome")),
        ("PATH:chromium", shutil.which("chromium")),
        ("PATH:chromium-browser", shutil.which("chromium-browser")),
    )


def _resolve_chrome() -> ChromeRuntimeInfo:
    explicit = os.environ.get("APS_CHROME_PATH")
    if explicit is not None:
        chrome_path = explicit.strip()
        if not chrome_path:
            return ChromeRuntimeInfo(
                chrome_path=chrome_path,
                chrome_source="APS_CHROME_PATH",
                exists=False,
                failure_kind="browser_env_bad_chrome_path",
                message="APS_CHROME_PATH 已设置，但内容为空。",
                explicit_config=True,
            )
        exists = Path(chrome_path).exists()
        if not exists:
            return ChromeRuntimeInfo(
                chrome_path=chrome_path,
                chrome_source="APS_CHROME_PATH",
                exists=False,
                failure_kind="browser_env_bad_chrome_path",
                message="APS_CHROME_PATH 指向的 Chrome 路径不存在，不会 fallback 到默认 Chrome。",
                explicit_config=True,
            )
        try:
            completed = _probe_chrome_version(chrome_path)
        except subprocess.TimeoutExpired as exc:
            stdout = _timeout_output_text(getattr(exc, "stdout", None) or getattr(exc, "output", None))
            stderr = _timeout_output_text(getattr(exc, "stderr", None))
            return ChromeRuntimeInfo(
                chrome_path=chrome_path,
                chrome_source="APS_CHROME_PATH",
                chrome_version_stdout=stdout,
                chrome_version_stderr=stderr,
                exists=True,
                failure_kind="browser_env_chrome_version_failed",
                message=f"APS_CHROME_PATH 指向的 Chrome 执行 --version 超时：{exc}",
                explicit_config=True,
            )
        except OSError as exc:
            return ChromeRuntimeInfo(
                chrome_path=chrome_path,
                chrome_source="APS_CHROME_PATH",
                exists=True,
                failure_kind="browser_env_chrome_version_failed",
                message=f"APS_CHROME_PATH 指向的 Chrome 无法执行 --version：{exc}",
                explicit_config=True,
            )
        if int(completed.returncode) != 0:
            return ChromeRuntimeInfo(
                chrome_path=chrome_path,
                chrome_source="APS_CHROME_PATH",
                chrome_version_stdout=str(completed.stdout or ""),
                chrome_version_stderr=str(completed.stderr or ""),
                chrome_version_returncode=int(completed.returncode),
                exists=True,
                failure_kind="browser_env_chrome_version_failed",
                message="APS_CHROME_PATH 指向的 Chrome 执行 --version 失败。",
                explicit_config=True,
            )
        return ChromeRuntimeInfo(
            chrome_path=chrome_path,
            chrome_source="APS_CHROME_PATH",
            chrome_version_stdout=str(completed.stdout or ""),
            chrome_version_stderr=str(completed.stderr or ""),
            chrome_version_returncode=int(completed.returncode),
            exists=True,
            explicit_config=True,
        )

    failures: List[ChromeRuntimeInfo] = []
    for source, candidate in _chrome_default_candidates():
        if not candidate:
            continue
        candidate_path = str(candidate)
        if not Path(candidate_path).exists():
            continue
        try:
            completed = _probe_chrome_version(candidate_path)
        except subprocess.TimeoutExpired as exc:
            failures.append(
                ChromeRuntimeInfo(
                    chrome_path=candidate_path,
                    chrome_source=source,
                    chrome_version_stdout=_timeout_output_text(getattr(exc, "stdout", None) or getattr(exc, "output", None)),
                    chrome_version_stderr=_timeout_output_text(getattr(exc, "stderr", None)),
                    exists=True,
                    failure_kind="browser_env_chrome_version_failed",
                    message=f"默认候选 Chrome 执行 --version 超时：{exc}",
                )
            )
            continue
        except OSError as exc:
            failures.append(
                ChromeRuntimeInfo(
                    chrome_path=candidate_path,
                    chrome_source=source,
                    exists=True,
                    failure_kind="browser_env_chrome_version_failed",
                    message=f"默认候选 Chrome 无法执行 --version：{exc}",
                )
            )
            continue
        if int(completed.returncode) == 0:
            return ChromeRuntimeInfo(
                chrome_path=candidate_path,
                chrome_source=source,
                chrome_version_stdout=str(completed.stdout or ""),
                chrome_version_stderr=str(completed.stderr or ""),
                chrome_version_returncode=int(completed.returncode),
                exists=True,
            )
        failures.append(
            ChromeRuntimeInfo(
                chrome_path=candidate_path,
                chrome_source=source,
                chrome_version_stdout=str(completed.stdout or ""),
                chrome_version_stderr=str(completed.stderr or ""),
                chrome_version_returncode=int(completed.returncode),
                exists=True,
                failure_kind="browser_env_chrome_version_failed",
                message="默认候选 Chrome 执行 --version 失败。",
            )
        )

    detail = "; ".join(f"{item.chrome_source}={item.chrome_path}: {item.message}" for item in failures) or "没有找到默认 Chrome/Chromium 候选。"
    return ChromeRuntimeInfo(
        chrome_path="",
        chrome_source="auto",
        exists=False,
        failure_kind="browser_env_missing_chrome",
        message=detail,
    )


def _find_chrome() -> ChromeRuntimeInfo:
    chrome = _resolve_chrome()
    if chrome.failure_kind:
        if chrome.explicit_config:
            pytest.fail(
                _format_browser_env_failure(
                    chrome.failure_kind,
                    message=chrome.message,
                    chrome=chrome,
                )
            )
        _fail_or_skip_env(chrome.failure_kind, chrome.message, chrome=chrome)
    return chrome


def _resolve_node_with_browser_runtime() -> NodeRuntimeInfo:
    node = shutil.which("node")
    if not node:
        return NodeRuntimeInfo(
            node_path="",
            node_realpath="",
            failure_kind="browser_env_missing_node",
            message="UI 浏览器几何 smoke 需要 Node.js，且全局 fetch/WebSocket 必须可用。",
        )
    node_realpath = os.path.realpath(node)
    try:
        version = _run_probe_command([node, "--version"], timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return NodeRuntimeInfo(
            node_path=node,
            node_realpath=node_realpath,
            failure_kind="browser_env_node_capability_failed",
            message=f"Node.js 无法执行 --version：{exc}",
        )
    capability_script = (
        "const missing = [];"
        "if (typeof fetch !== 'function') missing.push('fetch');"
        "if (typeof WebSocket !== 'function') missing.push('WebSocket');"
        "if (missing.length) { console.error('missing ' + missing.join(',')); process.exit(1); }"
        "console.log('fetch/WebSocket available');"
    )
    try:
        capability = _run_probe_command([node, "-e", capability_script], timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return NodeRuntimeInfo(
            node_path=node,
            node_realpath=node_realpath,
            node_version_stdout=str(version.stdout or ""),
            node_version_stderr=str(version.stderr or ""),
            node_version_returncode=int(version.returncode),
            failure_kind="browser_env_node_capability_failed",
            message=f"Node.js fetch/WebSocket 能力检查无法执行：{exc}",
        )
    if int(version.returncode) != 0 or int(capability.returncode) != 0:
        return NodeRuntimeInfo(
            node_path=node,
            node_realpath=node_realpath,
            node_version_stdout=str(version.stdout or ""),
            node_version_stderr=str(version.stderr or ""),
            node_version_returncode=int(version.returncode),
            node_capability_stdout=str(capability.stdout or ""),
            node_capability_stderr=str(capability.stderr or ""),
            node_capability_returncode=int(capability.returncode),
            failure_kind="browser_env_node_capability_failed",
            message="需要 Node.js，且全局 fetch/WebSocket 必须可用。建议使用 Node 24，但当前检查的是能力，不是只看版本号。",
        )
    return NodeRuntimeInfo(
        node_path=node,
        node_realpath=node_realpath,
        node_version_stdout=str(version.stdout or ""),
        node_version_stderr=str(version.stderr or ""),
        node_version_returncode=int(version.returncode),
        node_capability_stdout=str(capability.stdout or ""),
        node_capability_stderr=str(capability.stderr or ""),
        node_capability_returncode=int(capability.returncode),
    )


def _find_node_with_browser_runtime() -> NodeRuntimeInfo:
    node = _resolve_node_with_browser_runtime()
    if node.failure_kind:
        _fail_or_skip_env(node.failure_kind, node.message, node=node)
    return node
