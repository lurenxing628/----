from __future__ import annotations

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import textwrap
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import pytest
from werkzeug.serving import make_server

from tests.ui_geometry_contract_data import ERROR_PAGE_KEYWORDS, EXPECTED_PAGE_SIGNALS, UI_GEOMETRY_PAGE_PATHS

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATHS = UI_GEOMETRY_PAGE_PATHS
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


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(tmp_path / "aps_ui_geometry.db"))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(tmp_path / "templates_excel"))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates_excel").mkdir(parents=True, exist_ok=True)

    from core.infrastructure.database import ensure_schema

    ensure_schema(
        str(tmp_path / "aps_ui_geometry.db"),
        logger=None,
        schema_path=str(REPO_ROOT / "schema.sql"),
        backup_dir=None,
    )
    conn = sqlite3.connect(str(tmp_path / "aps_ui_geometry.db"))
    try:
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P_UI_GEOMETRY", "浏览器几何测试零件", "", "no"),
        )
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_UI_GEOMETRY", "P_UI_GEOMETRY", "浏览器几何测试零件", 1, "2026-05-20", "normal", "yes", "pending"),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory
                (schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-05-06 09:00:00",
                1,
                "priority_first",
                1,
                1,
                "success",
                json.dumps(
                    {
                        "algo": {
                            "mode": "improve",
                            "objective": "min_overdue",
                            "metrics": {
                                "total_tardiness_hours": 0,
                                "weighted_tardiness_hours": 0,
                                "makespan_hours": 1,
                                "changeover_count": 0,
                                "machine_util_avg": 0.5,
                            },
                        },
                        "warnings": [],
                        "errors": [],
                    },
                    ensure_ascii=False,
                ),
                "ui-smoke",
            ),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory
                (schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-05-06 10:00:00",
                2,
                "priority_first",
                1,
                1,
                "failed",
                "{bad json",
                "ui-smoke",
            ),
        )
        conn.execute(
            """
            INSERT INTO OperationLogs
                (log_time, log_level, module, action, target_type, target_id, detail, error_code, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-05-06 10:30:00",
                "ERROR",
                "plugins",
                "toggle",
                "plugin",
                "ui-smoke-plugin",
                "{bad json",
                "PLUGIN_LOAD_FAILED",
                "历史日志里保留 Traceback / Werkzeug / Internal Server Error 字样，用于确认正常应用页面不会被误判成错误页。",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)

    import app as app_mod

    app = app_mod.app
    app.config["PLUGIN_STATUS"] = {
        "loaded_at": "2026-05-06 09:00:00",
        "config_source": "default_due_to_config_read_failed",
        "telemetry_persisted": False,
        "degraded": True,
        "registry": {"capabilities": ("ui-smoke-capability",)},
        "degradation_events": (
            {"message": "扩展功能配置暂时读取不到，系统已按默认开关运行。"},
            {"message": "插件加载失败，请联系维护人员检查系统运行记录。"},
        ),
        "conflicted_capabilities": (),
        "statuses": (
            {
                "plugin_id": "ui-smoke-plugin",
                "name": "浏览器几何测试扩展",
                "version": "1.0",
                "enabled": "yes",
                "loaded": "no",
                "enabled_source": "default_due_to_config_read_failed",
                "error": "插件加载失败，请联系维护人员检查系统运行记录。",
                "capabilities": ("ui-smoke-capability",),
            },
        ),
    }
    return app


def _serve_app(app):
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return ServedApp(server=server, thread=thread, base_url=f"http://127.0.0.1:{server.server_port}")


def _shutdown_served_app(served: ServedApp) -> None:
    try:
        served.server.shutdown()
        served.thread.join(timeout=5)
        if served.thread.is_alive():
            print("WARNING: Flask test server thread did not stop within 5 seconds", file=sys.stderr, flush=True)
    finally:
        served.server.server_close()


def _kill_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except Exception:
                pass
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def _terminate_process_tree(process: subprocess.Popen, *, timeout: float = 5.0) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            process.terminate()
            process.wait(timeout=timeout)
            return
        except (OSError, subprocess.TimeoutExpired):
            _kill_process_tree(process)
            return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except Exception:
        try:
            process.terminate()
        except Exception:
            pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(process)


def _run_chrome_geometry_probe(
    *,
    chrome_path: str,
    node_path: str,
    base_url: str,
    tmp_path: Path,
    chrome_info: Optional[ChromeRuntimeInfo] = None,
    node_info: Optional[NodeRuntimeInfo] = None,
) -> List[Dict[str, Any]]:
    script = tmp_path / "ui_geometry_probe.mjs"
    script.write_text(
        textwrap.dedent(
            r"""
            import fs from "node:fs/promises";
            import path from "node:path";
            import { spawn } from "node:child_process";

            const chromePath = process.argv[2];
            const baseUrl = process.argv[3];
            const paths = JSON.parse(process.argv[4]);
            const expectedByPath = JSON.parse(process.argv[5]);
            const errorPageKeywords = JSON.parse(process.argv[6]);
            const profileBaseDir = process.argv[7];
            const runtimeContext = JSON.parse(process.argv[8] || "{}");
            await fs.mkdir(profileBaseDir, { recursive: true });
            const userDataDir = await fs.mkdtemp(path.join(profileBaseDir, "aps-ui-chrome-"));
            const chromeArgs = [
              "--headless=new",
              "--disable-gpu",
              "--disable-dev-shm-usage",
              "--no-first-run",
              "--no-default-browser-check",
              "--remote-debugging-port=0",
              `--user-data-dir=${userDataDir}`,
              "about:blank",
            ];

            const chrome = spawn(chromePath, chromeArgs, { stdio: ["ignore", "ignore", "pipe"] });

            const active = [];
            let chromeStderrTail = "";
            let chromeExited = false;
            let chromeExitCode = null;
            let chromeExitSignal = null;
            let chromeSpawnError = null;

            function appendChromeStderr(chunk) {
              chromeStderrTail += String(chunk || "");
              if (chromeStderrTail.length > 32768) {
                chromeStderrTail = chromeStderrTail.slice(-32768);
              }
            }

            if (chrome.stderr) {
              chrome.stderr.on("data", appendChromeStderr);
            }
            chrome.on("exit", (code, signal) => {
              chromeExited = true;
              chromeExitCode = code;
              chromeExitSignal = signal;
            });
            chrome.on("error", (error) => {
              chromeSpawnError = error;
            });

            class ProbeFailure extends Error {
              constructor(kind, details = {}) {
                super(kind);
                this.kind = kind;
                this.details = details;
              }
            }

            function failurePayload(kind, details = {}) {
              return {
                failure_kind: kind,
                stage: details.stage || "",
                message: details.message || kind,
                chromePath,
                chromeArgs,
                chromeExitCode,
                chromeExitSignal,
                chromeStderrTail,
                userDataDir,
                nodeVersion: process.version,
                baseUrl,
                runtime_context: runtimeContext,
                ...details,
              };
            }

            function fail(kind, details = {}) {
              throw new ProbeFailure(kind, failurePayload(kind, details));
            }

            async function sleep(ms) {
              await new Promise((resolve) => setTimeout(resolve, ms));
            }

            async function waitForChromeExit(timeoutMs) {
              if (chromeExited) {
                return { exited: true, code: chromeExitCode, signal: chromeExitSignal };
              }
              return await new Promise((resolve) => {
                const timer = setTimeout(() => resolve({ exited: false, timeoutMs }), timeoutMs);
                chrome.once("exit", (code, signal) => {
                  clearTimeout(timer);
                  resolve({ exited: true, code, signal });
                });
              });
            }

            async function readDebugPort() {
              const activePort = path.join(userDataDir, "DevToolsActivePort");
              const started = Date.now();
              for (let i = 0; i < 100; i += 1) {
                if (chromeSpawnError) {
                  fail("chrome_spawn_failed", {
                    stage: "readDebugPort",
                    message: String(chromeSpawnError && chromeSpawnError.stack ? chromeSpawnError.stack : chromeSpawnError),
                    activePort,
                    waitedMs: Date.now() - started,
                  });
                }
                if (chromeExited) {
                  fail("chrome_exited_before_devtools", {
                    stage: "readDebugPort",
                    activePort,
                    waitedMs: Date.now() - started,
                  });
                }
                try {
                  const content = await fs.readFile(activePort, "utf8");
                  const firstLine = content.trim().split(/\r?\n/)[0] || "";
                  const port = Number(firstLine);
                  if (!Number.isInteger(port) || port < 1 || port > 65535) {
                    fail("chrome_devtools_port_invalid", {
                      stage: "readDebugPort",
                      activePort,
                      rawContent: content.slice(0, 2048),
                      waitedMs: Date.now() - started,
                    });
                  }
                  return String(port);
                } catch (error) {
                  if (error instanceof ProbeFailure) {
                    throw error;
                  }
                  await sleep(100);
                }
              }
              fail("chrome_devtools_port_timeout", {
                stage: "readDebugPort",
                activePort,
                waitedMs: Date.now() - started,
              });
            }

            async function fetchWithTimeout(url, options = {}, timeoutMs = 5000) {
              const controller = new AbortController();
              const timer = setTimeout(() => controller.abort(), timeoutMs);
              try {
                return await fetch(url, { ...options, signal: controller.signal });
              } finally {
                clearTimeout(timer);
              }
            }

            async function withTimeout(promise, timeoutMs, message) {
              let timer;
              try {
                return await new Promise((resolve, reject) => {
                  timer = setTimeout(() => reject(new Error(message)), timeoutMs);
                  Promise.resolve(promise).then(resolve, reject);
                });
              } finally {
                clearTimeout(timer);
              }
            }

            async function preflightDevTools(port) {
              const url = `http://127.0.0.1:${port}/json/version`;
              let response;
              let body = "";
              try {
                response = await fetchWithTimeout(url, {}, 5000);
                body = await withTimeout(response.text(), 5000, "DevTools /json/version body timeout");
              } catch (error) {
                fail("chrome_devtools_version_unreachable", {
                  stage: "preflightDevTools",
                  port,
                  status: 0,
                  responseBody: String(error && error.stack ? error.stack : error).slice(0, 4096),
                });
              }
              if (!response.ok) {
                fail("chrome_devtools_version_unreachable", {
                  stage: "preflightDevTools",
                  port,
                  status: response.status,
                  responseBody: body.slice(0, 4096),
                });
              }
              let payload;
              try {
                payload = JSON.parse(body);
              } catch (error) {
                fail("chrome_devtools_version_unreachable", {
                  stage: "preflightDevTools",
                  port,
                  status: response.status,
                  responseBody: body.slice(0, 4096),
                  message: "DevTools /json/version did not return JSON",
                });
              }
              if (!payload.webSocketDebuggerUrl && !payload.Browser) {
                fail("chrome_devtools_version_unreachable", {
                  stage: "preflightDevTools",
                  port,
                  status: response.status,
                  responseBody: body.slice(0, 4096),
                  message: "DevTools /json/version missing Browser/webSocketDebuggerUrl",
                });
              }
              return payload;
            }

            class CdpClient {
              constructor(wsUrl) {
                this.nextId = 1;
                this.pending = new Map();
                this.waiters = new Map();
                this.ws = new WebSocket(wsUrl);
                this.context = {};
              }

              async open(timeoutMs = 10000) {
                await new Promise((resolve, reject) => {
                  let settled = false;
                  const finish = (callback, value) => {
                    if (settled) return;
                    settled = true;
                    clearTimeout(timer);
                    callback(value);
                  };
                  const websocketFailure = (stage, details = {}) => new ProbeFailure(
                    "cdp_websocket_failed",
                    failurePayload("cdp_websocket_failed", {
                      stage,
                      wsUrl: this.ws.url || "",
                      ...details,
                    })
                  );
                  const timer = setTimeout(() => {
                    finish(reject, websocketFailure("CdpClient.open.timeout", { timeoutMs }));
                  }, timeoutMs);
                  this.ws.onopen = () => finish(resolve, undefined);
                  this.ws.onerror = (error) => finish(reject, websocketFailure("CdpClient.open.error", {
                    message: String(error && error.message ? error.message : error),
                  }));
                  this.ws.onmessage = (event) => this.onMessage(event);
                  this.ws.onclose = (event) => finish(reject, websocketFailure("CdpClient.open.close", {
                    code: event && event.code,
                    reason: event && event.reason,
                  }));
                });
                this.ws.onerror = (error) => this.rejectAll(new ProbeFailure(
                  "cdp_websocket_failed",
                  failurePayload("cdp_websocket_failed", {
                    stage: "CdpClient.onerror",
                    wsUrl: this.ws.url || "",
                    message: String(error && error.message ? error.message : error),
                  })
                ));
                this.ws.onclose = (event) => this.rejectAll(new ProbeFailure(
                  "cdp_websocket_failed",
                  failurePayload("cdp_websocket_failed", {
                    stage: "CdpClient.onclose",
                    wsUrl: this.ws.url || "",
                    code: event && event.code,
                    reason: event && event.reason,
                  })
                ));
              }

              rejectAll(error) {
                for (const pending of this.pending.values()) {
                  clearTimeout(pending.timer);
                  pending.reject(error);
                }
                this.pending.clear();
                for (const waiters of this.waiters.values()) {
                  for (const waiter of waiters) {
                    clearTimeout(waiter.timer);
                    waiter.reject(error);
                  }
                }
                this.waiters.clear();
              }

              onMessage(event) {
                let payload;
                try {
                  payload = JSON.parse(event.data);
                } catch (error) {
                  this.rejectAll(new ProbeFailure(
                    "cdp_websocket_failed",
                    failurePayload("cdp_websocket_failed", {
                      stage: "CdpClient.onMessage.parse",
                      message: `CDP JSON parse failed: ${String(error)}`,
                    })
                  ));
                  return;
                }
                if (payload.id && this.pending.has(payload.id)) {
                  const { resolve, reject, timer } = this.pending.get(payload.id);
                  clearTimeout(timer);
                  this.pending.delete(payload.id);
                  if (payload.error) {
                    reject(new Error(JSON.stringify(payload.error)));
                  } else {
                    resolve(payload.result || {});
                  }
                  return;
                }
                const waiters = this.waiters.get(payload.method) || [];
                const waiter = waiters.shift();
                if (waiter) {
                  clearTimeout(waiter.timer);
                  waiter.resolve(payload.params || {});
                }
              }

              send(method, params = {}, timeoutMs = 10000) {
                const id = this.nextId;
                this.nextId += 1;
                return new Promise((resolve, reject) => {
                  const timer = setTimeout(() => {
                    this.pending.delete(id);
                    reject(new ProbeFailure("cdp_command_timeout", failurePayload("cdp_command_timeout", {
                      stage: "cdp.send",
                      method,
                      paramsSummary: JSON.stringify(params).slice(0, 1024),
                      pageUrl: this.context.url || "",
                      viewport: this.context.viewport || {},
                    })));
                  }, timeoutMs);
                  this.pending.set(id, { resolve, reject, timer, method, params });
                  try {
                    this.ws.send(JSON.stringify({ id, method, params }));
                  } catch (error) {
                    clearTimeout(timer);
                    this.pending.delete(id);
                    reject(error);
                  }
                });
              }

              waitEvent(method, timeoutMs = 10000) {
                return new Promise((resolve, reject) => {
                  const waiters = this.waiters.get(method) || [];
                  const waiter = {
                    resolve: (value) => {
                      clearTimeout(timer);
                      const rows = this.waiters.get(method) || [];
                      this.waiters.set(method, rows.filter((item) => item !== waiter));
                      resolve(value);
                    },
                    reject: (error) => {
                      clearTimeout(timer);
                      const rows = this.waiters.get(method) || [];
                      this.waiters.set(method, rows.filter((item) => item !== waiter));
                      reject(error);
                    },
                    timer: null,
                  };
                  const timer = setTimeout(() => {
                    const rows = this.waiters.get(method) || [];
                    this.waiters.set(method, rows.filter((item) => item !== waiter));
                    reject(new ProbeFailure("cdp_command_timeout", failurePayload("cdp_command_timeout", {
                      stage: "cdp.waitEvent",
                      event: method,
                      timeoutMs,
                      pageUrl: this.context.url || "",
                      viewport: this.context.viewport || {},
                    })));
                  }, timeoutMs);
                  waiter.timer = timer;
                  waiters.push(waiter);
                  this.waiters.set(method, waiters);
                });
              }

              close() {
                try { this.ws.close(); } catch {}
              }
            }

            async function responseTextWithTimeout(response, timeoutMs, stage) {
              try {
                return await withTimeout(response.text(), timeoutMs, `${stage} body timeout`);
              } catch (error) {
                fail("cdp_websocket_failed", {
                  stage,
                  status: response && response.status,
                  message: String(error && error.stack ? error.stack : error),
                });
              }
            }

            async function newPage(port) {
              const response = await fetchWithTimeout(`http://127.0.0.1:${port}/json/new`, { method: "PUT" }, 5000);
              const body = await responseTextWithTimeout(response, 5000, "newPage");
              if (!response.ok) {
                fail("cdp_websocket_failed", {
                  stage: "newPage",
                  status: response.status,
                  responseBody: body.slice(0, 4096),
                });
              }
              let page;
              try {
                page = JSON.parse(body);
              } catch (error) {
                fail("cdp_websocket_failed", {
                  stage: "newPage",
                  status: response.status,
                  responseBody: body.slice(0, 4096),
                  message: String(error && error.stack ? error.stack : error),
                });
              }
              if (!page.webSocketDebuggerUrl) {
                fail("cdp_websocket_failed", { stage: "newPage", page });
              }
              return page;
            }

            async function waitForPageStable(client, url, viewport) {
              const expression = `
                (async () => {
                  const withTimeout = (promise, ms, label) => new Promise((resolve, reject) => {
                    const timer = setTimeout(() => reject(new Error(label)), ms);
                    Promise.resolve(promise).then(
                      (value) => { clearTimeout(timer); resolve(value); },
                      (error) => { clearTimeout(timer); reject(error); }
                    );
                  });
                  if (document.readyState !== "complete") {
                    await withTimeout(new Promise((resolve) => {
                      window.addEventListener("load", resolve, { once: true });
                    }), 5000, "load timeout");
                  }
                  if (document.fonts && document.fonts.ready) {
                    await withTimeout(document.fonts.ready, 3000, "fonts timeout");
                  }
                  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                  const first = Math.max(
                    document.body ? document.body.scrollWidth : 0,
                    document.documentElement ? document.documentElement.scrollWidth : 0
                  );
                  await new Promise((resolve) => setTimeout(resolve, 100));
                  const second = Math.max(
                    document.body ? document.body.scrollWidth : 0,
                    document.documentElement ? document.documentElement.scrollWidth : 0
                  );
                  return { readyState: document.readyState, first, second };
                })()
              `;
              const evaluated = await client.send("Runtime.evaluate", {
                expression,
                awaitPromise: true,
                returnByValue: true,
              }, 10000);
              if (evaluated.exceptionDetails) {
                fail("page_stabilization_timeout", {
                  stage: "waitForPageStable",
                  url,
                  viewport,
                  details: evaluated.exceptionDetails,
                });
              }
              return evaluated.result ? evaluated.result.value : {};
            }

            async function inspectPage(port, url, expected, httpStatus) {
              const page = await newPage(port);
              const client = new CdpClient(page.webSocketDebuggerUrl);
              await client.open();
              active.push(client);
              await client.send("Page.enable");
              await client.send("Runtime.enable");
              const results = [];
              let pageLoaded = false;
              for (const width of [1024, 768]) {
                await client.send("Emulation.setDeviceMetricsOverride", {
                  width,
                  height: 900,
                  deviceScaleFactor: 1,
                  mobile: false,
                });
                client.context = { url, viewport: { width, height: 900 } };
                if (!pageLoaded) {
                  const loaded = client.waitEvent("Page.loadEventFired");
                  const navigateResult = await client.send("Page.navigate", { url });
                  if (navigateResult.errorText) {
                    fail("page_http_status_failed", {
                      stage: "Page.navigate",
                      url,
                      viewport: { width, height: 900 },
                      message: navigateResult.errorText,
                    });
                  }
                  await loaded;
                  pageLoaded = true;
                }
                await waitForPageStable(client, url, { width, height: 900 });
                const expression = `
                (() => {
                  const maxScrollWidth = Math.max(
                    document.body ? document.body.scrollWidth : 0,
                    document.documentElement ? document.documentElement.scrollWidth : 0
                  );
                  const bodyOverflow = maxScrollWidth > window.innerWidth + 1;
                  const toggleRows = [...document.querySelectorAll('.aps-toggle-row')];
                  const toggleOverlapCount = toggleRows.filter((row) => {
                    const track = row.querySelector('.aps-toggle-track');
                    const title = row.querySelector('.aps-toggle-title');
                    if (!track || !title) return false;
                    const a = track.getBoundingClientRect();
                    const b = title.getBoundingClientRect();
                    return !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
                  }).length;
                  const visibleNotices = [...document.querySelectorAll('.aps-notice,.aps-summary-item')]
                    .filter((el) => {
                      const rect = el.getBoundingClientRect();
                      return rect.width > 0 && rect.height > 0;
                    }).length;
                  document.documentElement.setAttribute('data-theme', 'dark');
                  const darkSummaryBadCount = [...document.querySelectorAll('.aps-summary-item')]
                    .filter((el) => {
                      const style = getComputedStyle(el);
                      return style.backgroundColor.includes('255, 255, 255') || style.color === style.backgroundColor;
                    }).length;
                  const logsTable = document.querySelector('#systemLogsTable');
                  const bodyText = document.body ? document.body.innerText || "" : "";
                  const titleText = document.title || "";
                  const hasAppShell = Boolean(document.querySelector('meta[name="aps-ui-template-env"]'))
                    && Boolean(document.querySelector('header nav, header.top-header, nav.sidebar-nav'))
                    && Boolean(document.getElementById('apsThemeToggle'));
                  function includesKeyword(value, keyword) {
                    return String(value || "").toLowerCase().includes(String(keyword || "").toLowerCase());
                  }
                  const errorKeywords = window.__APS_ERROR_PAGE_KEYWORDS__ || [];
                  const matchedTitleErrorKeyword = errorKeywords.find((keyword) => includesKeyword(titleText, keyword)) || "";
                  const matchedBodyErrorKeyword = errorKeywords.find((keyword) => includesKeyword(bodyText, keyword)) || "";
                  const matchedErrorKeyword = matchedTitleErrorKeyword || (!hasAppShell ? matchedBodyErrorKeyword : "");
                  const pageLooksError = ${httpStatus} >= 500 || Boolean(matchedErrorKeyword);
                  const expectedTexts = window.__APS_EXPECTED_SIGNALS__?.texts || [];
                  const expectedIds = window.__APS_EXPECTED_SIGNALS__?.ids || [];
                  const expectedPath = window.__APS_EXPECTED_SIGNALS__?.path || "";
                  const finalPath = location.pathname + location.search;
                  const missingExpectedTexts = expectedTexts.filter((text) => !bodyText.includes(text));
                  const missingExpectedIds = expectedIds.filter((id) => !document.getElementById(id));
                  const pathMismatch = Boolean(expectedPath && finalPath !== expectedPath);
                  function parseRgb(value) {
                    const text = String(value || "");
                    const start = text.indexOf("(");
                    const end = text.indexOf(")");
                    if (start < 0 || end <= start) return null;
                    const parts = text.slice(start + 1, end).split(",");
                    const alpha = parts.length >= 4 ? Number(String(parts[3] || "").trim()) : 1;
                    if (Number.isFinite(alpha) && alpha === 0) return null;
                    const channels = parts.slice(0, 3)
                      .map((part) => Number(String(part || "").trim()));
                    return channels.every((item) => Number.isFinite(item)) ? channels : null;
                  }
                  function channelToLinear(value) {
                    const normalized = value / 255;
                    return normalized <= 0.03928
                      ? normalized / 12.92
                      : Math.pow((normalized + 0.055) / 1.055, 2.4);
                  }
                  function luminance(rgb) {
                    return 0.2126 * channelToLinear(rgb[0])
                      + 0.7152 * channelToLinear(rgb[1])
                      + 0.0722 * channelToLinear(rgb[2]);
                  }
                  function contrastRatio(a, b) {
                    const high = Math.max(luminance(a), luminance(b));
                    const low = Math.min(luminance(a), luminance(b));
                    return (high + 0.05) / (low + 0.05);
                  }
                  function isVisible(el) {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                  }
                  function selectorFor(el) {
                    if (!el) return "";
                    const tag = String(el.tagName || "").toLowerCase();
                    const id = el.id ? "#" + el.id : "";
                    const classes = String(el.className || "").trim().split(/\s+/).filter(Boolean).slice(0, 3).join(".");
                    return tag + id + (classes ? "." + classes : "");
                  }
                  function horizontalScrollerAncestor(el) {
                    let node = el.parentElement;
                    while (node && node !== document.documentElement) {
                      const style = getComputedStyle(node);
                      if ((style.overflowX === "auto" || style.overflowX === "scroll") && node.scrollWidth > node.clientWidth + 1) {
                        return selectorFor(node);
                      }
                      node = node.parentElement;
                    }
                    return "";
                  }
                  const overflowOffenders = [...document.querySelectorAll("body *")]
                    .filter((el) => isVisible(el))
                    .map((el) => {
                      const rect = el.getBoundingClientRect();
                      const style = getComputedStyle(el);
                      const outside = rect.right > window.innerWidth + 1 || rect.left < -1;
                      return {
                        outside,
                        tagName: String(el.tagName || ""),
                        id: el.id || "",
                        className: String(el.className || "").slice(0, 160),
                        selector: selectorFor(el),
                        rect: { left: rect.left, right: rect.right, width: rect.width, height: rect.height },
                        position: style.position,
                        overflowX: style.overflowX,
                        whiteSpace: style.whiteSpace,
                        textSample: String(el.innerText || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80),
                        insideHorizontalScroller: Boolean(horizontalScrollerAncestor(el)),
                        horizontalScroller: horizontalScrollerAncestor(el),
                      };
                    })
                    .filter((row) => row.outside)
                    .slice(0, 20);
                  const scrollMetrics = {
                    bodyScrollWidth: document.body ? document.body.scrollWidth : 0,
                    documentScrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
                    innerWidth: window.innerWidth,
                  }
                  function nearestBackground(el) {
                    let node = el;
                    while (node && node !== document.documentElement) {
                      const bg = parseRgb(getComputedStyle(node).backgroundColor);
                      if (bg) {
                        return bg;
                      }
                      node = node.parentElement;
                    }
                    return parseRgb(getComputedStyle(document.body || document.documentElement).backgroundColor);
                  }
                  function lowContrastTextCount(selectors) {
                    return selectors.flatMap((selector) => [...document.querySelectorAll(selector)])
                      .filter((el) => isVisible(el))
                      .filter((el) => {
                        const fg = parseRgb(getComputedStyle(el).color);
                        const bg = nearestBackground(el);
                        return fg && bg && contrastRatio(fg, bg) < 3;
                      }).length;
                  }
                  function multilineTableComputedOk(selector) {
                    const table = document.querySelector(selector);
                    if (!table) {
                      return true;
                    }
                    if (!table.classList.contains('aps-table--multiline')) {
                      return false;
                    }
                    const cells = [...table.querySelectorAll('thead th, tbody td')].filter((cell) => isVisible(cell));
                    if (!cells.length) {
                      return false;
                    }
                    return cells.slice(0, 12).every((cell) => {
                      const style = getComputedStyle(cell);
                      const wrapOk = style.overflowWrap === 'anywhere' || style.wordBreak !== 'normal';
                      return (
                        style.whiteSpace === 'normal'
                        && style.textOverflow !== 'ellipsis'
                        && style.overflow !== 'hidden'
                        && wrapOk
                      );
                    });
                  }
                  const requiredToggleByPath = {
                    "/scheduler/": ["runEnforceReady", "runStrictMode"],
                    "/scheduler/batches": ["batchManageStrictMode"],
                    "/scheduler/excel/batches": ["batchImportAutoOps", "batchImportStrictMode"],
                    "/process/": ["processCreateStrictMode"],
                  };
                  const requiredToggleIds = requiredToggleByPath[location.pathname] || [];
                  const missingRequiredToggleIds = requiredToggleIds
                    .filter((id) => !document.getElementById(id));
                  const darkLowContrastSummaryCount = [...document.querySelectorAll('.aps-summary-item')]
                    .filter((el) => {
                      const style = getComputedStyle(el);
                      const fg = parseRgb(style.color);
                      const bg = parseRgb(style.backgroundColor);
                      return fg && bg && contrastRatio(fg, bg) < 3;
                    }).length;
                  const darkLowContrastTextCount = lowContrastTextCount([
                    '.aps-summary-label',
                    '.aps-summary-value',
                    '.aps-summary-desc',
                    '.aps-notice-title',
                    '.aps-notice-body',
                    '.aps-toggle-title',
                    '.aps-toggle-desc',
                  ]);
                  const darkNoticeBadCount = [...document.querySelectorAll('.aps-notice')]
                    .filter((el) => {
                      const style = getComputedStyle(el);
                      return style.backgroundColor.includes('255, 255, 255');
                    }).length;
                  const multilineTableChecks = {
                    systemLogsTable: multilineTableComputedOk('#systemLogsTable'),
                    pluginStatusTable: multilineTableComputedOk('#pluginStatusTable'),
                    systemHistoryTable: multilineTableComputedOk('#systemHistoryTable'),
                  };
                  return JSON.stringify({
                    path: finalPath,
                    expectedPath,
                    pathMismatch,
                    httpStatus: ${httpStatus},
                    url: location.href,
                    title: document.title || "",
                    hasAppShell,
                    pageLooksError,
                    matchedErrorKeyword,
                    missingExpectedTexts,
                    missingExpectedIds,
                    width: window.innerWidth,
                    bodyOverflow,
                    maxScrollWidth,
                    scrollMetrics,
                    overflowOffenders,
                    toggleCount: toggleRows.length,
                    toggleOverlapCount,
                    visibleNotices,
                    darkSummaryBadCount,
                    darkLowContrastSummaryCount,
                    darkLowContrastTextCount,
                    darkNoticeBadCount,
                    multilineTableChecks,
                    logsTableMultiline: multilineTableChecks.systemLogsTable,
                    requiredToggleIds,
                    missingRequiredToggleIds,
                  });
                })()
              `;
                await client.send("Runtime.evaluate", {
                  expression: `window.__APS_EXPECTED_SIGNALS__ = ${JSON.stringify(expected || {})};`,
                  returnByValue: true,
                });
                await client.send("Runtime.evaluate", {
                  expression: `window.__APS_ERROR_PAGE_KEYWORDS__ = ${JSON.stringify(errorPageKeywords || [])};`,
                  returnByValue: true,
                });
                const evaluated = await client.send("Runtime.evaluate", {
                  expression,
                  returnByValue: true,
                  awaitPromise: true,
                });
                if (evaluated.exceptionDetails) {
                  throw new Error(`页面检查脚本执行失败：${JSON.stringify(evaluated.exceptionDetails)}`);
                }
                if (!evaluated.result || typeof evaluated.result.value !== "string") {
                  throw new Error(`页面检查脚本没有返回 JSON 字符串：${JSON.stringify(evaluated.result || {})}`);
                }
                results.push(JSON.parse(evaluated.result.value));
              }
              client.close();
              return results;
            }

            try {
              const port = await readDebugPort();
              await preflightDevTools(port);
              const results = [];
              for (const pagePath of paths) {
                const url = `${baseUrl}${pagePath}`;
                const httpResponse = await fetchWithTimeout(url, { redirect: "manual" }, 5000);
                const httpStatus = httpResponse.status;
                results.push(...await inspectPage(port, url, expectedByPath[pagePath] || {}, httpStatus));
              }
              console.log(JSON.stringify(results));
            } catch (error) {
              if (error instanceof ProbeFailure) {
                console.error(JSON.stringify(error.details, null, 2));
              } else {
                console.error(JSON.stringify(failurePayload("cdp_websocket_failed", {
                  stage: "top-level",
                  message: String(error && error.stack ? error.stack : error),
                }), null, 2));
              }
              process.exitCode = 1;
            } finally {
              for (const client of active) client.close();
              try { chrome.kill("SIGTERM"); } catch {}
              const chromeExitWait = await waitForChromeExit(3000);
              if (!chromeExitWait.exited) {
                try { chrome.kill("SIGKILL"); } catch {}
              }
              try { await fs.rm(userDataDir, { recursive: true, force: true }); } catch (error) {
                console.error(JSON.stringify({
                  warning_kind: "chrome_profile_cleanup_warning",
                  userDataDir,
                  chromeExitWait,
                  message: String(error && error.stack ? error.stack : error),
                }, null, 2));
              }
            }
            """
        ),
        encoding="utf-8",
    )
    profile_base = tmp_path / "chrome-profiles"
    profile_base.mkdir(parents=True, exist_ok=True)
    runtime_context = _browser_runtime_context(chrome=chrome_info, node=node_info)
    command = [
        node_path,
        str(script),
        chrome_path,
        base_url,
        json.dumps(SMOKE_PATHS, ensure_ascii=False),
        json.dumps(EXPECTED_PAGE_SIGNALS, ensure_ascii=False),
        json.dumps(ERROR_PAGE_KEYWORDS, ensure_ascii=False),
        str(profile_base),
        json.dumps(runtime_context, ensure_ascii=False),
    ]
    popen_kwargs: Dict[str, Any] = {}
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        **popen_kwargs,
    )
    stdout = ""
    stderr = ""
    try:
        stdout, stderr = process.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired as exc:
            _kill_process_tree(process)
            try:
                process.kill()
            except Exception:
                pass
            stdout = _timeout_output_text(getattr(exc, "stdout", None) or getattr(exc, "output", None))
            stderr = _timeout_output_text(getattr(exc, "stderr", None))
        shutil.rmtree(str(profile_base), ignore_errors=True)
        raise AssertionError(
            json.dumps(
                {
                    "failure_kind": "node_probe_timeout",
                    "node_pid": process.pid,
                    "timeout_seconds": 90,
                    "stdout_tail": _tail_text(stdout, 4096),
                    "stderr_tail": _tail_text(stderr, 4096),
                    "runtime_context": runtime_context,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    finally:
        shutil.rmtree(str(profile_base), ignore_errors=True)
    profile_residue: List[str] = []
    if profile_base.exists():
        profile_residue = [str(path.relative_to(profile_base)) for path in profile_base.rglob("*")][:20]
    if process.returncode != 0:
        raise AssertionError(_tail_text(stderr or stdout, 32768))
    if "chrome_profile_cleanup_warning" in stderr or profile_residue:
        raise AssertionError(
            json.dumps(
                {
                    "failure_kind": "chrome_profile_cleanup_warning",
                    "stderr_tail": _tail_text(stderr, 8192),
                    "profile_base": str(profile_base),
                    "profile_residue": profile_residue,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return json.loads(stdout)


def test_ui_pages_do_not_create_body_level_overflow_in_real_browser(tmp_path, monkeypatch) -> None:
    chrome = _find_chrome()
    node = _find_node_with_browser_runtime()
    app = _build_app(tmp_path, monkeypatch)
    served = _serve_app(app)
    try:
        results = _run_chrome_geometry_probe(
            chrome_path=chrome.chrome_path,
            node_path=node.node_path,
            base_url=served.base_url,
            tmp_path=tmp_path,
            chrome_info=chrome,
            node_info=node,
        )
    finally:
        _shutdown_served_app(served)

    overflowing = [item for item in results if item["bodyOverflow"]]
    overlapping_toggles = [item for item in results if item["toggleOverlapCount"]]
    bad_dark_summary = [item for item in results if item["darkSummaryBadCount"]]
    bad_dark_summary_contrast = [item for item in results if item["darkLowContrastSummaryCount"]]
    bad_dark_text_contrast = [item for item in results if item["darkLowContrastTextCount"]]
    bad_dark_notice = [item for item in results if item["darkNoticeBadCount"]]
    bad_logs_table = [item for item in results if not item["logsTableMultiline"]]
    bad_multiline_tables = [
        item
        for item in results
        if any(not ok for ok in dict(item["multilineTableChecks"]).values())
    ]
    missing_required_toggles = [item for item in results if item["missingRequiredToggleIds"]]
    bad_http_status = [item for item in results if item["httpStatus"] != 200]
    bad_shell = [item for item in results if not item["hasAppShell"]]
    error_pages = [item for item in results if item["pageLooksError"]]
    wrong_paths = [item for item in results if item["pathMismatch"]]
    missing_expected_texts = [item for item in results if item["missingExpectedTexts"]]
    missing_expected_ids = [item for item in results if item["missingExpectedIds"]]

    failures: List[Dict[str, Any]] = []

    def add_failure(kind: str, rows: List[Dict[str, Any]], detail_keys: List[str]) -> None:
        for row in rows:
            failures.append(
                {
                    "kind": kind,
                    "path": row.get("path"),
                    "url": row.get("url"),
                    "viewport": {"width": row.get("width"), "height": 900},
                    "details": {key: row.get(key) for key in detail_keys},
                }
            )

    add_failure("page_http_status_failed", bad_http_status, ["httpStatus", "title"])
    add_failure("page_error_shell_failed", bad_shell, ["hasAppShell", "title"])
    add_failure("page_error_shell_failed", error_pages, ["matchedErrorKeyword", "title"])
    add_failure("page_expected_dom_failed", wrong_paths, ["expectedPath"])
    add_failure("page_expected_dom_failed", missing_expected_texts, ["missingExpectedTexts"])
    add_failure("page_expected_dom_failed", missing_expected_ids, ["missingExpectedIds"])
    add_failure("page_expected_dom_failed", missing_required_toggles, ["missingRequiredToggleIds"])
    add_failure("page_overflow_failed", overflowing, ["maxScrollWidth", "scrollMetrics", "overflowOffenders"])
    add_failure("page_visual_contract_failed", overlapping_toggles, ["toggleOverlapCount"])
    add_failure("page_visual_contract_failed", bad_dark_summary, ["darkSummaryBadCount"])
    add_failure("page_visual_contract_failed", bad_dark_summary_contrast, ["darkLowContrastSummaryCount"])
    add_failure("page_visual_contract_failed", bad_dark_text_contrast, ["darkLowContrastTextCount"])
    add_failure("page_visual_contract_failed", bad_dark_notice, ["darkNoticeBadCount"])
    add_failure("page_visual_contract_failed", bad_logs_table, ["logsTableMultiline"])
    add_failure("page_visual_contract_failed", bad_multiline_tables, ["multilineTableChecks"])

    if not any(item["toggleCount"] > 0 for item in results):
        failures.append({"kind": "page_expected_dom_failed", "details": {"message": "no visible toggle rows found"}})
    if not any(item["visibleNotices"] > 0 for item in results):
        failures.append({"kind": "page_expected_dom_failed", "details": {"message": "no visible notices found"}})
    if failures:
        raise AssertionError(json.dumps(failures, ensure_ascii=False, indent=2, sort_keys=True))


def test_ui_browser_geometry_smoke_covers_scheduler_run_page() -> None:
    backup_signals = EXPECTED_PAGE_SIGNALS["/system/backup"]
    logs_signals = EXPECTED_PAGE_SIGNALS["/system/logs"]
    history_version_signals = EXPECTED_PAGE_SIGNALS["/system/history?version=2"]
    assert "/scheduler/?status=pending" in SMOKE_PATHS
    assert "/scheduler/batches?status=pending" not in SMOKE_PATHS
    assert "/system/history" in SMOKE_PATHS
    assert "/system/history?version=2" in SMOKE_PATHS
    assert EXPECTED_PAGE_SIGNALS["/scheduler/?status=pending"]["ids"] == [
        "jsRunScheduleForm",
        "runEnforceReady",
        "runStrictMode",
    ]
    assert "pluginStatusTable" in cast(List[str], backup_signals["ids"])
    assert "启动问题" in cast(List[str], backup_signals["diagnostic_texts"])
    assert "详情格式异常" in cast(List[str], logs_signals["diagnostic_texts"])
    assert "当前版本的排产摘要读取失败" in cast(List[str], history_version_signals["diagnostic_texts"])
    assert EXPECTED_PAGE_SIGNALS["/system/history"]["ids"] == ["systemHistoryTable"]
    script_source = Path(__file__).read_text(encoding="utf-8")
    assert '"/scheduler/": ["runEnforceReady", "runStrictMode"]' in script_source
    assert "multilineTableComputedOk('#systemLogsTable')" in script_source
    assert "multilineTableComputedOk('#pluginStatusTable')" in script_source
    assert "multilineTableComputedOk('#systemHistoryTable')" in script_source
