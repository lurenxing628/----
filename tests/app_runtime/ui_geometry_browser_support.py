"""为 UI 几何浏览器契约测试提供支撑设施：用预置零件/批次/工序/排程/停机/历史/日志数据构建并以 werkzeug make_server 起一个真实 app，以及通过 Node + Chrome CDP 运行 ui_geometry_probe.mjs 探针（含超时杀进程树、Chrome profile 清理校验）采集各页面几何信号。无 test_ 用例，供 ui_geometry 浏览器回归调用。"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.serving import make_server

from tests._support.paths import REPO_ROOT
from tests.app_runtime.ui_geometry_contract_data import (
    ERROR_PAGE_KEYWORDS,
    EXPECTED_PAGE_SIGNALS,
    UI_GEOMETRY_PAGE_PATHS,
)
from tests.app_runtime.ui_geometry_fixture_support import managed_geometry_app
from tests.app_runtime.ui_geometry_runtime_support import (
    ChromeRuntimeInfo,
    NodeRuntimeInfo,
    ServedApp,
    _browser_runtime_context,
    _find_chrome,
    _find_node_with_browser_runtime,
    _format_browser_env_failure,
    _tail_text,
    _timeout_output_text,
)

SMOKE_PATHS = UI_GEOMETRY_PAGE_PATHS
UI_GEOMETRY_PROBE_SOURCE = REPO_ROOT / "tests" / "ui_geometry_probe.mjs"
UI_GEOMETRY_CDP_CLIENT_SOURCE = REPO_ROOT / "tests" / "ui_geometry_cdp_client.mjs"
UI_GEOMETRY_PAGE_EVAL_SOURCE = REPO_ROOT / "tests" / "ui_geometry_probe_page_eval.mjs"

def _build_app(tmp_path, monkeypatch, *, invalid_history=True):
    manager = managed_geometry_app(tmp_path, monkeypatch, invalid_history=invalid_history)
    app = manager.__enter__()
    app.extensions["ui_geometry_manager"] = manager
    return app


def _shutdown_app(app) -> None:
    app.extensions.pop("ui_geometry_manager").__exit__(None, None, None)


def _serve_app(app):
    from web.bootstrap.workbench_request_lifecycle import WorkbenchRequestHandler

    server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=WorkbenchRequestHandler)
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
    scenarios: Optional[List[Dict[str, Any]]] = None,
    deadline: Optional[float] = None,
    chrome_info: Optional[ChromeRuntimeInfo] = None,
    node_info: Optional[NodeRuntimeInfo] = None,
) -> List[Dict[str, Any]]:
    script = tmp_path / "ui_geometry_probe.mjs"
    script.write_text(UI_GEOMETRY_PROBE_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "ui_geometry_cdp_client.mjs").write_text(
        UI_GEOMETRY_CDP_CLIENT_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "ui_geometry_probe_page_eval.mjs").write_text(
        UI_GEOMETRY_PAGE_EVAL_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "ui_geometry_probe_scenarios.mjs").write_text(
        (REPO_ROOT / "tests" / "ui_geometry_probe_scenarios.mjs").read_text(encoding="utf-8"), encoding="utf-8",
    )
    profile_base = tmp_path / "chrome-profiles"
    profile_base.mkdir(parents=True, exist_ok=True)
    runtime_context = _browser_runtime_context(chrome=chrome_info, node=node_info)
    command = [
        node_path,
        str(script),
        chrome_path,
        base_url,
        json.dumps([case['case'] for case in scenarios or ()], ensure_ascii=False),
        json.dumps({case['case']: case for case in scenarios or ()}, ensure_ascii=False),
        json.dumps(ERROR_PAGE_KEYWORDS, ensure_ascii=False),
        str(profile_base),
        json.dumps(runtime_context, ensure_ascii=False),
    ]
    popen_kwargs: Dict[str, Any] = {}
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True
    timeout = 90 if deadline is None else min(90, deadline - time.monotonic())
    assert timeout > 0, "The original 90-second geometry budget was exhausted"
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
        stdout, stderr = process.communicate(timeout=timeout)
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
                    "remaining_seconds": timeout,
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
