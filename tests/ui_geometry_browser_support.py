"""为 UI 几何浏览器契约测试提供支撑设施：用预置零件/批次/工序/排程/停机/历史/日志数据构建并以 werkzeug make_server 起一个真实 app，以及通过 Node + Chrome CDP 运行 ui_geometry_probe.mjs 探针（含超时杀进程树、Chrome profile 清理校验）采集各页面几何信号。无 test_ 用例，供 ui_geometry 浏览器回归调用。"""

from __future__ import annotations

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.serving import make_server

from tests._support.paths import REPO_ROOT
from tests.ui_geometry_contract_data import ERROR_PAGE_KEYWORDS, EXPECTED_PAGE_SIGNALS, UI_GEOMETRY_PAGE_PATHS
from tests.ui_geometry_runtime_support import (
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
            ("B_UI_GEOMETRY", "P_UI_GEOMETRY", "浏览器几何测试零件", 1, "2026-05-01", "normal", "yes", "pending"),
        )
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("M_UI_GEOMETRY", "几何测试设备", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("O_UI_GEOMETRY", "几何测试人员", "active"))
        cur = conn.execute(
            """
            INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name, source, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("OP_UI_GEOMETRY", "B_UI_GEOMETRY", 1, "加工", "internal", "pending"),
        )
        op_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                op_id,
                "M_UI_GEOMETRY",
                "O_UI_GEOMETRY",
                "2026-05-06 08:00:00",
                "2026-05-06 12:00:00",
                "unlocked",
                1,
            ),
        )
        conn.execute(
            """
            INSERT INTO MachineDowntimes (machine_id, start_time, end_time, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("M_UI_GEOMETRY", "2026-05-06 09:00:00", "2026-05-06 10:00:00", "maintenance", "几何测试停机", "active"),
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
    script.write_text(UI_GEOMETRY_PROBE_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "ui_geometry_cdp_client.mjs").write_text(
        UI_GEOMETRY_CDP_CLIENT_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "ui_geometry_probe_page_eval.mjs").write_text(
        UI_GEOMETRY_PAGE_EVAL_SOURCE.read_text(encoding="utf-8"),
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
